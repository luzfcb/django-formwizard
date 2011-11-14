from __future__ import absolute_import, unicode_literals
from django.core.files.uploadedfile import UploadedFile
from django.utils.encoding import smart_str
from formwizard.storage.exceptions import NoFileStorageConfigured


class Step(object):
    """
    A single step in the wizard.

    :param  name: name of step
    :type   name: ``unicode``
    :param  data: form data
    :type   data: ``{"<field name>": "<raw value>", ...}``
    :param files: form files
    :type  files: ``{"<field name>": <UploadedFile object>, ...}``
    """
    # TODO: finish above docstring
    def __init__(self, name, data=None, files=None):
        self.name = name
        self.data = data or {}
        self.files = files or {}


class Storage(object):
    step_class = Step

    def __init__(self, prefix, file_storage):
        self._prefix = prefix
        self._file_storage = file_storage
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

    def __getitem__(self, name):
        """
        Returns the step with the given name.
        """
        if name not in self.steps:
            self.steps[name] = self.step_class(name)
        return self.steps[name]

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
        decoded = {}
        for name, data in files.iteritems():
            key = data.pop('file_storage_key')
            uploaded_file = UploadedFile(file=self._file_storage.open(key),
                                         **data)
            # In order to ensure that files aren't repeatedly saved to the file
            # storage, the filename of each file in the file storage is added
            # to ``UploadedFile`` objects as a ``_wizard_file_storage_key``
            # attribute when they're decoded. This acts as a marker to indicate
            # that the file already exists in the file storage.
            uploaded_file._wizard_file_storage_key = key
            files[name] = uploaded_file
        return decoded

    def _encode_files(self, files):
        """
        Performs the opposite conversion to ``_decode_files()``.
        """
        if files and not self._file_storage:
            raise NoFileStorageConfigured
        encoded = {}
        for name, uploadedfile in files.iteritems():
            key = getattr(uploadedfile, '_wizard_file_storage_key', None)
            if key is None:
                key = self._file_storage.save(uploadedfile.name, uploadedfile)
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
        return data

    def decode(self, data):
        """
        Performs reverse operation to ``encode()``.
        """
        self.current_step = data['current_step']
        for name, data in data['steps'].iteritems():
            self.steps[name] = self.step_class(
                    step_name, data=data['data'],
                    files=self._decode_files[data['files']])
