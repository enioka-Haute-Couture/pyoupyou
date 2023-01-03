import django.forms.widgets
import django_filters
from django.utils.translation import ugettext as _

from ref.models import Subsidiary


class SubsidiaryFilter(django_filters.FilterSet):
    subsidiary = django_filters.ModelChoiceFilter(
        queryset=Subsidiary.objects.all(),
        field_name="subsidiary",
        label="",
        empty_label=_("All subsidiaries"),
    )
