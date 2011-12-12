from attest import assert_hook, Tests
from django.conf.urls.defaults import patterns
from django_attest import TestContext
from formwizard.views import WizardView
from .app.forms import Page1


class TestWizard(WizardView):
    storage = "formwizard.storage.CookieStorage"
    steps = (
        ("Page 1", Page1),
    )
    template_name = "simple.html"
    wizard_step_templates = {
        "Page 1": "custom_step.html"
    }


urlpatterns = patterns('',
    ('^test/', TestWizard.as_view()),
)


tests = Tests()
tests.context(TestContext(urls='tests.templates'))


@tests.test
def wizard_step_templates_should_be_honored(client):
    response = client.get('/test/')
    assert "custom_step.html" in  [t.name for t in response.templates]
    assert response.content == "This is an empty custom step.\n\n"
