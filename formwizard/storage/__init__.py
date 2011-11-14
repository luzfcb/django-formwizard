from __future__ import absolute_import, unicode_literals
from django.utils.importlib import import_module
from formwizard.storage.base import Storage, Step
from formwizard.storage.exceptions import (MissingStorageModule,
    MissingStorageClass, NoFileStorageConfigured)


def get_storage(path):
    module, _, attr = path.rpartition('.')
    try:
        return getattr(import_module(module), attr)
    except ImportError, e:
        raise MissingStorageModule('Error loading storage %s: "%s"'
                                   % (module, e))
    except AttributeError:
        raise MissingStorageClass('Module "%s" does not define a storage named'
                                  ' "%s"' % (module, attr))
