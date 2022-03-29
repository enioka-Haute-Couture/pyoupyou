import django_filters

from interview.models import Process
from ref.models import Subsidiary, Consultant


class ProcessFilter(django_filters.FilterSet):
    class Meta:
        model = Process
        fields = ["subsidiary", "contract_type"]


class ProcessSummaryFilter(django_filters.FilterSet):
    subsidiary = django_filters.ModelChoiceFilter(queryset=Subsidiary.objects.all())
    last_state_change = django_filters.DateFromToRangeFilter(label="Date")


class InterviewSummaryFilter(django_filters.FilterSet):
    subsidiary = django_filters.ModelChoiceFilter(queryset=Subsidiary.objects.all(), field_name="process__subsidiary")
    last_state_change = django_filters.DateFromToRangeFilter(field_name="planned_date")


class InterviewListFilter(django_filters.FilterSet):
    subsidiary = django_filters.ModelChoiceFilter(queryset=Subsidiary.objects.all(), field_name="process__subsidiary")
    last_state_change = django_filters.DateFromToRangeFilter(field_name="planned_date")
    interviewer = django_filters.ModelChoiceFilter(
        queryset=Consultant.objects.filter(user__is_active=True).select_related("user"), field_name="interviewers"
    )
