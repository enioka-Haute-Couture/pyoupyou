# -*- coding: utf-8 -*-
from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Submit, Column
from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget

from interview.models import Consultant, Interview, Candidate, Process, Sources, Offer


class MultipleConsultantWidget(ModelSelect2MultipleWidget):
    model = Consultant
    queryset = Consultant.objects.filter(user__is_active=True)
    search_fields = ["user__trigramme__icontains", "user__full_name__icontains"]


class SourcesWidget(ModelSelect2Widget):
    model = Sources
    queryset = Sources.objects.filter(archived=False)
    search_fields = ["name__icontains"]


class ProcessCandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        helper = FormHelper()
        exclude = []

    cv = forms.FileField(label="CV (pour une candidature)", required=False)

    helper = FormHelper()
    helper.form_tag = False


class SelectOrCreateSource(SourcesWidget):
    def render(self, *args, **kwargs):
        output = [super().render(*args, **kwargs)]
        output.append(render_to_string("interview/select_or_create_source.html"))
        return mark_safe("\n".join(output))


class SelectOrCreateOffer(ModelSelect2Widget):
    model = Offer
    queryset = Offer.objects.filter(archived=False)
    search_fields = ["name__icontains", "subsidiary__name__icontains"]

    def render(self, *args, **kwargs):
        output = [super().render(*args, **kwargs)]
        output.append(render_to_string("interview/select_or_create_offer.html"))
        return mark_safe("\n".join(output))


class ProcessForm(forms.ModelForm):
    class Meta:
        model = Process
        exclude = ["candidate", "start_date", "end_date", "state", "closed_comment", "responsible", "last_state_change"]

        widgets = {"sources": SelectOrCreateSource, "offer": SelectOrCreateOffer}

    helper = FormHelper()
    helper.form_tag = False


class SourceForm(forms.ModelForm):
    class Meta:
        model = Sources
        fields = ["category", "name"]

    helper = FormHelper()
    helper.form_tag = False


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ["subsidiary", "name"]

    helper = FormHelper()
    helper.form_tag = False


class InterviewersForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["interviewers"]
        widgets = {"interviewers": MultipleConsultantWidget}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interviewers"].required = False

    helper = FormHelper()
    helper.form_tag = False


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["planned_date", "interviewers"]

        widgets = {"interviewers": MultipleConsultantWidget}

    helper = FormHelper()
    helper.form_method = "POST"
    helper.add_input(Submit("summit", _("Save"), css_class="btn-primary"))


class InterviewFormPlan(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["planned_date"]

    helper = FormHelper()
    helper.form_method = "POST"
    helper.add_input(Submit("summit", _("Save"), css_class="btn-primary"))
    helper.layout = Layout(Div(Column("planned_date"), css_class="relative"))


class InterviewFormEditInterviewers(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["interviewers"]
        widgets = {"interviewers": MultipleConsultantWidget}

    helper = FormHelper()
    helper.form_method = "POST"
    helper.add_input(Submit("summit", _("Save"), css_class="btn-primary"))


class InterviewMinuteForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["minute", "suggested_interviewer", "next_interview_goal"]

    helper = FormHelper()
    helper.form_tag = False


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ["name", "email", "phone"]

    helper = FormHelper()
    helper.form_method = "POST"
    helper.add_input(Submit("summit", _("Save"), css_class="btn-primary"))


class CloseForm(forms.ModelForm):
    class Meta:
        model = Process
        fields = ["state", "closed_comment"]

    # we remove open choice
    state = forms.ChoiceField(
        choices=Process.CLOSED_STATE + ((Process.JOB_OFFER, _("Waiting candidate feedback after a job offer")),)
    )
    helper = FormHelper()
    helper.form_tag = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        default_choice = Process.NO_GO
        if self.instance.interview_set.last() and self.instance.interview_set.last().state == Interview.GO:
            default_choice = Process.HIRED
        self.fields["state"].initial = default_choice


class UploadSeekubeFileForm(forms.Form):
    file = forms.FileField()
    helper = FormHelper()
    helper.form_method = "POST"
    helper.add_input(Submit("summit", _("Import"), css_class="btn-primary"))
