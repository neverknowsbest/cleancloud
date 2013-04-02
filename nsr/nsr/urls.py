from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='cleancloud/index.html'), name="index"),
	url(r'^account/', include('registration.backends.default.urls')),
    url(r'^admin/', include(admin.site.urls)),
)

urlpatterns += patterns('cleancloud.views',
	url(r'^upload/(\d*)/$', 'upload'),
	url(r'^select/(\d*)/$', 'select'),
	url(r'^review/(\d*)/$', 'review'),
	url(r'^configure/(\d*)/$', 'configure'),
	url(r'^check/(\d*)/$', 'check'),
	url(r'^results/(\d*)/$', 'results'),
	url(r'^cancel/(\d*)/$', 'cancel'),
	url(r'^status/(\d*)/$', 'status'),	
	url(r'^edit/(\d*)/$', 'edit'),
	url(r'^revert/(\d*)/(\d*-\d*)/$', 'revert'),
	url(r'^start/$', 'start'),	
	url(r'^continue/(\d*)/$', 'continue_job'),	
	url(r'^job_history/$', 'job_history'),	
	url(r'^functions/$', 'functions'),
	url(r'^status/$', 'status_form'),
	url(r'^files/$', 'files'),
	url(r'^remove/(\d*)/$', 'remove'),
)

urlpatterns += patterns('cleancloud.views',
	url(r'^account/profile/$', 'profile'),	
	url(r'^account/edit_profile/$', 'edit_profile'),
)