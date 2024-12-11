from django.conf import settings
from django.urls import re_path, include
from django.contrib import admin

from interview import views, feeds

urlpatterns = [
    re_path(r"^admin/dump_data", views.dump_data),
    re_path(r"^admin/", admin.site.urls),
    re_path(r"^$", views.dashboard, name="dashboard"),
    re_path(r"^processes/$", views.processes, name="process-list"),
    re_path(r"^processes/closed$", views.closed_processes, name="process-closed-list"),
    re_path(r"^processes/source/(?P<source_id>\d+)$", views.processes_for_source, name="process-list-source"),
    re_path(r"^processes/offer/(?P<offer_id>\d+)$", views.processes_for_offer, name="process-list-offer"),
    re_path(
        r"^switch_offer_subscription/(?P<offer_id>\d+)/$",
        views.switch_offer_subscription_ajax,
        name="switch-offer-subscription",
    ),
    re_path(r"^interviews/$", views.interviews_list, name="interviews-list"),
    re_path(r"^candidate/$", views.new_candidate, name="candidate-new"),
    re_path(
        r"^webhook/" + settings.FORM_WEB_HOOK_PREFIX + r"/(?P<subsidiary_id>\d+)/(?P<source_id>\d+)$",
        views.process_from_cognito_form,
        name="import-new-process-from-cognito-form",
    ),
    re_path(r"^process/(?P<process_id>\d+)(?P<slug_info>(\w-?)*)/$", views.process, name="process-details"),
    re_path(
        r"^switch_process_subscription/(?P<process_id>\d+)/$",
        views.switch_process_subscription_ajax,
        name="switch-process-subscription",
    ),
    re_path(r"^process/(?P<process_id>\d+)/close/$", views.close_process, name="process-close"),
    re_path(r"^process/(?P<process_id>\d+)/reopen/$", views.reopen_process, name="process-reopen"),
    re_path(
        r"^process/(?P<process_id>\d+)/interview/$", views.interview, {"action": "edit"}, name="process-new-interview"
    ),
    re_path(
        r"^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/plan$",
        views.interview,
        {"action": "plan"},
        name="interview-plan",
    ),
    re_path(
        r"^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/planning-request$",
        views.interview,
        {"action": "planning-request"},
        name="interview-planning-request",
    ),
    re_path(
        r"^process/(?P<process_id>\d+)/interview/(?P<interview_id>\d+)/edit$",
        views.interview,
        {"action": "edit"},
        name="interview-edit",
    ),
    re_path(r"^interview/(?P<interview_id>\d+)(?P<slug_info>(\w-?)*)/minute/$", views.minute, name="interview-minute"),
    re_path(r"^interview/(?P<interview_id>\d+)/minute/edit/$", views.minute_edit, name="interview-minute-edit"),
    re_path(
        r"^delete_document_interview_minute$",
        views.delete_document_minute_ajax,
        name="delete-document-minute",
    ),
    re_path(r"^reports/interviewers-load/$", views.interviewers_load, name="interviewers-load"),
    re_path(r"^reports/active-sources/$", views.active_sources, name="active-sources"),
    re_path(r"^reports/offers/$", views.offers, name="offers"),
    re_path(r"^reports/activity-summary/$", views.activity_summary, name="activity_summary"),
    re_path(r"^reports/pivotable/interviews/$", views.interviews_pivotable, name="interviews-pivotable"),
    re_path(r"^reports/pivotable/processes/$", views.processes_pivotable, name="processes-pivotable"),
    re_path(r"^candidate/(?P<process_id>\d+)/$", views.edit_candidate, name="candidate"),
    re_path(r"^candidate-reuse/(?P<candidate_id>\d+)/$", views.reuse_candidate, name="reuse_candidate"),
    re_path(r"^create_source/$", views.create_source_ajax, name="create_source"),
    re_path(r"^create_offer/$", views.create_offer_ajax, name="create_offer"),
    re_path(r"^create_account/$", views.create_account, name="create_acount"),
    re_path(r"^delete_account/(?P<trigramme>[a-z]{3})$", views.delete_account, name="delete_acount"),
    re_path(r"^feed/(?P<token>.+)/pyoupyou_full.ics$", feeds.FullInterviewFeed(), name="calendar_full"),
    re_path(
        r"^feed/(?P<token>.+)/subsidiary/(?P<subsidiary_id>\d+)/pyoupyou_interviews.ics$",
        feeds.SubsidiaryInterviewFeed(),
        name="calendar_subsidiary",
    ),
    re_path(
        r"^feed/(?P<token>.+)/user/(?P<user_id>\d+)/pyoupyou_interviews.ics$",
        feeds.PyouPyouUserInterviewFeed(),
        name="calendar_user",
    ),
    re_path(r"^select2/", include("django_select2.urls")),
    re_path(r"^search/", views.search, name="search"),
    re_path(r"^gantt/", views.gantt, name="gantt"),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.HAS_DDT:
    import debug_toolbar

    urlpatterns = [re_path(r"^__debug__/", include(debug_toolbar.urls))] + urlpatterns
