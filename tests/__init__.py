# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.app.settings'

from attest import Tests
from django.test.simple import DjangoTestSuiteRunner
from .forms import tests as form_tests
from .backends import tests as backend_tests


runner = DjangoTestSuiteRunner()
runner.setup_databases()
everything = Tests([backend_tests, form_tests])


# -----------------------------------------------------------------------------


junit = Tests()

@junit.test
def make_junit_output():
    import xmlrunner
    xmlrunner.XMLTestRunner(output='reports').run(everything.test_suite())


# -----------------------------------------------------------------------------


pylint = Tests()

@pylint.test
def make_pylint_output():
    from os.path import expanduser
    from pylint.lint import Run
    from pylint.reporters.text import ParseableTextReporter
    with open('reports/pylint.txt', 'wb') as handle:
        args = os.environ['PACKAGES'].split()
        Run(args, reporter=ParseableTextReporter(output=handle), exit=False)
