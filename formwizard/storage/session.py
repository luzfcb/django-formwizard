from formwizard.storage import Storage
from django.core.exceptions import ImproperlyConfigured


class SessionStorage(Storage):
    """
    A storage backend for form wizards that stores data into the user's
    session.
    """
    def __init__(self, *args, **kwargs):
        super(SessionStorage, self).__init__(*args, **kwargs)
        self.key = ('%s|%s' % (self.namespace, self.name)).encode('utf-8')
        self._deleted = False  # delete requested?

    def process_request(self, request):
        if not hasattr(request, 'session'):
            raise ImproperlyConfigured("Session middleware must be enabled to "
                                       "use %s" % self.__class__.__name__)
        self._session = request.session
        data = self._session.get(self.key)
        if data is None:
            data = {'current_step': None, 'steps': {}}
        self.decode(data)

    def process_response(self, response):
        if not self._deleted:
            self._session.setdefault(self.key, {}).update(self.encode())
            self._session.modified = True

    def delete(self):
        try:
            del self._session[self.key]
        except KeyError:
            pass
        self.reset()
        self._deleted = True
