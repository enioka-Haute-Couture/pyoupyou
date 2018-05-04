# -*- coding: utf-8 -*-

import datetime

from django.db import models
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from pyoupyou.settings import MINUTE_FORMAT
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
    category = models.ForeignKey(SourcesCategory)
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
    app_label = 'interview'
    model_name = 'candidate'

    objects = CandidateManager()

    def __str__(self):
        return ("{name}").format(name=self.name)

    class Meta:
        verbose_name = _("Candidate")

def document_path(instance, filename):
    # todo ensure uniqueness (if two documents have the same name we reach a problem)
    filename = filename.encode()
    extension = filename.split(b'.')[-1]
    filename = str(slugify(instance.candidate.name)).encode() + '.'.encode() + extension

    return "{}/{}_{}/{}".format(instance.document_type,
                                instance.candidate.id,
                                slugify(instance.candidate.name),
                                filename.decode())


class Document(models.Model):
    DOCUMENT_TYPE = (
        ('CV', 'CV'),
        ('CL', 'Cover Letter'),
        ('OT', 'Others'),
    )

    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation date"))
    candidate = models.ForeignKey(Candidate, verbose_name=_("Candidate"))
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
    WAITING_INTERVIEW_PLANIFICATION = 'WP'
    INTERVIEW_IS_PLANNED = 'WI'
    WAITING_ITW_MINUTE = 'WM'
    OPEN = 'OP'
    WAITING_INTERVIEWER_TO_BE_DESIGNED = 'WA'
    WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS = 'WK'
    NO_GO = 'NG'
    CANDIDATE_DECLINED = 'CD'
    HIRED = 'HI'
    OTHER = 'NO'
    JOB_OFFER = 'JO'

    CLOSED_STATE = (
        (NO_GO, _('Last interviewer interupt process')),
        (CANDIDATE_DECLINED, _('Candidate declined our offer')),
        (HIRED, _('Candidate accepted our offer')),
        (OTHER, _('Closed - other reason')),
    )

    INTERVIEW_STATE = (
        (WAITING_INTERVIEW_PLANIFICATION, _('Waiting interview planification')),
        (WAITING_ITW_MINUTE, _('Waiting interview minute')),
        (INTERVIEW_IS_PLANNED, _('Waiting interview')),
    )
    OPEN_STATE = (
        WAITING_INTERVIEWER_TO_BE_DESIGNED,
        WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS,
        JOB_OFFER,
    ) + INTERVIEW_STATE
    PROCESS_STATE = (
        (OPEN, _('Open')),
        (WAITING_INTERVIEWER_TO_BE_DESIGNED, _('Waiting interviewer to be designed')),
        (WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS, _('Waiting next interview designation or process termination')),
        (JOB_OFFER, _('Waiting candidate feedback after a job offer'))
    ) + INTERVIEW_STATE + CLOSED_STATE

    objects = ProcessManager()
    candidate = models.ForeignKey(Candidate, verbose_name=_("Candidate"))
    subsidiary = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"))

    start_date = models.DateField(verbose_name=_("Start date"), auto_now_add=True)
    end_date = models.DateField(verbose_name=_("End date"), null=True, blank=True)
    contract_type = models.ForeignKey(ContractType, null=True, blank=True, verbose_name=_("Contract type"))
    salary_expectation = models.IntegerField(verbose_name=_("Salary expectation (k€)"), null=True, blank=True)
    contract_duration = models.PositiveIntegerField(verbose_name=_("Contract duration in month"), null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    sources = models.ForeignKey(Sources, null=True, blank=True)
    responsible = models.ManyToManyField(Consultant, blank=True)
    state = models.CharField(max_length=3, choices=PROCESS_STATE, verbose_name=_("Closed reason"), default=WAITING_INTERVIEWER_TO_BE_DESIGNED)
    closed_comment = models.TextField(verbose_name=_("Closed comment"), blank=True)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        super().save(force_insert, force_update, using, update_fields)

        if self.state in (Process.WAITING_INTERVIEWER_TO_BE_DESIGNED,
                          Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS,
                          Process.JOB_OFFER):
            self.responsible.clear()
            self.responsible.add(self.subsidiary.responsible)
        if self.state in (Process.CANDIDATE_DECLINED, Process.HIRED):
            self.responsible.clear()
        if self.state in (Process.WAITING_INTERVIEW_PLANIFICATION,
                          Process.INTERVIEW_IS_PLANNED):
            self.responsible.clear()
            for interviewer in self.interview_set.last().interviewers.all():
                self.responsible.add(interviewer)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('process-details', args=[str(self.id)])


    # @cached_property
    # def state(self):
    #     if self.closed_reason == Process.OPEN:
    #         last_itw = self.interview_set.last()
    #         if last_itw:
    #             return self.interview_set.last().state
    #         return None
    #     else:
    #         return self.closed_reason

    # @cached_property
    # def next_action_display(self):
    #     if self.closed_reason == Process.OPEN:
    #         if self.state:
    #             if self.state == Interview.GO:
    #                 return _("Pick up next interviewer")
    #             if self.state == Interview.NO_GO:
    #                 return _("Inform candidate")
    #             return dict(Interview.ITW_STATE)[self.state]
    #         return _("Pick up next interviewer")
    #     else:
    #         return self.get_closed_reason_display()

    # @cached_property
    # def next_action_responsible(self):
    #     if self.state in (Interview.WAITING_PLANIFICATION, Interview.PLANNED):
    #         return self.interview_set.last().interviewers
    #     return self.subsidiary.responsible

    # def is_open(self):
    #     return self.state not in Process.CLOSED_STATE

    def __str__(self):
        return ("{candidate} {for_subsidiary} {subsidiary}").format(candidate=self.candidate,
                                                                    for_subsidiary=_("for subsidiary"),
                                                                    subsidiary=self.subsidiary)

    @property
    def is_active(self):
        if self.end_date is None:
            return True
        return self.end_date > datetime.date.today()

    @property
    def needs_attention(self):
        return self.is_active and self.state in (Process.WAITING_ITW_MINUTE,
                                  Process.WAITING_INTERVIEW_PLANIFICATION,
                                  Process.WAITING_INTERVIEWER_TO_BE_DESIGNED,
                                  Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS)

    @cached_property
    def is_recently_closed(self):
        if self.end_date is None:
            return False
        closed_since = datetime.date.today() - self.end_date

    @property
    def current_rank(self):
        last_interview = self.interview_set.last()
        if last_interview is None:
            return "0"
        return last_interview.rank


class InterviewManager(models.Manager):
    def for_user(self, user):
        return super(InterviewManager, self).get_queryset().filter(process__start_date__gte=user.date_joined)


class Interview(models.Model):
    WAITING_PLANIFICATION = 'NP'
    PLANNED = 'PL'
    GO = 'GO'
    NO_GO = 'NO'
    DRAFT = 'DR'
    WAIT_INFORMATION = 'WI'

    ITW_STATE = (
        (WAITING_PLANIFICATION, _('NEED PLANIFICATION')),
        (PLANNED, _('PLANNED')),
        (GO, _('GO')),
        (NO_GO, _('NO')),
        (DRAFT, _('DRAFT')),
        (WAIT_INFORMATION, _('WAIT INFORMATION')),
    )

    objects = InterviewManager()

    process = models.ForeignKey(Process)
    state = models.CharField(max_length=3, choices=ITW_STATE, verbose_name=_("next state"))
    rank = models.IntegerField(verbose_name=_("Rank"), blank=True, null=True)
    planned_date = models.DateTimeField(verbose_name=_("Planned date"), blank=True, null=True)
    interviewers = models.ManyToManyField(Consultant)

    minute = models.TextField(verbose_name=_("Minute"), blank=True)
    minute_format = models.CharField(max_length=3,
                                     choices=MINUTE_FORMAT,
                                     default=MINUTE_FORMAT[0][0])
    suggested_interviewer = models.ForeignKey(Consultant, verbose_name=_("Suggested interviewer"),
                                              related_name='suggested_interview_for', null=True, blank=True)
    next_interview_goal = models.TextField(verbose_name=_("Next interview goal"), blank=True)

    def __str__(self):
        return "#{rank} - {process}".format(process=self.process, rank=self.rank)

    def save(self, *args, **kwargs):
        current_state = self.state
        is_new = self.id is None

        if self.rank is None:
            # Rank is based on the number of interviews during the
            # same process that occured before the interview
            self.rank = (Interview.objects.filter(process=self.process).values_list('rank', flat=True).last() or 0) + 1

        if is_new:
            self.state = self.state or Interview.WAITING_PLANIFICATION

        if self.planned_date is None and self.state is None:
            self.state = self.WAITING_PLANIFICATION
        else:
            if self.state == self.WAITING_PLANIFICATION and self.planned_date is not None:
                self.state = self.PLANNED

        super(Interview, self).save(*args, **kwargs)
        if self.state == self.WAITING_PLANIFICATION:
            self.process.state = Process.WAITING_INTERVIEW_PLANIFICATION
            self.process.save()
        elif self.state == self.PLANNED:
            self.process.state = Process.INTERVIEW_IS_PLANNED
            self.process.save()
        if self.state in (Interview.GO, Interview.NO_GO):
            self.process.state = Process.WAITING_NEXT_INTERVIEWER_TO_BE_DESIGNED_OR_END_OF_PROCESS
            self.process.save()

        if is_new:
            self.trigger_notification()

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('interview-minute', args=[str(self.id)])

    class Meta:
        unique_together = (('process', 'rank'), )
        ordering = ['process', 'rank']

    @property
    def needs_attention(self):
        if self.planned_date is None:
            return (True, _("Interview must be planned"))
        if self.planned_date and self.planned_date.date() < datetime.date.today():
            if self.state in [self.PLANNED, self.WAITING_PLANIFICATION]:
                return (True, _("Interview result hasn't been submited"))
            if not self.minute:
                return (True, _("No minute has been written for this interview"))
        return (False, "")

    def trigger_notification(self):
        # print("NOTIFICATION : ")
        # print(self.interviewers.all())
        pass


@receiver(post_save, sender=Interview)
def interview_post_save(*args, **kwargs):
    # print("post save")
    # print(kwargs)
    # print(kwargs["instance"].interviewers.all())
    pass

@receiver(m2m_changed, sender=Interview.interviewers.through)
def interview_m2m_changed(sender, **kwargs):
    # # TODO filter actions (post_add
    # action = kwargs['action']
    # if action == "post_add":
    #     print(f"added {kwargs['pk_set']}")
    # if action == "post_remove":
    #     print(f"removed {kwargs['pk_remove']}")
    #
    # print("m2m")
    # instance = kwargs["instance"]
    # print(kwargs)
    # instance.trigger_notification()
    pass
