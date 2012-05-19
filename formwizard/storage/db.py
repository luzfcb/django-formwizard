from __future__ import absolute_import, unicode_literals
from django.core.exceptions import ImproperlyConfigured
from formwizard.storage import Storage
from formwizard.models import WizardState
import json


class DatabaseStorage(Storage):
    encoder = json.JSONEncoder(separators=(',', ':'))

    def __init__(self, *args, **kwargs):
        super(DatabaseStorage, self).__init__(*args, **kwargs)
        self._deleted = False

    def process_request(self, request):
        kwargs = {'name': self.name, 'namespace': self.namespace}
        # Either session or authentication information is used to scope the
        # wizard state. This is implicit with using CookieStorage or
        # SesssionStorage, but it must be done explicitly here. Preferably the
        # User is used, but fallback to the session key is supported
        try:
            assert request.user.is_authenticated()
            kwargs['user'] = request.user
        except (AssertionError, AttributeError):
            if not hasattr(request, 'session'):
                raise ImproperlyConfigured(
                        '%s requires that the sessions middleware is enabled.'
                        % type(self).__name__)
            if not request.session.session_key:
                # Starting in Django 1.4, the session_key isn't determined
                # until the first response is handled by the middleware.
                # We get around this by manually saving the session to trigger
                # the creation of session_key
                request.session.save()
            kwargs['session_key'] = request.session.session_key
        self._state, created = WizardState.objects.get_or_create(**kwargs)
        self.decode(self._state.data)

    def process_response(self, response):
        if not self._deleted:
            self._state.data = self.encode()
            self._state.full_clean()
            self._state.save()

    def delete(self):
        self._state.delete()
        self.reset()
        self._deleted = True

    def encode(self):
        return self.encoder.encode(super(DatabaseStorage, self).encode())

    def decode(self, data):
        return super(DatabaseStorage, self).decode(json.loads(data))
