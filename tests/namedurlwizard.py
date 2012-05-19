# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals, with_statement
from attest import Tests, TestBase, test
from contextlib import contextmanager
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import QueryDict
from django_attest import TestContext


class NamedUrlWizardTests(TestBase):
    url_name = None  # defined by subclasses
    prefix = None  # defined by subclasses

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
        response = self.client.get(self.url, follow=False)
        assert response.status_code == 302
        assert response['Location'].endswith('/step-1/')

        response = self.client.get(response['Location'])
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
    def initial_redirect_should_preserve_querystring(self):
        querystring = {'getvar1': 'getval1', 'getvar2': 'getval2'}
        response = self.client.get(self.url, querystring)
        assert response.status_code == 302

        # Test for proper redirect GET parameters
        location = response['Location']
        assert location.find('?') != -1
        querydict = QueryDict(location[location.find('?') + 1:])
        assert dict(querydict.items()) == querystring

    @test
    def posting_invalid_form_data_should_render_errors(self):
        # create new data using 'current step'
        data = {}
        for key, value in self.datas[0].iteritems():
            if key.startswith('mgmt-') or key.endswith('_FORMS'):
                data[key] = value
        url = reverse(self.url_name, kwargs={'slug': 'step-1'})
        response = self.client.post(url, data)

        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'
        (page1, comments) = response.context['wizard'].forms
        assert page1.errors == {
            'name': [u'This field is required.'],
            'user': [u'This field is required.']
        }

    @test
    def posting_valid_data_should_redirect_to_next_step(self):
        url = reverse(self.url_name, kwargs={'slug': 'step-1'})
        response = self.client.post(url, self.datas[0])
        # follow redirect
        response = self.client.get(response['Location'])
        assert response.status_code == 200

        steps = response.context['wizard'].steps
        assert steps.current.name == 'Step 2'
        assert steps.index == 1
        assert steps.previous.name == 'Step 1'
        assert steps.next.name == 'Step 3'

    @test
    def should_be_able_to_step_to_specific_form(self):
        url = reverse(self.url_name, kwargs={'slug': 'step-1'})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'

        url = reverse(self.url_name, kwargs={'slug': 'step-1'})
        response = self.client.post(url, self.datas[0])
        response = self.client.get(response['Location'])  # follow redirect
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 2'

        steps = response.context['wizard'].steps
        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, {'wizard_next_step': steps.previous.name})
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'

    @test
    def test_form_finish(self):
        url = reverse(self.url_name, kwargs={'slug': 'step-1'})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 1'
        steps = response.context['wizard'].steps

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[0])
        response = self.client.get(response['Location'])
        steps = response.context['wizard'].steps
        assert response.status_code == 200
        assert steps.current.name == 'Step 2'

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[1])
        response = self.client.get(response['Location'])
        steps = response.context['wizard'].steps
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 3'

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[2])
        response = self.client.get(response['Location'])
        steps = response.context['wizard'].steps
        assert response.status_code == 200
        assert response.context['wizard'].steps.current.name == 'Step 4'

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[3])
        response = self.client.get(response['Location'])

        assert response.status_code == 200

        cleaned_datas = []
        for fs in response.context['forms'].itervalues():
            cleaned_datas.append([f.cleaned_data for f in fs])
        # it's difficult to check equality of UploadedFile objects, so we'll
        # just remove it.
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
    def test_manipulated_data(self):
        url = reverse(self.url_name, kwargs={'slug': 'step-1'})
        response = self.client.get(url)
        assert response.status_code == 200
        steps = response.context['wizard'].steps

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[0])
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        steps = response.context['wizard'].steps

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[1])
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        steps = response.context['wizard'].steps

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[2])
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        steps = response.context['wizard'].steps

        self.client.cookies.pop('sessionid', None)
        self.client.cookies.pop('tests.app.views.namedurlwizard.CookieContactWizard|default', None)

        url = reverse(self.url_name, kwargs={'slug': steps.current.slug})
        response = self.client.post(url, self.datas[3])  # redirects to done
        response = self.client.post(response['Location'], self.datas[3])  # redirects to step1
        assert response.status_code == 302
        assert response['Location'] == 'http://testserver' + reverse(self.url_name, kwargs={'slug': steps.first.slug})


class SessionTests(NamedUrlWizardTests):
    url_name = 'namedurlwizard:session'
    prefix = 'tests.app.views.namedurlwizard.SessionContactWizard|default-'


class CookieTests(NamedUrlWizardTests):
    url_name = 'namedurlwizard:cookie'
    prefix = 'tests.app.views.namedurlwizard.CookieContactWizard|default-'


tests = Tests([SessionTests(), CookieTests()])
