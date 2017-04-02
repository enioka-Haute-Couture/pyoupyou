# -*- coding: utf-8 -*-
import datetime

from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Submit, HTML, Button, Row, Field
from crispy_forms.bootstrap import AppendedText, PrependedText, FormActions

from interview.models import Subsidiary, Consultant, Interview
from pyoupyou.settings import DOCUMENT_TYPE, MINUTE_FORMAT, ITW_STATE


class CandidateForm(forms.Form):
    name = forms.CharField(label="Name", required=True)
    email = forms.CharField(label="email", required=False)
    phone = forms.CharField(label="Phone", required=False)

    cv = forms.FileField(label="CV (pour une candidature)", required=False)
    subsidiary = forms.ModelChoiceField(label="Filliale", required=False,
                                        queryset=Subsidiary.objects.all())
    helper = FormHelper()
    helper.form_method = 'POST'
    helper.add_input(Submit('summit', 'Enregistrer', css_class='btn-primary'))


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        # TODO hide process field
        fields = ['date', 'interviewer', 'process']

    date = forms.DateField(label="Date", initial=datetime.date.today)
    interviewer = forms.ModelChoiceField(label="Personne en charge de l'interview", required=True,
                                         queryset=Consultant.objects.all())

    helper = FormHelper()
    helper.form_method = 'POST'
    helper.add_input(Submit('summit', 'Enregistrer', css_class='btn-primary'))


class InterviewMinuteForm(forms.Form):
    date = forms.DateField(label="Date", initial=datetime.date.today)
    interviewer = forms.ModelChoiceField(label="Personne en charge de l'interview", required=False,
                                         queryset=Consultant.objects.all(), disabled=True)
    minute = forms.CharField(label="Compte-rendu",
                             widget=forms.Textarea(attrs={'rows': 4, 'cols': 40}))
    next_state = forms.ChoiceField(label="Issue de l'interview", required=True,
                                   choices=ITW_STATE)
    helper = FormHelper()
    helper.form_method = 'POST'
    helper.add_input(Submit('summit', 'Enregistrer', css_class='btn-primary'))
