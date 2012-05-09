import base64
import pickle


class Endec(object):
    """
    Encodes objects to binary.
    """
    def encode(self, obj):
        raise NotImplementedError

    def decode(self, bytes):
        raise NotImplementedError


class PickleEndec(Endec):
    def encode(self, obj):
        pickled = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        return base64.encodestring(pickled)

    def decode(self, bytes):
        pickled = base64.decodestring(bytes)
        return pickle.loads(pickled, protocol=pickle.HIGHEST_PROTOCOL)


class DummyEndec(Endec):
    def encode(self, obj):
        return obj

    def decode(self, bytes):
        return bytes
