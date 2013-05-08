from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='cleancloud/index.html'), name="index"),
    url(r'^contact/$', TemplateView.as_view(template_name='cleancloud/contact.html'), name="contact"),
    url(r'^account/', include('registration.backends.default.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^functions/$', login_required(TemplateView.as_view(template_name='cleancloud/functions.html')), name="functions"),
)

urlpatterns += patterns('dedool_jobs.views',
    url(r'^continue/(\d*)/$', 'continue_job'),
    url(r'^job_history/$', 'job_history'),
)

urlpatterns += patterns('dedool_files.views',
    url(r'^files/$', 'files'),
)

urlpatterns += patterns('dedool_functions.views',
    url(r'^start/$', 'start'),
    url(r'^upload/(\d*)/$', 'upload'),
    url(r'^select/(\d*)/$', 'select'),
    url(r'^review/(\d*)/$', 'review'),
    url(r'^configure/(\d*)/$', 'configure'),
    url(r'^results/(\d*)/$', 'results'),
    url(r'^status/$', 'status_form'),
    url(r'^status/(\d*)/$', 'status'),
	url(r'^edit_results/(\d*)/$', 'edit_results'),
)

urlpatterns += patterns('cleancloud.ajax_views',
    url(r'^check/(\d*)/$', 'check'),
    url(r'^cancel/(\d*)/$', 'cancel'),
    url(r'^edit/(\d*)/$', 'edit'),
    url(r'^revert/(\d*)/(\d*-\d*)/$', 'revert'),
    url(r'^remove/(\d*)/$', 'remove'),
    url(r'^hide/(\d*)/$', 'hide'),
	url(r'^load/(\d*)/$', 'load_results'),
	url(r'^delete_row/(\d*)/(\d*)/$', 'delete_row'),
)

urlpatterns += patterns('dedool_profile.views',
    url(r'^account/profile/$', 'profile', name='profile'),
)
