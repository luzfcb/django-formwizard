from __future__ import absolute_import, unicode_literals
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.template import Context, Template
from formwizard.views import WizardView
import tempfile
from ..forms import Page1, Page2, Page3, Page4


class ContactWizard(WizardView):
    file_storage = FileSystemStorage(location=tempfile.mkdtemp())
    template_name = 'simple.html'

    def done(self, forms):
        return HttpResponse(Template('').render(Context({'forms': forms})))

    def get_context_data(self, **kwargs):
        context = super(ContactWizard, self).get_context_data(**kwargs)
        context['view'] = self
        if self.steps.current.name == 'Step 2':
            context.update({'another_var': True})
        return context


class SessionContactWizard(ContactWizard):
    storage = 'formwizard.storage.SessionStorage'
    steps = (
        ('Step 1', Page1),
        ('Step 2', Page2),
        ('Step 3', Page3),
        ('Step 4', Page4),
    )


class CookieContactWizard(ContactWizard):
    storage = 'formwizard.storage.CookieStorage'
    steps = (
        ('Step 1', Page1),
        ('Step 2', Page2),
        ('Step 3', Page3),
        ('Step 4', Page4),
    )
