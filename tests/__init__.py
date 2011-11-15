# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.app.settings'

from attest import Tests
from django.test.simple import DjangoTestSuiteRunner
from .forms import tests as form_tests
from .storage import tests as storage_tests


runner = DjangoTestSuiteRunner()
runner.setup_databases()
everything = Tests((form_tests, storage_tests))


# -----------------------------------------------------------------------------


junit = Tests()

@junit.test
def make_junit_output():
    import xmlrunner
    runner = xmlrunner.XMLTestRunner(output=b"reports")
    runner.run(everything.test_suite())


# -----------------------------------------------------------------------------


pylint = Tests()

@pylint.test
def make_pylint_output():
    from os.path import expanduser
    from pylint.lint import Run
    from pylint.reporters.text import ParseableTextReporter
    if not os.path.exists('reports'):
        os.mkdir('reports')
    with open('reports/pylint.report', 'wb') as handle:
        args = ['formwizard', 'tests', 'test_project']
        Run(args, reporter=ParseableTextReporter(output=handle), exit=False)
