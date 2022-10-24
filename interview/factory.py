import datetime
import random

import factory.fuzzy
import factory.faker as faker
import pytz

from ref.factory import SubsidiaryFactory
from ref.models import Subsidiary

test_tz = pytz.timezone("Europe/Paris")


class CandidateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Candidate"

    name = factory.Faker("name")
    email = factory.LazyAttribute(
        lambda candidate: "{candidate_name}@mail.com".format(candidate_name=candidate.name.replace(" ", "_").lower())
    )
    phone = factory.LazyFunction(
        lambda: "+336{random_digits}".format(random_digits=faker.faker.Faker().random_number(fix_len=True, digits=8))
    )


class ProcessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Process"

    candidate = factory.SubFactory(CandidateFactory)
    start_date = factory.fuzzy.FuzzyDateTime(datetime.datetime(2017, 1, 1, tzinfo=test_tz))
    subsidiary = factory.SubFactory(SubsidiaryFactory)


class InterviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Interview"

    planned_date = factory.fuzzy.FuzzyDateTime(datetime.datetime(2017, 1, 1, tzinfo=test_tz))


class ContractTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.ContractType"

    name = factory.Faker(
        "random_element", elements=["Contract Type 1", "Contract Type 2", "Contract Type 3", "Contract Type 4"]
    )


class SourcesCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.SourcesCategory"

    name = factory.Faker(
        "random_element", elements=["Source Category 1", "Source Category 2", "Source Category 3", "Source Category 4"]
    )


class SourcesFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Sources"

    if Subsidiary.objects.all().count() == 0:
        SubsidiaryFactory()

    name = factory.LazyFunction(lambda: random.choice(Subsidiary.objects.values_list("name", flat=True)))
    category = factory.SubFactory(SourcesCategoryFactory)


class InterviewKindFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.InterviewKind"

    name = factory.Faker(
        "random_element", elements=["Interview Kind 1", "Interview Kind 2", "Interview Kind 3", "Interview Kind 4"]
    )


class OfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Offer"

    name = factory.Sequence(lambda n: "Offer {offer_number}".format(offer_number=n))
    subsidiary = factory.Faker("random_element", elements=Subsidiary.objects.all())
