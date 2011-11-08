from os.path import abspath, dirname, join
from setuptools import setup, find_packages


def read(path):
    return open(join(dirname(abspath(__file__)), path)).read()


setup(
    name='django-formwizard',
    version='1.1.dev',
    description='A FormWizard for Django with multiple storage backends',
    long_description=read("README.rst"),
    author='Stephan Jaekel',
    author_email='steph@rdev.info',
    url='http://github.com/stephrdev/django-formwizard/',
    packages=find_packages(exclude=['test_project', 'test_project.*']),
    include_package_data=True,  # declarations in MANIFEST.in

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
    zip_safe=False,
)
