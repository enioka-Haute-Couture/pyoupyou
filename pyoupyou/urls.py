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

from interview import views, feeds

urlpatterns = [
    url(r"^admin/", admin.site.urls),
    url(r"^admin/dump_data", views.dump_data),
    url(r"^$", views.dashboard, name="dashboard"),
    url(r"^processes/$", views.processes, name="process-list"),
    url(r"^processes/closed$", views.closed_processes, name="process-closed-list"),
    url(r"^processes/source/(?P<source_id>\d+)$", views.processes_for_source, name="process-list-source"),
    url(r"^candidate/$", views.new_candidate, name="candidate-new"),
    url(r"^import-seekube/$", views.import_seekube, name="import-seekube"),
    url(r"^process/(?P<process_id>\d+)/$", views.process, name="process-details"),
    url(r"^process/(?P<process_id>\d+)/close/$", views.close_process, name="process-close"),
    url(r"^process/(?P<process_id>\d+)/reopen/$", views.reopen_process, name="process-reopen"),
    url(r"^process/(?P<process_id>\d+)/interview/$", views.interview, {"action": "edit"}, name="process-new-interview"),
    url(
        r"^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/plan$",
        views.interview,
        {"action": "plan"},
        name="interview-plan",
    ),
    url(
        r"^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/planning-request$",
        views.interview,
        {"action": "planning-request"},
        name="interview-planning-request",
    ),
    url(
        r"^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/edit$",
        views.interview,
        {"action": "edit"},
        name="interview-edit",
    ),
    url(r"^interview/(?P<interview_id>\d+)/minute/$", views.minute, name="interview-minute"),
    url(r"^interview/(?P<interview_id>\d+)/minute/edit/$", views.minute_edit, name="interview-minute-edit"),
    url(r"^reports/interviewers-load/$", views.interviewers_load, name="interviewers-load"),
    url(
        r"^reports/interviewers-load/(?P<subsidiary_id>\d*)$",
        views.interviewers_load,
        name="interviewers-load-subdidiary",
    ),
    url(r"^reports/active-sources/$", views.active_sources, name="active-sources"),
    url(r"^reports/active-sources/(?P<subsidiary_id>\d+)$", views.active_sources, name="active-sources-subsidiary"),
    url(r"^reports/activity-summary/$", views.activity_summary, name="activity_summary"),
    url(r"^candidate/(?P<process_id>\d+)/$", views.edit_candidate, name="candidate"),
    url(r"^create_source/$", views.create_source_ajax, name="create_source"),
    url(r"^create_offer/$", views.create_offer_ajax, name="create_offer"),
    url(r"^create_account/$", views.create_account, name="create_acount"),
    url(r"^delete_account/(?P<trigramme>[a-z]{3})$", views.delete_account, name="delete_acount"),
    url(r"^feed/pyoupyou_full.ics$", feeds.InterviewFeed(), name="calendar_full"),
    url(r"^export/all_interviews.tsv$", views.export_interviews_tsv, name="export_interviews_tsv"),
    url(r"^export/all_processes.tsv$", views.export_processes_tsv, name="export_processess_tsv"),
    url(r"^select2/", include("django_select2.urls")),
    url(r"^search/", views.search, name="search"),
    url(r"^gantt/", views.gantt, name="gantt"),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.HAS_DDT:
    import debug_toolbar

    urlpatterns = [url(r"^__debug__/", include(debug_toolbar.urls))] + urlpatterns
