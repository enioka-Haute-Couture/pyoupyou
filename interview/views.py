# -*- coding: utf-8 -*-
import datetime
import calendar
import io
from collections import defaultdict
import json

from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.admin.options import get_content_type_for_model
from django.contrib.auth.views import redirect_to_login
from plotly.offline import plot
import plotly.figure_factory as ff
import plotly.express as px

import pandas as pd

import django_tables2 as tables
import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.core.management import call_command
from django.db import transaction
from django.db.models import Q, Prefetch, F, Max
from django.db.models.functions import Trunc
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseNotFound, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware, now
from django.utils.html import format_html
from django.utils.translation import gettext as _t
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_tables2 import RequestConfig
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.dateparse import parse_date
from django.db.models import Count
from rest_framework.decorators import api_view

from interview.decorators import privilege_level_check
from interview.filters import (
    ProcessFilter,
    ProcessSummaryFilter,
    InterviewSummaryFilter,
    InterviewListFilter,
    ActiveSourcesFilter,
)
from interview.forms import (
    ProcessCandidateForm,
    InterviewMinuteForm,
    ProcessForm,
    InterviewFormPlan,
    InterviewFormEditInterviewers,
    SourceForm,
    CloseForm,
    OfferForm,
    InterviewersForm,
)
from interview.serializers import CognitoWebHookSerializer
from interview.models import Process, Document, Interview, Sources, SourcesCategory, Candidate, Offer, DocumentInterview
from ref.filters import SubsidiaryFilter
from ref.models import Consultant, PyouPyouUser, Subsidiary

import datetime
from django import template

register = template.Library()


def get_global_filter(request):
    """
    returns a SubsidiaryFilter based on current session's filter
    to access subsidiary: f.form.cleaned_data["subsidiary"]
    """
    f = SubsidiaryFilter(request.session, queryset=Subsidiary.objects.all())
    f.is_valid()
    return f


def log_action(added, object, user, view):
    LogEntry.objects.log_action(
        user_id=user.pk,
        content_type_id=get_content_type_for_model(object).pk,
        object_id=object.pk,
        object_repr=str(object),
        action_flag=ADDITION if added else CHANGE,
        change_message=f"{object} has been Added through {view.__name__}"
        if added
        else f"{object} has been updated through {view.__name__}",
    )


@register.simple_tag
def compare(candidate: Candidate, other: Candidate):
    return candidate.compare(other)


class ProcessTable(tables.Table):
    state = tables.Column(verbose_name=_("Process state"))
    needs_attention = tables.TemplateColumn(
        template_name="interview/tables/needs_attention_cell.html", verbose_name="", orderable=False
    )
    actions = tables.TemplateColumn(
        verbose_name="", orderable=False, template_name="interview/tables/process_actions.html"
    )
    candidate = tables.Column(attrs={"td": {"style": "font-weight: bold"}}, order_by=("candidate__name",))
    contract_type = tables.Column(order_by=("contract_type__name",))
    current_rank = tables.Column(verbose_name=_("No itw"), orderable=False)

    responsible = tables.Column(verbose_name=_("Responsible"), orderable=False)

    def render_responsible(self, value):
        return format_html(
            ", ".join(
                [
                    '<span title="{fullname}">{trigramme}</span>'.format(
                        fullname=c.user.full_name, trigramme=c.user.trigramme
                    )
                    for c in value.all()
                ]
            )
        )

    class Meta:
        model = Process
        template_name = "interview/_tables.html"
        attrs = {"class": "table table-striped table-condensed"}
        sequence = (
            "needs_attention",
            "current_rank",
            "candidate",
            "subsidiary",
            "start_date",
            "contract_type",
            "state",
            "responsible",
            "actions",
        )
        fields = sequence
        order_by = "start_date"
        empty_text = _("No data")
        row_attrs = {"class": lambda record: "danger" if record.needs_attention else None}


class ProcessEndTable(ProcessTable):
    class Meta(ProcessTable.Meta):
        sequence = (
            "needs_attention",
            "current_rank",
            "candidate",
            "subsidiary",
            "start_date",
            "end_date",
            "contract_type",
            "state",
            "actions",
        )
        fields = sequence

        order_by = "-end_date"


class ProcessLightTable(ProcessTable):
    class Meta(ProcessTable.Meta):
        sequence = ("subsidiary", "offer", "state", "actions")
        fields = sequence
        exclude = ("needs_attention", "current_rank", "candidate", "responsible", "start_date", "contract_type")


class InterviewTable(tables.Table):
    # rank = tables.Column(verbose_name='#')
    interviewers = tables.TemplateColumn(
        verbose_name=_("interviewers"), orderable=False, template_name="interview/tables/interview_interviewers.html"
    )
    planned_date = tables.TemplateColumn(
        verbose_name=_("Planned date"), orderable=False, template_name="interview/tables/interview_planned_date.html"
    )
    actions = tables.TemplateColumn(
        verbose_name=_("Minute"), orderable=False, template_name="interview/tables/interview_actions.html"
    )
    needs_attention = tables.TemplateColumn(
        template_name="interview/tables/needs_attention_cell.html", verbose_name="", orderable=False
    )
    state = tables.TemplateColumn(template_name="interview/tables/interview_state.html", orderable=False)

    kind_of_interview = tables.Column(verbose_name=_("Kind of interview"), orderable=False)

    class Meta:
        model = Interview
        template_name = "interview/_tables.html"
        attrs = {"class": "table table-striped table-condensed"}
        sequence = ("needs_attention", "interviewers", "planned_date", "state", "kind_of_interview", "actions")
        fields = sequence
        order_by = "id"
        empty_text = _("No data")
        row_attrs = {
            "class": lambda record: "danger" if record.needs_attention else None,
            "style": lambda record: "background-color: #e7cbf5;" if record.prequalification else None,
        }


class InterviewDetailTable(InterviewTable):
    process_detail = tables.TemplateColumn(
        verbose_name=_("Candidate"), orderable=False, template_name="interview/tables/interview_process.html"
    )
    rank = tables.Column(verbose_name=_("No itw"))

    class Meta(InterviewTable.Meta):
        sequence = (
            "rank",
            "needs_attention",
            "process.subsidiary",
            "process_detail",
            "interviewers",
            "planned_date",
            "state",
            "process.offer",
            "kind_of_interview",
        )
        fields = sequence
        per_page = 50

        order_by = "-planned_date"


@login_required
@require_http_methods(["GET"])
def process(request, process_id, slug_info=None):
    try:
        process = (
            Process.objects.for_user(request.user)
            .select_related("candidate", "contract_type", "sources__category", "subsidiary")
            .prefetch_related("candidate__document_set")
            .get(id=process_id)
        )
    except Process.DoesNotExist:
        return HttpResponseNotFound()
    interviews = (
        Interview.objects.filter(process=process)
        .select_related("process__candidate")
        .prefetch_related("interviewers__user")
    )
    interviews_for_process_table = InterviewTable(interviews)
    RequestConfig(request).configure(interviews_for_process_table)
    close_form = CloseForm(instance=process)
    others_process = (
        Process.objects.filter(candidate=process.candidate).exclude(id=process_id).select_related("subsidiary", "offer")
    )

    goal = None
    last_itw = interviews.last()
    if process.state not in Process.CLOSED_STATE_VALUES and len(interviews) > 0:
        if last_itw.next_interview_goal:
            goal = last_itw.next_interview_goal
        elif last_itw.goal:
            goal = last_itw.goal

    documents = process.candidate.document_set.all()
    context = {
        "process": process,
        "documents": documents,
        "interviews_for_process_table": interviews_for_process_table,
        "interviews": interviews,
        "close_form": close_form,
        "goal": goal,
        "subsidiaries": Subsidiary.objects.all(),
        "others_process": ProcessLightTable(others_process),
    }
    return render(request, "interview/process_detail.html", context)


@login_required
@require_http_methods(["POST"])
def switch_offer_subscription_ajax(request, offer_id):
    offer = None
    try:
        if offer_id is None:
            raise Offer.DoesNotExist
        offer = Offer.objects.get(id=offer_id)
    except Offer.DoesNotExist:
        return HttpResponseNotFound()

    if request.user in offer.subscribers.all():
        offer.subscribers.remove(request.user)
        return render(request, "interview/subscribe_button_offer.html", {})

    offer.subscribers.add(request.user)
    return render(request, "interview/unsubscribe_button_offer.html", {})


@login_required
@require_http_methods(["POST"])
def switch_process_subscription_ajax(request, process_id):
    p = None
    try:
        if process_id is None:
            raise Process.DoesNotExist
        p = Process.objects.get(id=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()

    if request.user in p.subscribers.all():
        p.subscribers.remove(request.user)
        return render(request, "interview/subscribe_button_process.html", {})

    p.subscribers.add(request.user)
    return render(request, "interview/unsubscribe_button_process.html", {})


@login_required
@require_http_methods(["POST"])
@privilege_level_check(
    authorised_level=[
        Consultant.PrivilegeLevel.ALL,
        Consultant.PrivilegeLevel.EXTERNAL_RPO,
    ]
)
def close_process(request, process_id):
    try:
        process = Process.objects.for_user(request.user).get(pk=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()

    form = CloseForm(request.POST, instance=process)
    if form.is_valid():
        if form.instance.state != Process.JOB_OFFER:
            form.instance.end_date = timezone.now()
        form.save()
        log_action(False, process, request.user, close_process)
    # TODO manage errors
    return HttpResponseRedirect(process.get_absolute_url())


@login_required
@require_http_methods(["GET"])
@privilege_level_check(
    authorised_level=[
        Consultant.PrivilegeLevel.ALL,
        Consultant.PrivilegeLevel.EXTERNAL_RPO,
    ]
)
def reopen_process(request, process_id):
    try:
        process = Process.objects.for_user(request.user).get(pk=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()

    process.end_date = None
    process.state = Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
    process.closed_comment = ""
    process.save()
    log_action(False, process, request.user, reopen_process)
    return HttpResponseRedirect(process.get_absolute_url())


@login_required
@require_http_methods(["GET"])
def closed_processes(request):
    subsidiary_filter = get_global_filter(request)

    closed_processes = subsidiary_filter.filter_queryset(
        Process.objects.for_table(request.user).filter(end_date__isnull=False)
    )

    closed_processes_table = ProcessEndTable(closed_processes, prefix="c")

    config = RequestConfig(request)
    config.configure(closed_processes_table)

    context = {
        "title": _("Closed processes"),
        "table": closed_processes_table,
        "subsidiaries": Subsidiary.objects.all(),
    }

    return render(request, "interview/single_table.html", context)


@login_required
@require_http_methods(["GET"])
def processes_for_source(request, source_id):
    if request.user.consultant.is_external and request.user.consultant.limited_to_source.id != source_id:
        return redirect_to_login(next=request.path)

    # override table's default sort by setting custom sort in request
    get_req = request.GET.copy()
    get_req.setdefault("csort", "-start_date")
    request.GET = get_req

    subsidiary_filter = get_global_filter(request)
    try:
        source = Sources.objects.get(id=source_id)
    except Sources.DoesNotExist:
        return HttpResponseNotFound()

    processes = subsidiary_filter.filter_queryset(Process.objects.for_table(request.user).filter(sources_id=source_id))
    processes_table = ProcessEndTable(processes, prefix="c")

    config = RequestConfig(request)
    config.configure(processes_table)

    context = {
        "title": source.name + " (" + source.category.name + ")",
        "table": processes_table,
        "subsidiaries": Subsidiary.objects.all(),
    }

    return render(request, "interview/single_table.html", context)


@login_required
@require_http_methods(["GET"])
@user_passes_test(lambda u: not u.consultant.is_external)
def processes_for_offer(request, offer_id):
    subsidiary_filter = get_global_filter(request)
    try:
        offer = Offer.objects.get(id=offer_id)
    except Offer.DoesNotExist:
        return HttpResponseNotFound()

    processes = subsidiary_filter.filter_queryset(Process.objects.for_table(request.user).filter(offer_id=offer_id))
    processes_table = ProcessEndTable(processes, prefix="c")

    config = RequestConfig(request)
    config.configure(processes_table)

    context = {
        "title": offer.name + " (" + offer.subsidiary.name + ")",
        "table": processes_table,
        "subsidiaries": Subsidiary.objects.all(),
        "subscribed_object": offer,
        "subscription_url": f"/switch_offer_subscription/{offer.id}/",
        "subscribe_button_template": "interview/subscribe_button_offer.html",
        "unsubscribe_button_template": "interview/unsubscribe_button_offer.html",
    }

    return render(request, "interview/single_table_subscribe_button.html", context)


@login_required
@require_http_methods(["GET"])
def processes(request):
    subsidiary_filter = get_global_filter(request)

    open_processes = subsidiary_filter.filter_queryset(
        Process.objects.for_table(request.user).filter(end_date__isnull=True)
    )
    a_week_ago = timezone.now() - datetime.timedelta(days=7)
    recently_closed_processes = subsidiary_filter.filter_queryset(
        Process.objects.for_table(request.user).filter(end_date__gte=a_week_ago)
    )

    open_processes_table = ProcessTable(open_processes, prefix="o")
    recently_closed_processes_table = ProcessEndTable(recently_closed_processes, prefix="c")

    config = RequestConfig(request)
    config.configure(open_processes_table)
    config.configure(recently_closed_processes_table)

    context = {
        "open_processes_table": open_processes_table,
        "recently_closed_processes_table": recently_closed_processes_table,
        "subsidiaries": Subsidiary.objects.all(),
    }
    return render(request, "interview/list_processes.html", context)


@require_http_methods(["POST"])
@privilege_level_check(
    authorised_level=[
        Consultant.PrivilegeLevel.ALL,
        Consultant.PrivilegeLevel.EXTERNAL_RPO,
        Consultant.PrivilegeLevel.EXTERNAL_FULL,
    ]
)
def reuse_candidate(request, candidate_id):
    return new_candidate(request, candidate_id)


def new_candidate_POST_handler(
    request,
    candidate_form,
    process_form,
    interviewers_form,
    past_candidate_id=None,
):
    duplicate_processes = None
    duplicates = None

    # reusing already existing candidate
    if past_candidate_id:
        candidate_form = ProcessCandidateForm(instance=Candidate.objects.get(id=past_candidate_id))
        candidate_form.full_clean()  # already valid form

    candidate = candidate_form.save(commit=False)

    # check for duplicates unless it has already been processed (re-used or ignored)
    if not ("new-candidate" in request.POST) and not past_candidate_id:
        duplicates = candidate.find_duplicates()
        duplicate_processes = Process.objects.distinct().filter(candidate__in=duplicates)

    if not duplicates:
        candidate.save()
        log_action(True, candidate, request.user, new_candidate)

        content = request.FILES.get("cv", None)
        if content:
            Document.objects.create(document_type="CV", content=content, candidate=candidate)

        process = process_form.save(commit=False)
        process.candidate = candidate
        process.creator = Consultant.objects.get(user=request.user)
        if request.user.consultant.limited_to_source:
            process.sources = request.user.consultant.limited_to_source
        process.save()
        log_action(True, process, request.user, new_candidate)

        if interviewers_form.cleaned_data["interviewers"]:
            interview = interviewers_form.save(commit=False)
            interview.process = process
            interview.save()
            log_action(True, interview, request.user, new_candidate)
            interviewers_form.save_m2m()

        return True, HttpResponseRedirect(process.get_absolute_url())

    # we found duplicates
    return False, duplicate_processes


@privilege_level_check(
    authorised_level=[
        Consultant.PrivilegeLevel.ALL,
        Consultant.PrivilegeLevel.EXTERNAL_RPO,
        Consultant.PrivilegeLevel.EXTERNAL_FULL,
    ]
)
def new_candidate(request, past_candidate_id=None):
    duplicate_processes = None
    candidate = None

    if request.method == "POST":
        candidate_form = ProcessCandidateForm(data=request.POST, files=request.FILES)
        process_form = ProcessForm(data=request.POST)
        interviewers_form = InterviewersForm(prefix="interviewers", data=request.POST)

        #  clicked on "reuse this candidate"
        if not "summit" in request.POST:
            candidate = Candidate.objects.get(id=past_candidate_id)
            if not candidate.name:
                candidate.name = candidate_form.data["name"]
            if candidate_form.data["email"]:
                candidate.email = candidate_form.data["email"]
            if candidate_form.data["phone"]:
                candidate.phone = candidate_form.data["phone"]
            candidate_form = ProcessCandidateForm(instance=candidate)

        # we want to try and save our candidate
        elif candidate_form.is_valid() and process_form.is_valid() and interviewers_form.is_valid():
            success, response = new_candidate_POST_handler(
                request, candidate_form, process_form, interviewers_form, past_candidate_id=past_candidate_id
            )

            if success:
                return response  # HttpRedirect(process.url)

            # duplicates were found and it was not already handled
            duplicate_processes = response
    else:
        candidate_form = ProcessCandidateForm()
        process_form = ProcessForm()
        interviewers_form = InterviewersForm(prefix="interviewers")
        process_form.fields["subsidiary"].initial = request.user.consultant.company.id

    if request.user.consultant.is_external:
        process_form.fields.pop("sources")

        # restrict available interviewers to process creator
        interviewers_form.fields["interviewers"].widget.queryset = interviewers_form.fields[
            "interviewers"
        ].queryset.filter(user=request.user)

    source_form = SourceForm(prefix="source")
    offer_form = OfferForm(prefix="offer")
    return render(
        request,
        "interview/new_candidate.html",
        {
            "candidate_form": candidate_form,
            "process_form": process_form,
            "source_form": source_form,
            "offer_form": offer_form,
            "interviewers_form": interviewers_form,
            "duplicates": duplicate_processes,
            "candidate": candidate,
            "subsidiaries": Subsidiary.objects.all(),
        },
    )


@require_http_methods(["GET", "POST"])
@transaction.atomic
@privilege_level_check(
    authorised_level=[
        Consultant.PrivilegeLevel.ALL,
        Consultant.PrivilegeLevel.EXTERNAL_RPO,
        Consultant.PrivilegeLevel.EXTERNAL_FULL,
    ]
)
def interview(request, process_id=None, interview_id=None, action=None):
    """
    Insert or update an interview. Date and Interviewers
    """
    if interview_id is not None:
        try:
            interview_model = Interview.objects.for_user(request.user).get(id=interview_id)
            if (
                action in ["plan", "planning-request"]
                and request.user.consultant not in interview_model.interviewers.all()
            ):
                return HttpResponseNotFound()

        except Interview.DoesNotExist:
            return HttpResponseNotFound()
    else:
        interview_model = Interview(process_id=process_id)

    InterviewForm = InterviewFormEditInterviewers if action == "edit" else InterviewFormPlan
    process = Process.objects.for_user(request.user).get(id=process_id)
    last_interview = Interview.objects.filter(process=process).exclude(pk=interview_id).last()
    goal = last_interview.next_interview_goal if last_interview else ""
    if request.method == "POST":
        ret = HttpResponseRedirect(process.get_absolute_url())
        if action == "planning-request":
            interview_model.toggle_planning_request()
            return ret

        if request.user.consultant.privilege not in [
            Consultant.PrivilegeLevel.ALL,
            Consultant.PrivilegeLevel.EXTERNAL_RPO,
        ]:
            # set interviewer to be external consultant
            tmp = request.POST.copy()
            tmp["interviewers"] = request.user.consultant.id
            request.POST = tmp
        form = InterviewForm(request.POST, instance=interview_model)

        if form.is_valid():
            form.save()
            log_action(False, interview_model, request.user, interview)
            return ret
    else:
        form = InterviewForm(instance=interview_model)

    if request.user.consultant.privilege not in [Consultant.PrivilegeLevel.ALL, Consultant.PrivilegeLevel.EXTERNAL_RPO]:
        form.fields.pop("interviewers", None)  # interviewer will always be user

    return render(
        request,
        "interview/interview.html",
        {
            "form": form,
            "process": process,
            "subsidiaries": Subsidiary.objects.all(),
            "goal": goal,
        },
    )


@require_http_methods(["GET", "POST"])
@privilege_level_check(
    authorised_level=[
        Consultant.PrivilegeLevel.ALL,
        Consultant.PrivilegeLevel.EXTERNAL_RPO,
        Consultant.PrivilegeLevel.EXTERNAL_FULL,
    ]
)
def minute_edit(request, interview_id):
    try:
        interview = Interview.objects.for_user(request.user).get(id=interview_id)
    except Interview.DoesNotExist:
        return HttpResponseNotFound()

    # check if user is allowed to edit
    if request.user.consultant not in interview.interviewers.all():
        return HttpResponseNotFound()
    if request.method == "POST":
        if "itw-go" in request.POST:
            interview.state = Interview.GO
        elif "itw-no" in request.POST:
            interview.state = Interview.NO_GO
        elif "itw-draft" in request.POST:
            interview.state = Interview.DRAFT
        if interview.planned_date is None:
            interview.planned_date = now()
        form = InterviewMinuteForm(request.POST, request.FILES, instance=interview)
        if form.is_valid():
            for document in request.FILES.getlist("document", []):
                DocumentInterview.objects.create(content=document, interview=interview, name=document.name)
            form.save()
            log_action(False, interview, request.user, minute_edit)
            return HttpResponseRedirect(interview.get_absolute_url())
    else:
        form = InterviewMinuteForm(instance=interview)

    return render(
        request,
        "interview/interview_minute_form.html",
        {
            "form": form,
            "process": interview.process,
            "interview": interview,
            "subsidiaries": Subsidiary.objects.all(),
            "documents": DocumentInterview.objects.filter(interview=interview),
        },
    )


@login_required
@require_http_methods(["POST"])
def delete_document_minute_ajax(request):
    document_id = request.POST.get("document_id")
    try:
        document = DocumentInterview.objects.get(id=document_id)
        document.delete()
    except DocumentInterview.DoesNotExist:
        return JsonResponse({"error": "Not found"})

    return JsonResponse({})


@login_required
@require_http_methods(["GET"])
def minute(request, interview_id, slug_info=None):
    try:
        interview = Interview.objects.for_user(request.user).get(id=interview_id)
    except Interview.DoesNotExist:
        return HttpResponseNotFound()

    try:
        if interview.goal:
            goal = interview.goal
        else:
            goal = Interview.objects.filter(process=interview.process).get(rank=interview.rank - 1).next_interview_goal
    except Interview.DoesNotExist:  # first itw case
        goal = ""

    context = {
        "interview": interview,
        "process": interview.process,
        "subsidiaries": Subsidiary.objects.all(),
        "goal": goal,
        "document": interview.documentinterview_set.all(),
    }
    return render(request, "interview/interview_minute.html", context)


@login_required
@require_http_methods(["GET"])
def dashboard(request):
    if request.user.consultant.limited_to_source:  # if None, dashboard will be empty anyways
        return processes_for_source(request, request.user.consultant.limited_to_source.id)

    a_week_ago = timezone.now() - datetime.timedelta(days=7)
    c = request.user.consultant
    actions_needed_processes = (
        Process.objects.for_table(request.user).exclude(state__in=Process.CLOSED_STATE_VALUES).filter(responsible=c)
    )

    actions_needed_processes_table = ProcessTable(actions_needed_processes, prefix="a")

    related_processes = (
        Process.objects.for_table(request.user)
        .filter(interview__interviewers__user=request.user)
        .filter(Q(end_date__gte=a_week_ago) | Q(state__in=Process.OPEN_STATE_VALUES))
        .distinct()
    )
    related_processes_table = ProcessTable(related_processes, prefix="r")

    subsidiary_processes = (
        Process.objects.for_table(request.user)
        .filter(Q(end_date__gte=a_week_ago) | Q(state__in=Process.OPEN_STATE_VALUES))
        .filter(subsidiary=c.company)
    )

    subsidiary_processes_table = ProcessTable(subsidiary_processes, prefix="s")

    config = RequestConfig(request)
    config.configure(actions_needed_processes_table)
    config.configure(related_processes_table)
    config.configure(subsidiary_processes_table)

    context = {
        "actions_needed_processes_table": actions_needed_processes_table,
        "related_processes_table": related_processes_table,
        "subsidiary_processes_table": subsidiary_processes_table,
        "subsidiaries": Subsidiary.objects.all(),
    }

    return render(request, "interview/dashboard.html", context)


@login_required
@require_http_methods(["POST"])
@user_passes_test(lambda u: not u.consultant.is_external)
def create_source_ajax(request):
    form = SourceForm(request.POST, prefix="source")
    if form.is_valid():
        form.save()
        log_action(True, form.instance, request.user, create_source_ajax)
        data = {}
        return JsonResponse(data)
    else:
        data = {"error": form.errors}
        return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
@user_passes_test(lambda u: not u.consultant.is_external)
def create_offer_ajax(request):
    form = OfferForm(request.POST, prefix="offer")
    if form.is_valid():
        form.save()
        log_action(True, form.instance, request.user, create_offer_ajax)
        data = {}
        return JsonResponse(data)
    else:
        data = {"error": form.errors}
        return JsonResponse(data)


@csrf_exempt
@require_http_methods(["POST"])
@user_passes_test(lambda u: u.is_superuser)
@user_passes_test(lambda u: not u.consultant.is_external)
def create_account(request):
    data = json.loads(request.body)
    subsidiary = Subsidiary.objects.filter(code=data["company"]).first()
    if not subsidiary:
        return JsonResponse({"error": "Company not found"}, status=404)
    try:
        extra_fields = {"date_joined": timezone.now()}
        if "date_joined" in data:
            if parse_date(data["date_joined"]) is None:
                return JsonResponse({"error": "ISO 8601 for date format"}, status=400)
            extra_fields["date_joined"] = data["date_joined"]
        consultant = Consultant.objects.create_consultant(
            trigramme=data["trigramme"].lower(),
            email=data["email"],
            company=subsidiary,
            full_name=data["name"],
            **extra_fields,
        )
        return JsonResponse({"consultant": consultant.__str__()})
    except:
        return JsonResponse({"error": "user already register"}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
@user_passes_test(lambda u: u.is_superuser)
@user_passes_test(lambda u: not u.consultant.is_external)
def delete_account(request, trigramme):
    user = PyouPyouUser.objects.filter(trigramme=trigramme.lower()).first()
    if not user:
        return JsonResponse({"error": "user not found"}, status=404)
    user.is_active = False
    user.save()
    return JsonResponse({"user": user.__str__()})


@require_http_methods(["GET", "POST"])
@privilege_level_check(
    authorised_level=[
        Consultant.PrivilegeLevel.ALL,
        Consultant.PrivilegeLevel.EXTERNAL_RPO,
        Consultant.PrivilegeLevel.EXTERNAL_FULL,
    ]
)
def edit_candidate(request, process_id):
    try:
        process = Process.objects.for_user(request.user).select_related("candidate").get(id=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()
    candidate = process.candidate

    if request.method == "POST":
        candidate_form = ProcessCandidateForm(data=request.POST, files=request.FILES, instance=candidate)
        process_form = ProcessForm(data=request.POST, instance=process)

        if candidate_form.is_valid() and process_form.is_valid():
            candidate_form.id = candidate.id
            candidate = candidate_form.save()
            log_action(False, candidate, request.user, edit_candidate)
            content = request.FILES.get("cv", None)
            if content:
                Document.objects.create(document_type="CV", content=content, candidate=candidate)
            process_form.id = process.id
            process = process_form.save(commit=False)
            process.save()
            log_action(False, process, request.user, edit_candidate)
            return HttpResponseRedirect(process.get_absolute_url())
    else:
        candidate_form = ProcessCandidateForm(instance=candidate)
        process_form = ProcessForm(instance=process)

    source_form = SourceForm(prefix="source")
    offer_form = OfferForm(prefix="offer")

    if request.user.consultant.is_external:
        process_form.fields.pop("sources")

    data = {
        "process": process,
        "candidate_form": candidate_form,
        "process_form": process_form,
        "source_form": source_form,
        "offer_form": offer_form,
        "subsidiaries": Subsidiary.objects.all(),
    }
    return render(request, "interview/new_candidate.html", data)


@user_passes_test(lambda u: u.is_active and u.is_superuser)
def dump_data(request):
    out = io.StringIO()
    call_command(
        "dumpdata",
        use_natural_foreign_keys=True,
        use_base_manager=True,
        exclude=["auth.Permission", "contenttypes"],
        stdout=out,
    )
    response = HttpResponse(out.getvalue(), content_type="application/json")
    response["Content-Disposition"] = "attachment; filename=pyoupyou_dump.json"
    return response


def process_stats(process):
    """Compute process length (in days and itw count), shared by TSV exports"""
    process_length = 0
    end_date = None
    if process.end_date:
        end_date = process.end_date
    else:
        last_interview = Interview.objects.filter(process=process).order_by("planned_date").last()
        if last_interview is None or last_interview.planned_date is None:
            end_date = datetime.datetime.now().date()
        else:
            end_date = last_interview.planned_date.date()

    process_length = (end_date - process.start_date).days
    process_interview_count = Interview.objects.filter(process=process).count()

    return process_length, process_interview_count


@login_required
@require_http_methods(["GET"])
def export_processes_tsv(request):
    processes = Process.objects.for_user(request.user).prefetch_related("interview_set")

    ret = []

    ret.append(
        "\t".join(
            str(x).replace("\t", " ")
            for x in [
                "process.id",
                "candidate.name",
                "subsidiary",
                "start_date",
                "end_date",
                "process length",
                "sources",
                "source_category",
                "offer",
                "contract_type",
                "contract_start_date",
                "contract_duration",
                "process state",
                "process state label",
                "process itw count",
                "mean days between itws",
            ]
        )
    )

    for process in processes:
        process_length, process_interview_count = process_stats(process)
        columns = [
            process.id,
            process.candidate.name,
            process.subsidiary,
            process.start_date,
            process.end_date,
            process_length,
            process.sources,
            "" if process.sources is None else process.sources.category.name,
            process.offer,
            process.contract_type,
            process.contract_start_date,
            process.contract_duration,
            process.state,
            process.get_state_display(),
            process_interview_count,
            0 if process_interview_count == 0 else int(process_length / process_interview_count),
        ]
        ret.append("\t".join(str(c).replace("\t", " ") for c in columns))

    response = HttpResponse("\n".join(ret), content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = "attachment; filename=all_processes.tsv"

    return response


@login_required
@require_http_methods(["GET"])
def export_interviews_tsv(request):
    consultants = Consultant.objects.filter(user__is_active=True).select_related("user").select_related("company")
    interviews = (
        Interview.objects.for_user(request.user)
        .select_related("process")
        .select_related("process__sources")
        .select_related("process__contract_type")
        .select_related("process__candidate")
        .select_related("process__subsidiary")
        .select_related("process__offer")
        .prefetch_related(Prefetch("interviewers", queryset=consultants))
    )

    ret = []

    ret.append(
        "\t".join(
            str(x).replace("\t", " ")
            for x in [
                "process.id",
                "candidate.name",
                "subsidiary",
                "start_date",
                "end_date",
                "process length",
                "source",
                "source category",
                "offer",
                "contract_type",
                "contract_start_date",
                "contract_duration",
                "process state",
                "process state label",
                "process itw count",
                "mean days between itws",
                "interview.id",
                "state",
                "interviewers",
                "interview rank",
                "days since last",
                "planned_date",
                "prequalification",
                "kind",
            ]
        )
    )
    processes_length = {}
    processes_itw_count = {}

    for interview in interviews:
        interviewers = ""
        for i in interview.interviewers.all():
            interviewers += i.user.trigramme + "_"
        interviewers = interviewers[:-1]

        if interview.process.id not in processes_length:
            process_length, process_interview_count = process_stats(interview.process)
            processes_length[interview.process.id] = process_length
            processes_itw_count[interview.process.id] = process_interview_count
        else:
            process_length = processes_length[interview.process.id]
            process_interview_count = processes_itw_count[interview.process.id]

        # Compute time elapsed since last event (previous interview or beginning of process)
        time_since_last_is_sound = True
        last_event_date = interview.process.start_date
        next_event_date = None
        if interview.rank > 1:
            last_itw = (
                Interview.objects.for_user(request.user)
                .filter(process=interview.process, rank=interview.rank - 1)
                .first()
            )
            if last_itw and last_itw.planned_date is not None:
                last_event_date = last_itw.planned_date.date()
            else:
                time_since_last_is_sound = False
        if interview.planned_date is None:
            time_since_last_is_sound = False
        else:
            next_event_date = interview.planned_date.date()
        if time_since_last_is_sound:
            time_since_last_event = int((next_event_date - last_event_date).days)
            # we have some processes that were created after the first itw was planned
            if time_since_last_event < 0:
                time_since_last_event = ""
        else:
            time_since_last_event = ""

        columns = [
            interview.process.id,
            interview.process.candidate.name,
            interview.process.subsidiary,
            interview.process.start_date,
            interview.process.end_date,
            process_length,
            interview.process.sources,
            "" if interview.process.sources is None else interview.process.sources.category.name,
            interview.process.offer,
            interview.process.contract_type,
            interview.process.contract_start_date,
            interview.process.contract_duration,
            interview.process.state,
            interview.process.get_state_display(),
            process_interview_count,
            0 if process_interview_count == 0 else int(process_length / process_interview_count),
            interview.id,
            interview.state,
            interviewers,
            interview.rank,
            time_since_last_event,
            interview.planned_date,
            interview.prequalification,
            interview.kind_of_interview,
        ]
        ret.append("\t".join(str(c).replace("\t", " ") for c in columns))

    response = HttpResponse("\n".join(ret), content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = "attachment; filename=all_interviews.tsv"

    return response


class LoadTable(tables.Table):
    subsidiary = tables.Column(verbose_name=_("Subsidiary"))
    interviewer = tables.TemplateColumn(
        template_name="interview/tables/interviewer_link_interviews.html", verbose_name=_("Interviewer")
    )
    load = tables.Column(verbose_name=_("Load"))
    itw_last_month = tables.Column(verbose_name=_("Past month"))
    itw_last_week = tables.Column(verbose_name=_("Past week"))
    itw_planned = tables.Column(verbose_name=_("Planned"))
    itw_not_planned_yet = tables.Column(verbose_name=_("To plan"))

    class Meta:
        template_name = "interview/_tables.html"
        attrs = {"class": "table table-striped table-condensed"}


def _interviewer_load(interviewer):
    a_month_ago = timezone.now() - datetime.timedelta(days=30)
    a_week_ago = timezone.now() - datetime.timedelta(days=7)
    end_of_today = timezone.now().replace(hour=23, minute=59, second=59)

    itw_last_month = calculate_load(
        Interview.objects.filter(interviewers=interviewer)
        .filter(planned_date__gte=a_month_ago)
        .filter(planned_date__lt=end_of_today)
        .values("prequalification")
        .annotate(load=Count("id"))
        .order_by("prequalification")
    )
    itw_last_week = calculate_load(
        Interview.objects.filter(interviewers=interviewer)
        .filter(planned_date__gte=a_week_ago)
        .filter(planned_date__lt=end_of_today)
        .values("prequalification")
        .annotate(load=Count("id"))
        .order_by("prequalification")
    )
    itw_planned = calculate_load(
        Interview.objects.filter(interviewers=interviewer)
        .filter(planned_date__gte=timezone.now())
        .values("prequalification")
        .annotate(load=Count("id"))
        .order_by("prequalification")
    )
    itw_not_planned_yet = calculate_load(
        Interview.objects.filter(interviewers=interviewer)
        .filter(planned_date=None)
        .filter(process__state__in=Process.OPEN_STATE_VALUES)
        .values("prequalification")
        .annotate(load=Count("id"))
        .order_by("prequalification")
    )

    load = pow(itw_planned + itw_not_planned_yet + 2, 2) + 2 * itw_last_week + itw_last_month - 4

    return {
        "load": load,
        "itw_last_month": itw_last_month,
        "itw_last_week": itw_last_week,
        "itw_not_planned_yet": itw_not_planned_yet,
        "itw_planned": itw_planned,
    }


def calculate_load(itws):
    prequalification_weight = 2
    loads = {x["prequalification"]: x["load"] for x in itws}
    return loads.get(False, 0) + (loads.get(True, 0) / prequalification_weight)


@login_required
@require_http_methods(["GET"])
@user_passes_test(lambda u: not u.consultant.is_external)
def interviewers_load(request):
    subsidiary_filter = get_global_filter(request)
    subsidiary = subsidiary_filter.form.cleaned_data.get("subsidiary", None)

    if subsidiary:
        consultants_qs = Consultant.objects.filter(company=subsidiary)
    else:
        consultants_qs = Consultant.objects.all()
    data = []
    for c in consultants_qs.filter(user__is_active=True).order_by("company", "user__full_name"):
        load = _interviewer_load(c)
        data.append(
            {
                "subsidiary": c.company,
                "interviewer": c,
                "load": load["load"],
                "itw_last_month": load["itw_last_month"],
                "itw_last_week": load["itw_last_week"],
                "itw_not_planned_yet": load["itw_not_planned_yet"],
                "itw_planned": load["itw_planned"],
                "a_month_ago": (timezone.now() - datetime.timedelta(days=30)).strftime(
                    "%d/%m/%Y"
                ),  # For the link to interviews_list
            }
        )

    load_table = LoadTable(data, order_by="-load")
    RequestConfig(request, paginate={"per_page": 100}).configure(load_table)
    return render(
        request,
        "interview/interviewers-load.html",
        {
            "subsidiary": subsidiary,
            "subsidiaries": Subsidiary.objects.all(),
            "load_table": load_table,
        },
    )


@login_required
@require_http_methods(["GET"])
@user_passes_test(lambda u: not u.consultant.is_external)
def search(request):
    q = request.GET.get("q", "").strip()

    results = Process.objects.filter(Q(candidate__name__icontains=q) | Q(candidate__email__icontains=q)).distinct()

    search_result = ProcessEndTable(results, prefix="c")

    config = RequestConfig(request)
    config.configure(search_result)

    context = {
        "title": _('Search result for "{q}"').format(q=q),
        "table": search_result,
        "search_query": q,
        "subsidiaries": Subsidiary.objects.all(),
    }

    return render(request, "interview/single_table.html", context)


@login_required
@require_http_methods(["GET"])
@user_passes_test(lambda u: not u.consultant.is_external)
def gantt(request):
    state_filter = Process.OPEN_STATE_VALUES + [Process.JOB_OFFER, Process.HIRED]
    today = timezone.now().date()
    processes = Process.objects.filter(state__in=state_filter).select_related("contract_type", "candidate")
    processes = get_global_filter(request).filter_queryset(processes)
    filter = ProcessFilter(request.GET, queryset=processes)

    processes_dict = []
    max_end_date = timezone.now().date()

    for process in filter.qs:
        if process.contract_type is None:
            continue
        if process.contract_type.has_duration:
            if not process.contract_start_date or not process.contract_duration:
                continue
            if process.contract_start_date < today - datetime.timedelta(30) * process.contract_duration:
                continue

        elif process.state in [Process.JOB_OFFER, Process.HIRED] and (
            not process.contract_start_date or process.contract_start_date < today - datetime.timedelta(7)
        ):
            continue

        duration = process.contract_duration
        start_date = process.contract_start_date or process.start_date
        end_date = start_date + datetime.timedelta(30) * duration if duration else None
        if end_date:
            max_end_date = max(end_date, max_end_date)
        if process.state == Process.JOB_OFFER:
            state = "📝"
        elif process.state == Process.HIRED:
            state = "✔️"
        else:
            state = ""
        processes_dict.append(
            {
                "Task": "<a href='{}'>{} {}</a>".format(process.get_absolute_url(), process.candidate.name, state),
                "ContractType": process.contract_type.name,
                "Start": start_date,
                "Finish": end_date,
            }
        )

    for process in processes_dict:
        if not process["Finish"]:
            process["Finish"] = max_end_date

    fig = ff.create_gantt(
        processes_dict, index_col="ContractType", show_colorbar=True, showgrid_x=True, showgrid_y=True
    )
    fig.layout.update(
        {
            "title": {"text": _t("Contracts")},
            "xaxis": {"rangeslider": {"visible": False}, "rangeselector": None, "fixedrange": True},
            "yaxis": {"fixedrange": True},
        }
    )

    config = dict({"scrollZoom": False, "staticPlot": False, "showAxisRangeEntryBoxes": False, "displayModeBar": False})

    grant_chart = plot(fig, output_type="div", config=config)

    context = {
        "gantt": grant_chart,
        "filter": filter,
        "subsidiaries": Subsidiary.objects.all(),
    }

    return render(request, "interview/gantt.html", context)


class PercentColumn(tables.Column):
    def render(self, value):
        return "{:.0f}%".format(value)


class ActiveSourcesTable(tables.Table):
    name = tables.Column(attrs={"td": {"style": "font-weight: bold"}}, verbose_name=_("Name"))
    source_category = tables.Column(verbose_name=_("Type"))
    active_processes_count = tables.Column(verbose_name=_("Active processes"))
    total_processes_count = tables.Column(verbose_name=_("Processes"))
    total_hired = tables.Column(verbose_name=_("Hired"))
    ratio = PercentColumn(verbose_name=_("Ratio"))
    offers = tables.Column(verbose_name=_("Offers"))
    last_state_change = tables.Column(verbose_name=_("Last change"))
    details = tables.TemplateColumn(verbose_name="", orderable=False, template_name="interview/tables/source_name.html")
    source_admin = tables.TemplateColumn(
        verbose_name="", orderable=False, template_name="interview/tables/edit_source.html"
    )

    class Meta:
        order_by = "name"
        template_name = "interview/_tables.html"
        attrs = {"class": "table table-striped table-condensed"}


class OffersTable(tables.Table):
    name = tables.Column(attrs={"td": {"style": "font-weight: bold"}}, verbose_name=_("Name"))
    subsidiary = tables.Column(verbose_name=_("Subsidiary"))
    active_processes_count = tables.Column(verbose_name=_("Active processes"))
    total_processes_count = tables.Column(verbose_name=_("Processes"))
    total_hired = tables.Column(verbose_name=_("Hired"))
    ratio = PercentColumn(verbose_name=_("Ratio"))
    sources = tables.Column(verbose_name=_("Sources"))
    last_state_change = tables.Column(verbose_name=_("Last change"))
    details = tables.TemplateColumn(verbose_name="", orderable=False, template_name="interview/tables/source_name.html")
    offer_admin = tables.TemplateColumn(
        verbose_name="", orderable=False, template_name="interview/tables/edit_source.html"
    )

    class Meta:
        order_by = "name"
        template_name = "interview/_tables.html"
        attrs = {"class": "table table-striped table-condensed"}


@login_required
@require_http_methods(["GET"])
@user_passes_test(lambda u: not u.consultant.is_external)
def active_sources(request):
    subsidiary_filter = get_global_filter(request)
    subsidiary = subsidiary_filter.form.cleaned_data.get("subsidiary")

    request_get = request.GET.copy()
    request_get.setdefault("archived", "False")

    sources_filter = ActiveSourcesFilter(
        request_get,
        queryset=Sources.objects.all()
        if subsidiary is None
        else Sources.objects.filter(process__subsidiary=subsidiary).distinct(),
    )
    sources_qs = sources_filter.qs

    subsidiary_id = sources_filter.data.get("subsidiary")
    if subsidiary_id:
        try:
            subsidiary = Subsidiary.objects.get(id=subsidiary_id)
        except Subsidiary.DoesNotExist:
            pass

    data = []
    filtered_process = Process.objects.all()
    if subsidiary:
        filtered_process = filtered_process.filter(subsidiary=subsidiary)
    for s in sources_qs:
        total_processes = filtered_process.filter(sources=s)
        total_processes_count = total_processes.count()
        active_processes_count = filtered_process.filter(sources=s, state__in=Process.OPEN_STATE_VALUES).count()
        total_hired = filtered_process.filter(sources=s, state=Process.HIRED).count()
        last_state_change = filtered_process.filter(sources=s).aggregate(Max("last_state_change"))
        distinct_offers = Offer.objects.filter(process__in=filtered_process.filter(sources=s)).distinct().count()

        row = {
            "name": s.name,
            "source_category": s.category.name,
            "last_active_process_days": last_state_change,
            "total_processes_count": total_processes_count,
            "active_processes_count": active_processes_count,
            "total_hired": total_hired,
            "ratio": 100 * total_hired / total_processes_count if total_processes_count > 0 else None,
            "last_state_change": last_state_change["last_state_change__max"],
            "url": reverse(viewname="process-list-source", kwargs={"source_id": s.id}),
            "admin_url": reverse(viewname="admin:interview_sources_change", kwargs={"object_id": s.id}),
            "offers": distinct_offers,
            "id": s.id,
        }

        data.append(row)

    all_sources_table = ActiveSourcesTable(
        data,
        order_by="-last_active_process_days",
    )

    # if no filtering by 'archived' is applied
    if not sources_filter.data.get("archived"):
        # change table rendering to gray out rows that are archived
        all_sources_table.attrs.update({"class": "table table-condensed"})
        all_sources_table.row_attrs.update(
            {"bgcolor": lambda record: "#e0e0e0" if Sources.objects.get(id=record["id"]).archived else None}
        )

    RequestConfig(request, paginate={"per_page": 100}).configure(all_sources_table)
    return render(
        request,
        "interview/active-sources.html",
        {
            "subsidiary": subsidiary,
            "subsidiaries": Subsidiary.objects.all(),
            "sources": all_sources_table,
            "filter": sources_filter,
        },
    )


@login_required
@require_http_methods(["GET"])
@user_passes_test(lambda u: not u.consultant.is_external)
def offers(request):
    subsidiary_filter = get_global_filter(request)
    subsidiary = subsidiary_filter.form.cleaned_data.get("subsidiary")

    offers = Offer.objects.all() if subsidiary is None else Offer.objects.filter(subsidiary=subsidiary)
    offers_qs = offers.filter(archived=False)

    data = []
    filtered_process = Process.objects.all()
    if subsidiary:
        filtered_process = filtered_process.filter(subsidiary=subsidiary)
    for o in offers_qs:
        total_processes = filtered_process.filter(offer=o)
        total_processes_count = total_processes.count()
        active_processes_count = filtered_process.filter(offer=o, state__in=Process.OPEN_STATE_VALUES).count()
        total_hired = filtered_process.filter(offer=o, state=Process.HIRED).count()
        last_state_change = filtered_process.filter(offer=o).aggregate(Max("last_state_change"))
        distinct_sources = Sources.objects.filter(process__in=filtered_process.filter(offer=o)).distinct().count()

        data.append(
            {
                "name": o.name,
                "subsidiary": o.subsidiary,
                "last_active_process_days": last_state_change,
                "total_processes_count": total_processes_count,
                "active_processes_count": active_processes_count,
                "total_hired": total_hired,
                "ratio": 100 * total_hired / total_processes_count if total_processes_count > 0 else None,
                "last_state_change": last_state_change["last_state_change__max"],
                "url": reverse(viewname="process-list-offer", kwargs={"offer_id": o.id}),
                "admin_url": reverse(viewname="admin:interview_offer_change", kwargs={"object_id": o.id}),
                "sources": distinct_sources,
            }
        )

    offers_table = OffersTable(data, order_by="-last_active_process_days")
    RequestConfig(request, paginate={"per_page": 100}).configure(offers_table)
    return render(
        request,
        "interview/offers.html",
        {
            "subsidiary": subsidiary,
            "subsidiaries": Subsidiary.objects.all(),
            "offers": offers_table,
        },
    )


@login_required
@require_http_methods(["GET"])
@user_passes_test(lambda u: not u.consultant.is_external)
def activity_summary(request):
    subsidiary_filter = get_global_filter(request)
    process_filter = ProcessSummaryFilter(
        request.GET, queryset=subsidiary_filter.filter_queryset(Process.objects.all())
    )
    interview_filter = InterviewSummaryFilter(
        request.GET,
        queryset=Interview.objects.filter(process__subsidiary=subsidiary_filter.form.cleaned_data["subsidiary"])
        if subsidiary_filter.form.cleaned_data["subsidiary"]
        else Interview.objects.all(),
    )

    # Processes started in the timespan
    new_processes_total = process_filter.qs.count()
    new_processes = process_filter.qs.values("subsidiary__name").annotate(count=Count("candidate"))

    # Processes closed and last modified in the timespan
    closed_processes_total = process_filter.qs.filter(state__in=Process.CLOSED_STATE_VALUES).count()
    closed_processes = (
        process_filter.qs.filter(state__in=Process.CLOSED_STATE_VALUES)
        .values("subsidiary__name")
        .annotate(count=Count("candidate"))
    )

    # Processes closed and last modified in the timespan and GO
    go_processes = process_filter.qs.filter(state=Process.HIRED).order_by("subsidiary")

    # Processes with a pending offer
    offer_processes = process_filter.qs.filter(state=Process.JOB_OFFER).order_by("subsidiary")

    # Processes declined by candidate
    declined_processes = process_filter.qs.filter(state=Process.CANDIDATE_DECLINED).order_by("subsidiary")

    # New interviews
    new_interviews_total = interview_filter.qs.count()
    new_interviews = (
        interview_filter.qs.order_by("process__subsidiary__name")
        .values("process__subsidiary__name")
        .annotate(count=Count("id"))
    )

    # New GO interviews
    new_interviews_go_total = interview_filter.qs.filter(state=Interview.GO).count()
    new_interviews_go = (
        interview_filter.qs.filter(state=Interview.GO)
        .order_by("process__subsidiary__name")
        .values("process__subsidiary__name")
        .annotate(count=Count("id"))
    )

    active_sources = process_filter.qs.values("sources__name").annotate(count=Count("sources")).filter(count__gt=0)

    start_date = Process.objects.order_by("start_date").first().start_date
    end_date = timezone.now()
    if process_filter.form.cleaned_data["last_state_change"]:
        if process_filter.form.cleaned_data["last_state_change"].start:
            start_date = process_filter.form.cleaned_data["last_state_change"].start
        if process_filter.form.cleaned_data["last_state_change"].stop:
            end_date = process_filter.form.cleaned_data["last_state_change"].stop
    subsidiary = subsidiary_filter.form.cleaned_data["subsidiary"]

    source_data = (
        interview_filter.qs.filter(planned_date__isnull=False)
        .order_by("process__subsidiary__name")
        .annotate(planned_date_month=Trunc("planned_date", "month"))
        .values("planned_date_month")
        .order_by("planned_date_month")
        .values("planned_date_month", "process__subsidiary__name", "state")
        .annotate(count=Count("id"))
    )

    df = pd.DataFrame(source_data)

    translated_values = [
        _t("NEED PLANIFICATION"),
        _t("WAIT PLANIFICATION RESPONSE"),
        _t("PLANNED"),
        _t("GO"),
        _t("NO"),
        _t("DRAFT"),
        _t("WAIT INFORMATION"),
    ]

    chart = None
    if len(df) > 0:
        df = df.replace(Interview.ALL_STATE_VALUES, translated_values)
        df["subsidiary_state"] = df["process__subsidiary__name"] + " " + df["state"]
        df = df.sort_values("subsidiary_state")

        fig = px.bar(
            df,
            x="planned_date_month",
            y="count",
            color="subsidiary_state",
            title="",
            labels={
                "planned_date_month": _t("Interview date"),
                "process__subsidiary__name": _t("Subsidiary"),
                "count": _t("Count"),
                "subsidiary_state": _t("Subsidiary and state"),
            },
        )

        config = dict(
            {"scrollZoom": False, "staticPlot": False, "showAxisRangeEntryBoxes": False, "displayModeBar": False}
        )
        chart = plot(fig, output_type="div", config=config)

    return render(
        request,
        "interview/summary.html",
        {
            "filter": process_filter,
            "interviews_total": new_interviews_total,
            "interviews_go_total": new_interviews_go_total,
            "interviews_details": zip(new_interviews, new_interviews_go) if not subsidiary else None,
            "new_processes_total": new_processes_total,
            "new_processes": new_processes if not subsidiary else None,
            "closed_processes_total": closed_processes_total,
            "closed_processes": closed_processes if not subsidiary else None,
            "active_sources": active_sources,
            "go_processes": go_processes,
            "offer_processes": offer_processes,
            "declined_processes": declined_processes,
            "start": start_date,
            "end": end_date,
            "plot_div": chart if chart else "",
            "subsidiaries": Subsidiary.objects.all(),
        },
    )


@login_required
@require_http_methods(["GET"])
def interviews_list(request):
    a_month_ago = timezone.now() - datetime.timedelta(days=30)

    subsidiary_filter = get_global_filter(request)
    itw_qs = Interview.objects.for_table(request.user)
    if subsidiary_filter.form.cleaned_data["subsidiary"]:
        itw_qs = itw_qs.filter(process__subsidiary=subsidiary_filter.form.cleaned_data["subsidiary"])
    interview_filter = InterviewListFilter(request.GET, queryset=itw_qs.order_by("planned_date"))

    # By default (if no filter data was sent in request), filter for
    #   - last month interviews
    interview_filter.data.setdefault("last_state_change_after", a_month_ago.strftime("%d/%m/%Y"))

    # interview that are not planned are not selected by default filter as it is a range on planned_date, hence this query
    interviews_not_planned = (
        Interview.objects.for_table(request.user)
        .filter(planned_date=None)
        .filter(process__state__in=Process.OPEN_STATE_VALUES)
    )

    # We need to replicate filters because we can't mutate an existing filter :(
    if interview_filter.data.get("subsidiary", None):
        interviews_not_planned = interviews_not_planned.filter(process__subsidiary=interview_filter.data["subsidiary"])
    if interview_filter.data.get("interviewer", None):
        interviews_not_planned = interviews_not_planned.filter(interviewers=interview_filter.data["interviewer"])

    # Only display planned interviews in the interviews list page iff the user has selected an end date
    if interview_filter.data.get("last_state_change_before", None):
        interviews_not_planned = []

    interviews_table = InterviewDetailTable(list(interview_filter.qs) + list(interviews_not_planned), prefix="i")

    config = RequestConfig(request)
    config.configure(interviews_table)

    context = {
        "interviews_table": interviews_table,
        "filter": interview_filter,
        "subsidiaries": Subsidiary.objects.all(),
    }

    return render(request, "interview/list_interviews.html", context)


@csrf_exempt
@api_view(["POST"])
def process_from_cognito_form(request, source_id, subsidiary_id):
    data = request.data

    data.update(
        {
            "sources": source_id,
            "subsidiary": subsidiary_id,
        }
    )

    serializer = CognitoWebHookSerializer(data=data)

    serializer.is_valid(raise_exception=True)

    serializer.create(serializer.validated_data)

    return HttpResponse("Success")
