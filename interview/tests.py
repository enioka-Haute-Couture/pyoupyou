import dateutil.relativedelta
from django.conf import settings
from django.core import mail
from django.test import TestCase, RequestFactory
import datetime
import hashlib

from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from interview import views
from interview.factory import (
    ProcessFactory,
    InterviewFactory,
    CandidateFactory,
    ContractTypeFactory,
    SourcesFactory,
    OfferFactory,
    InterviewKindFactory,
)
from interview.models import Process, Document, Interview, Candidate

import pytz

from interview.views import process, minute_edit, minute, interview, close_process, reopen_process
from ref.factory import SubsidiaryFactory, ConsultantFactory, PyouPyouUserFactory
from ref.models import Consultant

from django.conf import settings

from factory.faker import faker


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
    # TODO: change hardcoded urls to using reverse

    # subsidiary_processes_table.data => class TableQuerysetData(TableData) in
    # https://django-tables2.readthedocs.io/en/stable/_modules/django_tables2/data.html

    def setUp(self) -> None:
        self.url = reverse(views.dashboard)
        self.assertEqual(self.url, "/")

    def test_dashboard_not_logged_in(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, "/admin/login/?next={url}".format(url=self.url))

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
        processes = actions_needed_processes_table.data
        self.assertEqual(len(processes), 0)

        processes = related_processes_table.data
        self.assertEqual(len(processes), 0)

        processes = subsidiary_processes_table.data
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
        processes_actions_needed = actions_needed_processes_table.data
        self.assertEqual(len(processes_actions_needed), 1)
        self.assertEqual(p1.id, processes_actions_needed[0].id)

        related_processes = related_processes_table.data
        self.assertEqual(len(related_processes), 2)
        ids = []
        for tmp in related_processes:
            ids.append(tmp.id)
        self.assertTrue(p1.id in ids)
        self.assertTrue(p2.id in ids)

        subsidiary_processes = subsidiary_processes_table.data
        self.assertEqual(len(subsidiary_processes), 1)
        self.assertNotEquals(p1.id, subsidiary_processes[0].id)
        self.assertNotEquals(p2.id, subsidiary_processes[0].id)

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

        processes_actions_needed = actions_needed_processes_table.data
        for p in processes_actions_needed:
            self.assertTrue(p.needs_attention)
        self.assertEqual(len(processes_actions_needed), 4)

        related_processes = related_processes_table.data
        for p in related_processes:
            self.assertTrue(p.needs_attention)
        self.assertEqual(len(related_processes), 4)

        subsidiary_processes = subsidiary_processes_table.data
        for p in subsidiary_processes:
            self.assertTrue(p.needs_attention)
        self.assertEqual(len(subsidiary_processes), 4)


class ProcessCreationViewTestCase(TestCase):
    # TODO: change hardcoded urls to using reverse

    def setUp(self):
        self.url = reverse(views.new_candidate)
        self.assertEqual(self.url, "/candidate/")

        # create a consultant
        self.subsidiary = SubsidiaryFactory()
        self.consultant = ConsultantFactory(subsidiary=self.subsidiary)
        self.user = self.consultant.user

        self.fake = faker.Faker()

        self.tz = pytz.timezone("Europe/Paris")

    def test_process_creation_not_logged_in(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, "/admin/login/?next={url}".format(url=self.url))

    def test_process_creation_logged_in(self):
        # log user in
        self.client.force_login(user=self.user)

        # access process creation view
        response = self.client.get(self.url)

        # assert we were allowed to access this view
        self.assertEqual(response.status_code, 200)
        # assert the right template was called
        self.assertTemplateUsed(response, template_name="interview/new_candidate.html")
        # assert the header was rendered
        self.assertTemplateUsed(response, template_name="interview/base.html")

    def test_assert_all_needed_forms_are_displayed(self):
        # log user in
        self.client.force_login(user=self.user)

        # access dashboard
        response = self.client.get(self.url)

        context = response.context
        candidate_form = context["candidate_form"]
        process_form = context["process_form"]
        source_form = context["source_form"]
        offer_form = context["offer_form"]
        interviewers_form = context["interviewers_form"]
        duplicate_processes = context["duplicates"]
        candidate = context["candidate"]
        self.assertIsNotNone(candidate_form)
        self.assertIsNotNone(process_form)
        self.assertIsNotNone(source_form)
        self.assertIsNotNone(offer_form)
        self.assertIsNotNone(interviewers_form)
        self.assertIsNone(duplicate_processes)
        self.assertIsNone(candidate)

    def test_form_submit_with_least_data(self):
        # log user in
        self.client.force_login(user=self.user)

        candidate_name = self.fake.name()
        response = self.client.post(
            path="/candidate/",
            data={
                "name": candidate_name,
                "subsidiary": self.subsidiary.id,
                "summit": "Enregistrer",  # means having clicked on "Save" in the page
                "new-candidate": True,  # bypass checks for already existing candidate
            },
            follow=True,
        )

        p = Process.objects.filter(candidate__name=candidate_name).first()
        self.assertIsNotNone(p)
        self.assertRedirects(
            response,
            "/process/{process_id}_{name}/".format(process_id=p.id, name=slugify(candidate_name)),
        )

    def test_form_submit_with_full_data(self):
        # log user in
        self.client.force_login(user=self.user)

        candidate_name = self.fake.name()
        candidate_mail = "{name}@mail.com".format(name=slugify(candidate_name))
        candidate_phone = "+336{number}".format(number=self.fake.random_number(fix_len=True, digits=8))
        process_sub = self.subsidiary
        contract_type = ContractTypeFactory()
        expected_salary = 40
        contract_length = 24
        contract_start_date = datetime.date.today() + dateutil.relativedelta.relativedelta(months=1)
        source = SourcesFactory()
        offer = OfferFactory()
        complementary_informations = "This is a very useful comment"
        interviewers = self.consultant
        interview_kind = InterviewKindFactory()

        response = self.client.post(
            path="/candidate/",
            data={
                "name": candidate_name,
                "email": candidate_mail,
                "phone": candidate_phone,
                "subsidiary": process_sub.id,
                "contract_type": contract_type.id,
                "salary_expectation": expected_salary,
                "contract_duration": contract_length,
                "contract_start_date": contract_start_date,
                "sources": source.id,
                "offer": offer.id,
                "other_informations": complementary_informations,
                "interviewers-kind_of_interview": interview_kind.id,
                "interviewers-interviewers": interviewers.id,
                "summit": "Enregistrer",  # means having clicked on "Save" in the page
                "new-candidate": True,  # bypass checks for already existing candidate
            },
            follow=True,
        )

        p = Process.objects.filter(candidate__name=candidate_name).first()
        self.assertIsNotNone(p)
        self.assertRedirects(
            response,
            "/process/{process_id}_{name}/".format(process_id=p.id, name=slugify(candidate_name)),
        )

    def test_correct_display_of_existing_candidate(self):
        # log user in
        self.client.force_login(user=self.user)

        # create a new candidate
        candidate_name = self.fake.name()
        process_sub = self.subsidiary
        offer = OfferFactory()
        response = self.client.post(
            path="/candidate/",
            data={
                "name": candidate_name,
                "subsidiary": process_sub.id,
                "offer": offer.id,
                "summit": "Enregistrer",  # means having clicked on "Save" in the page
                "new-candidate": True,  # bypass checks for already existing candidate
            },
            follow=True,
        )

        # assert the candidate was correctly created
        p = Process.objects.filter(candidate__name=candidate_name).first()
        self.assertIsNotNone(p)
        self.assertRedirects(
            response,
            "/process/{process_id}_{name}/".format(process_id=p.id, name=slugify(candidate_name)),
        )

        # same call
        response = self.client.post(
            path="/candidate/",
            data={
                "name": candidate_name,
                "subsidiary": process_sub.id,
                "offer": offer.id,
                "summit": "Enregistrer",  # means having clicked on "Save" in the page
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Réutilisez un candidat ou créer en un nouveau. Les options sont en bas du formulaire."
        )
        self.assertIsNotNone(response.context["duplicates"])

    def test_form_submit_reusing_candidate(self):
        # log user in
        self.client.force_login(user=self.user)

        # create a new candidate
        candidate_name = self.fake.name()
        process_sub = self.subsidiary
        offer = OfferFactory()
        response = self.client.post(
            path="/candidate/",
            data={
                "name": candidate_name,
                "subsidiary": process_sub.id,
                "offer": offer.id,
                "summit": "Enregistrer",  # means having clicked on "Save" in the page
                "new-candidate": True,  # bypass checks for already existing candidate
            },
            follow=True,
        )

        # assert the candidate was correctly created
        p = Process.objects.filter(candidate__name=candidate_name).first()
        self.assertIsNotNone(p)
        self.assertRedirects(
            response,
            "/process/{process_id}_{name}/".format(process_id=p.id, name=slugify(candidate_name)),
        )

        new_offer = OfferFactory()

        response = self.client.post(
            path="/candidate-reuse/{p_id}/".format(p_id=p.id),
            data={
                "name": candidate_name,
                "subsidiary": process_sub.id,
                "offer": new_offer.id,
                "email": "",
                "phone": "",
                "summit": "Enregistrer",
            },
            follow=True,
        )

        process_for_candidate = Process.objects.filter(candidate__name=candidate_name).count()
        self.assertEqual(process_for_candidate, 2)
        p = Process.objects.filter(candidate__name=candidate_name).last()
        self.assertIsNotNone(p)
        self.assertRedirects(
            response,
            "/process/{process_id}_{name}/".format(process_id=p.id, name=slugify(candidate_name)),
        )


class ProcessDetailsViewTestCase(TestCase):
    # TODO: change hardcoded urls to using reverse

    def setUp(self):
        # create a process
        self.subsidiary = SubsidiaryFactory()
        self.consultant = ConsultantFactory(subsidiary=self.subsidiary)
        self.user = self.consultant.user
        self.process = ProcessFactory(
            subsidiary=self.subsidiary,
            contract_type=ContractTypeFactory(),
            offer=OfferFactory(),
            sources=SourcesFactory(),
        )
        self.candidate = self.process.candidate
        self.url = reverse(
            views.process, kwargs={"process_id": self.process.id, "slug_info": self.process.candidate.name_slug}
        )
        self.assertEqual(
            self.url, "/process/{id}{slug}/".format(id=self.process.id, slug=self.process.candidate.name_slug)
        )

    def test_process_details_not_logged_in(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, "/admin/login/?next={url}".format(url=self.url))

    def test_process_details_logged_in(self):
        # log user in
        self.client.force_login(user=self.user)

        # access process details
        response = self.client.get(self.url)

        # assert we were allowed to access our process details view
        self.assertEqual(response.status_code, 200)
        # assert the right template was called
        self.assertTemplateUsed(response, template_name="interview/process_detail.html")
        # assert the header was rendered
        self.assertTemplateUsed(response, template_name="interview/base.html")

    def test_process_details_info_display(self):

        # log user in
        self.client.force_login(user=self.user)

        # access process details
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        # open process
        self.assertContains(response, "Ce processus suit son cours")

        self.assertContains(
            response,
            '<a href="{candidate_url}">{candidat} </a> [{subsidiary}]'.format(
                candidate_url=reverse(views.edit_candidate, kwargs={"process_id": self.process.id}),
                candidat=self.candidate.name,
                subsidiary=self.subsidiary,
            ),
        )

        # Informations de contact
        self.assertContains(response, self.candidate.email)
        self.assertContains(response, self.candidate.phone)

        # Informations sur le contrat
        self.assertContains(response, self.process.sources)
        self.assertContains(response, self.process.offer.name)
        self.assertContains(response, "Documents")

        self.assertContains(response, self.process.contract_type)
        self.assertContains(response, self.process.contract_duration)
        self.assertContains(
            response,
            (
                "{dt.day} {month} {dt:%Y}".format(
                    dt=self.process.contract_start_date, month=_(self.process.contract_start_date.strftime("%B"))
                )
            ),
        )
        self.assertContains(response, "{value} k€".format(value=self.process.salary_expectation))

        self.assertContains(response, self.process.other_informations)

        self.assertContains(response, "Entretiens de ce processus")

        # assert that interview tables is empty
        interviews = response.context["interviews_for_process_table"].data
        self.assertFalse(interviews)

        # assert that add itw button exists
        self.assertContains(response, "Ajouter un entretien")

        # close the process
        response = self.client.post(
            path=reverse(views.close_process, kwargs={"process_id": self.process.id}),
            data={"state": "NG", "closed_comment": "", "summit": "Terminer+le+processus"},
            follow=True,
        )

        # update process values after state update
        self.process = Process.objects.get(id=self.process.id)

        self.assertRedirects(response, self.process.get_absolute_url())
        self.assertContains(
            response, "Ce processus est terminé - {state}".format(state=self.process.get_state_display())
        )
        self.assertContains(response, self.process.closed_comment)

    def test_process_details_interviews_table(self):
        # new process as it was closed by last test
        self.setUp()

        # log user in
        self.client.force_login(user=self.user)

        # add an interview
        itw1 = InterviewFactory(process=self.process, kind_of_interview=InterviewKindFactory())
        itw1.interviewers.add(self.consultant)  # needed to be able to render the process page
        itw1.save()

        # access process details
        response = self.client.get(self.url)

        interviews = response.context["interviews_for_process_table"].data
        self.assertEqual(len(interviews), 1)
        self.assertEqual(
            str(interviews[0]), str(itw1)
        )  # string representation should be enough to differentiate each itw

        # add an interview
        itw2 = InterviewFactory(process=self.process, kind_of_interview=InterviewKindFactory())
        itw2.interviewers.add(self.consultant)  # needed to be able to render the process page
        itw2.save()

        # access process details
        response = self.client.get(self.url)

        interviews = response.context["interviews_for_process_table"].data
        self.assertEqual(len(interviews), 2)
        self.assertEqual(
            str(interviews[1]), str(itw2)
        )  # string representation should be enough to differentiate each itw


class InterviewMinuteViewTestCase(TestCase):
    def setUp(self):
        self.subsidiary = SubsidiaryFactory()
        self.consultant = ConsultantFactory(subsidiary=self.subsidiary)
        self.user = self.consultant.user
        self.process = ProcessFactory(
            subsidiary=self.subsidiary,
            contract_type=ContractTypeFactory(),
            offer=OfferFactory(),
            sources=SourcesFactory(),
        )
        self.candidate = self.process.candidate

        self.itw = InterviewFactory(process=self.process, kind_of_interview=InterviewKindFactory())
        self.itw.interviewers.add(self.consultant)
        self.itw.save()

        self.url_minute = reverse(
            views.minute, kwargs={"interview_id": self.itw.id, "slug_info": self.process.candidate.name_slug}
        )
        self.assertEqual(
            self.url_minute,
            "/interview/{id}{slug}/minute/".format(id=self.itw.id, slug=self.process.candidate.name_slug),
        )

        self.url_edit = reverse(views.minute_edit, kwargs={"interview_id": self.itw.id})
        self.assertEqual(self.url_edit, "/interview/{id}/minute/edit/".format(id=self.itw.id))

    def test_interview_minute_not_logged_in(self):
        response = self.client.get(self.url_minute)
        self.assertRedirects(response, "/admin/login/?next={url}".format(url=self.url_minute))

    def test_interview_minute_edit_not_logged_in(self):
        response = self.client.get(self.url_edit)
        self.assertRedirects(response, "/admin/login/?next={url}".format(url=self.url_edit))

    def test_interview_minute_logged_in(self):
        # log user in
        self.client.force_login(user=self.user)

        # access process creation view
        response = self.client.get(self.url_minute)

        # assert we were allowed to access this view
        self.assertEqual(response.status_code, 200)
        # assert the right template was called
        self.assertTemplateUsed(response, template_name="interview/interview_minute.html")
        # assert the header was rendered
        self.assertTemplateUsed(response, template_name="interview/base.html")

    def test_interview_minute_edit_logged_in(self):
        # log user in
        self.client.force_login(user=self.user)

        # access process creation view
        response = self.client.get(self.url_edit)

        # assert we were allowed to access this view
        self.assertEqual(response.status_code, 200)
        # assert the right template was called
        self.assertTemplateUsed(response, template_name="interview/interview_minute_form.html")
        # assert the header was rendered
        self.assertTemplateUsed(response, template_name="interview/base.html")

    def test_interview_minute_display(self):
        # log user in
        self.client.force_login(user=self.user)

        # access process creation view
        response = self.client.get(self.url_minute)

        self.assertEqual(response.status_code, 200)

        #  Compte rendu d'entretien pour <assert 3> pour <assert 2> pour la filiale <assert 1>
        self.assertContains(response, self.subsidiary)
        self.assertContains(
            response,
            '<a href="{url}"> {name} </a>'.format(
                url=reverse(views.edit_candidate, kwargs={"process_id": self.process.id}), name=self.candidate.name
            ),
        )
        self.assertContains(
            response,
            '<a href="{url}"> pour le processus</a>'.format(url=self.process.get_absolute_url()),
        )

        # Interviewers (only one tho)
        self.assertContains(response, self.itw.interviewers.first())

        # CR
        self.assertContains(response, self.itw.kind_of_interview)
        self.assertContains(response, self.itw.minute)

        # Suggested interviewer
        self.assertContains(response, self.itw.suggested_interviewer)

        # Next itw goel
        self.assertContains(response, self.itw.next_interview_goal)

    def test_interview_minute_edit_display(self):
        # log user in
        self.client.force_login(user=self.user)

        # access process creation view
        response = self.client.get(self.url_edit)

        self.assertEqual(response.status_code, 200)

        #  Compte rendu d'entretien pour <assert 3> pour <assert 2> pour la filiale <assert 1>
        self.assertContains(response, self.subsidiary)
        self.assertContains(
            response,
            '<a href="{url}"> {name} </a>'.format(
                url=reverse(views.edit_candidate, kwargs={"process_id": self.process.id}), name=self.candidate.name
            ),
        )
        self.assertContains(
            response,
            '<a href="{url}"> pour le processus</a>'.format(url=self.process.get_absolute_url()),
        )

        # CR
        self.assertContains(response, self.itw.minute)

        # Suggested interviewer
        self.assertContains(response, self.itw.suggested_interviewer)

        # Suggested interviewer
        self.assertContains(response, self.itw.suggested_interviewer)

        # Type d'entretien
        self.assertContains(response, self.itw.kind_of_interview)

        # assert buttons are here
        self.assertContains(response, "NON")
        self.assertContains(response, "Brouillon")
        self.assertContains(response, "GO")
