from django.conf import settings
from django.core import mail
from django.test import TestCase, RequestFactory
import datetime
import hashlib

from django.urls import reverse

from interview import views
from interview.factory import ProcessFactory, InterviewFactory, CandidateFactory
from interview.models import Process, Document, Interview, Candidate

import pytz

from interview.views import process, minute_edit, minute, interview, close_process, reopen_process
from ref.factory import SubsidiaryFactory, ConsultantFactory, PyouPyouUserFactory
from ref.models import Consultant

from django.conf import settings


class InterviewTestCase(TestCase):
    def test_new_interview_state_equals_need_plannification(self):
        p = ProcessFactory()
        i1 = Interview(process_id=p.id)
        i1.save()
        self.assertEqual(Interview.WAITING_PLANIFICATION, i1.state)

    def test_set_interview_date_state_equals_planned(self):
        p = ProcessFactory()
        i1 = Interview(process_id=p.id)
        i1.save()
        i1.planned_date = datetime.datetime.now(pytz.timezone("Europe/Paris"))
        i1.save()
        self.assertEqual(Interview.PLANNED, i1.state)

    def test_interview_replanned_after_state_set_keeps_state(self):
        p = ProcessFactory()
        i1 = Interview(process_id=p.id)
        i1.save()
        i1.planned_date = datetime.datetime.now(pytz.timezone("Europe/Paris"))
        i1.save()
        i1.state = Interview.GO
        i1.save()
        self.assertEqual(Interview.GO, i1.state)


class AccessRestrictionDateTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        sub = SubsidiaryFactory()
        self.consultantOld = Consultant.objects.create_consultant("OLD", "old@mail.com", sub, "OLD")
        sub.responsible = self.consultantOld
        sub.responsible.save()
        userOld = self.consultantOld.user
        userOld.date_joined = datetime.datetime(2016, 1, 1, tzinfo=datetime.timezone.utc)
        userOld.save()
        self.consultantNew = Consultant.objects.create_consultant("NEW", "new@mail.com", sub, "NEW")
        userNew = self.consultantNew.user
        userNew.date_joined = datetime.datetime(2017, 11, 1, tzinfo=datetime.timezone.utc)
        userNew.save()

        self.p = ProcessFactory()
        self.p.start_date = datetime.datetime(2016, 10, 10, tzinfo=datetime.timezone.utc)
        self.p.save()
        self.i = InterviewFactory(process=self.p)
        self.i.interviewers.set([self.consultantOld, self.consultantNew])
        # self.i.save()

    def test_view_process(self):
        request = self.factory.get(
            reverse("process-details", kwargs={"process_id": self.p.id, "slug_info": f"_{self.p.candidate.name_slug}"})
        )

        request.user = self.consultantOld.user
        response = process(request, self.p.id)
        self.assertEqual(response.status_code, 200)

        request.user = self.consultantNew.user
        response = process(request, self.p.id)
        self.assertEqual(response.status_code, 404)

    def test_view_close_process(self):
        request = self.factory.post(reverse("process-close", kwargs={"process_id": self.p.id}))

        request.user = self.consultantNew.user
        response = close_process(request, self.p.id)
        self.assertEqual(response.status_code, 404)

    def test_view_reopen_process(self):
        request = self.factory.get(reverse("process-reopen", kwargs={"process_id": self.p.id}))

        request.user = self.consultantNew.user
        response = reopen_process(request, self.p.id)
        self.assertEqual(response.status_code, 404)

    def test_view_interview_plan(self):
        request = self.factory.post(
            reverse("interview-plan", kwargs={"process_id": self.p.id, "interview_id": self.i.id})
        )

        request.user = self.consultantNew.user
        response = interview(request, self.p.id, self.i.id, "plan")
        self.assertEqual(response.status_code, 404)

    def test_view_interview_edit(self):
        request = self.factory.post(
            reverse("interview-edit", kwargs={"process_id": self.p.id, "interview_id": self.i.id})
        )

        request.user = self.consultantNew.user
        response = interview(request, self.p.id, self.i.id, "edit")
        self.assertEqual(response.status_code, 404)

    def test_view_interview_minute_form(self):
        request = self.factory.get(reverse("interview-minute-edit", kwargs={"interview_id": self.i.id}))

        request.user = self.consultantOld.user
        response = minute_edit(request, self.i.id)
        self.assertEqual(response.status_code, 200)

        request.user = self.consultantNew.user
        response = minute_edit(request, self.i.id)
        self.assertEqual(response.status_code, 404)

    def test_view_interview_minute(self):
        request = self.factory.get(
            reverse(
                "interview-minute",
                kwargs={
                    "interview_id": self.i.id,
                    "slug_info": f"_{self.i.process.candidate.name_slug}-{self.i.interviewers_trigram_slug}-{self.i.rank}",
                },
            )
        )

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
        self.consultantItw = Consultant.objects.create_consultant("ITW", "itw@mail.com", sub, "ITW")
        self.consultantRestricted = Consultant.objects.create_consultant("RES", "res@mail.com", sub, "RES")

        self.p = ProcessFactory()
        self.i = InterviewFactory(process=self.p)
        self.i.interviewers.set([self.consultantItw])

    def test_only_assigned_user_can_edit_minute(self):
        request = self.factory.get(reverse("interview-minute-edit", kwargs={"interview_id": self.i.id}))

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
        # Mail will be sent to subsidiary responsible
        p = ProcessFactory(subsidiary=subsidiary)
        self.assertEqual(p.state, Process.WAITING_INTERVIEWER_TO_BE_DESIGNED)
        self.assertEqual(list(p.responsible.all()), [subsidiaryResponsible])
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(mail.outbox[0].to, [subsidiaryResponsible.user.email])
        mail.outbox = []

        # When we create an interview
        # Process state will be: WAITING_INTERVIEW_PLANIFICATION
        # Interview state will be: WAITING_PLANIFICATION
        # Action responsible will be: Interviewer
        # Mail will be sent to  subsidiary responsible and interviewer
        i1 = Interview(process_id=p.id)
        i1.save()
        i1.interviewers.add(interviewer)
        self.assertEqual(Process.objects.get(id=p.id).state, Process.WAITING_INTERVIEW_PLANIFICATION)
        self.assertEqual(i1.state, Interview.WAITING_PLANIFICATION)
        self.assertEqual(list(p.responsible.all()), [interviewer])
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(mail.outbox[0].to, [subsidiaryResponsible.user.email, interviewer.user.email])
        mail.outbox = []

        # After interview planification
        # Process state will be: INTERVIEW_IS_PLANNED
        # Interview state will be: PLANNED
        # Action responsible will be: Interviewer
        # Mail will be sent to  subsidiary responsible and interviewer if more than one
        i1.planned_date = datetime.datetime.now(pytz.timezone("Europe/Paris")) + datetime.timedelta(days=7)
        i1.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.INTERVIEW_IS_PLANNED)
        self.assertEqual(i1.state, Interview.PLANNED)

        self.assertEqual(list(p.responsible.all()), [interviewer])
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(mail.outbox[0].to, [subsidiaryResponsible.user.email, interviewer.user.email])
        mail.outbox = []

        # When ITW date is in the past cron will set state to WAIT_INFORMATION for the interview and indirectly to
        # WAITING_ITW_MINUTE (WM) for the process
        i1.state = Interview.WAIT_INFORMATION
        i1.save()
        self.assertEqual(i1.state, Interview.WAIT_INFORMATION)
        self.assertEqual(Process.objects.get(id=p.id).state, Process.WAITING_ITW_MINUTE)
        self.assertEqual(list(p.responsible.all()), [interviewer])

        # After Go/No Go
        # Process state will be: WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
        # Interview state will be: GO or NO_GO
        # Action responsible will be: Subsidiary responsible
        # Mail will be sent to subsidiary responsible
        i1.state = Interview.GO
        i1.save()

        self.assertEqual(
            Process.objects.get(id=p.id).state, Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
        )
        self.assertEqual(i1.state, Interview.GO)
        self.assertEqual(list(p.responsible.all()), [subsidiaryResponsible])
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(mail.outbox[0].to, [subsidiaryResponsible.user.email])
        mail.outbox = []

        # After we go for a job offer
        # Process state will be: JOB_OFFER
        # Action responsible will be: Subsidiary responsible
        # Mail will be sent to subsidiary responsible
        p.state = Process.JOB_OFFER
        p.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.JOB_OFFER)
        self.assertEqual(list(p.responsible.all()), [subsidiaryResponsible])
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(mail.outbox[0].to, [subsidiaryResponsible.user.email])
        mail.outbox = []

        # After we hired the candidate or we didn't hired him (can be our offer is refused by the candidate for example)
        # Process state will be: HIRED or JOB_OFFER_DECLINED
        # No more action responsible
        # Mail will be sent to subsidiary responsible
        p.state = Process.HIRED
        p.save()

        self.assertEqual(Process.objects.get(id=p.id).state, Process.HIRED)
        self.assertEqual(list(p.responsible.all()), [])
        self.assertCountEqual(mail.outbox[0].to, [subsidiaryResponsible.user.email])
        mail.outbox = 0


class AnonymizesCanditateTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        sub = SubsidiaryFactory()
        self.consultantItw = Consultant.objects.create_consultant("ITW", "itw@mail.com", sub, "ITW")
        self.consultantRestricted = Consultant.objects.create_consultant("RES", "res@mail.com", sub, "RES")

        self.p = ProcessFactory()

        self.p.candidate.name = "Nâme lAstName"
        self.p.candidate.email = "tesT@test.Com"
        self.p.candidate.phone = "12.34 56.78"
        self.p.start_date = datetime.datetime.now() - datetime.timedelta(365)  # one year ago

        Document.objects.create(document_type="CV", content="", candidate=self.p.candidate)

        self.p.candidate.save()

    def test_anonymize_candidate(self):
        self.p.candidate.anonymize()
        self.assertEqual(self.p.candidate.anonymized, True)

        # name
        name_hash = hashlib.sha256()
        name_hash.update(settings.SECRET_ANON_SALT.encode("utf-8"))
        name_hash.update("name lastname".encode("utf-8"))

        self.assertEqual(self.p.candidate.name, "")
        self.assertEqual(self.p.candidate.anonymized_hashed_name, name_hash.hexdigest())

        # email
        email_hash = hashlib.sha256()
        email_hash.update(settings.SECRET_ANON_SALT.encode("utf-8"))
        email_hash.update("test@test.com".encode("utf-8"))
        self.assertEqual(self.p.candidate.email, "")
        self.assertEqual(self.p.candidate.anonymized_hashed_email, email_hash.hexdigest())

        # phone
        self.assertEqual(self.p.candidate.phone, "")

        self.assertEqual(0, Document.objects.filter(candidate=self.p.candidate).count())

        self.p.candidate.save()

        other_candidate1 = CandidateFactory()
        other_candidate1.name = "Nâme lAstName"
        self.assertEqual(other_candidate1.anonymized_name(), name_hash.hexdigest())
        previous_candidate_anoymized = other_candidate1.find_duplicates()
        self.assertEqual(1, previous_candidate_anoymized.count())
        other_candidate1.save()

        other_candidate1b = CandidateFactory()
        other_candidate1b.name = "lastname nâme"  # reverse order and lower case
        previous_candidate_anoymized = other_candidate1b.find_duplicates()
        self.assertEqual(2, previous_candidate_anoymized.count())

        other_candidate2 = CandidateFactory()
        other_candidate2.email = "tesT@test.Com"
        self.assertEqual(other_candidate2.anonymized_email(), email_hash.hexdigest())
        previous_candidate_anoymized = other_candidate2.find_duplicates()
        self.assertEqual(1, previous_candidate_anoymized.count())


class HomeViewTestCase(TestCase):

    # subsidiary_processes_table.data => class TableQuerysetData(TableData) in
    # https://django-tables2.readthedocs.io/en/stable/_modules/django_tables2/data.html

    def setUp(self) -> None:
        self.url = reverse(views.dashboard)
        self.assertEqual(self.url, "/")

    def test_dashboard_not_logged_in(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, "/admin/login/?next=/")

    def test_dashboard_logged_in(self):
        # create a consultant
        subsidiary = SubsidiaryFactory()
        consultant = ConsultantFactory(subsidiary=subsidiary)
        user = consultant.user

        # log user in
        self.client.force_login(user=user)

        # access dashboard
        response = self.client.get(self.url)

        # assert we were allowed to access dashboard
        self.assertEqual(response.status_code, 200)
        # assert the right template was called
        self.assertTemplateUsed(response, template_name="interview/dashboard.html")
        # assert the header was rendered
        self.assertTemplateUsed(response, template_name="interview/base.html")
        # assert some tables were rendered inside the dashboard
        self.assertTemplateUsed(response, template_name="interview/_tables.html")

    def test_dashboard_no_data(self):
        # create a consultant
        subsidiary = SubsidiaryFactory()
        consultant = ConsultantFactory(subsidiary=subsidiary)
        user = consultant.user

        # log user in
        self.client.force_login(user=user)

        # access dashboard
        response = self.client.get(self.url)
        # retrieve the three tables displayed
        actions_needed_processes_table = response.context["actions_needed_processes_table"]
        related_processes_table = response.context["related_processes_table"]
        subsidiary_processes_table = response.context["subsidiary_processes_table"]

        # assert all three tables are empty
        processes = []
        for p in actions_needed_processes_table.data:
            processes.append(p)
        self.assertEqual(len(processes), 0)

        processes = []
        for p in related_processes_table.data:
            processes.append(p)
        self.assertEqual(len(processes), 0)

        processes = []
        for p in subsidiary_processes_table.data:
            processes.append(p)
        self.assertEqual(len(processes), 0)

    def test_dashboard_with_data(self):
        # create a consultant
        subsidiary = SubsidiaryFactory()
        consultant = ConsultantFactory(subsidiary=subsidiary)
        user = consultant.user

        # create 1 process in actions_needed_processes_table & in related_process_table
        p1 = ProcessFactory()
        itw1 = InterviewFactory(process=p1)
        itw1.interviewers.add(consultant)
        itw1.save()

        # create 1 process only appearing in related_process_table
        p2 = ProcessFactory()
        itw2 = InterviewFactory(process=p2)
        itw2.interviewers.add(consultant)
        itw2.save()
        p2.end_date = datetime.datetime.now()
        p2.state = Process.OTHER
        p2.save()

        # create a process that will only appear in subsidiary_process_table
        ProcessFactory(subsidiary=subsidiary)

        # log user in
        self.client.force_login(user=user)

        # access dashboard
        response = self.client.get(self.url)

        # retrieve the three tables displayed
        actions_needed_processes_table = response.context["actions_needed_processes_table"]
        related_processes_table = response.context["related_processes_table"]
        subsidiary_processes_table = response.context["subsidiary_processes_table"]

        # assert all three tables are correctly displayed
        processes_actions_needed = []
        for p in actions_needed_processes_table.data:
            processes_actions_needed.append(p)
        self.assertEqual(len(processes_actions_needed), 1)

        related_processes = []
        for p in related_processes_table.data:
            related_processes.append(p)
        self.assertEqual(len(related_processes), 2)

        subsidiary_processes = []
        for p in subsidiary_processes_table.data:
            subsidiary_processes.append(p)
        self.assertEqual(len(subsidiary_processes), 1)

        # assert that process in subsidiary_process_table and actions_needed_process-table are different
        self.assertNotEquals(processes_actions_needed[0].candidate, subsidiary_processes[0].candidate)

    def test_dashboard_with_needs_attention(self):

        # create a consultant
        subsidiary = SubsidiaryFactory()
        consultant = ConsultantFactory(subsidiary=subsidiary)
        user = consultant.user

        # to have need_attention property we need:
        #   p.is_active ( == p.end_date is None => default in factory) &&
        #   p.state in (
        #               WAITING_ITW_MINUTE ||
        #               Process.WAITING_INTERVIEW_PLANIFICATION ||
        #               WAITING_INTERVIEWER_TO_BE_DESIGNED ||
        #               WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
        #               )

        # creating one of each possibility
        p1 = ProcessFactory(subsidiary=subsidiary)
        itw1 = InterviewFactory(process=p1)
        itw1.interviewers.add(consultant)
        itw1.save()  # saving an itw updates process state, hence we set process state afterwards
        p1.state = Process.WAITING_ITW_MINUTE
        p1.save()

        p2 = ProcessFactory(subsidiary=subsidiary)
        itw2 = InterviewFactory(process=p2)
        itw2.interviewers.add(consultant)
        itw2.save()  # saving an itw updates process state, hence we set process state afterwards
        p2.state = Process.WAITING_INTERVIEW_PLANIFICATION
        p2.save()

        p3 = ProcessFactory(subsidiary=subsidiary)
        itw3 = InterviewFactory(process=p3)
        itw3.interviewers.add(consultant)
        itw3.save()  # saving an itw updates process state, hence we set process state afterwards
        p3.state = Process.WAITING_INTERVIEWER_TO_BE_DESIGNED
        p3.save()

        p4 = ProcessFactory(subsidiary=subsidiary)
        itw4 = InterviewFactory(process=p4)
        itw4.interviewers.add(consultant)
        itw4.save()  # saving an itw updates process state, hence we set process state afterwards
        p4.state = Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
        p4.save()

        # log user in
        self.client.force_login(user=user)

        # access dashboard
        response = self.client.get(self.url)

        # retrieve the three tables displayed
        actions_needed_processes_table = response.context["actions_needed_processes_table"]
        related_processes_table = response.context["related_processes_table"]
        subsidiary_processes_table = response.context["subsidiary_processes_table"]

        processes_actions_needed = []
        for p in actions_needed_processes_table.data:
            processes_actions_needed.append(p)
            self.assertTrue(p.needs_attention)
        self.assertEqual(len(processes_actions_needed), 4)

        related_processes = []
        for p in related_processes_table.data:
            related_processes.append(p)
            self.assertTrue(p.needs_attention)
        self.assertEqual(len(related_processes), 4)

        subsidiary_processes = []
        for p in subsidiary_processes_table.data:
            subsidiary_processes.append(p)
            self.assertTrue(p.needs_attention)
        self.assertEqual(len(subsidiary_processes), 4)
