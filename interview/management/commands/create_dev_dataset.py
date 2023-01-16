import datetime

# factory.fuzzy and factory.Faker share a dedicated instance of random.Random, which can be managed through the
# factory.random module
from factory.random import random


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
from interview.models import ContractType, SourcesCategory, InterviewKind, Interview, Process, Sources
from ref.factory import SubsidiaryFactory, PyouPyouUserFactory
from interview.factory import (
    date_minus_time_ago,
    date_random_plus_minus_time,
    test_tz,
)

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
    if not InterviewKind.objects.exists():
        for i in range(1, 5):
            InterviewKindFactory(name="Interview Kind {no}".format(no=i))

    # generate ContractType
    if not ContractType.objects.exists():
        for i in range(1, 5):
            ContractTypeFactory(name="Contract Type {no}".format(no=i))

    # generate SourcesCategory
    source_categories = SourcesCategory.objects.all()
    if not source_categories:
        source_categories = []
        for i in range(1, 5):
            source_categories.append(SourcesCategoryFactory(name="Source Category {no}".format(no=i)))

    # generate Sources
    for category in source_categories:
        SourcesFactory(category=category, name=subsidiary.name)


def set_random_process_given_offer_to_hired(offer):
    process_hired = random.choice(Process.objects.filter(offer=offer))
    process_hired.state = Process.HIRED
    process_hired.save()

    # update last interview state to reflect hired
    last_itw = Interview.objects.filter(process=process_hired).last()
    last_itw.state = Interview.GO
    last_itw.save()


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        for i in range(1, 3):
            # create subsidiary
            subsidiary = SubsidiaryFactory(name="Subsidiary {no}".format(no=i), code="SU{no}".format(no=i))
            generate_basic_data(subsidiary)

            # create consultants for this subsidiary
            subsidiary_consultants = []
            for k in range(5):
                subsidiary_consultants.append(PyouPyouUserFactory(company=subsidiary))

            # we need at least one consultant which is both a superuser and staff to access the admin board
            # note: superusers cannot be created with manage.py because they also need a consultant
            admin = subsidiary_consultants[0]
            admin.is_superuser = True
            admin.is_staff = True
            admin.save()

            # set subsidiary's responsible
            subsidiary.responsible = subsidiary_consultants[0]
            subsidiary.save()

            # create offers for this subsidiary
            subsidiary_offers = []
            for k in range(random.randrange(start=9, stop=12)):
                subsidiary_offers.append(OfferFactory(subsidiary=subsidiary))

            # for each offer create some process for it
            for offer in subsidiary_offers:
                processes = OfferFactory.create_processes(offer=offer, subsidiary=subsidiary)

                # for each process create some itw
                for process in processes:
                    ProcessFactory.create_interviews(process=process)

                # set one process of each offer to Hired
                set_random_process_given_offer_to_hired(offer=offer)

            # create an offer sill ongoing
            pending_offer = OfferFactory(subsidiary=subsidiary)
            pending_processes = OfferFactory.create_processes(
                offer=pending_offer, subsidiary=subsidiary, min_number_of_process=5, max_number_of_process=10
            )

            # create some itw for each process
            for process in pending_processes:
                start_date = date_minus_time_ago(weeks=3) + relativedelta(days=random.randrange(3, 10))
                ProcessFactory.create_interviews(process=process, min_number_of_itw=2, start_date=start_date)
