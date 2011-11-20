from __future__ import absolute_import, unicode_literals
from datetime import datetime
from django.core.exceptions import ValidationError
from django.db import models


class WizardState(models.Model):
    """
    This model provides the backend for the ``DatabaseStorage`` storage.

    As wizard prefixes are only unique within the context of a single user,
    either ``session_key`` or ``user`` must be provided. This is enforced via
    ``clean``, so be sure to call ``full_clean`` prior to saving.
    """
    name = models.CharField(max_length=200)
    namespace = models.CharField(max_length=200)
    session_key = models.CharField(max_length=40, blank=True)
    user = models.ForeignKey('auth.User', null=True)
    data = models.TextField(default='{"current_step":null,"steps":{}}')
    created_at = models.DateTimeField(default=datetime.now)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('name', 'namespace')

    def clean(self):
        if not (self.session_key or self.user):
            raise ValidationError('Either `session_key` or `user` must be '
                                  'provided.')
