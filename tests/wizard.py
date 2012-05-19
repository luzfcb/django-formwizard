# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals, with_statement
from attest import Assert, Tests, TestBase, test
from contextlib import contextmanager
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from django_attest import TestContext
from formwizard.views import WizardView
from .app.forms import Page1


class WizardTests(TestBase):
    url_name = None  # defined by subclasses

    def __context__(self):
        manager = contextmanager(TestContext())
        with manager() as client:
            self.client = client
            file1 = open(__file__, 'rb')
            self.user = User.objects.create(username='brad')
            self.datas = (
                {
                    'form-0-name': 'Pony',
                    'form-0-thirsty': '2',
                    'form-0-user': self.user.pk,
                    'form-1-0-name': 'Bradley Ayers',
                    'form-1-0-message': 'Two forms on a single step is good.',
                    'form-1-1-name': 'Sunny Phung',
                    'form-1-1-message': 'I agree.',
                    'form-1-INITIAL_FORMS': '0',
                    'form-1-TOTAL_FORMS': '2',
                    'form-1-MAX_NUM_FORMS': '0',
                    'mgmt-current_step': 'Step 1',
                },
                {
                    'form-0-address1': '123 Main St',
                    'form-0-address2': 'Djangoland',
                    'form-0-file1': file1,
                    'mgmt-current_step': 'Step 2',
                },
                {
                    'form-0-random_crap': 'blah blah',
                    'mgmt-current_step': 'Step 3',
                },
                {
                    'form-0-INITIAL_FORMS': '0',
                    'form-0-TOTAL_FORMS': '2',
                    'form-0-MAX_NUM_FORMS': '0',
                    'form-0-0-random_crap': 'blah blah',
                    'form-0-1-random_crap': 'blah blah',
                    'mgmt-current_step': 'Step 4',
                }
            )
            try:
                yield
            finally:
                file1.close()

    @property
    def url(self):
        return reverse(self.url_name)

    @test
    def initial_request_should_work(self):
        response = self.client.get(self.url)
        assert response.status_code == 200

        steps = response.context['wizard'].steps
        assert steps.current.name == 'Step 1'
        assert steps.index == 0
        assert steps.index0 == 0
        assert steps.index1 == 1
        assert steps.last.name == 'Step 4'
        assert steps.previous == None
        assert steps.next.name == 'Step 2'
        assert steps.count == 4

    @test
    def posting_incomplete_data_should_return_form_errors(self):
        # create new data using 'current step'
        data = {}
        for key, value in self.datas[0].iteritems():
            if key.startswith('mgmt-') or key.endswith('_FORMS'):
                data[key] = value
        response = self.client.post(self.url, data)
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'
        (page1, comments) = response.context['wizard'].forms
        assert page1.errors == {
            'name': [u'This field is required.'],
            'user': [u'This field is required.']
        }

    @test
    def posting_correct_data_should_render_next_step(self):
        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200

        steps = response.context['wizard'].steps
        assert steps.current.name == 'Step 2'
        assert steps.index0 == 1
        assert steps.previous.name == 'Step 1'
        assert steps.next.name == 'Step 3'

    @test
    def should_allow_jumping_between_steps(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'

        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 2'

        response = self.client.post(self.url, {
            'wizard_next_step': response.context['wizard'].steps.previous.name
        })
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'

    @test
    def should_have_extra_template_context_in_subclass(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'
        assert response.context['is_step_2'] == False

        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 2'
        assert response.context['is_step_2'] == True

    @test
    def test_cleaned_forms_from_completed_wizard(self):
        response = self.client.get(self.url)
        assert response.status_code == 200

        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200
        assert response.context['view'].steps.current.name == 'Step 2'

        response = self.client.post(self.url, self.datas[1])
        assert response.status_code == 200
        assert response.context['view'].steps.current.name == 'Step 3'

        response = self.client.post(self.url, self.datas[2])
        assert response.status_code == 200
        assert response.context['view'].steps.current.name == 'Step 4'

        response = self.client.post(self.url, self.datas[3])
        assert response.status_code == 200

        forms = response.context['forms']
        with open(__file__, 'rb') as handle:
            expected = forms['Step 2'][0].cleaned_data['file1'].read()
            actual = handle.read()
            assert expected == actual

        cleaned_datas = []
        for fs in forms.itervalues():
            cleaned_datas.append([f.cleaned_data for f in fs])
        del cleaned_datas[1][0]['file1']

        assert cleaned_datas == [
            [
                {'name': 'Pony', 'thirsty': True, 'user': self.user},
                [
                    {'name': 'Bradley Ayers', 'message': 'Two forms on a single step is good.'},
                    {'name': 'Sunny Phung', 'message': 'I agree.'},
                ]
            ],
            [
                {'address1': '123 Main St', 'address2': 'Djangoland'}
            ],
            [
                {'random_crap': 'blah blah'}
            ],
            [
                [{'random_crap': 'blah blah'}, {'random_crap': 'blah blah'}],
            ],
        ]

    @test
    def clearing_data_should_revert_to_step1(self):
        response = self.client.get(self.url)
        assert response.status_code == 200

        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200

        response = self.client.post(self.url, self.datas[1])
        assert response.status_code == 200

        response = self.client.post(self.url, self.datas[2])
        assert response.status_code == 200

        # Since this test case is subclassed, we might might be using cookie
        # storage or session storage, either way invalidate both.
        self.client.cookies.pop('sessionid', None)
        self.client.cookies.pop('tests.app.views.wizard.CookieContactWizard|default', None)

        response = self.client.post(self.url, self.datas[3])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'


    @test
    def resubmitting_a_form_shouldnt_break_things(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'

        # post correct data, should proceed to step 2
        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 2'

        # post same data, this is essentially a 'browser refresh'
        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 2'

        # post valid data for the second step
        response = self.client.post(self.url, self.datas[1])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 3'

        response = self.client.post(self.url, self.datas[2])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 4'

        response = self.client.post(self.url, self.datas[0])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 2'

        response = self.client.post(self.url, self.datas[3])
        assert response.status_code == 200


class SessionTests(WizardTests):
    url_name = 'wizard:session'
    prefix = 'tests.app.views.wizard.SessionContactWizard|default-'


class CookieTests(WizardTests):
    url_name = 'wizard:cookie'
    prefix = 'tests.app.views.wizard.CookieContactWizard|default-'


tests = Tests([SessionTests(), CookieTests()])


@tests.test
def missing_storage_class_should_raise_improperly_configured():
    class TestWizard(WizardView):  # pylint: ignore=W0223
        steps = (
            ("Page 1", Page1),
        )

    factory = RequestFactory()
    view = TestWizard.as_view()
    with Assert.raises(ImproperlyConfigured):
        view(factory.get('/'))
