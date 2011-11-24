from __future__ import absolute_import, unicode_literals
from django.core.exceptions import ImproperlyConfigured
from django.utils import simplejson as json
from formwizard.storage import Storage
from formwizard.models import WizardState


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
                        % self.__class__.__name__)
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
