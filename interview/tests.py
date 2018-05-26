from django.test import TestCase, RequestFactory
import datetime

from django.urls import reverse

from interview.factory import ProcessFactory, InterviewFactory
from interview.models import Process, Document, Interview, Candidate

import pytz

from interview.views import process, minute_edit, minute, interview, close_process, reopen_process
from ref.factory import SubsidiaryFactory, ConsultantFactory
from ref.models import Consultant
from django.utils.translation import ugettext_lazy as _


# class InterviewTestCase(TestCase):
#     def test_new_interview_state_equals_need_plannification(self):
#         p = ProcessFactory()
#         i1 = Interview(process_id=p.id)
#         i1.save()
#         self.assertEqual(Interview.WAITING_PLANIFICATION, i1.state)
#
#     def test_set_interview_date_state_equals_planned(self):
#         p = ProcessFactory()
#         i1 = Interview(process_id=p.id)
#         i1.save()
#         i1.planned_date = datetime.datetime.now(pytz.timezone("Europe/Paris"))
#         i1.save()
#         self.assertEqual(Interview.PLANNED, i1.state)
#
#     def test_interview_replanned_after_state_set_keeps_state(self):
#         p = ProcessFactory()
#         i1 = Interview(process_id=p.id)
#         i1.save()
#         i1.planned_date = datetime.datetime.now(pytz.timezone("Europe/Paris"))
#         i1.save()
#         i1.state = Interview.GO
#         i1.save()
#         self.assertEqual(Interview.GO, i1.state)


class AccessRestrictionDateTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        sub = SubsidiaryFactory()
        self.consultantOld = Consultant.objects.create_consultant('OLD', 'old@mail.com', sub, 'OLD')
        sub.responsible = self.consultantOld
        sub.responsible.save()
        userOld = self.consultantOld.user
        userOld.date_joined = datetime.date(2016, 1, 1)
        userOld.save()
        self.consultantNew = Consultant.objects.create_consultant('NEW', 'new@mail.com', sub, 'NEW')
        userNew = self.consultantNew.user
        userNew.date_joined = datetime.date(2017, 11, 1)
        userNew.save()

        self.p = ProcessFactory()
        self.p.start_date = datetime.date(2016, 10, 10)
        self.p.save()
        self.i = InterviewFactory(process=self.p)
        self.i.interviewers = [self.consultantOld, self.consultantNew]
        self.i.save()

    def test_view_process(self):
        request = self.factory.get(reverse('process-details', kwargs={'process_id': self.p.id}))

        request.user = self.consultantOld.user
        response = process(request, self.p.id)
        self.assertEqual(response.status_code, 200)

        request.user = self.consultantNew.user
        response = process(request, self.p.id)
        self.assertEqual(response.status_code, 404)

    def test_view_close_process(self):
        request = self.factory.post(reverse('process-close', kwargs={'process_id': self.p.id}))

        request.user = self.consultantNew.user
        response = close_process(request, self.p.id)
        self.assertEqual(response.status_code, 404)

    def test_view_reopen_process(self):
        request = self.factory.get(reverse('process-reopen', kwargs={'process_id': self.p.id}))

        request.user = self.consultantNew.user
        response = reopen_process(request, self.p.id)
        self.assertEqual(response.status_code, 404)

    def test_view_interview_plan(self):
        request = self.factory.post(
            reverse('interview-plan', kwargs={'process_id': self.p.id, 'interview_id': self.i.id}))

        request.user = self.consultantNew.user
        response = interview(request, self.p.id, self.i.id, "plan")
        self.assertEqual(response.status_code, 404)

    def test_view_interview_edit(self):
        request = self.factory.post(
            reverse('interview-edit', kwargs={'process_id': self.p.id, 'interview_id': self.i.id}))

        request.user = self.consultantNew.user
        response = interview(request, self.p.id, self.i.id, "edit")
        self.assertEqual(response.status_code, 404)

    def test_view_interview_minute_form(self):
        request = self.factory.get(reverse('interview-minute-edit', kwargs={'interview_id': self.i.id}))

        request.user = self.consultantOld.user
        response = minute_edit(request, self.i.id)
        self.assertEqual(response.status_code, 200)

        request.user = self.consultantNew.user
        response = minute_edit(request, self.i.id)
        self.assertEqual(response.status_code, 404)

    def test_view_interview_minute(self):
        request = self.factory.get(reverse('interview-minute', kwargs={'interview_id': self.i.id}))

        request.user = self.consultantOld.user
        response = minute(request, self.i.id)
        self.assertEqual(response.status_code, 200)

        request.user = self.consultantNew.user
        response = minute(request, self.i.id)
        self.assertEqual(response.status_code, 404)


class AccessRestrictionUserTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        sub = SubsidiaryFactory()
        self.consultantItw = Consultant.objects.create_consultant('ITW', 'itw@mail.com', sub, 'ITW')
        self.consultantRestricted = Consultant.objects.create_consultant('RES', 'res@mail.com', sub, 'RES')

        self.p = ProcessFactory()
        self.i = InterviewFactory(process=self.p)
        self.i.interviewers = [self.consultantItw, ]
        self.i.save()

    def test_only_assigned_user_can_edit_minute(self):
        request = self.factory.get(reverse('interview-minute-edit', kwargs={'interview_id': self.i.id}))

        request.user = self.consultantItw.user
        response = minute_edit(request, self.i.id)
        self.assertEqual(response.status_code, 200)

        request.user = self.consultantRestricted.user
        response = minute_edit(request, self.i.id)
        self.assertEqual(response.status_code, 404)


class StatusAndNotificationTestCase(TestCase):
    def test_status_and_notification(self):
        subsidiary = SubsidiaryFactory()
        subsidiaryResponsible = ConsultantFactory(company=subsidiary)
        subsidiary.responsible = subsidiaryResponsible
        subsidiary.save()
        interviewer = ConsultantFactory(company=subsidiary)

        # When we create a process
        # Process state will be: WAITING_INTERVIEWER_TO_BE_DESIGNED
        # Action responsible will be: Subsidiary responsible
        # Mail will be sent to global HR
        p = ProcessFactory(subsidiary=subsidiary)
        self.assertEqual(p.state, Process.WAITING_INTERVIEWER_TO_BE_DESIGNED)
        self.assertEqual(list(p.responsible.all()), [subsidiaryResponsible,])
        # TODO check mail global HR

        # When we create an interview
        # Process state will be: WAITING_INTERVIEW_PLANIFICATION
        # Interview state will be: WAITING_PLANIFICATION
        # Action responsible will be: Interviewer
        # Mail will be sent to global HR and interviewer
        i1 = Interview(process_id=p.id)
        i1.save()

        i1.interviewers.add(interviewer)
        i1.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.WAITING_INTERVIEW_PLANIFICATION)
        self.assertEqual(i1.state, Interview.WAITING_PLANIFICATION)
        self.assertEqual(list(p.responsible.all()), [interviewer,])
        # TODO check mail global HR and interviewer

        # After interview planification
        # Process state will be: INTERVIEW_IS_PLANNED
        # Interview state will be: PLANNED
        # Action responsible will be: Interviewer
        # Mail will be sent to global HR and interviewer if more than one
        i1.planned_date = datetime.datetime.now() + datetime.timedelta(days=7)
        i1.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.INTERVIEW_IS_PLANNED)
        self.assertEqual(i1.state, Interview.PLANNED)
        self.assertEqual(list(p.responsible.all()), [interviewer,])
        # TODO assert notification recrutement team

        # When ITW date is in the past cron will set state to WAIT_INFORMATION for the interview and indirectly to
        # WAITING_ITW_MINUTE (WM) for the process
        i1.state = Interview.WAIT_INFORMATION
        i1.save()
        self.assertEqual(i1.state, Interview.WAIT_INFORMATION)
        self.assertEqual(Process.objects.get(id=p.id).state, Process.WAITING_ITW_MINUTE)
        self.assertEqual(list(p.responsible.all()), [interviewer,])

        # After Go/No Go
        # Process state will be: WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
        # Interview state will be: GO or NO_GO
        # Action responsible will be: Subsidiary responsible
        # Mail will be sent to global HR
        i1.state = Interview.GO
        i1.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS)
        self.assertEqual(i1.state, Interview.GO)
        self.assertEqual(list(p.responsible.all()), [subsidiaryResponsible,])
        # TODO assert notification recrutement team

        # After we go for a job offer
        # Process state will be: JOB_OFFER
        # Action responsible will be: Subsidiary responsible
        # Mail will be sent to global HR
        p.state = Process.JOB_OFFER
        p.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.JOB_OFFER)
        self.assertEqual(list(p.responsible.all()), [subsidiaryResponsible, ])
         # TODO assert notification recrutement team

        # After we hired the candidate or we didn't hired him (can be our offer is refused by the candidate for example)
        # Process state will be: HIRED or JOB_OFFER_DECLINED
        # No more action responsible
        # Mail will be sent to global HR
        p.state = Process.HIRED
        p.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.HIRED)
        self.assertEqual(list(p.responsible.all()), [])
        # TODO assert notification recrutement team


