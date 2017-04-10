# -*- coding: utf-8 -*-
import datetime

from django.contrib.auth.decorators import login_required
from django.forms import inlineformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext as _

import django_tables2 as tables
from django.views.decorators.http import require_http_methods
from django_tables2 import RequestConfig

from interview.models import Process, Candidate, Document, Interview, InterviewInterviewer
from interview.forms import CandidateForm, InterviewForm, InterviewMinuteForm, ProcessForm
from pyoupyou.settings import DOCUMENT_TYPE

from ref.models import Consultant

# move to file

PROCESS_TABLE_ACTIONS = '<a class="btn btn-info btn-xs" href="{% url \'process-details\' process_id=record.pk %}">' \
                        '<i class="fa fa-folder-open" aria-hidden="true"></i> Show' \
                        '</a>'

INTERVIEW_TABLE_ACTIONS = '<a class="btn btn-info btn-xs" href="{% url \'interview-minute\' interview_id=record.pk %}">' \
                          '<i class="fa fa-file-text-o" aria-hidden="true"></i> Compte-Rendu' \
                          '</a>&nbsp;' \
                          '<a class="btn btn-info btn-xs" href="{% url \'interview-plan\' record.process_id record.pk %}">' \
                          '<i class="fa fa-pencil-square-o" aria-hidden="true"></i> Edit' \
                          '</a>'

class ProcessTable(tables.Table):
    needs_attention = tables.TemplateColumn("{% if record.needs_attention_bool %} <p class='glyphicon glyphicon-warning-sign' title='{{ record.needs_attention_reason }}'></p> {% endif %}",
                                 verbose_name="", orderable=False)
    next_action_display = tables.Column(verbose_name=_("Next action"))
    actions = tables.TemplateColumn(verbose_name='', orderable=False, template_code=PROCESS_TABLE_ACTIONS)

    def render_next_action_responsible(self, value):
        if isinstance(value, Consultant):
            return value
        return ', '.join(str(c) for c in value.all())
    class Meta:
        model = Process
        template = 'interview/_tables.html'
        attrs = {'class': 'table table-striped table-condensed'}
        sequence = ("needs_attention", "candidate", "subsidiary", "start_date", "contract_type", "next_action_display", "next_action_responsible", "actions")
        fields = sequence
        order_by = "start_date"
        empty_text = _('No data')
        row_attrs = {
            'class': lambda record: 'danger' if record.needs_attention_bool else None
        }

class InterviewTable(tables.Table):
    #rank = tables.Column(verbose_name='#')
    actions = tables.TemplateColumn(verbose_name='', orderable=False, template_code=INTERVIEW_TABLE_ACTIONS)
    needs_attention = tables.TemplateColumn("{% if record.needs_attention_bool %} <p class='glyphicon glyphicon-warning-sign' title='{{ record.needs_attention_reason }}'></p> {% endif %}",
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
def process(request, process_id):
    process = Process.objects.get(id=process_id)
    interviews = Interview.objects.filter(process=process).prefetch_related('process__candidate', 'interviewers')
    interviews_for_process_table = InterviewTable(interviews)
    RequestConfig(request).configure(interviews_for_process_table)

    documents = Document.objects.filter(candidate=process.candidate)
    context = {"process": process,
               "documents": documents,
               "interviews_for_process_table": interviews_for_process_table,
               "interviews": interviews}
    return render(request, "interview/process_detail.html", context)


@login_required
def close_process(request, process_id):
    process_obj = Process.objects.get(id=process_id)
    process_obj.end_date = datetime.date.today()
    process_obj.save()
    return process(request, process_id)


@login_required
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
        candidate_form = CandidateForm(data=request.POST, files=request.FILES)
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
        candidate_form = CandidateForm()
        process_form = ProcessForm()
    return render(request, "interview/new_candidate.html", {"candidate_form": candidate_form, "process_form": process_form})


@require_http_methods(["GET", "POST"])
@login_required
def interview(request, process_id=None, interview_id=None):
    """
    Insert or update an interview. Date and Interviewers
    """
    if request.method == 'POST':
        form = InterviewForm(request.POST)

        if form.is_valid():
            interview, created = Interview.objects.update_or_create(id=interview_id,
                                                                    process_id=process_id,
                                                                    planned_date=form.cleaned_data["planned_date"])
            interviewers = form.cleaned_data["interviewers"]
            # TODO manage to allow to delete not only add
            for interviewer in interviewers.all():
                InterviewInterviewer.objects.get_or_create(interview=interview, interviewer=interviewer)

            return HttpResponseRedirect(reverse(viewname="process-details",
                                                kwargs={"process_id": process_id}))

    else:

        if interview_id is not None:
            interview = Interview.objects.get(id=interview_id)
        else:
            interview = Interview()
            interview.process_id = process_id
            interview.planned_date = datetime.date.today()

        form = InterviewForm(instance=interview)

    process = Process.objects.get(id=process_id)

    return render(request, "interview/interview.html", {'form': form,
                                                        'process': process})


@login_required
def minute(request, interview_id):
    interview = None
    if request.method == 'POST':
        form = InterviewMinuteForm(request.POST)
        interview = Interview.objects.get(id=interview_id)
        if form.is_valid():
            interviewInterviewer = InterviewInterviewer.objects.filter(interview=interview).first()
            interview.planned_date = form.cleaned_data["date"]
            interview.next_state = form.cleaned_data["next_state"]
            interviewInterviewer.minute = form.cleaned_data["minute"]
            interview.save()
            interviewInterviewer.save()
            return HttpResponseRedirect(reverse(viewname="process-details",
                                                kwargs={"process_id": interview.process.id}))

    interview_interviewer = None
    if interview_id is not None:
        interview = Interview.objects.get(id=interview_id)
        try:
            interview_interviewer = InterviewInterviewer.objects.get(interview=interview)
        except InterviewInterviewer.DoesNotExist:
            pass
        if interview_interviewer is not None:
            minute = interview_interviewer.minute
            interviewer = interview_interviewer.interviewer
        else:
            minute = None
            interviewer = None
        form = InterviewMinuteForm(initial={"date": interview.planned_date,
                                            "process": interview.process,
                                            "minute": minute,
                                            "next_state": interview.next_state,
                                            "interviewer": interviewer})

    return render(request, "interview/interview_minute.html", {'form': form,
                                                     "process": interview.process,
                                                     "interview": interview})


@login_required
def dashboard(request):
    related_processes = Process.objects.filter(interview__interviewinterviewer__interviewer__user=request.user).distinct()
    related_processes_table = ProcessTable(related_processes)

    subsidiary_processes = Process.objects.filter(subsidiary=request.user.consultant.company)
    subsidiary_processes_table = ProcessTable(subsidiary_processes)

    # RequestConfig(request).configure(open_processes_table)

    context = {"subsidiary_processes_table": subsidiary_processes_table,
               "related_processes_table": related_processes_table}

    return render(request, "interview/dashboard.html", context)
