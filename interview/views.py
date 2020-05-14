# -*- coding: utf-8 -*-
import datetime
import re

import requests
from django.conf import settings

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.core.management import call_command
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseNotFound, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.six import StringIO
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import ugettext as _
from django.db import transaction

from django.views.decorators.http import require_http_methods
from django_tables2 import RequestConfig
import django_tables2 as tables

from interview.models import Process, Document, Interview, Sources, SourcesCategory, Candidate
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
)

from ref.models import Consultant, Subsidiary


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
def process(request, process_id):
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
def new_candidate(request):
    if request.method == "POST":
        candidate_form = ProcessCandidateForm(data=request.POST, files=request.FILES)
        process_form = ProcessForm(data=request.POST)
        if candidate_form.is_valid() and process_form.is_valid():
            candidate = candidate_form.save()
            content = request.FILES.get("cv", None)
            if content:
                Document.objects.create(document_type="CV", content=content, candidate=candidate)
            process = process_form.save(commit=False)
            process.candidate = candidate
            process.save()
            return HttpResponseRedirect(reverse(processes))
    else:
        candidate_form = ProcessCandidateForm()
        process_form = ProcessForm()
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
            interview = Interview.objects.for_user(request.user).get(id=interview_id)
            if action in ["plan", "planning-request"] and request.user.consultant not in interview.interviewers.all():
                return HttpResponseNotFound()

        except Interview.DoesNotExist:
            return HttpResponseNotFound()
    else:
        interview = Interview(process_id=process_id)

    InterviewForm = InterviewFormEditInterviewers if action == "edit" else InterviewFormPlan
    if request.method == "POST":
        ret = HttpResponseRedirect(reverse(viewname="process-details", kwargs={"process_id": process_id}))
        if action == "planning-request":
            interview.toggle_planning_request()
            return ret
        form = InterviewForm(request.POST, instance=interview)
        if form.is_valid():
            form.save()
            return ret
    else:
        form = InterviewForm(instance=interview)

    process = Process.objects.for_user(request.user).get(id=process_id)

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
        form = InterviewMinuteForm(request.POST, instance=interview)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse(viewname="interview-minute", kwargs={"interview_id": interview.id}))
    else:
        form = InterviewMinuteForm(instance=interview)

    return render(
        request,
        "interview/interview_minute_form.html",
        {"form": form, "process": interview.process, "interview": interview},
    )


@login_required
@require_http_methods(["GET"])
def minute(request, interview_id):
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
        data = {}
        return JsonResponse(data)
    else:
        data = {"error": form.errors}
        return JsonResponse(data)


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
            content = request.FILES.get("cv", None)
            if content:
                Document.objects.create(document_type="CV", content=content, candidate=candidate)
            process_form.id = process.id
            process = process_form.save(commit=False)
            process.save()
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
    out = StringIO()
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


@login_required
@require_http_methods(["GET"])
def export_interviews_tsv(request):
    interviews = Interview.objects.for_user(request.user)
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
                "contract_type",
                "contract_start_date",
                "contract_duration",
                "process state",
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
    for interview in interviews:
        interviewers = ""
        for i in interview.interviewers.all():
            interviewers += i.user.trigramme + "_"
        interviewers = interviewers[:-1]

        # Compute process length (in days)
        process_length = 0
        end_date = None
        if interview.process.end_date:
            end_date = interview.process.end_date
        else:
            last_interview = Interview.objects.filter(process=interview.process).order_by("planned_date").last()
            if last_interview is None or last_interview.planned_date is None:
                end_date = datetime.datetime.now().date()
            else:
                end_date = last_interview.planned_date.date()
        process_length = end_date - interview.process.start_date
        process_length = process_length.days

        # Compute time elapsed since last event (previous interview or beginning of process)
        time_since_last_is_sound = True
        last_event_date = interview.process.start_date
        next_event_date = None
        if interview.rank > 1:
            last_itw = Interview.objects.filter(process=interview.process, rank=interview.rank - 1).first()
            if last_itw.planned_date is not None:
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
            interview.process.contract_type,
            interview.process.contract_start_date,
            interview.process.contract_duration,
            interview.process.state,
            Interview.objects.filter(process=interview.process).count(),
            int(process_length / Interview.objects.filter(process=interview.process).count()),
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


#
# def import_seekube_validate(request):
