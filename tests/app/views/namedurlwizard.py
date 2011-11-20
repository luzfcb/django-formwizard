from __future__ import absolute_import, unicode_literals
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.template import Context, Template
from formwizard.views import NamedUrlWizardView
import tempfile
from ..forms import Page1, Page2, Page3, Page4


class ContactWizard(NamedUrlWizardView):
    file_storage = FileSystemStorage(location=tempfile.mkdtemp())
    wizard_done_step_name = 'done'
    form_list = (
        ('form1', Page1),
        ('form2', Page2),
        ('form3', Page3),
        ('form4', Page4),
    )

    def done(self, forms):
        return HttpResponse(Template('').render(Context({'forms': forms})))


class SessionContactWizard(ContactWizard):
    storage_name = 'formwizard.storage.session.SessionStorage'
    wizard_url_name = 'namedurlwizard:session'


class CookieContactWizard(ContactWizard):
    storage_name = 'formwizard.storage.cookie.CookieStorage'
    wizard_url_name = 'namedurlwizard:cookie'
