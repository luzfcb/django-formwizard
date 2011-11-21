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
                    'form-name': 'Pony',
                    'form-thirsty': '2',
                    'form-user': self.user.pk,
                    'mgmt-current_step': 'form1',
                },
                {
                    'form-address1': '123 Main St',
                    'form-address2': 'Djangoland',
                    'form-file1': file1,
                    'mgmt-current_step': 'form2',
                },
                {
                    'form-random_crap': 'blah blah',
                    'mgmt-current_step': 'form3',
                },
                {
                    'form-INITIAL_FORMS': '0',
                    'form-TOTAL_FORMS': '2',
                    'form-MAX_NUM_FORMS': '0',
                    'form-0-random_crap': 'blah blah',
                    'form-1-random_crap': 'blah blah',
                    'mgmt-current_step': 'form4',
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
        assert response['Location'].endswith('/form1/')

        response = self.client.get(response['Location'])
        steps = response.context['wizard']['steps']
        assert steps.current.name == 'form1'
        assert steps.index == 0
        assert steps.index0 == 0
        assert steps.index1 == 1
        assert steps.last.name == 'form4'
        assert steps.prev == None
        assert steps.next.name == 'form2'
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
        for k, v in self.datas[0].iteritems():
            if k.endswith('current_step'):
                invalid = {k: v}
                break
        url = reverse(self.url_name, kwargs={'step': 'form1'})
        response = self.client.post(url, invalid)

        assert response.status_code == 200
        assert response.context['wizard']['steps'].current.name == 'form1'
        assert response.context['wizard']['form'].errors == {
            'name': [u'This field is required.'],
            'user': [u'This field is required.']
        }

    @test
    def posting_valid_data_should_redirect_to_next_step(self):
        url = reverse(self.url_name, kwargs={'step': 'form1'})
        response = self.client.post(url, self.datas[0])
        # follow redirect
        response = self.client.get(response['Location'])
        assert response.status_code == 200

        steps = response.context['wizard']['steps']
        assert steps.current.name == 'form2'
        assert steps.index == 1
        assert steps.prev.name == 'form1'
        assert steps.next.name == 'form3'

    @test
    def should_be_able_to_step_to_specific_form(self):
        url = reverse(self.url_name, kwargs={'step': 'form1'})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context['wizard']['steps'].current.name == 'form1'

        url = reverse(self.url_name, kwargs={'step': 'form1'})
        response = self.client.post(url, self.datas[0])
        response = self.client.get(response['Location'])  # follow redirect
        assert response.status_code == 200
        assert response.context['wizard']['steps'].current.name == 'form2'

        steps = response.context['wizard']['steps']
        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, {'wizard_next_step': steps.prev.name})
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        assert response.context['wizard']['steps'].current.name == 'form1'

    @test
    def test_form_finish(self):
        url = reverse(self.url_name, kwargs={'step': 'form1'})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.context['wizard']['steps'].current.name == 'form1'
        steps = response.context['wizard']['steps']

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[0])
        response = self.client.get(response['Location'])
        steps = response.context['wizard']['steps']
        assert response.status_code == 200
        assert steps.current.name == 'form2'

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[1])
        response = self.client.get(response['Location'])
        steps = response.context['wizard']['steps']
        assert response.status_code == 200
        assert response.context['wizard']['steps'].current.name == 'form3'

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[2])
        response = self.client.get(response['Location'])
        steps = response.context['wizard']['steps']
        assert response.status_code == 200
        assert response.context['wizard']['steps'].current.name == 'form4'

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[3])
        response = self.client.get(response['Location'])
        assert response.status_code == 200

        cleaned_datas = [f.cleaned_data
                         for f in response.context['forms'].values()]

        # it's difficult to check equality of UploadedFile objects, so we'll
        # just remove it.
        cleaned_datas[1].pop('file1')

        assert cleaned_datas == [
            {
                'name': 'Pony',
                'thirsty': True,
                'user': self.user,
            },
            {
                'address1': '123 Main St',
                'address2': 'Djangoland',
            },
            {
                'random_crap': 'blah blah'
            },
            [
                {'random_crap': 'blah blah'},
                {'random_crap': 'blah blah'},
            ]
        ]

    @test
    def test_manipulated_data(self):
        url = reverse(self.url_name, kwargs={'step': 'form1'})
        response = self.client.get(url)
        assert response.status_code == 200
        steps = response.context['wizard']['steps']

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[0])
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        steps = response.context['wizard']['steps']

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[1])
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        steps = response.context['wizard']['steps']

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[2])
        response = self.client.get(response['Location'])
        assert response.status_code == 200
        steps = response.context['wizard']['steps']

        self.client.cookies.pop('sessionid', None)
        self.client.cookies.pop('tests.app.views.namedurlwizard.CookieContactWizard|default', None)

        url = reverse(self.url_name, kwargs={'step': steps.current.name})
        response = self.client.post(url, self.datas[3])  # redirects to done
        response = self.client.post(response['Location'], self.datas[3])  # redirects to step1
        assert response.status_code == 302
        assert response['Location'] == 'http://testserver' + reverse(self.url_name, kwargs={'step': steps.first.name})


class SessionTests(NamedUrlWizardTests):
    url_name = 'namedurlwizard:session'
    prefix = 'tests.app.views.namedurlwizard.SessionContactWizard|default-'


class CookieTests(NamedUrlWizardTests):
    url_name = 'namedurlwizard:cookie'
    prefix = 'tests.app.views.namedurlwizard.CookieContactWizard|default-'


tests = Tests([SessionTests(), CookieTests()])


#
#class NamedSessionWizardTests(NamedWizardTests, TestCase):
#    wizard_urlname = 'nwiz_session'
#    wizard_step_1_data = {
#        'session_contact_wizard-current_step': 'form1',
#    }
#    wizard_step_data = (
#        {
#            'form1-name': 'Pony',
#            'form1-thirsty': '2',
#            'session_contact_wizard-current_step': 'form1',
#        },
#        {
#            'form2-address1': '123 Main St',
#            'form2-address2': 'Djangoland',
#            'session_contact_wizard-current_step': 'form2',
#        },
#        {
#            'form3-random_crap': 'blah blah',
#            'session_contact_wizard-current_step': 'form3',
#        },
#        {
#            'form4-INITIAL_FORMS': '0',
#            'form4-TOTAL_FORMS': '2',
#            'form4-MAX_NUM_FORMS': '0',
#            'form4-0-random_crap': 'blah blah',
#            'form4-1-random_crap': 'blah blah',
#            'session_contact_wizard-current_step': 'form4',
#        }
#    )
#
#class NamedCookieWizardTests(NamedWizardTests, TestCase):
#    wizard_urlname = 'nwiz_cookie'
#    wizard_step_1_data = {
#        'cookie_contact_wizard-current_step': 'form1',
#    }
#    wizard_step_data = (
#        {
#            'form1-name': 'Pony',
#            'form1-thirsty': '2',
#            'cookie_contact_wizard-current_step': 'form1',
#        },
#        {
#            'form2-address1': '123 Main St',
#            'form2-address2': 'Djangoland',
#            'cookie_contact_wizard-current_step': 'form2',
#        },
#        {
#            'form3-random_crap': 'blah blah',
#            'cookie_contact_wizard-current_step': 'form3',
#        },
#        {
#            'form4-INITIAL_FORMS': '0',
#            'form4-TOTAL_FORMS': '2',
#            'form4-MAX_NUM_FORMS': '0',
#            'form4-0-random_crap': 'blah blah',
#            'form4-1-random_crap': 'blah blah',
#            'cookie_contact_wizard-current_step': 'form4',
#        }
#    )
#
#
#class NamedFormTests(object):
#    urls = 'formwizard.tests.namedwizardtests.urls'
#
#    def test_revalidation(self):
#        request = get_request()
#
#        testform = self.formwizard_class.as_view(
#            [('start', Step1), ('step2', Step2)],
#            url_name=self.wizard_urlname)
#        response, instance = testform(request, step='done')
#
#        instance.render_done(None)
#        self.assertEqual(instance.storage.current_step, 'start')
#
#class TestNamedUrlSessionFormWizard(NamedUrlSessionWizardView):
#
#    def dispatch(self, request, *args, **kwargs):
#        response = super(TestNamedUrlSessionFormWizard, self).dispatch(request, *args, **kwargs)
#        return response, self
#
#class TestNamedUrlCookieFormWizard(NamedUrlCookieWizardView):
#
#    def dispatch(self, request, *args, **kwargs):
#        response = super(TestNamedUrlCookieFormWizard, self).dispatch(request, *args, **kwargs)
#        return response, self
#
#
#class NamedSessionFormTests(NamedFormTests, TestCase):
#    formwizard_class = TestNamedUrlSessionFormWizard
#    wizard_urlname = 'nwiz_session'
#
#
#class NamedCookieFormTests(NamedFormTests, TestCase):
#    formwizard_class = TestNamedUrlCookieFormWizard
#    wizard_urlname = 'nwiz_cookie'
