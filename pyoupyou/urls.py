"""pyoupyou URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url, include
from django.contrib import admin

from interview import views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', views.dashboard, name="dashboard"),
    url(r'^processes/$', views.processes, name="process-list"),
    url(r'^processes/closed$', views.closed_processes, name="process-closed-list"),
    url(r'^candidate/$', views.new_candidate, name="candidate-new"),
    url(r'^process/(?P<process_id>\d+)/$', views.process, name="process-details"),
    url(r'^process/(?P<process_id>\d+)/close/$', views.close_process, name="process-close"),
    url(r'^process/(?P<process_id>\d+)/reopen/$', views.reopen_process, name="process-reopen"),
    url(r'^process/(?P<process_id>\d+)/interview/$', views.interview, {"action":"edit"}, name="process-new-interview"),
    url(r'^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/plan$', views.interview, {"action":"plan"}, name="interview-plan"),
    url(r'^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/edit$', views.interview, {"action":"edit"}, name="interview-edit"),
    url(r'^interview/(?P<interview_id>\d+)/minute/$', views.minute, name="interview-minute"),
    url(r'^candidate/(?P<candidate_id>\d+)/$', views.edit_candidate, name="candidate"),
    url(r'^create_source/$', views.create_source_ajax, name="create_source"),
    url(r'^select2/', include('django_select2.urls')),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.HAS_DDT:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
