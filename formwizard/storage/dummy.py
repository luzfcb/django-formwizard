from __future__ import absolute_import, unicode_literals
from formwizard.storage import Storage


# in memory storage
_DATA = {}


class DummyStorage(Storage):
    """
    A dummy storage that stores all data in memory. Designed for testing. Not
    thread safe.
    """
    def __init__(self, *args, **kwargs):
        super(DummyStorage, self).__init__(*args, **kwargs)
        self._deleted = False

    def process_request(self, request):
        self.decode(_DATA.setdefault(self.namespace, {})
                         .setdefault(self.name, {'current_step': None,
                                                 'steps': {}}))

    def process_response(self, response):
        if not self._deleted:
            _DATA[self.namespace][self.name].update(self.encode())

    def delete(self):
        del _DATA[self.namespace][self.name]
        if _DATA[self.namespace] == {}:
            del _DATA[self.namespace]
        self._deleted = True
