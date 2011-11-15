from __future__ import absolute_import, unicode_literals
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.utils import simplejson as json
from django.utils.hashcompat import sha_constructor
from django.utils.encoding import smart_str
from formwizard.storage import Storage
import hmac


class CookieStorage(Storage):
    # explicitly specifying the separators removes extraneous whitespace in the
    # JSON output
    encoder = json.JSONEncoder(separators=(',', ':'))

    def process_request(self, request):
        key = self._prefix.encode('utf-8')
        self.decode(request.COOKIES.get(key, ''))

    def process_response(self, response):
        if self.steps or self.current_step:
            key = self._prefix.encode('utf-8')
            response.set_cookie(key, self.encode())

    def decode(self, data):
        # check integrity
        hmac, _, payload = data.partition('$')
        if payload:
            if hmac != self.hmac(payload):
                raise SuspiciousOperation('Form wizard cookie manipulated')
            decoded = json.loads(payload, cls=json.JSONDecoder)
        else:
            decoded = {'current_step': None, 'steps': {}}
        super(CookieStorage, self).decode(decoded)

    def encode(self):
        data = super(CookieStorage, self).encode()
        payload = self.encoder.encode(data)
        return '%s$%s' % (self.hmac(payload), payload)

    def hmac(self, data):
        key = smart_str('%s$%s' % (settings.SECRET_KEY, self._prefix))
        msg = smart_str(data)
        return hmac.new(key, msg, sha_constructor).hexdigest()
