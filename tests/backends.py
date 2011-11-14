# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from attest import assert_hook, Assert, Tests
from django.core.exceptions import ImproperlyConfigured
from django.contrib.sessions.middleware import SessionMiddleware
from django import forms
from django.test.client import RequestFactory
from formwizard.views import SessionWizardView


class Step1(forms.Form):
    name = forms.CharField()


class Step2(forms.Form):
    name = forms.CharField()


factory = RequestFactory()
sessions = Tests()


@sessions.test
def should_raise_exception_if_session_middleware_not_used():
    view = SessionWizardView.as_view([Step1, Step2])
    request = factory.get('/')
    with Assert.raises(ImproperlyConfigured):
        view(request)

    # use session middleware and no exceptions should be raised
    middleware = SessionMiddleware()
    request = factory.get('/')
    middleware.process_request(request)
    view(request)


tests = Tests([sessions])

