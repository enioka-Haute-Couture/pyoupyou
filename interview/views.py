# -*- coding: utf-8 -*-
import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.db import transaction

import django_tables2 as tables
from django.views.decorators.http import require_http_methods
from django_tables2 import RequestConfig

from interview.models import Process, Document, Interview, Candidate
from interview.forms import ProcessCandidateForm, InterviewMinuteForm, ProcessForm, InterviewFormPlan, \
    InterviewFormEditInterviewers, SourceForm, CandidateForm, CloseForm

from ref.models import Consultant


class ProcessTable(tables.Table):
    needs_attention = tables.TemplateColumn(template_name='interview/tables/needs_attention_cell.html',
                                            verbose_name="", orderable=False)
    next_action_display = tables.Column(verbose_name=_("Next action"), orderable=False)
    next_action_responsible = tables.Column(orderable=False)
    actions = tables.TemplateColumn(verbose_name='', orderable=False,
                                    template_name='interview/tables/process_actions.html')
    candidate = tables.Column(attrs={"td": {"style": "font-weight: bold"}}, order_by=('candidate__name',))
    contract_type = tables.Column(order_by=('contract_type__name',))

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


class InterviewTable(tables.Table):
    #rank = tables.Column(verbose_name='#')
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
    process = Process.objects.get(id=process_id)
    interviews = Interview.objects.filter(process=process).prefetch_related('process__candidate', 'interviewers')
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
    process = Process.objects.get(pk=process_id)
    form = CloseForm(request.POST, instance=process)
    if form.is_valid():
        form.instance.end_date = datetime.date.today()
        form.save()
    # TODO manage errors
    return HttpResponseRedirect(process.get_absolute_url())


@login_required
@require_http_methods(["GET"])
def reopen_process(request, process_id):
    process = Process.objects.get(id=process_id)
    process.end_date = None
    process.closed_reason = Process.OPEN
    process.closed_comment = ''
    process.save()
    return HttpResponseRedirect(process.get_absolute_url())


@login_required
@require_http_methods(["GET"])
def closed_processes(request):
    closed_processes = Process.objects.filter(end_date__isnull=False).select_related('candidate', 'contract_type')

    closed_processes_table = ProcessTable(closed_processes, prefix='c')

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
    open_processes = [p for p in Process.objects.all() if p.is_active]
    recently_closed_processes = Process.objects.filter(end_date__isnull=False).order_by("end_date")

    open_processes_table = ProcessTable(open_processes, prefix='o')
    recently_closed_processes_table = ProcessTable(recently_closed_processes, prefix='c')

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
            Document.objects.create(document_type='CV',
                                    content=request.FILES["cv"],
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
        interview = Interview.objects.get(id=interview_id)
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

    process = Process.objects.get(id=process_id)

    return render(request, "interview/interview.html", {'form': form,
                                                        'process': process})


@login_required
@require_http_methods(["GET", "POST"])
def minute(request, interview_id):
    interview = Interview.objects.get(id=interview_id)
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

    return render(request, "interview/interview_minute.html", {'form': form,
                                                               "process": interview.process,
                                                               "interview": interview})


@login_required
@require_http_methods(["GET"])
def dashboard(request):
    related_processes = Process.objects.filter(interview__interviewers__user=request.user).distinct()
    related_processes_table = ProcessTable(related_processes, prefix='r')

    subsidiary_processes = Process.objects.filter(subsidiary=request.user.consultant.company)
    subsidiary_processes_table = ProcessTable(subsidiary_processes, prefix='s')

    config = RequestConfig(request)
    config.configure(related_processes_table)
    config.configure(subsidiary_processes_table)

    context = {"subsidiary_processes_table": subsidiary_processes_table,
               "related_processes_table": related_processes_table}

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
def edit_candidate(request, candidate_id):
    candidate = Candidate.objects.get(pk=candidate_id)

    if request.method == 'POST':
        form = CandidateForm(request.POST, instance=candidate)
        if form.is_valid():
            form.instance.id = candidate_id
            form.save()
            return HttpResponseRedirect(candidate.process_set.last().get_absolute_url())
    else:
        form = CandidateForm(instance=candidate)
    return render(request, "interview/candidate.html", {"form": form})
