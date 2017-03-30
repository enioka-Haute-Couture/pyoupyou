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

    def __str__(self):
        return _("{name}").format(name=self.name)


def document_path(instance, filename):
    return "{}/{}/{}".format(instance.document_type, slugify(instance.candidate.name), filename) # TODO manage homonyms


class Document(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    candidate = models.ForeignKey(Candidate)
    document_type = models.CharField(max_length=2, choices=DOCUMENT_TYPE)
    document = models.FileField(upload_to=document_path)
    still_valid = models.BooleanField(default=True)

    def __str__(self):
        return _("{candidate} - {document_type}").format(candidate=self.candidate, document_type=self.document_type)


class Process(models.Model):
    candidate = models.ForeignKey(Candidate)
    subsidiary = models.ForeignKey(Subsidiary)
    start_date = models.DateField(verbose_name=_("start date"), auto_now_add=True)
    end_date = models.DateField(verbose_name=_("end date"), null=True, blank=True)
    contract_type = models.ForeignKey(ContractType, null=True)
    salary_expectation = models.IntegerField(verbose_name=_("Salary expectation (k€)"), null=True, blank=True)
    duration = models.PositiveIntegerField(verbose_name=_("Contract duration in month"), null=True, blank=True)

    @property
    def state(self):
        return self.interview_set.last().next_state

    def __str__(self):
        return _("{candidate} for {subsidiary}").format(candidate=self.candidate, subsidiary=self.subsidiary)


class Interview(models.Model):
    process = models.ForeignKey(Process)
    next_state = models.CharField(max_length=3, choices=ITW_STATE, verbose_name=_("next state"))
    rank = models.IntegerField(verbose_name=_("rank")) # TODO editable false and auto generate when saving first time
    planned_date = models.DateTimeField(verbose_name=_("planned date"), blank=True, null=True)

    def __str__(self):
        return _("#{rank} - {process}").format(process=self.process, rank=self.rank)

    class Meta:
        unique_together = (('process', 'rank'), )
        ordering = ['process', 'rank']


class InterviewInterviewer(models.Model):
    interview = models.ForeignKey(Interview, verbose_name=_("interview"))
    interviewer = models.ForeignKey(Consultant, verbose_name=_("interviewer"), related_name='interviewer_for')
    minute = models.TextField(verbose_name=_("minute"), blank=True)
    minute_format = models.CharField(max_length=3, choices=MINUTE_FORMAT)
    suggested_interviewer = models.ForeignKey(Consultant, verbose_name=_("suggested interviewer"),
                                              related_name='suggested_interview_for', null=True, blank=True)

    class Meta:
        unique_together = (('interview', 'interviewer'))

    def __str__(self):
        return _("{interviewer}").format(interviewer=self.interviewer)
