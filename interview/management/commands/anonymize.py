from dateutil.relativedelta import relativedelta

from datetime import date
import logging
from django.core.management import BaseCommand
from django.utils.timezone import now

from interview.models import Process, Candidate

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
        )
        logger.info("Start batch anonymization {}".format(current_date))

        candidates_with_only_closed_process = (
            Candidate.objects.filter(anonymized=False)
            .prefetch_related("process_set")
            .filter(process__end_date__isnull=False)
            .filter(process__end_date__lte=current_date)
            .exclude(process__state__in=Process.OPEN_STATE_VALUES)
        )

        for candidate in candidates_with_only_closed_process:
            logger.info("Anonymizing candidate {candidate_id}".format(candidate_id=candidate.id))
            candidate.anonymize()
            candidate.save()

            for proc in candidate.process_set.all():
                for interview in proc.interview_set.all():
                    interview.anonymize()
                    interview.save()

                proc.anonymize()
                proc.save(trigger_notification=False)

        logger.info("End batch anonymization")
