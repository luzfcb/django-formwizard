from django.conf.urls.defaults import include, patterns, url
from .views import namedurlwizard, wizard


wizard_patterns = patterns('',
    url(r'^session/$', wizard.SessionContactWizard.as_view(), name='session'),
    url(r'^cookie/$',  wizard.CookieContactWizard.as_view(),  name='cookie'),
)

namedurlwizard_patterns = patterns('',
    url(r'^session/$',              namedurlwizard.SessionContactWizard.as_view(), name='session'),
    url(r'^session/(?P<step>.+)/$', namedurlwizard.SessionContactWizard.as_view(), name='session'),
    url(r'^cookie/$',               namedurlwizard.CookieContactWizard.as_view(),  name='cookie'),
    url(r'^cookie/(?P<step>.+)/$',  namedurlwizard.CookieContactWizard.as_view(),  name='cookie'),
)

urlpatterns = patterns('',
    (r'namedurlwizard/', include(namedurlwizard_patterns, namespace='namedurlwizard')),
    (r'wizard/',         include(wizard_patterns,         namespace='wizard')),
)
