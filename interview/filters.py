import django_filters

from interview.models import Process


class ProcessFilter(django_filters.FilterSet):
    class Meta:
        model = Process
        fields = ["subsidiary", "contract_type"]
