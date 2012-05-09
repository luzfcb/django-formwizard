from __future__ import absolute_import, unicode_literals
from django.core.files.uploadedfile import UploadedFile
from django.template.defaultfilters import slugify
from django.utils.encoding import smart_str
from formwizard.storage.exceptions import NoFileStorageConfigured
from .endecs import PickleEndec


class Step(object):
    """
    A single step in the wizard.

    :param  name: name of step
    :type   name: ``unicode``
    :param  data: form data
    :type   data: ``{"<field name>": "<raw value>", ...}``
    :param files: form files
    :type  files: ``{"<field name>": <UploadedFile object>, ...}``
    :param forms: all the forms for the step
    :type  forms: iterable
    """
    def __init__(self, name, data=None, files=None, forms=None):
        self.name = name
        self.data = data
        self.files = files
        self.forms = forms

    @property
    def slug(self):
        return slugify(self.name)


class Storage(object):
    """
    Base class for all wizard storages.

    A *storage* is the mechanism that allows state of the wizard to be stored
    across multiple HTTP requests. Information required to acomplish this
    is the *current step* and the raw data and files for each form in the
    wizard.

    :param         name: A unique identifier within context of *namespace*.
                         Used to differentiate state betwen different instances
                         of the same wizard.
    :type          name: ``unicode``
    :param    namespace: A unique identifier for each wizard.
    :type     namespace: ``unicode``
    :param file_storage: Django file storage backend used to store form files.
                         If omitted, this storage will refuse to store forms
                         that include file fields.
    :type  file_storage: ``django.core.files.Storage`` class
    """
    step_class = Step
    endec = PickleEndec()

    def __init__(self, name, namespace, file_storage=None):
        self.name = name
        self.namespace = namespace
        self.file_storage = file_storage
        self.steps = {}
        self.current_step = None

    def process_request(self, request):
        """
        Performs any required functions when the request is made available.
        Typically this is used to populate ``self.steps``
        """
        pass

    def process_response(self, response):
        """
        Makes any changes to the response that are required by the storage
        (e.g. adding cookies)
        """
        pass

    def reset(self):
        """
        Reset the storage for the current wizard back to a clean initial state.
        """
        self.steps = {}
        self.current_step = None

    def delete(self):
        """
        Deletes the record entirely from the storage.
        """
        raise NotImplementedError

    def __getitem__(self, name):
        """
        Returns the step with the given name.
        """
        if name not in self.steps:
            self.steps[name] = self.step_class(name)
        return self.steps[name]

    def __contains__(self, name):
        return name in self.steps

    def _decode_files(self, files):
        """
        Helper method that when given *files* -- a ``dict`` with the
        structure::

            {
                "<field_name>": {
                    "file_storage_key": "<unicode>",
                    "name": "<unicode>",
                    "content_type": "<unicode>",
                    "size": "<int>",
                    "charset": "<unicode>",
                },
                ...
            }

        a new ``dict`` it returned with the structure::

            {
                "<field_name>": <UploadedFile object>,
                ...
            }

        """
        if files is None:
            return None
        decoded = {}
        for name, data in files.iteritems():
            key = data.pop('file_storage_key')
            uploaded_file = UploadedFile(file=self.file_storage.open(key),
                                         **data)
            # In order to ensure that files aren't repeatedly saved to the file
            # storage, the filename of each file in the file storage is added
            # to ``UploadedFile`` objects as a ``_wizard_file_storage_key``
            # attribute when they're decoded. This acts as a marker to indicate
            # that the file already exists in the file storage.
            uploaded_file._wizard_file_storage_key = key
            decoded[name] = uploaded_file
        return decoded

    def _encode_files(self, files):
        """
        Performs the opposite conversion to ``_decode_files()``.
        """
        if files is None:
            return None
        if files and not self.file_storage:
            raise NoFileStorageConfigured
        encoded = {}
        for name, uploadedfile in files.iteritems():
            key = getattr(uploadedfile, '_wizard_file_storage_key', None)
            if key is None:
                key = self.file_storage.save(uploadedfile.name, uploadedfile)
            encoded[name] = {
                'file_storage_key': key,
                'name': uploadedfile.name,
                'content_type': uploadedfile.content_type,
                'size': uploadedfile.size,
                'charset': uploadedfile.charset
            }
        return encoded

    def encode(self):
        """
        Encodes the current wizard state to a ``dict``::

            {
                "current_step": "<name>",
                "steps": {
                    "<name>": {
                        "files": { ... },
                        "data": {"<fieldname>": "<rawfieldvalue>", ... },
                    },
                    ...
                }
            }

        See ``_encode_files()`` for the structure of each step's *files*.
        """
        current = self.current_step
        data = {
            'current_step': None if current is None else current.name,
            'steps': {},
        }
        for step in self.steps.itervalues():
            data['steps'][step.name] = {
                'files': self._encode_files(step.files),
                'data': step.data,
            }
        return self.endec.encode(data)

    def decode(self, bytes_):
        """
        Performs reverse operation to ``encode()``.
        """
        obj = self.endec.decode(bytes_)
        for name, attrs in obj['steps'].iteritems():
            self.steps[name] = self.step_class(
                    name, data=attrs['data'],
                    files=self._decode_files(attrs['files']))
        # It's important to set the current step *after* creating all the Step
        # objects, so that ``self.current_step`` refers to an object in
        # ``self.steps``
        if obj['current_step'] is None:
            self.current_step = None
        else:
            self.current_step = self[obj['current_step']]
