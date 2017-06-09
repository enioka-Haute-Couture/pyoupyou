from datetime import timedelta

from django.http.response import HttpResponseNotAllowed, HttpResponse
from django.utils.encoding import force_text
from django.utils.html import escape
from django_ical.views import ICalFeed

from interview.models import Interview


class InterviewFeed(ICalFeed):
    """
    A simple event calender
    """
    product_id = '-//pyoupyou//Full'
    timezone = 'Europe/Paris'
    file_name = "calendar_full.ics"

    def __call__(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponse('Unauthenticated user', status=401)
        return super().__call__(request, *args, **kwargs)

    def items(self):
        return Interview.objects.filter(planned_date__isnull=False).order_by('-planned_date')

    def item_title(self, item):
        itws = ', '.join([i.user.trigramme for i in item.interviewers.all()])
        return escape(force_text("#{} {} [{}]".format(item.rank, item.process.candidate.name, itws)))

    def item_description(self, item):
        return ""

    def item_start_datetime(self, item):
        return item.planned_date

    def item_end_datetime(self, item):
        return item.planned_date + timedelta(hours=1)
