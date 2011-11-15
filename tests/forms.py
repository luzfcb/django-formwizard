from __future__ import absolute_import, unicode_literals
from attest import assert_hook, Assert, Tests
from django import forms
from django.http import HttpRequest
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.forms.formsets import formset_factory, BaseFormSet
from django.forms.models import modelformset_factory
from django.db import models
from django.db.models.query import QuerySet
from django.test import TestCase
from django.test.client import RequestFactory
from django.template.response import TemplateResponse
from django.utils.importlib import import_module
from django.views.generic.base import TemplateView
from django.utils.datastructures import SortedDict
from formwizard.views import (CookieWizardView, SessionWizardView, WizardMixin)
from .app.models import Person


factory = RequestFactory()
as_view = Tests()


class Step1(forms.Form):
    name = forms.CharField()


class Step2(forms.Form):
    name = forms.CharField()


class Step3(forms.Form):
    data = forms.CharField()


class DispatchHookMixin(object):
    """
    A view mixin that causes the view instance to be returned from
    ``dispatch()``. This allows ``as_view()`` in generic views to be tested.
    """
    def dispatch(self, request, *args, **kwargs):
        super(DispatchHookMixin, self).dispatch(request, *args, **kwargs)
        return self


@as_view.test
def should_enumerate_unnamed_forms():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (Step1, Step2)

    expected = SortedDict((
        ('0', Step1),
        ('1', Step2)
    ))
    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.form_list == expected


@as_view.test
def should_preserve_named_forms():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            ('step1', Step1),
            ('step2', Step2),
        )

    expected = SortedDict((
        ('step1', Step1),
        ('step2', Step2),
    ))
    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.form_list == expected


@as_view.test
def should_handle_mixed_forms():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1,
            Step2,
            ('finish', Step3),
        )

    expected = SortedDict((
        ('0', Step1),
        ('1', Step2),
        ('finish', Step3),
    ))
    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.form_list == expected


steps = Tests()


@steps.test
def by_default_the_first_form_should_be_the_current_step():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1,
            Step2,
        )
    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.steps.current.name == '0'

    # check named version
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            ('step1', Step1),
            ('step2', Step2),
        )
    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.steps.current.name == 'step1'


@steps.test
def current_step_should_be_persisted_in_backend():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1,
            Step2,
        )

    view = TestWizardView.as_view()

    request = factory.get('/')
    instance = view(request)
    assert instance.storage.current_step.name == '0'

    request = factory.post('/', {'test_wizard_view-current_step': '1'})
    instance = view(request)
    assert instance.storage.current_step.name == '1'


@steps.test
def form_list_should_honor_conditions():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1,
            Step2,
        )
        condition_dict = {
            '0': lambda view: False,
        }

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.get_form_list() == {'1': Step2}


@steps.test
def initial_dict_should_be_honored():
    class InitialRequiredForm(forms.Form):
        def __init__(self, *args, **kwargs):
            if kwargs.get('initial') != 'expected value':
                raise ValueError
            super(InitialRequiredForm, self).__init__(*args, **kwargs)

    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            InitialRequiredForm,
            Step2,
        )
        initial_dict = {
            '0': 'expected value',
        }

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    step = instance.storage['1']
    assert instance.get_form_initial(step) == None


@steps.test
def instance_dict_should_be_honored():
    person = Person.objects.create(name='brad')

    class InstanceRequiredForm(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            if kwargs.get('instance') != person:
                raise ValueError
            super(InstanceRequiredForm, self).__init__(*args, **kwargs)

        class Meta:
            model = Person

    InstanceRequiredFormSet = modelformset_factory(
            Person, InstanceRequiredForm, extra=0)

    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            InstanceRequiredForm,
            InstanceRequiredFormSet,
            Step2,
        )
        instance_dict = {
            '0': person,
            '1': Person.objects.all(),
        }

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    instance.get_form(instance.storage['0'])
    instance.get_form(instance.storage['1'])
    instance.get_form(instance.storage['2'])
    assert instance.get_form_instance(instance.storage['2']) == None


@steps.test
def done_raises_exception_unless_implemented():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1,
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    with Assert.raises(NotImplementedError):
        instance.done(form_list=[])


@steps.test
def render_done_performs_validation():
    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1,
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    instance.render_done()
    assert instance.storage.current_step.name == '0'


formsets = Tests()


@formsets.test
def should_honor_extra_forms_correctly():
    Step1Formset = formset_factory(Step1, extra=3)

    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1Formset,
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)

    step = instance.storage['0']
    formset = instance.get_form(step)
    assert len(formset.forms) == 3

    # Now add some data for the first form
    step.data = {
        '0-0-name': 'Brad',
        '0-1-name': '',
        '0-2-name': '',
        '0-TOTAL_FORMS': 3,
        '0-INITIAL_FORMS': 0,
        '0-MAX_NUM_FORMS': '',
    }
    formset = instance.get_form(step)
    assert len(formset.forms) == 3


@formsets.test
def formsets_should_be_validated():
    class BorkedFormset(BaseFormSet):
        def clean(self):
            raise ValidationError("Expected error")

    Step1BorkedFormset = formset_factory(Step1, BorkedFormset)

    class TestWizardView(DispatchHookMixin, CookieWizardView):
        form_list = (
            Step1BorkedFormset,
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    step = instance.storage['0']
    assert not instance.get_form(step).non_form_errors()

    # Add some data so the form is bound then we should get non_form_errors
    step.data = {'0-TOTAL_FORMS': '1', '0-INITIAL_FORMS': 0,
                 '0-MAX_NUM_FORMS': ''}
    assert instance.get_form(step).non_form_errors() == ['Expected error']


tests = Tests((as_view, formsets, steps))
