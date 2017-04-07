import datetime

from django.db import models
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from os.path import join

from pyoupyou.settings import DOCUMENT_TYPE, MINUTE_FORMAT, ITW_STATE
from ref.models import Consultant, Subsidiary


class ContractType(models.Model):
    name = models.CharField(_("Name"), max_length=200)
    has_duration = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Candidate(models.Model):
    name = models.CharField(_("Name"), max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)

    # TODO Required by the reverse admin url resolver?
    app_label = 'interview'
    model_name = 'candidate'

    def __str__(self):
        return ("{name}").format(name=self.name)


def document_path(instance, filename):
    # TODO : remove filename and only keep extension
    return "{}/{}_{}/{}".format(instance.document_type,
                                instance.candidate.id,
                                slugify(instance.candidate.name),
                                filename)


class Document(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    candidate = models.ForeignKey(Candidate)
    document_type = models.CharField(max_length=2, choices=DOCUMENT_TYPE)
    content = models.FileField(upload_to=document_path)
    still_valid = models.BooleanField(default=True)

    def __str__(self):
        return ("{candidate} - {document_type}").format(candidate=self.candidate, document_type=self.document_type)


class Process(models.Model):
    candidate = models.ForeignKey(Candidate)
    subsidiary = models.ForeignKey(Subsidiary)
    start_date = models.DateField(verbose_name=_("Start date"), auto_now_add=True)
    end_date = models.DateField(verbose_name=_("End date"), null=True, blank=True)
    contract_type = models.ForeignKey(ContractType, null=True)
    salary_expectation = models.IntegerField(verbose_name=_("Salary expectation (k€)"), null=True, blank=True)
    duration = models.PositiveIntegerField(verbose_name=_("Contract duration in month"), null=True, blank=True)

    @property
    def state(self):
        return self.interview_set.last().next_state

    def __str__(self):
        return ("{candidate} {for_subsidiary} {subsidiary}").format(candidate=self.candidate,
                                                                    for_subsidiary = _("for subsidiary"),
                                                                    subsidiary=self.subsidiary)

    @property
    def is_active(self):
        if self.end_date is None:
            return True
        return self.end_date > datetime.date.today()

    @property
    def is_late(self):
        # Is late:
        # - is_active
        # - last interview past and no minute
        # - no next interview planned
        if not self.is_active:
            return False
        last_interview = self.interview_set.last()
        if last_interview is None:
            return False
        if last_interview.planned_date.date() < datetime.date.today():
            return True

        return True

    @property
    def is_recently_closed(self):
        if self.end_date is None:
            return False
        closed_since = datetime.date.today() - self.end_date


class Interview(models.Model):
    process = models.ForeignKey(Process)
    next_state = models.CharField(max_length=3, choices=ITW_STATE, verbose_name=_("next state"))
    # TODO editable false and auto generate when saving first time
    rank = models.IntegerField(verbose_name=_("Rank"), blank=True, null=True)
    planned_date = models.DateTimeField(verbose_name=_("Planned date"), blank=True, null=True)

    def __str__(self):
        return "#{rank} - {process}".format(process=self.process, rank=self.rank)

    def save(self, *args, **kwargs):
        if self.rank is None:
            # Rank is based on the number of interviews during the
            # same process that occured before the interview, or the
            # total number of interview already in the list
            self.rank = Interview.objects.filter(process=self.process).count() + 1
        super(Interview, self).save(*args, **kwargs)

    class Meta:
        unique_together = (('process', 'rank'), )
        ordering = ['process', 'rank']

    @property
    def interviewers(self):
        interview_interviewers = InterviewInterviewer.objects.filter(interview=self.id).first()
        return(interview_interviewers)

    @property
    def needs_attention(self):
        if self.planned_date.date() < datetime.date.today():
            if self.next_state in ["PD", "PL"]:
                return True
            try:
                interview_interviewer = InterviewInterviewer.objects.get(interview=self)
                if interview_interviewer.minute is None:
                    return True
                if "" == interview_interviewer.minute:
                    return True
            except InterviewInterviewer.DoesNotExist:
                return True
        return False


class InterviewInterviewer(models.Model):
    interview = models.ForeignKey(Interview, verbose_name=_("Interview"))
    interviewer = models.ForeignKey(Consultant, verbose_name=_("Interviewer"))
    minute = models.TextField(verbose_name=_("Minute"), blank=True)
    minute_format = models.CharField(max_length=3,
                                     choices=MINUTE_FORMAT,
                                     default=MINUTE_FORMAT[0][0])
    suggested_interviewer = models.ForeignKey(Consultant, verbose_name=_("Suggested interviewer"),
                                              related_name='suggested_interview_for', null=True, blank=True)

    class Meta:
        unique_together = (('interview',))
        pass

    def __str__(self):
        return "{interviewer}".format(interviewer=self.interviewer)
