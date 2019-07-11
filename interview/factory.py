import factory
import factory.faker
import factory.fuzzy

import datetime

from ref.factory import SubsidiaryFactory

import pytz

test_tz = pytz.timezone("Europe/Paris")


class CandidateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'interview.Candidate'

    name = factory.Faker('name')


class ProcessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'interview.Process'

    candidate = factory.SubFactory(CandidateFactory)
    start_date = factory.fuzzy.FuzzyDateTime(datetime.datetime(2017, 1, 1,
                                                               tzinfo=test_tz))
    subsidiary = factory.SubFactory(SubsidiaryFactory)


class InterviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'interview.Interview'

    planned_date = factory.fuzzy.FuzzyDateTime(datetime.datetime(2017, 1, 1,
                                                                 tzinfo=test_tz))
