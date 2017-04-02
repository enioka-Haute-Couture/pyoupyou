# -*- coding: utf-8 -*-
import datetime

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template import loader
from django.core import urlresolvers
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist

import django_tables2 as tables
from django_tables2 import RequestConfig
from django_tables2.utils import A

from interview.models import Process, Candidate, Document, Interview, InterviewInterviewer
from interview.forms import CandidateForm, InterviewForm, InterviewMinuteForm
from pyoupyou.settings import DOCUMENT_TYPE


class ProcessTable(tables.Table):
    edit = tables.LinkColumn('process-details', text="Détails", kwargs={"process_id": A('pk')}, orderable=False)
    late = tables.TemplateColumn("{% if record.is_late %} <b>LATE</b> {% endif %}")

    class Meta:
        model = Process
        attrs = {'class': 'paleblue'}
        sequence = ("candidate", "late", "subsidiary", "start_date", "contract_type", "edit")
        fields = sequence
        order_by = "start_date"


class InterviewTable(tables.Table):
    interviewers = tables.TemplateColumn("{{ record.interviewers }}")
    edit = tables.LinkColumn(text="Compte-rendu", viewname="interview-minute",
                             kwargs={"interview_id": A('id')})
    change = tables.LinkColumn(text="Éditer", viewname="interview-plan",
                               kwargs={"interview_id": A('id')})
    needs_attention = tables.TemplateColumn("{% if record.needs_attention %} <b>Attention</b> {% endif %}")

    class Meta:
        model = Interview
        attrs = {"class": "paleblue"}
        sequence = ("edit", "change", "needs_attention", "planned_date", "interviewers", "next_state")
        fields = sequence
        order_by = "planned_date"


def process(request, process_id):
    process = Process.objects.get(id=process_id)
    interviews = Interview.objects.filter(process=process)
    interviews_for_process_table = InterviewTable(interviews)
    RequestConfig(request).configure(interviews_for_process_table)

    documents = Document.objects.filter(candidate=process.candidate)
    context = {"process": process,
               "documents": documents,
               "interviews_for_process_table": interviews_for_process_table,
               "interviews": interviews}
    return render(request, "interview/process_detail.html", context)


def close_process(request, process_id):
    process_obj = Process.objects.get(id=process_id)
    process_obj.end_date = datetime.date.today()
    process_obj.save()
    return process(request, process_id)


def processes(request):
    open_processes = [p for p in Process.objects.all() if p.is_active]
    recently_closed_processes = Process.objects.filter(end_date__isnull=False).order_by("end_date")
    # TODO Slice recent processes
    # recently_closed_processes = recently_closed_processes[:5]

    open_processes_table = ProcessTable(open_processes)
    recently_closed_processes_table = ProcessTable(recently_closed_processes)

    RequestConfig(request).configure(open_processes_table)

    context = {"open_processes_table": open_processes_table,
               "recently_closed_processes_table": recently_closed_processes_table}
    return render(request, "interview/list_processes.html", context)


def new_candidate(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST)
        if form.is_valid():
            c = Candidate()
            c.name = form.cleaned_data["name"]
            c.email = form.cleaned_data["email"]
            c.phone = form.cleaned_data["phone"]

            c.save()
            if request.FILES and request.FILES["cv"] is not None:
                p = Process()
                p.candidate = c
                p.subsidiary = form.cleaned_data["subsidiary"]
                p.save()

                d = Document()
                d.candidate = c
                d.content = request.FILES["cv"]
                d.document_type = "CV"
                d.save()

            return HttpResponseRedirect(reverse(processes))
    else:
        form = CandidateForm()
    return render(request, "interview/new_candidate.html", {'form': form})


def interview(request, process_id=None, interview_id=None):
    form = None
    interview = None
    if request.method == 'POST':
        form = InterviewForm(request.POST)
        if form.is_valid():
            if interview_id is not None:
                interview = Interview.objects.get(id=interview_id)
            else:
                interview = Interview()
                interview.process = Process.objects.get(id=process_id)

            if process_id is None:
                process = interview.process
            else:
                process = Process.objects.get(id=process_id)
                interview.process = process

            interview.planned_date = form.cleaned_data["date"]

            interview.save()
            try:
                previous_interview_interviewer = InterviewInterviewer.objects.get(interview=interview)
                # TODO : do not change that if state has been set to go/no go , done*
                # if
                # previous_interview_interviewer.interview.next_state
                # is not None and
                # previous_interview_interviewer.interview.next_state
                # in
                previous_interview_interviewer.delete()
            except ObjectDoesNotExist:
                pass

            interview_interviewer = InterviewInterviewer(interviewer=form.cleaned_data["interviewer"],
                                                         interview=interview)
            interview_interviewer.save()
            return HttpResponseRedirect(reverse(viewname="process-details",
                                                kwargs={"process_id": process.id}))
        else:
            return render(request, "interview/interview.html", {'form': form,
                                                      "interview": interview,
                                                      "process": process})
    else:
        interviewInterviewer = None
        if interview_id is not None:
            interview = Interview.objects.get(id=interview_id)
            interviewInterviewer = InterviewInterviewer.objects.filter(interview=interview).first()
        else:
            interview = Interview()
            interview.process = Process.objects.get(id=process_id)
            interview.planned_date = datetime.date.today()

        interviewer = interviewInterviewer.interviewer if interviewInterviewer else None
        form = InterviewForm(initial={"date": interview.planned_date,
                                      "process": interview.process,
                                      "interviewer": interviewer})

    if process_id is None:
        process = interview.process
    else:
        process = Process.objects.get(id=process_id)

    return render(request, "interview/interview.html", {'form': form,
                                              "interview": interview,
                                              "process": process})


def minute(request, interview_id=None):
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

    interview = Interview.objects.get(id=interview_id)
    interview_interviewer = None
    if interview_id is not None:
        interview = Interview.objects.get(id=interview_id)
        try:
            interview_interviewer = InterviewInterviewer.objects.get(interview=interview)
        except ObjectDoesNotExist:
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
