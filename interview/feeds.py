from datetime import timedelta

from django.http.response import HttpResponse
from django.utils.encoding import force_str
from django.utils.html import escape
from django_ical.views import ICalFeed
from django.utils import timezone

from interview.models import Interview
from ref.models import Subsidiary, PyouPyouUser, Consultant


class AbstractPyoupyouInterviewFeed(ICalFeed):

    timezone = "Europe/Paris"

    def __call__(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.consultant.privilege != Consultant.PrivilegeLevel.ALL:
            return HttpResponse("Unauthenticated user", status=401)
        return super().__call__(request, *args, **kwargs)

    def item_title(self, item):
        itws = ", ".join([i.user.trigramme for i in item.interviewers.all()])
        return escape(force_str("#{} {} [{}]".format(item.rank, item.process.candidate.name, itws)))

    def item_description(self, item):
        return ""

    def item_start_datetime(self, item):
        return item.planned_date

    def item_end_datetime(self, item):
        return item.planned_date + timedelta(hours=1)


class SubsidiaryInterviewFeed(AbstractPyoupyouInterviewFeed):
    """
    A simple event calendar for a given subsidiary
    """

    timezone = "Europe/Paris"

    def title(self, obj):
        return f"{obj.name} Pyoupyou Interviews"

    def product_id(self, obj):
        return f"-//pyoupyou//{obj.name}"

    def file_name(self, obj):
        return f"pyoupyou_{obj.name}.ics"

    def get_object(self, request, subsidiary_id=None):
        return Subsidiary.objects.get(id=subsidiary_id)

    def items(self, obj):
        last_month = timezone.now() - timedelta(days=30)
        return Interview.objects.filter(process__subsidiary=obj, planned_date__gte=last_month).order_by("-planned_date")


class FullInterviewFeed(AbstractPyoupyouInterviewFeed):
    """
    A simple event calender
    """

    def title(self, obj):
        return "Pyoupyou Interviews"

    def product_id(self, obj):
        return "-//pyoupyou//Full"

    def file_name(self, obj):
        return "pyoupyou_full.ics"

    def get_object(self, request, subsidiary_id=None):
        return None

    def items(self, obj):
        last_month = timezone.now() - timedelta(days=30)
        return Interview.objects.filter(planned_date__gte=last_month).order_by("-planned_date")


class ConsultantInterviewFeed(AbstractPyoupyouInterviewFeed):
    """
    A simple event calendar for a given Consultant
    """

    timezone = "Europe/Paris"

    def title(self, obj):
        return f"{obj.get_short_name()} Pyoupyou Interviews"

    def product_id(self, obj):
        return f"-//pyoupyou//{obj.get_short_name()}"

    def file_name(self, obj):
        return f"pyoupyou_{obj.trigramme}.ics"

    def get_object(self, request, user_id=None):
        return PyouPyouUser.objects.get(id=user_id)

    def items(self, user):
        last_month = timezone.now() - timedelta(days=30)
        return Interview.objects.filter(interviewers__user=user, planned_date__gte=last_month).order_by("-planned_date")
