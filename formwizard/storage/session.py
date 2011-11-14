from formwizard.storage import Storage
from django.core.exceptions import ImproperlyConfigured


class SessionStorage(Storage):
    """
    A storage backend for form wizards that stores data into the user's
    session.
    """
    def process_request(self, request):
        if not hasattr(request, 'session'):
            raise ImproperlyConfigured("Session middleware must be enabled to "
                                       "use %s" % self.__class__.__name__)
        self._session = request.session
        data = self._session.get(self._prefix)
        if data is None:
            data = {'current_step': None, 'steps': {}}
        self.decode(data)

    def process_response(self, response):
        self._session.setdefault(self._prefix, {}).update(self.encode())
        self._session.modified = True
