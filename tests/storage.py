# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from attest import assert_hook, Assert, Tests
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.backends.db import SessionStore
from django import forms
from django.http import HttpResponse
from django.test.client import RequestFactory
from django_attest import TestContext
from formwizard.models import WizardState
from formwizard.storage import (CookieStorage, DatabaseStorage, DummyStorage,
                                get_storage, MissingStorageClass,
                                MissingStorageModule, SessionStorage, Step,
                                Storage)
from formwizard.views import WizardView
import shutil
import tempfile


factory = RequestFactory()
core = Tests()


@core.context
def temporary_directory():
    """
    Create temporary directory that can be used for stuff (e.g. as file storage
    location).
    """
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path)


@core.test
def get_storage_should_return_correct_class():
    assert get_storage('formwizard.storage.Storage') == Storage
    assert get_storage('formwizard.storage.CookieStorage') == CookieStorage
    assert get_storage('formwizard.storage.DummyStorage') == DummyStorage
    assert get_storage('formwizard.storage.SessionStorage') == SessionStorage

    with Assert.raises(MissingStorageModule):
        get_storage('formwizard.idontexist.NonExistentStorage')

    with Assert.raises(MissingStorageClass):
        get_storage('formwizard.storage.NonExistentStorage')


@core.test
def should_encode_and_decode_properly(temp):
    file_storage = FileSystemStorage(location=temp)

    storage = Storage('name', 'namespace', file_storage)
    assert storage.encode() == {'current_step': None, 'steps': {}}
    restored = Storage('name', 'namespace', file_storage)
    restored.decode(storage.encode())
    assert storage.encode() == restored.encode()

    storage.current_step = storage['step1']
    restored.decode(storage.encode())
    assert storage.encode() == restored.encode()

    storage.steps = {'step1': storage['step1']}
    restored.decode(storage.encode())
    assert storage.encode() == restored.encode()

    step = storage['step1']
    step.data = {}
    assert storage.encode() == {
        'current_step': 'step1',
        'steps': {
            'step1': {
                'files': None,
                'data': {},
            },
        }
    }
    restored.decode(storage.encode())
    assert storage.encode() == restored.encode()

    with open(__file__, 'rb')as f:
        content = f.read()

    step = storage['step1']
    step.files = {'file1': InMemoryUploadedFile(file=open(__file__),
                                                field_name="file1",
                                                name="filename",
                                                content_type="text/plain",
                                                size=len(content),
                                                charset="utf-8")}

    restored.decode(storage.encode())
    restored_step = restored['step1']
    assert restored_step.files['file1'].read() == content


session = Tests()


@session.test
def should_raise_exception_if_session_middleware_not_used():
    class Step1(forms.Form):
        name = forms.CharField()

    class Step2(forms.Form):
        name = forms.CharField()

    class StepsWizardView(WizardView):
        storage_name = 'formwizard.storage.SessionStorage'
        form_list = (Step1, Step2)

    view = StepsWizardView.as_view()
    request = factory.get('/')
    with Assert.raises(ImproperlyConfigured):
        view(request)

    # use session middleware and no exceptions should be raised
    middleware = SessionMiddleware()
    request = factory.get('/')
    middleware.process_request(request)
    view(request)


cookie = Tests()


@cookie.test
def should_add_cookies_to_response():
    storage = CookieStorage('name', 'namespace')
    request, response = factory.get('/'), HttpResponse('')
    storage.process_request(request)
    storage.steps = {'step1': Step('step1')}
    storage.process_response(response)
    assert response.cookies[storage.key].value == storage.encode()


@cookie.test
def state_should_be_preserved_between_encode_and_decode():
    original = CookieStorage('name', 'namespace')
    request = factory.get('/')
    original.process_request(request)
    original.steps = {'step1': Step('step1')}
    # create new storage by decoding original
    restored = CookieStorage('name', 'namespace')
    restored.decode(original.encode())
    # they should be the same
    assert restored.encode() == original.encode()


@cookie.test
def should_complain_when_cookie_is_tampered():
    storage = CookieStorage('name', 'namespace')
    request = factory.get('/')
    request.COOKIES[storage.key] = 'i$am$manipulated'
    with Assert.raises(SuspiciousOperation):
        storage.process_request(request)


@cookie.test
def reset_should_clear_data():
    storage = CookieStorage('name', 'namespace')
    storage.steps = {'step1': Step('step1')}

    expected = '{"current_step":null,"steps":{"step1":{"files":null,"data":null}}}'
    assert storage.encode() == '%s$%s' % (storage.hmac(expected), expected)

    storage.reset()

    expected = '{"current_step":null,"steps":{}}'
    assert storage.encode() == '%s$%s' % (storage.hmac(expected), expected)


db = Tests()
db.context(TestContext())


@db.test
def should_complain_if_no_session_and_has_anonymous_user():
    storage = DatabaseStorage('name', 'namespace')
    request = factory.get('/')
    request.user = AnonymousUser()
    with Assert.raises(ImproperlyConfigured):
        storage.process_request(request)


@db.test
def should_complain_if_no_session_and_has_no_user():
    storage = DatabaseStorage('name', 'namespace')
    request = factory.get('/')
    with Assert.raises(ImproperlyConfigured):
        storage.process_request(request)


@db.test
def shouldnt_complain_if_no_session_and_has_authenticated_user():
    storage = DatabaseStorage('name', 'namespace')
    request = factory.get('/')
    request.user = User.objects.create_user('username', 'email@example.com')
    storage.process_request(request)


@db.test
def shouldnt_complain_if_has_session():
    storage = DatabaseStorage('name', 'namespace')
    request = factory.get('/')
    SessionMiddleware().process_request(request)  # add 'session' attribute
    storage.process_request(request)


@db.test
def should_create_new_model_instance_linked_to_user():
    assert WizardState.objects.count() == 0

    storage = DatabaseStorage('name', 'namespace')
    request, response = factory.get('/'), HttpResponse('')
    request.user = User.objects.create_user('username', 'email@example.com')
    storage.process_request(request)
    storage.process_response(response)

    assert WizardState.objects.count() == 1
    assert WizardState.objects.get(name='name', namespace='namespace',
                                   user=request.user)


@db.test
def should_create_new_model_instance_referencing_to_session():
    assert WizardState.objects.count() == 0
    storage = DatabaseStorage('name', 'namespace')
    request = factory.get('/')
    request.session = SessionStore()
    storage.process_request(request)
    print request.session.session_key
    assert WizardState.objects.count() == 1
    assert WizardState.objects.get(name='name', namespace='namespace',
                                   session_key=request.session.session_key)


tests = Tests((cookie, core, db, session))
