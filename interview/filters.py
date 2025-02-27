import django_filters

from interview.models import Process, Interview, Sources, Offer

from ref.models import PyouPyouUser
from django.utils.translation import gettext_lazy as _


class ProcessFilter(django_filters.FilterSet):
    class Meta:
        model = Process
        fields = ["contract_type"]


class KanbanProcessFilter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        subsidiary = kwargs.pop("subsidiary", None)
        super().__init__(*args, **kwargs)

        if subsidiary:
            self.filters["offer"].queryset = self.filters["offer"].queryset.filter(subsidiary=subsidiary)

    sources = django_filters.ModelChoiceFilter(queryset=Sources.objects.filter(archived=False), field_name="sources")
    offer = django_filters.ModelChoiceFilter(queryset=Offer.objects.filter(archived=False), field_name="offer")

    class Meta:
        model = Process
        fields = ["contract_type", "sources", "offer"]


class ProcessSummaryFilter(django_filters.FilterSet):
    last_state_change = django_filters.DateFromToRangeFilter(label="Date")


class InterviewSummaryFilter(django_filters.FilterSet):
    last_state_change = django_filters.DateFromToRangeFilter(field_name="planned_date")


class InterviewListFilter(django_filters.FilterSet):
    last_state_change = django_filters.DateFromToRangeFilter(field_name="planned_date")
    interviewer = django_filters.ModelChoiceFilter(
        queryset=PyouPyouUser.objects.filter(is_active=True), field_name="interviewers"
    )
    state = django_filters.ChoiceFilter(choices=Interview.ITW_STATE, field_name="state", empty_label=_("All states"))


class ActiveSourcesFilter(django_filters.FilterSet):
    # this is a choice filter instead of a BooleanFilter to allow better display of 'empty label'
    archived = django_filters.ChoiceFilter(
        choices=((True, _("Yes")), (False, _("No"))), label=_("Archived"), empty_label=_("All")
    )
