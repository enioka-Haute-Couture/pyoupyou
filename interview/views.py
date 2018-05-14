# -*- coding: utf-8 -*-
import datetime

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseNotFound, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.six import StringIO
from django.utils.translation import ugettext as _
from django.db import transaction

import django_tables2 as tables
from django.views.decorators.http import require_http_methods
from django_tables2 import RequestConfig

from interview.models import Process, Document, Interview
from interview.forms import ProcessCandidateForm, InterviewMinuteForm, ProcessForm, InterviewFormPlan, \
    InterviewFormEditInterviewers, SourceForm, CloseForm

from ref.models import Consultant


class ProcessTable(tables.Table):
    needs_attention = tables.TemplateColumn(template_name='interview/tables/needs_attention_cell.html',
                                            verbose_name="", orderable=False)
    next_action_display = tables.Column(verbose_name=_("Next action"), orderable=False)
    next_action_responsible = tables.Column(verbose_name=_("Next action responsible"), orderable=False)
    actions = tables.TemplateColumn(verbose_name='', orderable=False,
                                    template_name='interview/tables/process_actions.html')
    candidate = tables.Column(attrs={"td": {"style": "font-weight: bold"}}, order_by=('candidate__name',))
    contract_type = tables.Column(order_by=('contract_type__name',))
    current_rank = tables.Column(verbose_name=_("No itw"), orderable=False)

    def render_next_action_responsible(self, value):
        if isinstance(value, Consultant):
            return value
        return ', '.join(str(c) for c in value.all())

    class Meta:
        model = Process
        template = 'interview/_tables.html'
        attrs = {'class': 'table table-striped table-condensed'}
        sequence = (
            "needs_attention",
            "current_rank",
            "candidate",
            "subsidiary",
            "start_date",
            "contract_type",
            "next_action_display",
            "next_action_responsible",
            "actions"
        )
        fields = sequence
        order_by = "start_date"
        empty_text = _('No data')
        row_attrs = {
            'class': lambda record: 'danger' if record.needs_attention_bool else None
        }


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
            "next_action_display",
            "next_action_responsible",
            "actions"
        )
        fields = sequence
        order_by = "-end_date"


class InterviewTable(tables.Table):
    # rank = tables.Column(verbose_name='#')
    actions = tables.TemplateColumn(verbose_name='', orderable=False,
                                    template_name='interview/tables/interview_actions.html')
    needs_attention = tables.TemplateColumn(template_name='interview/tables/needs_attention_cell.html',
                                            verbose_name="", orderable=False)

    def render_interviewers(self, value):
        return ', '.join(str(c) for c in value.all())

    class Meta:
        model = Interview
        template = 'interview/_tables.html'
        attrs = {"class": "table table-striped table-condensed"}
        sequence = ("needs_attention", "interviewers", "planned_date", "next_state", "actions")
        fields = sequence
        order_by = "id"
        empty_text = _('No data')
        row_attrs = {
            'class': lambda record: 'danger' if record.needs_attention_bool else None
        }


@login_required
@require_http_methods(["GET"])
def process(request, process_id):
    try:
        process = Process.objects.for_user(request.user).get(id=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()
    interviews = Interview.objects.for_user(request.user).filter(process=process).prefetch_related('process__candidate',
                                                                                                   'interviewers')
    interviews_for_process_table = InterviewTable(interviews)
    RequestConfig(request).configure(interviews_for_process_table)
    close_form = CloseForm(instance=process)

    documents = Document.objects.filter(candidate=process.candidate)
    context = {"process": process,
               "documents": documents,
               "interviews_for_process_table": interviews_for_process_table,
               "interviews": interviews,
               "close_form": close_form}
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
    process.closed_reason = Process.OPEN
    process.closed_comment = ''
    process.save()
    return HttpResponseRedirect(process.get_absolute_url())


@login_required
@require_http_methods(["GET"])
def closed_processes(request):
    closed_processes = Process.objects.for_user(request.user).filter(end_date__isnull=False).select_related('candidate',
                                                                                                            'contract_type')

    closed_processes_table = ProcessEndTable(closed_processes, prefix='c')

    config = RequestConfig(request)
    config.configure(closed_processes_table)

    context = {
        'title': _('Closed processes'),
        'table': closed_processes_table,
    }

    return render(request, "interview/single_table.html", context)


@login_required
@require_http_methods(["GET"])
def processes(request):
    open_processes = Process.objects.for_user(request.user).filter(closed_reason=Process.OPEN)
    a_week_ago = datetime.date.today() - datetime.timedelta(days=7)
    recently_closed_processes = Process.objects.for_user(request.user).filter(end_date__gte=a_week_ago)

    open_processes_table = ProcessTable(open_processes, prefix='o')
    recently_closed_processes_table = ProcessEndTable(recently_closed_processes, prefix='c')

    config = RequestConfig(request)
    config.configure(open_processes_table)
    config.configure(recently_closed_processes_table)

    context = {"open_processes_table": open_processes_table,
               "recently_closed_processes_table": recently_closed_processes_table}
    return render(request, "interview/list_processes.html", context)


@login_required
def new_candidate(request):
    if request.method == 'POST':
        candidate_form = ProcessCandidateForm(data=request.POST, files=request.FILES)
        process_form = ProcessForm(data=request.POST)
        if candidate_form.is_valid() and process_form.is_valid():
            candidate = candidate_form.save()
            content = request.FILES.get('cv', None)
            if content:
                Document.objects.create(document_type='CV',
                                        content=content,
                                        candidate=candidate)
            process = process_form.save(commit=False)
            process.candidate = candidate
            process.save()
            return HttpResponseRedirect(reverse(processes))
    else:
        candidate_form = ProcessCandidateForm()
        process_form = ProcessForm()
    source_form = SourceForm(prefix='source')
    return render(request, "interview/new_candidate.html", {"candidate_form": candidate_form,
                                                            "process_form": process_form,
                                                            "source_form": source_form})


@require_http_methods(["GET", "POST"])
@login_required
@transaction.atomic
def interview(request, process_id=None, interview_id=None, action=None):
    """
    Insert or update an interview. Date and Interviewers
    """
    InterviewForm = InterviewFormEditInterviewers if action == "edit" else InterviewFormPlan
    if interview_id is not None:
        try:
            interview = Interview.objects.for_user(request.user).get(id=interview_id)
        except Interview.DoesNotExist:
            return HttpResponseNotFound()
    else:
        interview = Interview(process_id=process_id)
    if request.method == 'POST':
        form = InterviewForm(request.POST, instance=interview)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse(viewname="process-details",
                                                kwargs={"process_id": process_id}))
    else:
        form = InterviewForm(instance=interview)

    process = Process.objects.for_user(request.user).get(id=process_id)

    return render(request, "interview/interview.html", {'form': form,
                                                        'process': process})


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
    if request.method == 'POST':
        if 'itw-go' in request.POST:
            interview.next_state = Interview.GO
        elif 'itw-no' in request.POST:
            interview.next_state = Interview.NO_GO
        form = InterviewMinuteForm(request.POST, instance=interview)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse(viewname="process-details",
                                                kwargs={"process_id": interview.process.id}))
    else:
        form = InterviewMinuteForm(instance=interview)

    return render(request, "interview/interview_minute_form.html", {'form': form,
                                                                    "process": interview.process,
                                                                    "interview": interview})


@login_required
@require_http_methods(["GET"])
def minute(request, interview_id):
    try:
        interview = Interview.objects.for_user(request.user).get(id=interview_id)
    except Interview.DoesNotExist:
        return HttpResponseNotFound()

    context = {'interview': interview,
               'process': interview.process}
    return render(request, "interview/interview_minute.html", context)


@login_required
@require_http_methods(["GET"])
def dashboard(request):
    a_week_ago = datetime.date.today() - datetime.timedelta(days=7)
    actions_needed_processes = Process.objects.for_user(request.user).filter(
        closed_reason=Process.OPEN).prefetch_related('interview_set__interviewers').select_related(
        'subsidiary__responsible')
    c = request.user.consultant
    actions_needed_processes = [
        p for p in actions_needed_processes
        if p.next_action_responsible == c
           or (hasattr(p.next_action_responsible, 'iterator')
               and c in p.next_action_responsible.iterator())
    ]
    actions_needed_processes_table = ProcessTable(actions_needed_processes, prefix='a')

    related_processes = Process.objects.for_user(request.user).filter(interview__interviewers__user=request.user). \
        filter(Q(end_date__gte=a_week_ago) | Q(closed_reason=Process.OPEN)).distinct()
    related_processes_table = ProcessTable(related_processes, prefix='r')

    subsidiary_processes = Process.objects.for_user(request.user). \
        filter(Q(end_date__gte=a_week_ago) | Q(closed_reason=Process.OPEN)).filter(
        subsidiary=request.user.consultant.company)
    subsidiary_processes_table = ProcessTable(subsidiary_processes, prefix='s')

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
    form = SourceForm(request.POST, prefix='source')
    if form.is_valid():
        form.save()
        data = {}
        return JsonResponse(data)
    else:
        data = {'error': form.errors}
        return JsonResponse(data)


@login_required
@require_http_methods(["GET", "POST"])
def edit_candidate(request, process_id):
    try:
        process = Process.objects.for_user(request.user).select_related('candidate').get(id=process_id)
    except Process.DoesNotExist:
        return HttpResponseNotFound()
    candidate = process.candidate

    if request.method == 'POST':
        candidate_form = ProcessCandidateForm(data=request.POST, files=request.FILES, instance=candidate)
        process_form = ProcessForm(data=request.POST, instance=process)

        if candidate_form.is_valid() and process_form.is_valid():
            candidate_form.id = candidate.id
            candidate = candidate_form.save()
            content = request.FILES.get("cv", None)
            if content:
                Document.objects.create(document_type='CV',
                                        content=content,
                                        candidate=candidate)
            process_form.id = process.id
            process = process_form.save(commit=False)
            process.save()
            return HttpResponseRedirect(process.get_absolute_url())
    else:
        candidate_form = ProcessCandidateForm(instance=candidate)
        process_form = ProcessForm(instance=process)
    source_form = SourceForm(prefix='source')
    data = {
        'process': process,
        'candidate_form': candidate_form,
        'process_form': process_form,
        'source_form': source_form,
    }
    return render(request, "interview/new_candidate.html", data)


@user_passes_test(lambda u: u.is_active and u.is_superuser)
def dump_data(request):
    out = StringIO()
    call_command('dumpdata', use_natural_foreign_keys=True, use_base_manager=True, stdout=out)
    response = HttpResponse(out.getvalue(), content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename=dump.json'
    return response

@login_required
@require_http_methods(["GET"])
def export_interviews_tsv(request):
    interviews = Interview.objects.for_user(request.user)
    ret = []

    ret.append("\t".join(str(x).replace("\t", " ") for x in ["process.id",
                                                             "candidate.name",
                                                             "subsidiary",
                                                             "start_date",
                                                             "end_date",
                                                             "process length",
                                                             "sources",
                                                             "contract_type",
                                                             "process closed_reason",
                                                             "process itw count",
                                                             "mean days between itws",
                                                             "interview.id",
                                                             "next_state",
                                                             "interviewers",
                                                             "interview rank",
                                                             "days since last",
                                                             "planned_date"]))
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
            last_itw = Interview.objects.filter(process=interview.process,
                                                rank=interview.rank - 1).first()
            if last_itw.planned_date is not None:
                last_event_date = last_itw.planned_date.date()
            else:
                print("Past interview without date: {}".format(last_itw.id))
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

        ret.append("\t".join(str(x).replace("\t", " ") for x in [interview.process.id,
                                                                 interview.process.candidate.name,
                                                                 interview.process.subsidiary,
                                                                 interview.process.start_date,
                                                                 interview.process.end_date,
                                                                 process_length,
                                                                 interview.process.sources,
                                                                 interview.process.contract_type,
                                                                 interview.process.closed_reason,
                                                                 Interview.objects.filter(process=interview.process).count(),
                                                                 int(process_length/Interview.objects.filter(process=interview.process).count()),
                                                                 interview.id,
                                                                 interview.next_state,
                                                                 interviewers,
                                                                 interview.rank,
                                                                 time_since_last_event,
                                                                 interview.planned_date]))

    response = HttpResponse("\n".join(ret), content_type='text/plain; charset=utf-8')
    response["Content-Disposition"] = 'attachment; filename=all_interviews.tsv'
    return response
