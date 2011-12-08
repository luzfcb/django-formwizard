from __future__ import absolute_import, unicode_literals
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.urlresolvers import reverse, resolve
from django.forms import FileField
from django.forms.formsets import BaseFormSet
from django.forms.models import ModelForm, BaseModelFormSet
from django.http import Http404
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


class StepsManager(object):
    """
    A helper class that makes accessing steps easier.
    """

    def __init__(self, wizard):
        self._wizard = wizard

    def __dir__(self):
        return self.all

    def __len__(self):
        return self.count

    def __repr__(self):
        return '<%s for %s (steps: %s)>' % (self.__class__.__name__,
                                            self._wizard, self.all)

    def __getitem__(self, step_name):
        """
        :param item: step name
        :type  item: ``unicode``
        """
        step = self._wizard.storage[step_name]
        if not step.forms:
            step.forms = self._wizard.forms[step_name]
        return step

    def __iter__(self):
        for name in self._wizard.get_forms().keys():
            yield self[name]

    def from_slug(self, slug):
        for step in self:
            if step.slug == slug:
                return step

    @property
    def all(self):
        """Returns a ``list`` of all steps in the wizard."""
        return list(self)

    @property
    def count(self):
        """Returns the total number of steps/forms in this the wizard."""
        return len(self._wizard.get_forms())

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
        return self[self._wizard.get_forms().keyOrder[0]]

    @property
    def last(self):
        "Returns the name of the last step."
        return self[self._wizard.get_forms().keyOrder[-1]]

    @property
    def next(self):
        """
        Returns the next step. If no more steps are available, ``None`` will be
        returned.
        """
        key = self.index + 1
        forms = self._wizard.get_forms()
        if len(forms.keyOrder) > key:
            return self[forms.keyOrder[key]]
        return None

    @property
    def prev(self):
        "Returns the previous step."
        key = self.index - 1
        forms = self._wizard.get_forms()
        if key >= 0:
            return self[forms.keyOrder[key]]
        return None

    @property
    def index(self):
        """Returns the index for the current step (0-based)."""
        return self._wizard.get_forms().keyOrder.index(self.current.name)

    index0 = index

    @property
    def index1(self):
        """Returns thei ndex for the current step (1-based)."""
        return self.index0 + 1


class WizardMixin(object):
    """
    The WizardView is used to create multi-page forms and handles all the
    storage and validation. The wizard is based on Django's generic class based
    views.

    :param               storage: module path to wizard ``Storage`` class
    :type                storage: ``unicode``
    :param          file_storage: module path to one of Django's File Storage
    :type           file_storage: ``unicode``
    :param                 steps: The pieces in the wizard. This is converted
                                  to a ``StepsManager`` object during
                                  ``as_view()``.
    :type                  steps: ``(("name", Form), ...)`` or
                                  ``(("name", [Form, ...]), ...)``
    :param       wizard_template: Template to render for ``wizard.as_html``
                                  (default: ``formwizard/wizard_form.html``)
    :type        wizard_template: ``unicode``
    :param wizard_step_templates: Templates for individual steps
    :type  wizard_step_templates: ``{step_name: template, ...}``
    """
    storage = None
    file_storage = None
    forms = None
    steps = ()
    wizard_template = 'formwizard/wizard_form.html'
    wizard_step_templates = None

    def __repr__(self):
        return '<%s: forms: %s>' % (self.__class__.__name__, self.forms)

    @classonlymethod
    def as_view(cls, steps=None, *args, **kwargs):
        steps = steps or cls.steps

        # validation
        view = '%s.%s' % (cls.__module__, cls.__name__)  # used in errors
        if len(steps) == 0:
            raise ImproperlyConfigured("`%s` requires at least one step." % view)
        if not all((isinstance(i, (tuple, list)) and len(i) == 2 for i in steps)):
            raise ImproperlyConfigured("`%s.steps` poorly formed." % view)

        forms_dict = SortedDict()

        # populate forms
        for name, forms in steps:
            if not isinstance(forms, (tuple, list)):
                forms = (forms, )
            forms_dict[unicode(name)] = forms

        # If any forms are using FileField, ensure file storage is configured.
        if not cls.file_storage:
            for forms in (form for form in forms_dict.itervalues()):
                for form in forms:
                    if issubclass(form, BaseFormSet):
                        form = form.form
                    for field in form.base_fields.itervalues():
                        if isinstance(field, FileField):
                            view = '%s.%s' % (cls.__module__, cls.__name__)
                            raise NoFileStorageConfigured(
                                    "%s contains a FileField, but "
                                    "`%s.file_storage` was not specified."
                                    % (form, view))

        # build the kwargs for the formwizard instances
        kwargs.setdefault('wizard_step_templates', {})
        kwargs['forms'] = forms_dict
        return super(WizardMixin, cls).as_view(*args, **kwargs)

    def get_forms(self):
        """
        Returns the forms to include in the wizard. This can be used as a hook
        to filter the forms based on some runtime state.

        :rtype: ``SortedDict``
        """
        return self.forms

    def get_name(self):
        return 'default'

    def get_namespace(self):
        return '%s.%s' % (self.__class__.__module__, self.__class__.__name__)

    def get_storage(self):
        if self.storage is None:
            view = '%s.%s' % (self.__class__.__module__,
                              self.__class__.__name__)
            raise ImproperlyConfigured("%s.storage is not specified." % view)
        if isinstance(self.storage, basestring):
            storage_class = get_storage(self.storage)
            return storage_class(name=self.name,
                                 namespace=self.namespace,
                                 file_storage=self.get_file_storage())
        else:
            return self.storage

    def get_file_storage(self):
        return self.file_storage

    def dispatch(self, request, *args, **kwargs):
        """
        This method gets called by the routing engine. The first argument is
        ``request`` which contains a ``HttpRequest`` instance. The storage
        instance is stored in ``self.storage``.

        After processing the request using the ``dispatch`` method, the
        response gets updated by the storage engine (for example add cookies).
        """
        # View.dispatch() does this too, but we're doing some initialisation
        # before that's called, so we'll do this now.
        self.request, self.args, self.kwargs = request, args, kwargs
        # other stuff to init
        self.name = self.get_name()
        self.namespace = self.get_namespace()
        self.steps = StepsManager(self)
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
        return self.render(self.get_validated_step_forms(step))

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

        if wizard_next_step:
            step = self.steps[wizard_next_step]
            if step:
                step = self.steps[wizard_next_step]
                self.storage.current_step = step
                forms = self.get_validated_step_forms(step)
                return self.render(forms)

        # Check if form was refreshed
        validation_error = ValidationError(
                'ManagementForm data is missing or has been tampered.')
        management_form = ManagementForm(self.request.POST, prefix='mgmt')
        if not management_form.is_valid():
            raise validation_error
        try:
            step = self.steps[management_form.cleaned_data['current_step']]
        except KeyError:
            raise validation_error
        self.storage.current_step = step
        forms = self.get_validated_step_forms(step,
                                              data=self.request.POST,
                                              files=self.request.FILES)
        if all((form.is_valid() for form in forms)):
            # Update step with valid data
            step.data  = self.request.POST
            step.files = self.request.FILES
            if step == self.steps.last:
                return self.render_done()
            else:
                return self.render_next_step()
        return self.render(forms)

    def get_forms_initials(self, step):
        """
        Returns the initial data to pass to the forms for *step*.

        :rtype: iterable with same length as number of forms for *step*
        """
        return (None, ) * len(step.forms)

    def get_forms_instances(self, step):
        """
        Returns the model instances to pass to the forms for *step*.

        :rtype: iterable with same length as number of forms for *step*
        """
        return (None, ) * len(step.forms)

    def get_forms_kwargs(self, step):
        """
        Returns the keyword arguments for instantiating the forms
        (or formsets) on given step.

        This is useful if a specific form needs some extra constructor
        arguments, e.g. a form that requires the HTTP request.

        :rtype: iterable with same length as number of forms for *step*
        """
        kwargss = []
        initials = self.get_forms_initials(step)
        if not isinstance(initials, (list, tuple)):
            initials = (initials, )
        instances = self.get_forms_instances(step)
        if not isinstance(instances, (list, tuple)):
            instances = (instances, )
        for i, form in enumerate(step.forms):
            kwargs = {
                'data': step.data,
                'files': step.files,
                'prefix': 'form-%s' % i,
                'initial': initials[i],
            }
            if issubclass(form, ModelForm):
                # If the form is based on ModelForm, add instance if available.
                kwargs['instance'] = instances[i]
            elif issubclass(form, BaseModelFormSet):
                # If the form is based on ModelFormSet, add queryset if
                # available.
                kwargs['queryset'] = instances[i]
            kwargss.append(kwargs)
        return kwargss

    def get_validated_step_forms(self, step, **kwargs):
        """
        Returns validated form objects for the given *step*.
        """
        forms = []
        kwargss = self.get_forms_kwargs(step)
        if not isinstance(kwargss, (list, tuple)):
            kwargss = (kwargss, )
        for form_kwargs, form in zip(kwargss, step.forms):
            form_kwargs.update(kwargs)
            f = form(**form_kwargs)
            f.is_valid()  # trigger validation
            forms.append(f)
        return forms

    def get_context_data(self, forms, **kwargs):
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
            'forms': forms,
            'steps': self.steps,
            'management_form': ManagementForm(prefix='mgmt', initial={
                'current_step': self.steps.current.name,
            }),
            'as_html': lambda: self.get_wizard_html(
                    RequestContext(self.request, context))
        }
        return context

    def get_wizard_template(self, step):
        """
        :param step: the step whose template to return
        :type  step: ``Step`` object
        :returns   : ``Template`` object
        """
        return get_template(self.wizard_step_templates.get(
                step.name, self.wizard_template))

    def get_wizard_html(self, context):
        return self.get_wizard_template().render(context)

    # -- views ----------------------------------------------------------------

    def done(self, forms):
        """
        This method muss be overrided by a subclass to process to form data
        after processing all steps.
        """
        raise NotImplementedError("Your %s class has not defined a done() "
            "method, which is required." % self.__class__.__name__)


    def render(self, forms=None):
        """
        Returns a ``HttpResponse`` containing a all needed context data.
        """
        forms = forms or self.get_validated_step_forms(step=self.steps.current)
        context = self.get_context_data(forms=forms)
        return self.render_to_response(context)

    def render_done(self):
        """
        This method gets called when all forms passed. The method should also
        re-validate all steps to prevent manipulation. If any form don't
        validate, ``render_revalidation_failure`` should get called.

        If everything is fine call ``done``.
        """
        valid_forms = SortedDict()
        # ensure all the forms are valid
        for step in self.steps:
            forms = self.get_validated_step_forms(step=step)
            if not all((form.is_valid() for form in forms)):
                return self.render_revalidation_failure(step)
            # flatten single item tuples into just the form
            if len(forms) == 1:
                forms = forms[0]
            valid_forms[step.name] = forms

        # render the done view and reset the wizard before returning the
        # response. This is needed to prevent from rendering done with the
        # same data twice.
        response = self.done(valid_forms)
        self.storage.reset()
        return response

    def render_revalidation_failure(self, step):
        """
        Gets called when a form doesn't validate when rendering the done
        view. By default, it changed the current step to failing forms step
        and renders the form.

        :param step: the step that failed validation
        :type  step: ``Step`` object
        """
        self.storage.current_step = step
        return self.render()

    def render_next_step(self):
        """
        When using the NamedUrlFormWizard, we have to redirect to update the
        browser's URL to match the shown step.
        """
        self.storage.current_step = self.steps.next
        return self.render()


class WizardView(WizardMixin, TemplateView):
    """
    A view premixed with ``WizardMixin`` and ``TemplateView``. To use this a
    *storage* must be specified.
    """


class NamedUrlWizardMixin(WizardMixin):
    """
    A WizardView with URL named steps support.
    """
    wizard_done_step_slug = "finished"

    def get(self, request, *args, **kwargs):
        """
        This renders the form or, if needed, does the HTTP redirects.
        """
        slug = kwargs.get('slug')
        if not slug:
            if request.GET:
                query_string = "?%s" % request.GET.urlencode()
            else:
                query_string = ""
            return redirect(self.steps.current.url + query_string)

        # is the current step the "done" name/view?
        if slug == self.wizard_done_step_slug:
            return self.render_done()

        step = self.steps.from_slug(slug)
        if step:
            self.storage.current_step = step
            return self.render(self.get_validated_step_forms(step))

        # invalid step name, reset to first and redirect.
        self.storage.current_step = self.steps.first
        return redirect(self.steps.first.url)

    def post(self, request, *args, **kwargs):
        """
        Do a redirect if user presses the prev. step button. The rest of this
        is super'd from FormWizard.
        """
        next_step_name = request.POST.get('wizard_next_step')
        if next_step_name:
            next_step = self.steps[next_step_name]
            if next_step:
                self.storage.current_step = next_step
                return redirect(next_step.url)
        return super(NamedUrlWizardMixin, self).post(request, *args, **kwargs)

    def get_step_url(self, **kwargs):
        match = getattr(self, '_step_url_match', None)
        if not match:
            try:
                self._step_url_match = match = resolve(self.request.path)
            except Http404:
                raise ImproperlyConfigured(
                        "Unable to automatically determine wizard URL pattern."
                        " %s.get_step_url() must be implemented."
                        % self.__class__.__name__)
        kwargs = dict(match.kwargs, **kwargs)
        url_name = ':'.join((match.namespaces + [match.url_name]))
        return reverse(url_name, args=match.args, kwargs=kwargs,
                       current_app=match.app_name)

    def get_storage(self):
        wizard = self

        class NamedUrlStep(Step):
            @property
            def url(self):
                return wizard.get_step_url(slug=self.slug)

        storage = super(NamedUrlWizardMixin, self).get_storage()
        storage.step_class = NamedUrlStep
        return storage

    # -- views ----------------------------------------------------------------

    def render_done(self):
        """
        When rendering the done view, we have to redirect first (if the URL
        name doesn't fit).
        """
        # for any steps that don't have any form data, change it to a suitable
        # default
        # TODO: clean-up this, does it need to go in WizardMixin?
        for step in self.steps:
            if step.data is None:
                step.data = {}
                # if it's a formset, we need to create a plain management form
                # to use as the step data, otherwise we'll get "ManagementForm
                # data is missing or has been tampered with" error
                validated_step_forms = self.get_validated_step_forms(step, data=None)  # cache
                for i, form in enumerate(step.forms):
                    if issubclass(form, BaseFormSet):
                        management_form = validated_step_forms[i].management_form
                        for key, value in management_form.initial.iteritems():
                            step.data[management_form.add_prefix(key)] = value
        # Make sure we're on the right page.
        if self.kwargs.get('slug') != self.wizard_done_step_slug:
            return redirect(self.get_step_url(slug=self.wizard_done_step_slug))
        return super(NamedUrlWizardMixin, self).render_done()

    def render_next_step(self):
        """
        When using the NamedUrlFormWizard, we have to redirect to update the
        browser's URL to match the shown step.
        """
        next_step = self.steps.next
        self.storage.current_step = next_step
        return redirect(next_step.url)

    def render_revalidation_failure(self, step):
        """
        When a step fails, we have to redirect the user to the first failing
        step.
        """
        self.storage.current_step = step
        return redirect(step.url)


class NamedUrlWizardView(NamedUrlWizardMixin, TemplateView):
    """
    A view premixed with ``NamedUrlWizardMixin`` and ``TemplateView``. To use
    this a *storage* must be specified.
    """
