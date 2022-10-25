import random

import factory
import pytz
from dateutil.relativedelta import relativedelta
from django.core.management import BaseCommand
from django.core.management import call_command
from factory.faker import faker

from interview.factory import (
    OfferFactory,
    ProcessFactory,
    ContractTypeFactory,
    SourcesCategoryFactory,
    SourcesFactory,
    InterviewKindFactory,
    InterviewFactory,
)
from interview.models import ContractType, SourcesCategory, InterviewKind, Interview, Process
from ref.factory import SubsidiaryFactory, PyouPyouUserFactory, ConsultantFactory
from ref.models import Consultant
from interview.factory import date_minus_time_ago, date_random_plus_minus_time, test_tz

"""
Create some data and load them

Empty db: ./manage.py flush [--no-input]

For now 2 subsidiaries
            5 users per subsidiary
            around 100 process per subsidiary in the last 2 years
                an average of 3 itw per process
"""


def generate_basic_data(subsidiary):
    # generate InterviewKind
    if InterviewKind.objects.all().count() == 0:
        for i in range(1, 5):
            InterviewKindFactory(name="Interview Kind {no}".format(no=i))

    # generate ContractType
    if ContractType.objects.all().count() == 0:
        for i in range(1, 5):
            ContractTypeFactory(name="Contract Type {no}".format(no=i))

    # generate SourcesCategory
    source_categories = SourcesCategory.objects.all()
    if source_categories.count() == 0:
        source_categories = []
        for i in range(1, 5):
            source_categories.append(SourcesCategoryFactory(name="Source Category {no}".format(no=i)))

    # generate Sources
    for category in source_categories:
        SourcesFactory(category=category, name=subsidiary.name)


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        call_command("flush", "--no-input")
        for i in range(1, 3):
            # create subsidiary
            subsidiary = SubsidiaryFactory()
            generate_basic_data(subsidiary)

            # create consultants for this subsidiary
            subsidiary_consultants = []
            for _ in range(5):
                subsidiary_consultants.append(ConsultantFactory(company=subsidiary))

            # set subsidiary's responsible
            subsidiary.responsible = subsidiary_consultants[0]
            subsidiary.save()

            # create offers for this subsidiary
            subsidiary_offers = []
            for _ in range(random.randrange(start=9, stop=12)):
                subsidiary_offers.append(OfferFactory(subsidiary=subsidiary))

            # for each offer create some process for it
            processes_given_offer = []
            for offer in subsidiary_offers:
                processes = []
                for _ in range(random.randrange(start=9, stop=12)):
                    process = ProcessFactory(offer=offer, subsidiary=subsidiary)

                    process.responsible.set([subsidiary.responsible])
                    process.save()

                    processes.append(process)
                processes_given_offer.append(processes)

            # for each process create some itw
            for processes in processes_given_offer:
                for process in processes:
                    number_of_itw = random.randrange(1, 5)

                    # generate random date
                    fake = faker.Faker()
                    process.start_date = fake.date_time_between(
                        start_date=date_minus_time_ago(years=2, tz=test_tz),
                        end_date=date_minus_time_ago(weeks=(2 + 2 * number_of_itw), tz=test_tz),
                        tzinfo=test_tz
                    )
                    process.save()

                    # first itw around a week after +|- 5 days
                    next_planned_date = date_random_plus_minus_time(
                        date=(process.start_date + relativedelta(weeks=1)), days=5
                    )

                    # generate itws for process
                    for itw_number in range(number_of_itw):
                        all_itw = Interview.objects.filter(process=process)

                        itw = InterviewFactory(process=process, planned_date=next_planned_date)

                        # if there are more interview then the last ones were a GO
                        if itw_number + 1 < number_of_itw:
                            itw.state = Interview.GO
                        else:
                            # choose random if GO or NO_GO
                            # itw.state = random.choice([Interview.GO, Interview.NO_GO])
                            itw.state = Interview.NO_GO
                            # set Process: state, end_date
                            process.contract_start_date = next_planned_date + relativedelta(weeks=2)
                            process.end_date = next_planned_date
                            process.state = random.choices(
                                [Process.NO_GO, Process.CANDIDATE_DECLINED], weights=(80, 20), k=1
                            )[0]

                        possible_interviewer = (
                            Consultant.objects.filter(subsidiary=subsidiary)
                            .exclude(id__in=all_itw.values_list("interviewers", flat=True))
                            .distinct()
                        )
                        if len(possible_interviewer) == 0:
                            possible_interviewer = Consultant.objects.filter(subsidiary=subsidiary)

                        itw.interviewers.add(random.choice(possible_interviewer))
                        itw.save()

                        # compute next planned date
                        next_planned_date = date_random_plus_minus_time(
                            (next_planned_date + relativedelta(weeks=1)), days=5
                        )

            # set one process of each offer to Hired
            for o in subsidiary_offers:
                process_hired = random.choice(Process.objects.filter(offer=o))
                process_hired.state = Process.HIRED
                process_hired.save()

                # update last interview state to reflect hired
                last_itw = Interview.objects.filter(process=process_hired).last()
                last_itw.state = Interview.GO
                last_itw.save()
