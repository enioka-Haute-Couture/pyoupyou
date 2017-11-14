from django.test import TestCase
import datetime

from interview.factory import ProcessFactory, InterviewFactory
from interview.models import Process, Document, Interview, Candidate

import pytz

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
