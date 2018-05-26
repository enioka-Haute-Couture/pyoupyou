import time
from django.core.management import BaseCommand
from django.utils.timezone import now
from email.utils import parsedate_to_datetime

from interview.models import Interview, Process


class Command(BaseCommand):
    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('current_date', nargs='?', type=str)

    def handle(self, *args, **options):
        current_date = parsedate_to_datetime(options['current_date']) if options['current_date'] else now()
        for i in Interview.objects.filter(planned_date__lte=current_date, process__state__in=Process.OPEN_STATE_VALUES,
                                          state=Interview.PLANNED):
            i.state = Interview.WAIT_INFORMATION
            i.save()
