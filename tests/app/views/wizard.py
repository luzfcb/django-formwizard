from __future__ import absolute_import, unicode_literals
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.template import Context, Template
from formwizard.views import WizardView
import tempfile
from ..forms import Page1, Page2, Page3, Page4


class ContactWizard(WizardView):
    file_storage = FileSystemStorage(location=tempfile.mkdtemp())

    def done(self, forms):
        return HttpResponse(Template('').render(Context({'forms': forms})))

    def get_context_data(self, **kwargs):
        context = super(ContactWizard, self).get_context_data(**kwargs)
        context['view'] = self
        if self.steps.current.name == 'form2':
            context.update({'another_var': True})
        return context


class SessionContactWizard(ContactWizard):
    storage_name = 'formwizard.storage.SessionStorage'
    form_list = (
        ('form1', Page1),
        ('form2', Page2),
        ('form3', Page3),
        ('form4', Page4),
    )


class CookieContactWizard(ContactWizard):
    storage_name = 'formwizard.storage.CookieStorage'
    form_list = (
        ('form1', Page1),
        ('form2', Page2),
        ('form3', Page3),
        ('form4', Page4),
    )
