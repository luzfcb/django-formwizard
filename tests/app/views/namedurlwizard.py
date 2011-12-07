from __future__ import absolute_import, unicode_literals
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.template import Context, Template
from formwizard.views import NamedUrlWizardView
import tempfile
from ..forms import Page1, Page1Comments, Page2, Page3, Page4


class ContactWizard(NamedUrlWizardView):
    file_storage = FileSystemStorage(location=tempfile.mkdtemp())
    steps = (
        ('Step 1', (Page1, Page1Comments)),
        ('Step 2', Page2),
        ('Step 3', Page3),
        ('Step 4', Page4),
    )
    template_name = 'simple.html'

    def done(self, forms):
        return HttpResponse(Template('').render(Context({'forms': forms})))


class SessionContactWizard(ContactWizard):
    storage = 'formwizard.storage.session.SessionStorage'


class CookieContactWizard(ContactWizard):
    storage = 'formwizard.storage.cookie.CookieStorage'
