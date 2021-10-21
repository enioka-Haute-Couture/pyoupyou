# -*- coding: utf-8 -*-
import datetime
import calendar
import io
import re
from collections import defaultdict
import json

from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.admin.options import get_content_type_for_model
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
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseNotFound, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.html import format_html
from django.utils.translation import ugettext as _t
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_tables2 import RequestConfig
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.dateparse import parse_date
from django.db.models import Count

from interview.filters import ProcessFilter, ProcessSummaryFilter, InterviewSummaryFilter
from interview.forms import (
    ProcessCandidateForm,
    InterviewMinuteForm,
    ProcessForm,
    InterviewFormPlan,
    InterviewFormEditInterviewers,
    SourceForm,
    CloseForm,
    UploadSeekubeFileForm,
    OfferForm,
    InterviewersForm,
)
from interview.models import Process, Document, Interview, Sources, SourcesCategory, Candidate, Offer
from ref.models import Consultant, PyouPyouUser, Subsidiary

import datetime
from django import template

register = template.Library()


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
    needs_attention = tables.TemplateColumn(
        template_name="interview/tables/needs_attention_cell.html", verbose_name="", orderable=False
    )
    actions = tables.TemplateColumn(
        verbose_name="", orderable=False, template_name="interview/tables/process_actions.html"
    )
    candidate = tables.Column(attrs={"td": {"style": "font-weight: bold"}}, order_by=("candidate__name",))
    contract_type = tables.Column(order_by=("contract_type__name",))
    current_rank = tables.Column(verbose_name=_("No itw"), orderable=False)

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

    class Meta:
        model = Interview
        template_name = "interview/_tables.html"
        attrs = {"class": "table table-striped table-condensed"}
        sequence = ("needs_attention", "interviewers", "planned_date", "state", "actions")
        fields = sequence
        order_by = "id"
        empty_text = _("No data")
        row_attrs = {"class": lambda record: "danger" if record.needs_attention else None}


@login_required
@require_http_methods(["GET"])
def process(request, process_id, slug_info=None):
    try:
        process = Process.objects.for_user(request.user).get(id=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()
    interviews = (
        Interview.objects.for_user(request.user)
        .filter(process=process)
        .prefetch_related("process__candidate", "interviewers")
    )
    interviews_for_process_table = InterviewTable(interviews)
    RequestConfig(request).configure(interviews_for_process_table)
    close_form = CloseForm(instance=process)

    documents = Document.objects.filter(candidate=process.candidate)
    context = {
        "process": process,
        "documents": documents,
        "interviews_for_process_table": interviews_for_process_table,
        "interviews": interviews,
        "close_form": close_form,
    }
    return render(request, "interview/process_detail.html", context)


@login_required
@require_http_methods(["POST"])
def close_process(request, process_id):
    try:
        process = Process.objects.for_user(request.user).get(pk=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()

    form = CloseForm(request.POST, instance=process)
    if form.is_valid():
        form.instance.end_date = datetime.date.today()
        form.save()
        log_action(False, process, request.user, close_process)
    # TODO manage errors
    return HttpResponseRedirect(process.get_absolute_url())


@login_required
@require_http_methods(["GET"])
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
    closed_processes = (
        Process.objects.for_user(request.user)
        .filter(end_date__isnull=False)
        .select_related("candidate", "contract_type")
    )

    closed_processes_table = ProcessEndTable(closed_processes, prefix="c")

    config = RequestConfig(request)
    config.configure(closed_processes_table)

    context = {"title": _("Closed processes"), "table": closed_processes_table}

    return render(request, "interview/single_table.html", context)


@login_required
@require_http_methods(["GET"])
def processes_for_source(request, source_id):
    try:
        source = Sources.objects.get(id=source_id)
    except Sources.DoesNotExist:
        return HttpResponseNotFound()

    processes = (
        Process.objects.for_user(request.user).filter(sources_id=source_id).select_related("candidate", "contract_type")
    )

    processes_table = ProcessEndTable(processes, prefix="c")

    config = RequestConfig(request)
    config.configure(processes_table)

    context = {"title": source.name + " (" + source.category.name + ")", "table": processes_table}

    return render(request, "interview/single_table.html", context)


@login_required
@require_http_methods(["GET"])
def processes(request):
    open_processes = Process.objects.for_user(request.user).filter(end_date__isnull=True)
    a_week_ago = datetime.date.today() - datetime.timedelta(days=7)
    recently_closed_processes = Process.objects.for_user(request.user).filter(end_date__gte=a_week_ago)

    open_processes_table = ProcessTable(open_processes, prefix="o")
    recently_closed_processes_table = ProcessEndTable(recently_closed_processes, prefix="c")

    config = RequestConfig(request)
    config.configure(open_processes_table)
    config.configure(recently_closed_processes_table)

    context = {
        "open_processes_table": open_processes_table,
        "recently_closed_processes_table": recently_closed_processes_table,
    }
    return render(request, "interview/list_processes.html", context)


@login_required
@require_http_methods(["POST"])
def reuse_candidate(request, candidate_id):
    return new_candidate(request, candidate_id)


@login_required
def new_candidate(request, past_candidate_id=None):
    duplicate_processes = None
    candidate = None
    if request.method == "POST":
        candidate_form = ProcessCandidateForm(data=request.POST, files=request.FILES)
        process_form = ProcessForm(data=request.POST)
        interviewers_form = InterviewersForm(prefix="interviewers", data=request.POST)
        if candidate_form.is_valid() and process_form.is_valid() and interviewers_form.is_valid():
            candidate = candidate_form.save(commit=False)
            duplicates = None
            if past_candidate_id:
                if not "summit" in request.POST:
                    candidate = Candidate.objects.get(id=past_candidate_id)
                    if not candidate.name:
                        candidate.name = candidate_form.data["name"]
                    if candidate_form.data["email"]:
                        candidate.email = candidate_form.data["email"]
                    if candidate_form.data["phone"]:
                        candidate.phone = candidate_form.data["phone"]
                    candidate_form = ProcessCandidateForm(instance=candidate)
            elif not "new-candidate" in request.POST:
                duplicates = candidate.find_duplicates()
                duplicate_processes = Process.objects.distinct().filter(candidate__in=duplicates)
            if (
                not duplicates or candidate.id is not None or "new-candidate" in request.POST
            ) and "summit" in request.POST:
                candidate.save()
                log_action(True, candidate, request.user, new_candidate)
                content = request.FILES.get("cv", None)
                if content:
                    Document.objects.create(document_type="CV", content=content, candidate=candidate)
                process = process_form.save(commit=False)
                process.candidate = candidate
                process.save()
                log_action(True, process, request.user, new_candidate)

                if interviewers_form.cleaned_data["interviewers"]:
                    interview = interviewers_form.save(commit=False)
                    interview.process = process
                    interview.save()
                    log_action(True, interview, request.user, new_candidate)
                    interviewers_form.save_m2m()

                return HttpResponseRedirect(process.get_absolute_url())
    else:
        candidate_form = ProcessCandidateForm()
        process_form = ProcessForm()
        interviewers_form = InterviewersForm(prefix="interviewers")
        process_form.fields["subsidiary"].initial = request.user.consultant.company.id

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
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
@transaction.atomic
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
    if request.method == "POST":
        ret = HttpResponseRedirect(process.get_absolute_url())
        if action == "planning-request":
            interview_model.toggle_planning_request()
            return ret
        form = InterviewForm(request.POST, instance=interview_model)
        if form.is_valid():
            form.save()
            log_action(False, interview_model, request.user, interview)
            return ret
    else:
        form = InterviewForm(instance=interview_model)

    return render(request, "interview/interview.html", {"form": form, "process": process})


@login_required
@require_http_methods(["GET", "POST"])
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
        form = InterviewMinuteForm(request.POST, instance=interview)
        if form.is_valid():
            form.save()
            log_action(False, interview, request.user, minute_edit)
            return HttpResponseRedirect(interview.get_absolute_url())
    else:
        form = InterviewMinuteForm(instance=interview)

    return render(
        request,
        "interview/interview_minute_form.html",
        {"form": form, "process": interview.process, "interview": interview},
    )


@login_required
@require_http_methods(["GET"])
def minute(request, interview_id, slug_info=None):
    try:
        interview = Interview.objects.for_user(request.user).get(id=interview_id)
    except Interview.DoesNotExist:
        return HttpResponseNotFound()

    context = {"interview": interview, "process": interview.process}
    return render(request, "interview/interview_minute.html", context)


@login_required
@require_http_methods(["GET"])
def dashboard(request):
    a_week_ago = datetime.date.today() - datetime.timedelta(days=7)
    c = request.user.consultant
    actions_needed_processes = (
        Process.objects.for_user(request.user)
        .exclude(state__in=Process.CLOSED_STATE_VALUES)
        .filter(responsible=c)
        .select_related("candidate", "subsidiary__responsible__user")
    )

    actions_needed_processes_table = ProcessTable(actions_needed_processes, prefix="a")

    related_processes = (
        Process.objects.for_user(request.user)
        .filter(interview__interviewers__user=request.user)
        .filter(Q(end_date__gte=a_week_ago) | Q(state__in=Process.OPEN_STATE_VALUES))
        .select_related("candidate", "subsidiary__responsible__user")
        .distinct()
    )
    related_processes_table = ProcessTable(related_processes, prefix="r")

    subsidiary_processes = (
        Process.objects.for_user(request.user)
        .filter(Q(end_date__gte=a_week_ago) | Q(state__in=Process.OPEN_STATE_VALUES))
        .filter(subsidiary=c.company)
        .select_related("candidate", "subsidiary__responsible__user")
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
    }

    return render(request, "interview/dashboard.html", context)


@login_required
@require_http_methods(["POST"])
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
def create_account(request):
    data = json.loads(request.body)
    subsidiary = Subsidiary.objects.filter(name=data["company"]).first()
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
def delete_account(request, trigramme):
    user = PyouPyouUser.objects.filter(trigramme=trigramme.lower()).first()
    if not user:
        return JsonResponse({"error": "user not found"}, status=404)
    user.is_active = False
    user.save()
    return JsonResponse({"user": user.__str__()})


@login_required
@require_http_methods(["GET", "POST"])
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

    data = {
        "process": process,
        "candidate_form": candidate_form,
        "process_form": process_form,
        "source_form": source_form,
        "offer_form": offer_form,
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
    consultants = Consultant.objects.filter(productive=True).select_related("user").select_related("company")
    interviews = (
        Interview.objects.for_user(request.user)
        .select_related("process")
        .select_related("process__sources")
        .select_related("process__contract_type")
        .select_related("process__candidate")
        .select_related("process__subsidiary")
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
        ]
        ret.append("\t".join(str(c).replace("\t", " ") for c in columns))

    response = HttpResponse("\n".join(ret), content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = "attachment; filename=all_interviews.tsv"

    return response


class LoadTable(tables.Table):
    subsidiary = tables.Column(verbose_name=_("Subsidiary"))
    interviewer = tables.Column(verbose_name=_("Interviewer"), attrs={"td": {"style": "font-weight: bold"}})
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

    itw_last_month = (
        Interview.objects.filter(interviewers=interviewer)
        .filter(planned_date__gte=a_month_ago)
        .filter(planned_date__lt=end_of_today)
        .count()
    )
    itw_last_week = (
        Interview.objects.filter(interviewers=interviewer)
        .filter(planned_date__gte=a_week_ago)
        .filter(planned_date__lt=end_of_today)
        .count()
    )
    itw_planned = Interview.objects.filter(interviewers=interviewer).filter(planned_date__gte=timezone.now()).count()
    itw_not_planned_yet = (
        Interview.objects.filter(interviewers=interviewer)
        .filter(planned_date=None)
        .filter(process__state__in=Process.OPEN_STATE_VALUES)
        .count()
    )

    load = pow(itw_planned + itw_not_planned_yet + 2, 2) + 2 * itw_last_week + itw_last_month - 4

    return {
        "load": load,
        "itw_last_month": itw_last_month,
        "itw_last_week": itw_last_week,
        "itw_not_planned_yet": itw_not_planned_yet,
        "itw_planned": itw_planned,
    }


@login_required
@require_http_methods(["GET"])
def interviewers_load(request, subsidiary_id=None):
    subsidiary = None
    if subsidiary_id:
        try:
            subsidiary = Subsidiary.objects.get(id=subsidiary_id)
        except Subsidiary.DoesNotExist:
            subsidiary = None

    if subsidiary:
        consultants_qs = Consultant.objects.filter(company=subsidiary_id)
    else:
        consultants_qs = Consultant.objects.all()
    data = []
    for c in consultants_qs.filter(productive=True).order_by("company", "user__full_name"):
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
            }
        )

    load_table = LoadTable(data, order_by="-load")
    RequestConfig(request, paginate={"per_page": 100}).configure(load_table)
    return render(
        request,
        "interview/interviewers-load.html",
        {"subsidiary": subsidiary, "subsidiaries": Subsidiary.objects.all(), "load_table": load_table},
    )


@login_required
@require_http_methods(["GET"])
def search(request):
    q = request.GET.get("q", "")

    results = (
        Process.objects.for_user(request.user)
        .filter(Q(candidate__name__icontains=q) | Q(candidate__email__icontains=q))
        .distinct()
    )

    search_result = ProcessEndTable(results, prefix="c")

    config = RequestConfig(request)
    config.configure(search_result)

    context = {"title": _('Search result for "{q}"').format(q=q), "table": search_result, "search_query": q}

    return render(request, "interview/single_table.html", context)


RE_NAME = re.compile(r"SUMMARY:(?P<name>.*) - Entretien")
RE_SOURCE = re.compile(r"https:\/\/app\.seekube\.com\/jobdating-(?P<source>.*)\/recruiter\/jobdating\/interview\?")
RE_DATE = re.compile(r"DTSTART:(?P<date>.*)")
RE_CV_URL = re.compile(r"(Lien CV Candidat : )(?P<url>.*)\\nPour modifier ou supprimer")
RE_EMAIL = re.compile(r"Email : (?P<email>.*) \\nLien Profil Candidat")
RE_PHONE = re.compile(r"Téléphone : (?P<phone>\d+)")
RE_DESCRIPTION = re.compile(r"DESCRIPTION:(?P<description>(.|\n)*)LAST-MODIFIED")


@login_required
@require_http_methods(["GET", "POST"])
def import_seekube(request):
    if request.method == "GET":
        form = UploadSeekubeFileForm()

    else:
        form = UploadSeekubeFileForm(data=request.POST, files=request.FILES)

        if form.is_valid():
            try:
                file = request.FILES.get("file")
                content = file.read().decode("utf-8")
                description = RE_DESCRIPTION.search(content, re.MULTILINE).group("description")
                description = "".join([l.lstrip() for l in description.splitlines()])
                print(description)
                extracted_name = RE_NAME.search(content).group("name")
                extracted_source = RE_SOURCE.search(description).group("source")
                print(extracted_source)
                extracted_cv_url = RE_CV_URL.search(description).group("url")
                print(extracted_cv_url)
                extracted_date = RE_DATE.search(content).group("date").replace("Z", "+0000").strip()
                extracted_date = datetime.datetime.strptime(extracted_date, "%Y%m%dT%H%M%S%z")
                print(extracted_date)
                extracted_phone = RE_PHONE.search(description).group("phone")
                print(extracted_phone)
                extracted_email = RE_EMAIL.search(description).group("email")
                print(extracted_email)
                candidate = Candidate.objects.create(name=extracted_name, email=extracted_email, phone=extracted_phone)
                source, created = Sources.objects.get_or_create(
                    name=extracted_source, category=SourcesCategory.objects.get(id=settings.SEEKUBE_SOURCE_ID)
                )
                process = Process.objects.create(
                    candidate=candidate, subsidiary=request.user.consultant.company, sources=source
                )
                itw = Interview.objects.create(process=process, planned_date=extracted_date)
                itw.interviewers.add(request.user.consultant)
                cv_content = requests.get(extracted_cv_url).content
                ext = "." + extracted_cv_url.split(".")[-1]
                file_tmp = NamedTemporaryFile(delete=True, suffix=ext)
                file_tmp.write(cv_content)
                file_tmp.flush()
                Document.objects.create(document_type="CV", content=File(file_tmp), candidate=candidate)
                return HttpResponseRedirect(process.get_absolute_url())
            except Exception as e:
                print(e)
                form.add_error(None, _("Processing seekube ics failed"))

    return render(request, "interview/seekube_import.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def gantt(request):
    state_filter = Process.OPEN_STATE_VALUES + [Process.JOB_OFFER, Process.HIRED]
    today = datetime.date.today()
    processes = Process.objects.filter(state__in=state_filter).select_related("contract_type", "candidate")
    filter = ProcessFilter(request.GET, queryset=processes)

    processes_dict = []
    max_end_date = datetime.date.today()

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

    context = {"gantt": grant_chart, "filter": filter}

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


@login_required
@require_http_methods(["GET"])
def active_sources(request, subsidiary_id=None):
    subsidiary = None
    sources_qs = Sources.objects.filter(archived=False)
    if subsidiary_id:
        try:
            subsidiary = Subsidiary.objects.get(id=subsidiary_id)
            sources_qs = sources_qs.filter(process__subsidiary=subsidiary).distinct()
        except Subsidiary.DoesNotExist:
            pass

    data = []

    for s in sources_qs:
        total_processes = Process.objects.filter(sources=s)
        total_processes_count = total_processes.count()
        active_processes_count = Process.objects.filter(sources=s, state__in=Process.OPEN_STATE_VALUES).count()
        total_hired = Process.objects.filter(sources=s, state=Process.HIRED).count()
        last_state_change = Process.objects.filter(sources=s).aggregate(Max("last_state_change"))
        distinct_offers = Offer.objects.filter(process__in=Process.objects.filter(sources=s)).distinct().count()

        data.append(
            {
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
            }
        )

    sources_table = ActiveSourcesTable(data, order_by="-last_active_process_days")
    RequestConfig(request, paginate={"per_page": 100}).configure(sources_table)
    return render(
        request,
        "interview/active-sources.html",
        {"subsidiary": subsidiary, "subsidiaries": Subsidiary.objects.all(), "active_sources": sources_table},
    )


@login_required
@require_http_methods(["GET"])
def activity_summary(request):
    process_filter = ProcessSummaryFilter(request.GET, queryset=Process.objects.all())
    interview_filter = InterviewSummaryFilter(request.GET, queryset=Interview.objects.all())

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
    end_date = datetime.date.today()
    if process_filter.form.cleaned_data["last_state_change"]:
        if process_filter.form.cleaned_data["last_state_change"].start:
            start_date = process_filter.form.cleaned_data["last_state_change"].start
        if process_filter.form.cleaned_data["last_state_change"].stop:
            end_date = process_filter.form.cleaned_data["last_state_change"].stop
    subsidiary = process_filter.form.cleaned_data["subsidiary"]

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

    config = dict({"scrollZoom": False, "staticPlot": False, "showAxisRangeEntryBoxes": False, "displayModeBar": False})
    chart = plot(fig, output_type="div", config=config)

    plot_div = chart

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
            "plot_div": plot_div,
        },
    )
