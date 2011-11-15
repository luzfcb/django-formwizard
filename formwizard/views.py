from django import forms
from django.core.urlresolvers import reverse
from django.forms import formsets, ValidationError
from django.forms.models import ModelForm, BaseModelFormSet
from django.shortcuts import redirect
from django.template.loader import get_template
from django.template import RequestContext
from django.views.generic import TemplateView
from django.utils.datastructures import SortedDict
from django.utils.decorators import classonlymethod
from formwizard.storage import get_storage, Step
from formwizard.storage.exceptions import NoFileStorageConfigured
from formwizard.forms import ManagementForm
import re


def normalize_name(name):
    new = re.sub('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))', '_\\1', name)
    return new.lower().strip('_')


class StepsHelper(object):

    def __init__(self, wizard):
        self._wizard = wizard

    def __dir__(self):
        return self.all

    def __len__(self):
        return self.count

    def __repr__(self):
        return '<StepsHelper for %s (steps: %s)>' % (self._wizard, self.all)

    @property
    def all(self):
        """Returns a ``list`` of all steps in the wizard."""
        return [self._wizard.storage[s]
                for s in self._wizard.get_form_list().keys()]

    @property
    def count(self):
        """Returns the total number of steps/forms in this the wizard."""
        return len(self._wizard.get_form_list())

    @property
    def current(self):
        """
        Returns the current step. If no current step is stored in the
        storage backend, the first step will be returned.
        """
        return self._wizard.storage.current_step or self.first

    @property
    def first(self):
        "Returns the name of the first step."
        form_list = self._wizard.get_form_list()
        return self._wizard.storage[form_list.keyOrder[0]]

    @property
    def last(self):
        "Returns the name of the last step."
        form_list = self._wizard.get_form_list()
        return self._wizard.storage[form_list.keyOrder[-1]]

    @property
    def next(self):
        """
        Returns the next step. If no more steps are available, ``None`` will be
        returned.
        """
        key = self.index + 1
        form_list = self._wizard.get_form_list()
        if len(form_list.keyOrder) > key:
            return self._wizard.storage[form_list.keyOrder[key]]
        return None

    @property
    def prev(self):
        "Returns the previous step."
        key = self.index - 1
        form_list = self._wizard.get_form_list()
        if key >= 0:
            return self._wizard.storage[form_list.keyOrder[key]]
        return None

    @property
    def index(self):
        "Returns the index for the current step."
        return self._wizard.get_form_list().keyOrder.index(self.current.name)

    @property
    def step0(self):
        return int(self.index)

    @property
    def step1(self):
        return int(self.index) + 1


class WizardMixin(object):
    """
    The WizardView is used to create multi-page forms and handles all the
    storage and validation stuff. The wizard is based on Django's generic
    class based views.

    :param     wizard_template: Template to render for ``wizard.as_html``
                                (default: ``console/includes/tab_wizard.html``)
    :type      wizard_template: unicode
    """
    storage_name = None
    form_list = ()
    file_storage = None
    initial_dict = None
    instance_dict = None
    condition_dict = None
    template_name = 'formwizard/wizard_form.html'
    wizard_template_name = 'formwizard/wizard_form.html'

    def __repr__(self):
        return '<%s: forms: %s>' % (self.__class__.__name__, self.form_list)

    @classonlymethod
    def as_view(cls, form_list=None, initial_dict=None, instance_dict=None,
                condition_dict=None, *args, **kwargs):
        """
        This method is used within urls.py to create unique formwizard
        instances for every request. We need to override this method because
        we add some kwargs which are needed to make the formwizard usable.

        Creates a dict with all needed parameters for the form wizard
        instances.

        * `form_list` - is a list of forms. The list entries can be single form
          classes or tuples of (`<step name>`, `<form class>`). If you pass a
          list of forms, the formwizard will convert the class list to
          (`zero_based_counter`, `form_class`). This is needed to access the
          form for a specific step.
        * `initial_dict` - contains a dictionary of initial data dictionaries.
          The key should be equal to the `step_name` in the `form_list` (or
          the str of the zero based counter - if no step_names added in the
          `form_list`)
        * `instance_dict` - contains a dictionary of instance objects. This
          list is only used when `ModelForm`s are used. The key should be equal
          to the `step_name` in the `form_list`. Same rules as for
          `initial_dict` apply.
        * `condition_dict` - contains a dictionary of boolean values or
          callables. If the value of for a specific `step_name` is callable it
          will be called with the formwizard instance as the only argument.
          If the return value is true, the step's form will be used.
        """
        form_list = form_list or cls.form_list
        assert len(form_list) > 0, 'at least one form is needed'

        kwargs.update({
            'initial_dict': initial_dict or cls.initial_dict or {},
            'instance_dict': instance_dict or cls.instance_dict or {},
            'condition_dict': condition_dict or cls.condition_dict or {},
        })
        form_dict = SortedDict()

        # walk through the passed form list
        for i, item in enumerate(form_list):
            if isinstance(item, (list, tuple)):
                # if the element is a tuple, add the tuple to the new created
                # sorted dictionary.
                form_dict[unicode(item[0])] = item[1]
            else:
                # if not, add the form with a zero based counter as unicode
                form_dict[unicode(i)] = item

        if not cls.file_storage:
            # If any forms are using FileField, ensure file storage is
            # configured.
            for form_class in form_dict.itervalues():
                if issubclass(form_class, formsets.BaseFormSet):
                    form_class = form_class.form
                for field in form_class.base_fields.itervalues():
                    if isinstance(field, forms.FileField):
                        raise NoFileStorageConfigured

        # build the kwargs for the formwizard instances
        kwargs['form_list'] = form_dict
        return super(WizardMixin, cls).as_view(*args, **kwargs)

    def get_prefix(self):
        # TODO: Add some kind of unique id to prefix
        return normalize_name(self.__class__.__name__)

    def get_form_list(self):
        """
        This method returns a form_list based on the initial form list but
        checks if there is a condition method/value in the condition_list.
        If an entry exists in the condition list, it will call/read the value
        and respect the result. (True means add the form, False means ignore
        the form)

        The form_list is always generated on the fly because condition methods
        could use data from other (maybe previous forms).
        """
        filtered = SortedDict()
        for step_name, form_class in self.form_list.iteritems():
            # try to fetch the value from condition list, by default, the form
            # gets passed to the new list.
            condition = self.condition_dict.get(step_name, True)
            if callable(condition):
                # call the value if needed, passes the current instance.
                condition = condition(self)
            if condition:
                filtered[step_name] = form_class
        return filtered

    def get_storage(self):
        storage_class = get_storage(self.storage_name)
        return storage_class(self.prefix, self.file_storage)

    def dispatch(self, request, *args, **kwargs):
        """
        This method gets called by the routing engine. The first argument is
        ``request`` which contains a ``HttpRequest`` instance. The storage
        instance is stored in ``self.storage``.

        After processing the request using the ``dispatch`` method, the
        response gets updated by the storage engine (for example add cookies).
        """
        # View.dispatch() does this too, but we're doing some initialisation
        # before that's called, so we'll save these here.
        self.request = request
        self.args = args
        self.kwargs = kwargs
        # other stuff to init
        self.steps = StepsHelper(self)
        self.prefix = self.get_prefix()
        self.storage = self.get_storage()
        self.storage.process_request(request)
        response = super(WizardMixin, self).dispatch(request, *args, **kwargs)
        self.storage.process_response(response)
        return response

    def get(self, request, *args, **kwargs):
        """
        This method handles GET requests.

        If a GET request reaches this point, the wizard assumes that the user
        just starts at the first step or wants to restart the process.
        The data of the wizard will be resetted before rendering the first step.
        """
        self.storage.reset()

        # reset the current step to the first step.
        step = self.steps.first
        self.storage.current_step = step
        return self.render(self.get_form(step))

    def post(self, request, *args, **kwargs):
        """
        This method handles POST requests.

        The wizard will render either the current step (if form validation
        wasn't successful), the next step (if the current step was stored
        successful) or the done view (if no more steps are available)
        """
        # Look for a wizard_next_step element in the posted data which
        # contains a valid step name. If one was found, render the requested
        # form. (This makes stepping back a lot easier).
        wizard_next_step = self.request.POST.get('wizard_next_step')
        if wizard_next_step and wizard_next_step in self.get_form_list():
            step = self.storage[wizard_next_step]
            self.storage.current_step = step
            form = self.get_form(step)
            return self.render(form)

        # Check if form was refreshed
        management_form = ManagementForm(self.request.POST, prefix=self.prefix)
        if not management_form.is_valid():
            raise ValidationError('ManagementForm data is missing or has been '
                                  'tampered.')

        step = self.storage[management_form.cleaned_data['current_step']]
        self.storage.current_step = step
        form = self.get_form(step,
                             data=self.request.POST,
                             files=self.request.FILES)

        if form.is_valid():
            # Update step with valid data
            step.data = form.data
            self.files = form.files
            if step == self.steps.last:
                return self.render_done(form)
            else:
                return self.render_next_step()
        return self.render(form)

    def get_form_prefix(self, step, form):
        """
        Returns the prefix which will be used when calling the actual form for
        the given step.

        :param step: the form's step
        :type  step: ``Step`` object
        :param form: the form
        :type  form: ``Form`` subclass

        If no step is given, the form_prefix will determine the current step
        automatically.
        """
        return step.name

    def get_form_initial(self, step):
        """
        Returns a dictionary which will be passed to the form for ``step``
        as ``initial``. If no initial data was provied while initializing the
        form wizard, a empty dictionary will be returned.
        """
        return self.initial_dict.get(step.name)

    def get_form_instance(self, step):
        """
        Returns a object which will be passed to the form for ``step``
        as ``instance``. If no instance object was provied while initializing
        the form wizard, None be returned.
        """
        return self.instance_dict.get(step.name)

    def get_form_kwargs(self, step):
        """
        Returns the keyword arguments for instantiating the form
        (or formset) on given step.

        This is useful if a specific form needs some extra constructor
        arguments, e.g. a form that requires the HTTP request.
        """
        kwargs = {
            'data': step.data,
            'files': step.files,
            'prefix': self.get_form_prefix(step, self.form_list[step.name]),
            'initial': self.get_form_initial(step),
        }
        form_class = self.form_list[step.name]
        if issubclass(form_class, ModelForm):
            # If the form is based on ModelForm, add instance if available.
            kwargs.update({'instance': self.get_form_instance(step)})
        elif issubclass(form_class, BaseModelFormSet):
            # If the form is based on ModelFormSet, add queryset if available.
            kwargs.update({'queryset': self.get_form_instance(step)})
        return kwargs

    def get_form(self, step, **kwargs):
        """
        Constructs the form for a given ``step``.

        The form will be initialized using the ``data`` argument to prefill the
        new form. If needed, instance or queryset (for ``ModelForm`` or
        ``ModelFormSet``) will be added too.
        """
        form_kwargs = self.get_form_kwargs(step)
        form_kwargs.update(kwargs)
        form_class = self.form_list[step.name]
        return form_class(**form_kwargs)

    def get_context_data(self, form, **kwargs):
        """
        Returns the template context for a step. You can overwrite this method
        to add more data for all or some steps. This method returns a
        dictionary containing the rendered form step. Available template
        context variables are:

        * ``wizard`` -- a container of useful data

        Example::

            class MyWizard(SessionWizardView):
                def get_context_data(self, form, **kwargs):
                    context = super(MyWizard, self).get_context_data(
                            form, **kwargs)
                    if self.steps.current.name == 'my_step_name':
                        context.update({'another_var': True})
                    return context

        """
        context = super(WizardMixin, self).get_context_data(**kwargs)
        context['wizard'] = {
            'form': form,
            'steps': self.steps,
            'management_form': ManagementForm(prefix=self.prefix, initial={
                'current_step': self.steps.current.name,
            }),
            'as_html': lambda: self.get_wizard_html(RequestContext(
                    self.request, context))
        }
        return context

    def get_wizard_template_name(self):
        return self.wizard_template_name

    def get_wizard_html(self, context):
        template = get_template(self.get_wizard_template_name())
        return template.render(context)

    def done(self, form_list):
        """
        This method muss be overrided by a subclass to process to form data
        after processing all steps.
        """
        raise NotImplementedError("Your %s class has not defined a done() "
            "method, which is required." % self.__class__.__name__)

    # -- views ----------------------------------------------------------------

    def render(self, form=None):
        """
        Returns a ``HttpResponse`` containing a all needed context data.
        """
        form = form or self.get_form()
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def render_done(self):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form don't
        validate, ``render_revalidation_failure`` should get called.

        If everything is fine call ``done``.
        """
        validated_forms = []
        # walk through the form list and try to validate the data again.
        for step_name in self.get_form_list():
            step = self.storage[step_name]
            form = self.get_form(step=step)
            if not form.is_valid():
                return self.render_revalidation_failure(step, form)
            validated_forms.append(form)

        # render the done view and reset the wizard before returning the
        # response. This is needed to prevent from rendering done with the
        # same data twice.
        response = self.done(validated_forms)
        self.storage.reset()
        return response

    def render_revalidation_failure(self, step, form):
        """
        Gets called when a form doesn't validate when rendering the done
        view. By default, it changed the current step to failing forms step
        and renders the form.

        :param step: the step that failed validation
        :type  step: ``Step`` object
        :param form: the form that failed validation
        :type  form: ``Form`` or ``FormSet`` object
        """
        self.storage.current_step = step
        return self.render(form)

    def render_next_step(self):
        """
        When using the NamedUrlFormWizard, we have to redirect to update the
        browser's URL to match the shown step.
        """
        self.storage.current_step = self.steps.next
        return self.render()


class SessionWizardView(WizardMixin, TemplateView):
    """
    A WizardView with pre-configured SessionStorage backend.
    """
    storage_name = 'formwizard.storage.session.SessionStorage'


class CookieWizardView(WizardMixin, TemplateView):
    """
    A WizardView with pre-configured CookieStorage backend.
    """
    storage_name = 'formwizard.storage.cookie.CookieStorage'


class NamedUrlWizardMixin(WizardMixin):
    """
    A WizardView with URL named steps support.
    """
    wizard_step_url_name = None
    wizard_done_step_name = None

    def get(self, request, *args, **kwargs):
        """
        This renders the form or, if needed, does the HTTP redirects.
        """
        step_name = kwargs.get('step', None)
        if step_name is None:
            if request.GET:
                query_string = "?%s" % request.GET.urlencode()
            else:
                query_string = ""
            return redirect(self.steps.current.url + query_string)

        # is the current step the "done" name/view?
        elif step_name == self.wizard_done_step_name:
            return self.render_done()

        elif step_name in self.form_list:
            step = self.storage[step_name]
            self.storage.current_step = step
            return self.render(self.get_form(step))

        # invalid step name, reset to first and redirect.
        else:
            self.storage.current_step = self.steps.first
            return redirect(self.steps.first.url)

    def post(self, request, *args, **kwargs):
        """
        Do a redirect if user presses the prev. step button. The rest of this
        is super'd from FormWizard.
        """
        next_step_name = request.POST.get('wizard_next_step')
        if next_step_name and next_step_name in self.get_form_list():
            next_step = self.storage[next_step_name]
            self.storage.current_step = next_step
            return redirect(next_step.url)
        return super(NamedUrlWizardMixin, self).post(request, *args, **kwargs)

    def get_step_url(self, step_name):
        return reverse(self.wizard_step_url_name, kwargs={'step': step_name})

    def get_storage(self):
        wizard = self

        class NamedUrlStep(Step):
            @property
            def url(self):
                return wizard.get_step_url(self.name)

        storage = super(NamedUrlWizardMixin, self).get_storage()
        storage.step_class = NamedUrlStep
        return storage

    # -- views ----------------------------------------------------------------

    def render_done(self):
        """
        When rendering the done view, we have to redirect first (if the URL
        name doesn't fit).
        """
        if self.kwargs.get('step', None) != self.wizard_done_step_name:
            return redirect(self.get_step_url(self.wizard_done_step_name))
        return super(NamedUrlWizardMixin, self).render_done()

    def render_next_step(self):
        """
        When using the NamedUrlFormWizard, we have to redirect to update the
        browser's URL to match the shown step.
        """
        next_step = self.steps.next
        self.storage.current_step = next_step
        return redirect(next_step.url)

    def render_revalidation_failure(self, step, form):
        """
        When a step fails, we have to redirect the user to the first failing
        step.
        """
        step.data = step.data or {}
        self.storage.current_step = step
        return redirect(step.url)


class NamedUrlSessionWizardView(NamedUrlWizardMixin, TemplateView):
    """
    A NamedUrlWizardView with pre-configured SessionStorage backend.
    """
    storage_name = 'formwizard.storage.session.SessionStorage'


class NamedUrlCookieWizardView(NamedUrlWizardMixin, TemplateView):
    """
    A NamedUrlFormWizard with pre-configured CookieStorageBackend.
    """
    storage_name = 'formwizard.storage.cookie.CookieStorage'
