import datetime

from django.db import models
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from pyoupyou.settings import DOCUMENT_TYPE, MINUTE_FORMAT
from ref.models import Consultant, Subsidiary


class ContractType(models.Model):
    name = models.CharField(_("Name"), max_length=200)
    has_duration = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class SourcesCategory(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class Sources(models.Model):
    name = models.CharField(max_length=50)
    category = models.ForeignKey(SourcesCategory)

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
    filename = filename.encode()
    extension = filename.split(b'.')[-1]
    filename = str(slugify(instance.candidate.name)).encode() + '.'.encode() + extension

    return "{}/{}_{}/{}".format(instance.document_type,
                                  instance.candidate.id,
                                  slugify(instance.candidate.name),
                                  filename.decode())

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
    contract_type = models.ForeignKey(ContractType, null=True, blank=True)
    salary_expectation = models.IntegerField(verbose_name=_("Salary expectation (k€)"), null=True, blank=True)
    contract_duration = models.PositiveIntegerField(verbose_name=_("Contract duration in month"), null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    sources = models.ForeignKey(Sources, null=True, blank=True)

    @property
    def state(self):
        last_itw = self.interview_set.last()
        if last_itw:
            return self.interview_set.last().next_state
        return None

    @property
    def next_action_display(self):
        if self.state:
            return dict(Interview.ITW_STATE)[self.state]
        return 'Pick up next interviewer'

    @property
    def next_action_responsible(self):
        if self.state in (Interview.NEED_PLANIFICATION, Interview.PLANNED):
            return self.interview_set.last().interviewers
        return self.subsidiary.responsible

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
    def needs_attention(self):
        # Is late:
        # - is_active
        # - last interview past and no minute
        # - no next interview planned
        if not self.is_active:
            return (False, "")
        last_interview = self.interview_set.last()
        if last_interview is None:
            return (True, _("No interview has been planned yet"))
        if last_interview.planned_date and last_interview.planned_date < datetime.date.today():
            for i in self.interview_set.all():
                if i.needs_attention_bool:
                    return (True, _("Last interview needs attention"))
            else:
                return (False, "")
        return (False, "")

    @property
    def needs_attention_bool(self):
        return self.needs_attention[0]

    @property
    def needs_attention_reason(self):
        return self.needs_attention[1]

    @property
    def is_recently_closed(self):
        if self.end_date is None:
            return False
        closed_since = datetime.date.today() - self.end_date


class Interview(models.Model):
    NEED_PLANIFICATION = 'NP'
    PLANNED = 'PL'
    GO = 'GO'
    NO_GO = 'NO'

    ITW_STATE = (
        (NEED_PLANIFICATION, _('NEED PLANIFICATION')),
        (PLANNED, _('PLANNED')),
        (GO, _('GO')),
        (NO_GO, _('NO')),
    )

    process = models.ForeignKey(Process)
    next_state = models.CharField(max_length=3, choices=ITW_STATE, verbose_name=_("next state"))
    rank = models.IntegerField(verbose_name=_("Rank"), blank=True, null=True)
    planned_date = models.DateField(verbose_name=_("Planned date"), blank=True, null=True)
    interviewers = models.ManyToManyField(Consultant, through='InterviewInterviewer',
                                          through_fields=('interview', 'interviewer'))

    def __str__(self):
        return "#{rank} - {process}".format(process=self.process, rank=self.rank)

    def save(self, *args, **kwargs):
        if self.rank is None:
            # Rank is based on the number of interviews during the
            # same process that occured before the interview
            self.rank = (Interview.objects.filter(process=self.process).values_list('rank', flat=True).last() or 0) + 1
        if self.id is None:
            self.next_state = self.next_state or Interview.NEED_PLANIFICATION

        if self.planned_date is None:
            self.next_state = self.NEED_PLANIFICATION
        else:
            if self.next_state == self.NEED_PLANIFICATION:
                self.next_state = self.PLANNED

        super(Interview, self).save(*args, **kwargs)

    class Meta:
        unique_together = (('process', 'rank'), )
        ordering = ['process', 'rank']

    @property
    def needs_attention(self):
        if self.planned_date is None:
            return (True, _("Interview must be planned"))
        if self.planned_date and self.planned_date < datetime.date.today():
            if self.next_state in [self.PLANNED, self.NEED_PLANIFICATION]:
                return (True, _("Interview result hasn't been submited"))
            nb_minute = InterviewInterviewer.objects.filter(interview=self)\
                                                    .exclude(minute__isnull=True)\
                                                    .exclude(minute__exact='').count()
            if nb_minute == 0:
                return (True, _("No minute has been written for this interview"))
        return (False, "")

    @property
    def needs_attention_bool(self):
        return self.needs_attention[0]

    @property
    def needs_attention_reason(self):
        return self.needs_attention[1]

class InterviewInterviewer(models.Model):
    interview = models.ForeignKey(Interview, verbose_name=_("Interview"), on_delete=models.CASCADE)
    interviewer = models.ForeignKey(Consultant, verbose_name=_("Interviewer"), on_delete=models.CASCADE)
    minute = models.TextField(verbose_name=_("Minute"), blank=True)
    minute_format = models.CharField(max_length=3,
                                     choices=MINUTE_FORMAT,
                                     default=MINUTE_FORMAT[0][0])
    suggested_interviewer = models.ForeignKey(Consultant, verbose_name=_("Suggested interviewer"),
                                              related_name='suggested_interview_for', null=True, blank=True)

    class Meta:
        unique_together = (('interview','interviewer'))

    def __str__(self):
        return "{candidate} - {interviewer}".format(candidate=self.interview.process.candidate, interviewer=self.interviewer)
