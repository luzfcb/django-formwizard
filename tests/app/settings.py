DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS = [
    'django.contrib.sessions',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'tests.app',
    'formwizard',
]

SECRET_KEY = 'abcdefghiljklmnopqrstuvwxyz'

ROOT_URLCONF = 'tests.app.urls'
