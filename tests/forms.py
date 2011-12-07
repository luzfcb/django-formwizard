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
from formwizard.views import WizardView
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
    ``dispatch()``. This allows the internals of a view to be tested.
    """
    def dispatch(self, request, *args, **kwargs):
        super(DispatchHookMixin, self).dispatch(request, *args, **kwargs)
        return self


@as_view.test
def should_preserve_named_forms():
    class TestWizardView(DispatchHookMixin, WizardView):
        storage = 'formwizard.storage.dummy.DummyStorage'
        template_name = 'simple.html'
        steps = (
            ('Step 1', Step1),
            ('Step 2', Step2),
        )

    expected = SortedDict((
        ('Step 1', (Step1, )),
        ('Step 2', (Step2, )),
    ))
    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.forms == expected

steps = Tests()


@steps.test
def by_default_the_first_form_should_be_the_current_step():
    class TestWizardView(DispatchHookMixin, WizardView):
        storage = 'formwizard.storage.dummy.DummyStorage'
        template_name = 'simple.html'
        steps = (
            ('Step 1', Step1),
            ('Step 2', Step2),
        )
    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    assert instance.steps.current.name == 'Step 1'


@steps.test
def current_step_should_be_persisted_in_backend():
    class TestWizardView(DispatchHookMixin, WizardView):
        storage = 'formwizard.storage.dummy.DummyStorage'
        template_name = 'simple.html'
        steps = (
            ("Step 1", Step1),
            ("Step 2", Step2),
        )

    view = TestWizardView.as_view()

    request = factory.get('/')
    instance = view(request)
    assert instance.storage.current_step.name == 'Step 1'

    request = factory.post('/', {'mgmt-current_step': 'Step 2'})
    instance = view(request)
    assert instance.storage.current_step.name == 'Step 2'


@steps.test
def done_raises_exception_unless_implemented():
    class TestWizardView(DispatchHookMixin, WizardView):
        storage = 'formwizard.storage.dummy.DummyStorage'
        template_name = 'simple.html'
        steps = (
            ("Step 1", Step1),
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    with Assert.raises(NotImplementedError):
        instance.done([])


@steps.test
def render_done_performs_validation():
    class TestWizardView(DispatchHookMixin, WizardView):
        storage = 'formwizard.storage.dummy.DummyStorage'
        template_name = 'simple.html'
        steps = (
            ("Step 1", Step1),
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    instance.render_done()
    assert instance.storage.current_step.name == 'Step 1'


formsets = Tests()


@formsets.test
def should_honor_extra_forms_correctly():
    Step1Formset = formset_factory(Step1, extra=3)

    class TestWizardView(DispatchHookMixin, WizardView):
        storage = 'formwizard.storage.dummy.DummyStorage'
        template_name = 'simple.html'
        steps = (
            ("Step 1", Step1Formset),
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)

    step = instance.steps['Step 1']
    (formset, ) = instance.get_validated_step_forms(step)
    assert len(formset.forms) == 3

    # Now add some data for the first form
    step.data = {
        'form-0-0-name': 'Brad',
        'form-0-1-name': '',
        'form-0-2-name': '',
        'form-0-TOTAL_FORMS': 3,
        'form-0-INITIAL_FORMS': 0,
        'form-0-MAX_NUM_FORMS': '',
    }
    (formset, ) = instance.get_validated_step_forms(step)
    assert len(formset.forms) == 3


@formsets.test
def formsets_should_be_validated():
    class BorkedFormset(BaseFormSet):
        def clean(self):
            raise ValidationError("Expected error")

    Step1BorkedFormset = formset_factory(Step1, BorkedFormset)

    class TestWizardView(DispatchHookMixin, WizardView):
        storage = 'formwizard.storage.dummy.DummyStorage'
        template_name = 'simple.html'
        steps = (
            ("Step 1", Step1BorkedFormset),
        )

    view = TestWizardView.as_view()
    request = factory.get('/')
    instance = view(request)
    step = instance.steps['Step 1']
    (formset, ) = instance.get_validated_step_forms(step)
    assert not formset.non_form_errors()

    # Add some data so the form is bound then we should get non_form_errors
    step.data = {
        'form-0-TOTAL_FORMS': '1',
        'form-0-INITIAL_FORMS': 0,
        'form-0-MAX_NUM_FORMS': ''
    }
    (formset, ) = instance.get_validated_step_forms(step)
    assert formset.non_form_errors() == ['Expected error']


tests = Tests((as_view, formsets, steps))
