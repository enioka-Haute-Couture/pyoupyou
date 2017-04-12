# -*- coding: utf-8 -*-
import datetime

from django import forms
from django.utils.translation import ugettext as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Submit, HTML, Button, Row, Field
from crispy_forms.bootstrap import AppendedText, PrependedText, FormActions
from django_select2.forms import ModelSelect2MultipleWidget

from interview.models import Subsidiary, Consultant, Interview, Candidate, Process
from pyoupyou.settings import DOCUMENT_TYPE, MINUTE_FORMAT

class MultipleConsultantWidget(ModelSelect2MultipleWidget):
    model = Consultant
    search_fields = [
        'user__trigramme__icontains',
        'user__full_name__icontains',
    ]


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        helper = FormHelper()
        exclude = []

    cv = forms.FileField(label="CV (pour une candidature)", required=True)

    helper = FormHelper()
    helper.form_tag = False


class ProcessForm(forms.ModelForm):
    class Meta:
        model = Process
        exclude = ['candidate', 'start_date', 'end_date']

    helper = FormHelper()
    helper.form_tag = False

# class CandidateForm(forms.Form):
#     name = forms.CharField(label="Name", required=True)
#     email = forms.CharField(label="email", required=False)
#     phone = forms.CharField(label="Phone", required=False)
#
#     cv = forms.FileField(label="CV (pour une candidature)", required=False)
#     subsidiary = forms.ModelChoiceField(label="Filliale", required=False,
#                                         queryset=Subsidiary.objects.all())
#     helper = FormHelper()
#     helper.form_method = 'POST'
#     helper.add_input(Submit('summit', _('Save'), css_class='btn-primary'))


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ['planned_date', 'interviewers']

        widgets = {
            'interviewers': MultipleConsultantWidget,
        }

    helper = FormHelper()
    helper.form_method = 'POST'
    helper.add_input(Submit('summit', _('Save'), css_class='btn-primary'))

class InterviewFormPlan(InterviewForm):
    class Meta:
        model = Interview
        fields = ['planned_date']

class InterviewFormEditInterviewers(InterviewForm):
    class Meta:
        model = Interview
        fields = ['interviewers']
        widgets = {
            'interviewers': MultipleConsultantWidget,
        }


class InterviewMinuteForm(forms.Form):
    date = forms.DateField(label="Date", initial=datetime.date.today)
    interviewer = forms.ModelChoiceField(label=_("Interviewer"), required=False,
                                         queryset=Consultant.objects.all(), disabled=True)
    minute = forms.CharField(label=_("Minute"),
                             widget=forms.Textarea(attrs={'rows': 4, 'cols': 40}))
    next_state = forms.ChoiceField(label=_("Result"), required=True,
                                   choices=Interview.ITW_STATE)
    helper = FormHelper()
    helper.form_method = 'POST'
    helper.add_input(Submit('summit', _('Save'), css_class='btn-primary'))
