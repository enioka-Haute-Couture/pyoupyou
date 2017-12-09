from django.test import TestCase, RequestFactory
import datetime

from django.urls import reverse

from interview.factory import ProcessFactory, InterviewFactory
from interview.models import Process, Document, Interview, Candidate

import pytz

from interview.views import process, minute_edit, minute, interview, close_process, reopen_process
from ref.factory import SubsidiaryFactory
from ref.models import Consultant
from django.utils.translation import ugettext_lazy as _


class ProcessTestCase(TestCase):
    def test_state(self):
        p = ProcessFactory()
        i1 = InterviewFactory(process=p, rank=1, next_state='GO')
        i3 = InterviewFactory(process=p, rank=3, next_state='PL')
        i2 = InterviewFactory(process=p, rank=2, next_state='NO')
        self.assertEqual(p.state, i3.next_state)

    def test_next_action_display(self):
        p = ProcessFactory()
        self.assertEqual(p.next_action_display, _("Pick up next interviewer"))


class InterviewTestCase(TestCase):
    def test_new_interview_state_equals_need_plannification(self):
        p = ProcessFactory()
        i1 = Interview(process_id=p.id)
        i1.save()
        self.assertEqual(Interview.NEED_PLANIFICATION, i1.next_state)

    def test_set_interview_date_state_equals_planned(self):
        p = ProcessFactory()
        i1 = Interview(process_id=p.id)
        i1.save()
        i1.planned_date = datetime.datetime.now(pytz.timezone("Europe/Paris"))
        i1.save()
        self.assertEqual(Interview.PLANNED, i1.next_state)

    def test_interview_replanned_after_state_set_keeps_state(self):
        p = ProcessFactory()
        i1 = Interview(process_id=p.id)
        i1.save()
        i1.planned_date = datetime.datetime.now(pytz.timezone("Europe/Paris"))
        i1.save()
        i1.next_state = Interview.GO
        i1.save()
        self.assertEqual(Interview.GO, i1.next_state)


class AccessRestrictionDateTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        sub = SubsidiaryFactory()
        self.consultantOld = Consultant.objects.create_consultant('OLD', 'old@mail.com', sub, 'OLD')
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
