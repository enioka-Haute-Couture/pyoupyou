# -*- coding: utf-8 -*-

import datetime
import os

from django.conf import settings
from django.core import mail
from django.db import models
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from pyoupyou.settings import MINUTE_FORMAT, STALE_DAYS
from ref.models import Consultant, Subsidiary


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


class CandidateManager(models.Manager):
    def for_user(self, user):
        return Candidate.objects.distinct().filter(process__in=Process.objects.for_user(user))


class Candidate(models.Model):
    name = models.CharField(_("Name"), max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)

    # TODO Required by the reverse admin url resolver?
    app_label = "interview"
    model_name = "candidate"

    objects = CandidateManager()

    def __str__(self):
        return ("{name}").format(name=self.name)

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


class ProcessManager(models.Manager):
    def for_user(self, user):
        return super(ProcessManager, self).get_queryset().filter(start_date__gte=user.date_joined)


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

    start_date = models.DateField(verbose_name=_("Start date"), auto_now_add=True)
    end_date = models.DateField(verbose_name=_("End date"), null=True, blank=True)
    contract_type = models.ForeignKey(
        ContractType, null=True, blank=True, verbose_name=_("Contract type"), on_delete=models.SET_NULL
    )
    salary_expectation = models.IntegerField(verbose_name=_("Salary expectation (k€)"), null=True, blank=True)
    contract_duration = models.PositiveIntegerField(verbose_name=_("Contract duration in month"), null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    sources = models.ForeignKey(Sources, null=True, blank=True, on_delete=models.SET_NULL)
    responsible = models.ManyToManyField(Consultant, blank=True)
    state = models.CharField(
        max_length=3, choices=PROCESS_STATE, verbose_name=_("Closed reason"), default=WAITING_INTERVIEWER_TO_BE_DESIGNED
    )
    last_state_change = models.DateTimeField(verbose_name=_("Last State Change"), default=now)
    closed_comment = models.TextField(verbose_name=_("Closed comment"), blank=True)

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

        return reverse("process-details", args=[str(self.id)])

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

    @property
    def current_rank(self):
        last_interview = self.interview_set.last()
        if last_interview is None:
            return "0"
        return last_interview.rank

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

        elif self.state == Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS and self.interview_set.last().state in [
            Interview.GO,
            Interview.NO_GO,
        ]:

            subject = _("Process {process}: {result}").format(process=self, result=self.interview_set.last().state)
            body_template = "interview/email/minute_done.txt"

        elif self.state == Process.JOB_OFFER:
            subject = _("Process {process}: job offer").format(process=self)
            body_template = "interview/email/job_offer.txt"

        if subject and body_template:
            url = os.path.join(settings.SITE_HOST, self.get_absolute_url().lstrip("/"))
            body = render_to_string(body_template, {"process": self, "url": url})
            recipient_list = [settings.MAIL_HR]
            if self.subsidiary.responsible:
                recipient_list.append(self.subsidiary.responsible.user.email)
            mail.send_mail(
                subject=subject, message=body, from_email=settings.MAIL_FROM, recipient_list=set(recipient_list)
            )


class InterviewManager(models.Manager):
    def for_user(self, user):
        return super(InterviewManager, self).get_queryset().filter(process__start_date__gte=user.date_joined)


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

    objects = InterviewManager()

    process = models.ForeignKey(Process, on_delete=models.CASCADE)
    state = models.CharField(max_length=3, choices=ITW_STATE, verbose_name=_("next state"))
    rank = models.IntegerField(verbose_name=_("Rank"), blank=True, null=True)
    planned_date = models.DateTimeField(verbose_name=_("Planned date"), blank=True, null=True)
    interviewers = models.ManyToManyField(Consultant)

    minute = models.TextField(verbose_name=_("Minute"), blank=True)
    minute_format = models.CharField(max_length=3, choices=MINUTE_FORMAT, default=MINUTE_FORMAT[0][0])
    suggested_interviewer = models.ForeignKey(
        Consultant,
        verbose_name=_("Suggested interviewer"),
        related_name="suggested_interview_for",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    next_interview_goal = models.TextField(verbose_name=_("Next interview goal"), blank=True)

    def __str__(self):
        interviewers = ", ".join(i.user.trigramme for i in self.interviewers.all())
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

        return reverse("interview-minute", args=[str(self.id)])

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
            return ", ".join(i.user.get_full_name() for i in self.interviewers.all())
        return ""

    def trigger_notification(self):
        recipient_list = [settings.MAIL_HR]
        if self.process.subsidiary.responsible:
            recipient_list.append(self.process.subsidiary.responsible.user.email)
        if self.id:
            recipient_list = recipient_list + [i.user.email for i in self.interviewers.all()]

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


@receiver(m2m_changed, sender=Interview.interviewers.through)
def interview_m2m_changed(sender, **kwargs):
    if kwargs["action"] == "post_add":
        instance = kwargs["instance"]
        # update process state
        instance.process.save()
        # trigger notification
        instance.trigger_notification()
