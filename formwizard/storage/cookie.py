from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.utils import simplejson as json
from django.utils.hashcompat import sha_constructor
from formwizard.storage import Storage
import hmac


class CookieStorage(Storage):
    encoder = json.JSONEncoder(separators=(',', ':'))

    def process_request(self, request):
        self.decode(request.COOKIES.get(self._prefix, ''))

    def process_response(self, response):
        if self.steps or self.current_step:
            response.set_cookie(self._prefix, self.encode())

    def decode(self, data):
        # check integrity
        hash, _, payload = data.partition('$')
        if payload:
            if hash != self.hash(payload):
                raise SuspiciousOperation('Form wizard cookie manipulated')
            decoded = json.loads(payload, cls=json.JSONDecoder)
        else:
            decoded = {'current_step': None, 'steps': {}}
        super(CookieStorage, self).decode(decoded)

    def encode(self):
        data = super(CookieStorage, self).encode()
        payload = self.encoder.encode(data)
        return '%s$%s' % (self.hash(payload), payload)

    def hash(self, data):
        return hmac.new('%s$%s' % (settings.SECRET_KEY, self._prefix),
                        data, sha_constructor).hexdigest()
