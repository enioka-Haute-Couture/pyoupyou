# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Submit, Column, Field
from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget

from interview.models import Interview, Candidate, Process, Sources, Offer
from ref.models import PyouPyouUser


class MultipleConsultantWidget(ModelSelect2MultipleWidget):
    model = PyouPyouUser
    queryset = PyouPyouUser.objects.filter(is_active=True)
    search_fields = ["trigramme__icontains", "full_name__icontains"]


class SingleConsultantWidget(ModelSelect2Widget):
    model = PyouPyouUser
    queryset = PyouPyouUser.objects.filter(is_active=True)
    search_fields = ["trigramme__icontains", "full_name__icontains"]


class SourcesWidget(ModelSelect2Widget):
    model = Sources
    queryset = Sources.objects.filter(archived=False)
    search_fields = ["name__icontains"]


class ProcessCandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        helper = FormHelper()
        exclude = ("anonymized", "anonymized_hashed_name", "anonymized_hashed_email")

    cv = forms.FileField(label="CV (pour une candidature)", required=False)

    helper = FormHelper()
    helper.form_tag = False


class ProcessReuseCandidateForm(ProcessCandidateForm):
    def clean(self):
        cleaned_data = super().clean()

        for changed_data in self.changed_data:
            # When reusing a candidate, data object keys for which a value if blank are removed
            # Instance data override are kept if data changed but keys don't exist
            if changed_data not in self.data and self.instance.__dict__[changed_data] is not None:
                cleaned_data[changed_data] = self.instance.__dict__[changed_data]

        return cleaned_data


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
        exclude = [
            "candidate",
            "start_date",
            "end_date",
            "state",
            "closed_comment",
            "responsible",
            "last_state_change",
            "creator",
            "subscribers",
        ]

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
    def clean(self):
        cleaned_data = super().clean()
        interviewers = cleaned_data.get("interviewers")
        planned_date = cleaned_data.get("planned_date")

        if not interviewers and planned_date:
            raise ValidationError(_("Interviewers must be specified when setting planned date"))

    class Meta:
        model = Interview
        fields = ["interviewers", "planned_date", "kind_of_interview", "prequalification"]
        widgets = {"interviewers": MultipleConsultantWidget}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interviewers"].required = False

    helper = FormHelper()
    helper.form_tag = False


class InterviewFormPlan(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["planned_date", "kind_of_interview"]

    helper = FormHelper()
    helper.form_method = "POST"
    helper.add_input(Submit("summit", _("Save"), css_class="btn-primary"))
    helper.layout = Layout(Div(Column("planned_date", "kind_of_interview"), css_class="relative"))


class InterviewFormEditInterviewers(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["interviewers", "kind_of_interview", "goal", "prequalification"]
        widgets = {
            "interviewers": MultipleConsultantWidget,
            "goal": forms.Textarea(attrs={"placeholder": _("Add a goal only if it differs")}),
        }

    helper = FormHelper()
    helper.form_method = "POST"
    helper.add_input(Submit("summit", _("Save"), css_class="btn-primary"))


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class InterviewMinuteForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["minute", "next_interview_goal", "kind_of_interview"]

    document = forms.FileField(label="Document", required=False, widget=MultipleFileInput())
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
