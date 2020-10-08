from dateutil.relativedelta import relativedelta

from datetime import date
import logging
from django.core.management import BaseCommand
from django.utils.timezone import now

from interview.models import Process

logger = logging.getLogger("pyoupyou.batch")

"""
Usage: ./manage.py anonymize [date]

Will anonymize candidate not hired whose process stopped before date.

`date` must have format "2020-12-10"
By defaut date is 12 months ago.

"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument("date", nargs="?", type=str)

    def handle(self, *args, **options):

        current_date = (
            date.fromisoformat(options["date"]) if options["date"] else now().date() - relativedelta(months=12)
        )  # 6 months ago by default
        logger.info("Start batch anonymization {}".format(current_date))

        closed_processes = (
            Process.objects.filter(end_date__isnull=False)
            .filter(end_date__lte=current_date)
            .filter(state__in=Process.CLOSED_STATE_VALUES)
            .select_related("candidate", "contract_type")
            .filter(candidate__anonymized=False)
        )

        for proc in closed_processes:
            if proc.state != Process.HIRED:
                logger.info("Anonymizing candidate {candidate_id}".format(candidate_id=proc.candidate.id))
                proc.candidate.anonymize()
                proc.candidate.save()

        logger.info("End batch anonymization")
