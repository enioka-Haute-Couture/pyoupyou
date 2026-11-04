from django.conf import settings
from django.urls import include, path, re_path
from django.contrib import admin

from interview import views, feeds

urlpatterns = [
    re_path(r"^admin/dump_data", views.dump_data),
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("processes/", views.processes, name="process-list"),
    path("processes/closed", views.closed_processes, name="process-closed-list"),
    path("processes/source/<int:source_id>", views.processes_for_source, name="process-list-source"),
    path("processes/offer/<int:offer_id>", views.processes_for_offer, name="process-list-offer"),
    path(
        "switch_offer_subscription/<int:offer_id>/",
        views.switch_offer_subscription_ajax,
        name="switch-offer-subscription",
    ),
    path("interviews/", views.interviews_list, name="interviews-list"),
    path("candidate/", views.new_candidate, name="candidate-new"),
    path("candidate/candidate-submit/", views.submit_candidate, name="candidate-submit"),
    path(
        f"webhook/{settings.FORM_WEB_HOOK_PREFIX}/<int:subsidiary_id>/<int:source_id>",
        views.process_from_cognito_form,
        name="import-new-process-from-cognito-form",
    ),
    re_path(r"^process/(?P<process_id>\d+)(?P<slug_info>(\w-?)*)/$", views.process, name="process-details"),
    re_path(
        r"^process/(?P<pk>\d+)(?P<slug_info>(\w-?)*)/delete/$", views.ProcessDeleteView.as_view(), name="process-delete"
    ),
    path(
        "switch_process_subscription/<int:process_id>/",
        views.switch_process_subscription_ajax,
        name="switch-process-subscription",
    ),
    path("process/<int:process_id>/close/", views.close_process, name="process-close"),
    path("process/<int:process_id>/reopen/", views.reopen_process, name="process-reopen"),
    path("process/<int:process_id>/interview/", views.interview, {"action": "edit"}, name="process-new-interview"),
    path(
        "process/<int:process_id>/interview/<int:interview_id>/plan",
        views.interview,
        {"action": "plan"},
        name="interview-plan",
    ),
    path(
        "process/<int:process_id>/interview/<int:interview_id>/planning-request",
        views.interview,
        {"action": "planning-request"},
        name="interview-planning-request",
    ),
    path(
        "process/<int:process_id>/interview/<int:interview_id>/edit",
        views.interview,
        {"action": "edit"},
        name="interview-edit",
    ),
    re_path(r"^interview/(?P<interview_id>\d+)(?P<slug_info>(\w-?)*)/minute/$", views.minute, name="interview-minute"),
    path("interview/<int:interview_id>/minute/edit/", views.minute_edit, name="interview-minute-edit"),
    path("interview/<int:pk>/delete", views.InterviewDeleteView.as_view(), name="interview-delete"),
    path("delete_document_interview_minute", views.delete_document_minute_ajax, name="delete-document-minute"),
    path("reports/interviewers-load/", views.interviewers_load, name="interviewers-load"),
    path("reports/active-sources/", views.active_sources, name="active-sources"),
    path("reports/offers/", views.offers, name="offers"),
    path("reports/activity-summary/", views.activity_summary, name="activity_summary"),
    path("reports/pivotable/interviews/", views.interviews_pivotable, name="interviews-pivotable"),
    path("reports/pivotable/processes/", views.processes_pivotable, name="processes-pivotable"),
    path("candidate/<int:process_id>/", views.edit_candidate, name="candidate"),
    path("create_source/", views.create_source_ajax, name="create_source"),
    path("create_offer/", views.create_offer_ajax, name="create_offer"),
    path("create_account/", views.create_account, name="create_acount"),
    re_path(r"^delete_account/(?P<trigramme>[a-z]{3})$", views.delete_account, name="delete_acount"),
    path("feed/<path:token>/pyoupyou_full.ics", feeds.FullInterviewFeed(), name="calendar_full"),
    path(
        "feed/<path:token>/subsidiary/<int:subsidiary_id>/pyoupyou_interviews.ics",
        feeds.SubsidiaryInterviewFeed(),
        name="calendar_subsidiary",
    ),
    path(
        "feed/<path:token>/user/<int:user_id>/pyoupyou_interviews.ics",
        feeds.PyouPyouUserInterviewFeed(),
        name="calendar_user",
    ),
    path("select2/", include("django_select2.urls")),
    path("search/", views.search, name="search"),
    path("gantt/", views.gantt, name="gantt"),
    path("kanban/", views.kanban, name="kanban"),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.HAS_DDT:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
