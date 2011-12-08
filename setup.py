from setuptools import setup, find_packages


setup(
    name='django-formwizard',
    version='1.3.5',
    description='A FormWizard for Django with multiple storage backends',
    long_description=open("README.rst").read(),
    author='Bradley Ayers',
    author_email='bradley.ayers@gmail.com',
    url='http://github.com/bradleyayers/django-formwizard/',
    packages=find_packages(exclude=['tests', 'tests.*',
                                    'test_project', 'test_project.*']),
    include_package_data=True,  # declarations in MANIFEST.in

    install_requires=['Django >=1.3'],
    tests_require=['Django >=1.3', 'Attest >=0.5', 'django-attest >=0.2.2',
                   'unittest-xml-reporting'],

    test_loader='tests:loader',
    test_suite='tests.everything',

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
