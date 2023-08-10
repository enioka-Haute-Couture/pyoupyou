import django_filters

from interview.models import Process, Interview
from ref.models import Subsidiary, Consultant
from django.utils.translation import gettext_lazy as _


class ProcessFilter(django_filters.FilterSet):
    class Meta:
        model = Process
        fields = ["contract_type"]


class ProcessSummaryFilter(django_filters.FilterSet):
    last_state_change = django_filters.DateFromToRangeFilter(label="Date")


class InterviewSummaryFilter(django_filters.FilterSet):
    last_state_change = django_filters.DateFromToRangeFilter(field_name="planned_date")


class InterviewListFilter(django_filters.FilterSet):
    last_state_change = django_filters.DateFromToRangeFilter(field_name="planned_date")
    interviewer = django_filters.ModelChoiceFilter(
        queryset=Consultant.objects.filter(user__is_active=True).select_related("user"), field_name="interviewers"
    )
    state = django_filters.ChoiceFilter(choices=Interview.ITW_STATE, field_name="state", empty_label=_("All states"))


class ActiveSourcesFilter(django_filters.FilterSet):
    # this is a choice filter instead of a BooleanFilter to allow better display of 'empty label'
    archived = django_filters.ChoiceFilter(
        choices=((True, _("Yes")), (False, _("No"))), label=_("Archived"), empty_label=_("All")
    )
