# -*- coding: utf-8 -*-

import datetime
import os
import hashlib
import unicodedata
import itertools

from django.conf import settings
from django.core import mail
from django.db import models
from django.db.models import Q, CharField, Count
from django.db.models.signals import post_save, m2m_changed
from django.db.models.functions import Lower
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from pyoupyou.settings import MINUTE_FORMAT, STALE_DAYS
from ref.models import Subsidiary, PyouPyouUser

CharField.register_lookup(Lower)


class ContractType(models.Model):
    name = models.CharField(_("Name"), max_length=200)
    has_duration = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Contract type")


class SourcesCategory(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class Sources(models.Model):
    name = models.CharField(max_length=50)
    category = models.ForeignKey(SourcesCategory, null=True, on_delete=models.SET_NULL)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class CandidateManager(models.Manager):
    def for_user(self, user):
        return Candidate.objects.distinct().filter(process__in=Process.objects.for_user(user))


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    only_ascii = nfkd_form.encode("ASCII", "ignore")
    return only_ascii


def anonymize_text(text):
    h = hashlib.sha256()
    h.update(settings.SECRET_ANON_SALT.encode("utf-8"))
    h.update(remove_accents(text.lower()))
    return h.hexdigest()


class Candidate(models.Model):
    name = models.CharField(_("Name"), max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)
    anonymized_hashed_name = models.CharField(_("Anonymized Hashed Name"), max_length=64, blank=True)
    anonymized_hashed_email = models.CharField(_("Anonymized Hashed Email"), max_length=64, blank=True)
    anonymized = models.BooleanField(default=False)
    linkedin_url = models.URLField(verbose_name=_("LinkedIn link"), blank=True)

    # TODO Required by the reverse admin url resolver?
    app_label = "interview"
    model_name = "candidate"

    objects = CandidateManager()

    def compute_anonymized_fields(self):
        if not self.anonymized:
            if self.name != "":
                self.anonymized_hashed_name = self.anonymized_name()
            if self.email != "":
                self.anonymized_hashed_email = self.anonymized_email()

    def save(self, *args, **kwargs):
        self.compute_anonymized_fields()
        super(Candidate, self).save(*args, **kwargs)

    def __str__(self):
        return ("{name}").format(name=self.name)

    def anonymize(self):
        """
        Anonymize the candidate data, removing its documents
        This is irreversible
        """
        if not self.anonymized:
            # remove the candidate's documents
            for doc in Document.objects.filter(candidate=self):
                doc.content.delete()
            Document.objects.filter(candidate=self).delete()
            # remove directory as well
            try:
                path = settings.MEDIA_ROOT + f"/CV/{self.id}_{self.name}"
                os.rmdir(path)
            except FileNotFoundError:
                print(f"directory {path} doesnt exist")

            self.name = ""
            self.email = ""
            self.phone = ""

            self.anonymized = True

    def anonymized_name(self):
        return anonymize_text(self.name)

    def anonymized_email(self):
        if self.email:
            return anonymize_text(self.email)
        return ""

    def find_duplicates(self):
        name_permutations = list(itertools.permutations(self.name.lower().split(" ")))
        hash_permutations = map(lambda words: anonymize_text(" ".join(words)), name_permutations)

        return Candidate.objects.filter(
            (
                ~Q(id=self.id)
                & (
                    (~Q(anonymized_hashed_name="") & Q(anonymized_hashed_name__in=hash_permutations))
                    | (~Q(anonymized_hashed_email="") & Q(anonymized_hashed_email=self.anonymized_email()))
                )
            )
        )

    def compare(self, other):
        res = []

        if self.name:
            name_permutations = list(itertools.permutations(self.name.lower().split(" ")))
            hash_permutations = map(lambda words: anonymize_text(" ".join(words)), name_permutations)

            if other.anonymized_hashed_name in hash_permutations:
                res.append("name")

        if self.email and self.anonymized_email() == other.anonymized_hashed_email:
            res.append("email")

        return res

    @property
    def display_name(self):
        return self.name if not self.anonymized else _("anonymized")

    @property
    def name_slug(self):
        return slugify(self.name)

    class Meta:
        verbose_name = _("Candidate")


def document_path(instance, filename):
    # todo ensure uniqueness (if two documents have the same name we reach a problem)
    filename = filename.encode()
    extension = filename.split(b".")[-1]
    filename = str(slugify(instance.candidate.name)).encode() + ".".encode() + extension

    return "{}/{}_{}/{}".format(
        instance.document_type, instance.candidate.id, slugify(instance.candidate.name), filename.decode()
    )


class Document(models.Model):
    DOCUMENT_TYPE = (("CV", "CV"), ("CL", "Cover Letter"), ("OT", "Others"))

    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation date"))
    candidate = models.ForeignKey(Candidate, verbose_name=_("Candidate"), on_delete=models.CASCADE)
    document_type = models.CharField(max_length=2, choices=DOCUMENT_TYPE, verbose_name=_("Kind of document"))
    content = models.FileField(upload_to=document_path, verbose_name=_("Content file"))
    # content_url = models.URLField(verbose_name=_("Content URL"))
    still_valid = models.BooleanField(default=True, verbose_name=_("Still valid"))

    def __str__(self):
        return ("{candidate} - {document_type}").format(candidate=self.candidate, document_type=self.document_type)


class Offer(models.Model):
    name = models.CharField(max_length=50)
    subsidiary = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return "{name} ({sub})".format(name=self.name, sub=self.subsidiary)


class ProcessManager(models.Manager):
    def for_user(self, user):
        q = (
            super()
            .get_queryset()
            .filter(Q(start_date__gte=user.date_joined) | Q(responsible__in=[user]) | Q(interview__interviewers=user))
            .distinct()
        )
        if user.is_external:
            q = q.filter(sources=user.limited_to_source)
        return q

    def for_table(self, user):
        qs = (
            self.for_user(user)
            .select_related("subsidiary", "candidate", "contract_type")
            .prefetch_related("responsible")
            .annotate(current_rank=Count("interview", distinct=True))
        )
        return qs


class Process(models.Model):
    WAITING_INTERVIEW_PLANIFICATION = "WP"
    WAITING_INTERVIEW_PLANIFICATION_RESPONSE = "WR"
    INTERVIEW_IS_PLANNED = "WI"
    WAITING_ITW_MINUTE = "WM"
    OPEN = "OP"
    WAITING_INTERVIEWER_TO_BE_DESIGNED = "WA"
    WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS = "WK"
    NO_GO = "NG"
    CANDIDATE_DECLINED = "CD"
    HIRED = "HI"
    OTHER = "NO"
    JOB_OFFER = "JO"

    CLOSED_STATE = (
        (NO_GO, _("Last interviewer interupt process")),
        (CANDIDATE_DECLINED, _("Candidate declined our offer")),
        (HIRED, _("Candidate accepted our offer")),
        (OTHER, _("Closed - other reason")),
    )

    INTERVIEW_STATE = (
        (WAITING_INTERVIEW_PLANIFICATION, _("Waiting interview planification")),
        (WAITING_INTERVIEW_PLANIFICATION_RESPONSE, _("Waiting for interview planification response")),
        (WAITING_ITW_MINUTE, _("Waiting interview minute")),
        (INTERVIEW_IS_PLANNED, _("Waiting interview")),
    )

    PROCESS_STATE = (
        (
            (OPEN, _("Open")),
            (WAITING_INTERVIEWER_TO_BE_DESIGNED, _("Waiting interviewer to be designed")),
            (
                WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS,
                _("Waiting next interview designation or process termination"),
            ),
            (JOB_OFFER, _("Waiting candidate feedback after a job offer")),
        )
        + INTERVIEW_STATE
        + CLOSED_STATE
    )

    ALL_STATE_VALUES = [
        WAITING_INTERVIEW_PLANIFICATION,
        WAITING_INTERVIEW_PLANIFICATION_RESPONSE,
        INTERVIEW_IS_PLANNED,
        WAITING_ITW_MINUTE,
        OPEN,
        WAITING_INTERVIEWER_TO_BE_DESIGNED,
        WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS,
        NO_GO,
        CANDIDATE_DECLINED,
        HIRED,
        OTHER,
        JOB_OFFER,
    ]
    CLOSED_STATE_VALUES = [s[0] for s in CLOSED_STATE]
    OPEN_STATE_VALUES = list(set(ALL_STATE_VALUES) - set(CLOSED_STATE_VALUES))
    objects = ProcessManager()
    candidate = models.ForeignKey(Candidate, verbose_name=_("Candidate"), on_delete=models.CASCADE)
    subsidiary = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)

    start_date = models.DateField(verbose_name=_("Process start date"), auto_now_add=True)
    end_date = models.DateField(verbose_name=_("End date"), null=True, blank=True)
    contract_type = models.ForeignKey(
        ContractType, null=True, blank=True, verbose_name=_("Contract type"), on_delete=models.SET_NULL
    )
    salary_expectation = models.IntegerField(verbose_name=_("Salary expectation (k€)"), null=True, blank=True)
    contract_duration = models.PositiveIntegerField(verbose_name=_("Contract duration in month"), null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    sources = models.ForeignKey(Sources, null=True, blank=True, on_delete=models.SET_NULL)
    responsible = models.ManyToManyField(PyouPyouUser, blank=True)
    state = models.CharField(
        max_length=3, choices=PROCESS_STATE, verbose_name=_("Closed reason"), default=WAITING_INTERVIEWER_TO_BE_DESIGNED
    )
    last_state_change = models.DateTimeField(verbose_name=_("Last State Change"), default=now)
    closed_comment = models.TextField(verbose_name=_("Closed comment"), blank=True)

    offer = models.ForeignKey(Offer, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("Offer"))

    other_informations = models.TextField(verbose_name=_("Other informations"), blank=True)

    creator = models.ForeignKey(
        PyouPyouUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="process_creator",
        verbose_name=_("Process creator"),
    )

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        is_new = False if self.id else True
        if is_new:
            self.last_state_change = now()
        else:
            old = Process.objects.get(id=self.id)
            if old.state != self.state:
                self.last_state_change = now()
        super().save(force_insert, force_update, using, update_fields)
        if self.state in (
            Process.WAITING_INTERVIEWER_TO_BE_DESIGNED,
            Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS,
            Process.JOB_OFFER,
        ):
            self.responsible.clear()
            if self.subsidiary.responsible:
                self.responsible.add(self.subsidiary.responsible)
        if self.state in (Process.CANDIDATE_DECLINED, Process.HIRED):
            self.responsible.clear()
        if self.state in (
            Process.WAITING_INTERVIEW_PLANIFICATION,
            Process.WAITING_INTERVIEW_PLANIFICATION_RESPONSE,
            Process.INTERVIEW_IS_PLANNED,
        ):
            self.responsible.clear()
            for interviewer in self.interview_set.last().interviewers.all():
                self.responsible.add(interviewer)

        if self.is_open():
            for interview in self.interview_set.exclude(state__in=[Interview.GO, Interview.NO_GO]):
                for interviewer in interview.interviewers.all():
                    self.responsible.add(interviewer)
        self.trigger_notification(is_new)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("process-details", kwargs={"process_id": self.id, "slug_info": f"_{self.candidate.name_slug}"})

    def is_open(self):
        return self.state not in Process.CLOSED_STATE_VALUES

    def __str__(self):
        return ("{candidate} {for_subsidiary} {subsidiary}").format(
            candidate=self.candidate, for_subsidiary=_("for subsidiary"), subsidiary=self.subsidiary
        )

    @property
    def is_active(self):
        if self.end_date is None:
            return True
        return self.end_date > datetime.date.today()

    @property
    def is_stale(self):
        return now() - self.last_state_change > datetime.timedelta(days=STALE_DAYS)

    @property
    def needs_attention(self):
        return self.is_active and (
            self.is_stale
            or self.state
            in (
                Process.WAITING_ITW_MINUTE,
                Process.WAITING_INTERVIEW_PLANIFICATION,
                Process.WAITING_INTERVIEWER_TO_BE_DESIGNED,
                Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS,
            )
        )

    def trigger_notification(self, is_new):
        subject = None
        body_template = None
        if is_new:
            subject = _("New process {candidate}").format(candidate=self.candidate)
            body_template = "interview/email/new_process.txt"
        elif self.state == Process.CANDIDATE_DECLINED:
            subject = _("Process {process}: candidate declined").format(process=self)
            body_template = "interview/email/candidate_declined.txt"

        elif self.state == Process.HIRED:
            subject = _("Process {process}: Candidate accepted our offer").format(process=self)
            body_template = "interview/email/candidate_hired.txt"

        elif (
            self.state == Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
            and not self.interview_set.last()
        ):
            pass  # No mail in this case, reached at least when we reopen a process without interview

        elif (
            self.state == Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
            and self.interview_set.last().state
            in [
                Interview.GO,
                Interview.NO_GO,
            ]
        ):

            subject = _("Process {process}: {result}").format(process=self, result=self.interview_set.last().state)
            body_template = "interview/email/minute_done.txt"

        elif self.state == Process.JOB_OFFER:
            subject = _("Process {process}: job offer").format(process=self)
            body_template = "interview/email/job_offer.txt"

        if subject and body_template:
            url = os.path.join(settings.SITE_HOST, self.get_absolute_url().lstrip("/"))
            body = render_to_string(body_template, {"process": self, "url": url})
            recipient_list = []
            if self.subsidiary.responsible:
                recipient_list.append(self.subsidiary.responsible.email)
            mail.send_mail(
                subject=subject, message=body, from_email=settings.MAIL_FROM, recipient_list=set(recipient_list)
            )

    def get_all_interviewers_for_process(self):
        return PyouPyouUser.objects.filter(interview__process=self)


class InterviewKind(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class InterviewManager(models.Manager):
    def for_user(self, user):
        q = (
            super(InterviewManager, self)
            .get_queryset()
            .filter(Q(process__start_date__gte=user.date_joined) | Q(interviewers__in=[user]))
            .distinct()
        )
        if user.is_external:
            q = q.filter(process__sources=user.limited_to_source)
        return q

    def for_table(self, user):
        qs = (
            self.for_user(user)
            .select_related(
                "process",
                "process__subsidiary",
                "process__candidate",
                "process__offer",
                "kind_of_interview",
                "process__offer__subsidiary",
            )
            .prefetch_related("interviewers")
        )
        return qs


class Interview(models.Model):
    WAITING_PLANIFICATION = "NP"
    WAITING_PLANIFICATION_RESPONSE = "PR"
    PLANNED = "PL"
    GO = "GO"
    NO_GO = "NO"
    DRAFT = "DR"
    WAIT_INFORMATION = "WI"

    ITW_STATE = (
        (WAITING_PLANIFICATION, _("NEED PLANIFICATION")),
        (WAITING_PLANIFICATION_RESPONSE, _("WAIT PLANIFICATION RESPONSE")),
        (PLANNED, _("PLANNED")),
        (GO, _("GO")),
        (NO_GO, _("NO")),
        (DRAFT, _("DRAFT")),
        (WAIT_INFORMATION, _("WAIT INFORMATION")),
    )

    ALL_STATE_VALUES = [
        WAITING_PLANIFICATION,
        WAITING_PLANIFICATION_RESPONSE,
        PLANNED,
        GO,
        NO_GO,
        DRAFT,
        WAIT_INFORMATION,
    ]

    objects = InterviewManager()

    process = models.ForeignKey(Process, on_delete=models.CASCADE)
    state = models.CharField(max_length=3, choices=ITW_STATE, verbose_name=_("next state"))
    rank = models.IntegerField(verbose_name=_("Rank"), blank=True, null=True)
    planned_date = models.DateTimeField(verbose_name=_("Planned date"), blank=True, null=True)
    interviewers = models.ManyToManyField(PyouPyouUser)

    minute = models.TextField(verbose_name=_("Minute"), blank=True)
    minute_format = models.CharField(max_length=3, choices=MINUTE_FORMAT, default=MINUTE_FORMAT[0][0])
    next_interview_goal = models.TextField(verbose_name=_("Next interview goal"), blank=True)
    goal = models.TextField(verbose_name=_("Interview goal"), blank=True)
    prequalification = models.BooleanField(verbose_name=_("Prequalification"), default=False)
    kind_of_interview = models.ForeignKey(
        InterviewKind, verbose_name=_("Kind of interview"), blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        interviewers = ", ".join(i.trigramme for i in self.interviewers.all())
        return "#{rank} - {process} - {itws}".format(rank=self.rank, process=self.process, itws=interviewers)

    def save(self, *args, **kwargs):
        is_new = self.id is None

        if self.rank is None:
            # Rank is based on the number of interviews during the
            # same process that occured before the interview
            self.rank = (Interview.objects.filter(process=self.process).values_list("rank", flat=True).last() or 0) + 1

        if is_new:
            self.state = Interview.WAITING_PLANIFICATION

        if self.state is None and self.planned_date is None:
            self.state = self.WAITING_PLANIFICATION
        elif (
            self.state in [self.WAITING_PLANIFICATION, self.WAITING_PLANIFICATION_RESPONSE]
            and self.planned_date is not None
        ):
            self.state = self.PLANNED
            self.trigger_notification()
        elif self.state == self.PLANNED and self.planned_date is None:
            self.state = self.WAITING_PLANIFICATION

        super(Interview, self).save(*args, **kwargs)
        if is_new or (Interview.objects.filter(process=self.process).last() == self and self.process.is_open()):
            if self.state == self.WAITING_PLANIFICATION:
                self.process.state = Process.WAITING_INTERVIEW_PLANIFICATION
            if self.state == self.WAITING_PLANIFICATION_RESPONSE:
                self.process.state = Process.WAITING_INTERVIEW_PLANIFICATION_RESPONSE
            elif self.state == self.PLANNED:
                self.process.state = Process.INTERVIEW_IS_PLANNED
            elif self.state == self.WAIT_INFORMATION:
                self.process.state = Process.WAITING_ITW_MINUTE
            elif self.state in (Interview.GO, Interview.NO_GO):
                self.process.state = Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
            self.process.save()

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse(
            "interview-minute",
            kwargs={
                "interview_id": self.id,
                "slug_info": f"_{self.process.candidate.name_slug}-{self.interviewers_trigram_slug}-{self.rank}",
            },
        )

    @property
    def planning_request_sent(self):
        return self.planned_date is not None or self.state == self.WAITING_PLANIFICATION_RESPONSE

    def toggle_planning_request(self):
        if self.state == self.WAITING_PLANIFICATION:
            self.state = self.WAITING_PLANIFICATION_RESPONSE
        elif self.state == self.WAITING_PLANIFICATION_RESPONSE:
            self.state = self.WAITING_PLANIFICATION
        self.save()

    class Meta:
        unique_together = (("process", "rank"),)
        ordering = ["process", "rank"]

    @property
    def needs_attention(self):
        if not self.planning_request_sent:
            return True
        if self.planned_date and self.planned_date.date() < datetime.date.today():
            if self.state in [self.PLANNED, self.WAITING_PLANIFICATION] or not self.minute:
                return True
        return False

    @property
    def interviewers_str(self):
        if self.id:
            return ", ".join(i.get_full_name() for i in self.interviewers.all())
        return ""

    @property
    def interviewers_trigram_slug(self):
        if self.id:
            return "-".join(i.trigramme for i in self.interviewers.all())
        return ""

    def trigger_notification(self):
        recipient_list = []
        if self.process.subsidiary.responsible:
            recipient_list.append(self.process.subsidiary.responsible.email)
        if self.id:
            recipient_list = recipient_list + [i.email for i in self.interviewers.all()]

        subject = None
        body_template = None
        if self.state == Interview.WAITING_PLANIFICATION:
            subject = _("New interview for {process}").format(process=self.process)
            body_template = "interview/email/new_interview.txt"

        elif self.state == Interview.PLANNED:
            subject = _("Interview planned: {process}").format(process=self.process)
            body_template = "interview/email/interview_planned.txt"

        if subject and body_template:
            url = os.path.join(settings.SITE_HOST, self.process.get_absolute_url().lstrip("/"))
            body = render_to_string(body_template, {"interview": self, "url": url})
            mail.send_mail(
                subject=subject, message=body, from_email=settings.MAIL_FROM, recipient_list=set(recipient_list)
            )

    def get_goal(self):
        if self.goal:
            return self.goal
        try:
            return Interview.objects.filter(process=self.process).get(rank=self.rank - 1).next_interview_goal
        except Interview.DoesNotExist:
            return None


def document_minute_path(instance, filename):
    interview = instance.interview
    filename = filename.encode()
    extension = filename.split(b".")[-1]
    filename = str(slugify(interview.process.candidate)).encode() + ".".encode() + extension

    return "{}/{}_{}/{}".format("CompteRendu", interview.process, interview.rank, filename.decode())


class DocumentInterview(models.Model):

    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation date"))
    interview = models.ForeignKey(Interview, verbose_name=_("Interview"), on_delete=models.CASCADE)
    content = models.FileField(upload_to=document_minute_path, verbose_name=_("Content file"))
    name = models.CharField(max_length=255, verbose_name=_("Name"), blank=True)

    def __str__(self):
        return ("{candidate} - {interview}").format(
            candidate=self.interview.process.candidate, interview=self.interview
        )


@receiver(m2m_changed, sender=Interview.interviewers.through)
def interview_m2m_changed(sender, **kwargs):
    if kwargs["action"] == "post_add":
        instance = kwargs["instance"]
        # update process state
        instance.process.save()
        # trigger notification
        instance.trigger_notification()
