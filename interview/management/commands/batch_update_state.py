import time

import logging
from django.core.management import BaseCommand
from django.utils import log
from django.utils.timezone import now
from email.utils import parsedate_to_datetime

from interview.models import Interview, Process


logger = logging.getLogger('pyoupyou.batch')


class Command(BaseCommand):
    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('current_date', nargs='?', type=str)

    def handle(self, *args, **options):
        current_date = parsedate_to_datetime(options['current_date']) if options['current_date'] else now()
        logger.info("Start batch update state {}".format(current_date))
        for i in Interview.objects.filter(planned_date__lte=current_date, process__state__in=Process.OPEN_STATE_VALUES,
                                          state=Interview.PLANNED):
            logger.info("Interview {i} - state moved to Wait information".format(i=i))
            i.state = Interview.WAIT_INFORMATION
            i.save()
        logger.info("End batch update state")
