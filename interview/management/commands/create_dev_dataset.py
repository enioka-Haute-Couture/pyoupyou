import random

import factory
from django.core.management import BaseCommand
from django.core.management import call_command

from interview.factory import (
    OfferFactory,
    ProcessFactory,
    ContractTypeFactory,
    SourcesCategoryFactory,
    SourcesFactory,
    InterviewKindFactory,
    InterviewFactory,
)
from interview.models import ContractType, SourcesCategory, InterviewKind, Interview
from ref.factory import SubsidiaryFactory, PyouPyouUserFactory, ConsultantFactory
from ref.models import Consultant

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
                    # TODO: add fine tuning for process dates (start, end, etc)
                    process = ProcessFactory(offer=offer, subsidiary=subsidiary)

                    # TODO: maybe change responsible for it not to be only the same person
                    process.responsible.set([subsidiary.responsible])
                    process.save()

                    processes.append(process)
                processes_given_offer.append({offer: processes})

            # for each process create some itw
            for item in processes_given_offer:
                offer, processes = item.popitem()
                for process in processes:
                    number_of_itw = random.randrange(1, 5)
                    for itw_number in range(number_of_itw):
                        all_itw = Interview.objects.filter(process=process)

                        # TODO: set correct planned date
                        itw = InterviewFactory(process=process)

                        # if there are more interview then the last ones were a GO
                        if itw_number + 1 < number_of_itw:
                            itw.state = Interview.GO

                        possible_interviewer = (
                            Consultant.objects.filter(subsidiary=subsidiary)
                            .exclude(id__in=all_itw.values_list("interviewers", flat=True))
                            .distinct()
                        )
                        if len(possible_interviewer) == 0:
                            possible_interviewer = Consultant.objects.filter(subsidiary=subsidiary)

                        itw.interviewers.add(random.choice(possible_interviewer))
                        itw.save()
