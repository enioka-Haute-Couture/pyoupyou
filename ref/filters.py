import django_filters
from django.utils.translation import ugettext_lazy as _

from ref.models import Subsidiary


class SubsidiaryFilter(django_filters.FilterSet):
    subsidiary = django_filters.ModelChoiceFilter(
        queryset=Subsidiary.objects.all(), field_name="subsidiary", label=_("Subsidiary"), empty_label=_("All")
    )
