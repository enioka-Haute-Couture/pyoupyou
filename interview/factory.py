import datetime
import random

import factory.fuzzy
import factory.faker as faker
import pytz
from dateutil.relativedelta import relativedelta

from interview.models import Interview, Sources, SourcesCategory, ContractType, InterviewKind
from ref.factory import SubsidiaryFactory
from ref.models import Subsidiary, Consultant

test_tz = pytz.timezone("Europe/Paris")


# TODO: test these functions
def date_minus_time_ago(years=0, months=0, weeks=0, days=0, tz=test_tz):
    return datetime.datetime.now(tz=tz) - relativedelta(years=years, months=months, weeks=weeks, days=days)


def date_random_plus_minus_time(date=None, years=0, months=0, weeks=0, days=0, tz=test_tz):
    if date is None:
        return datetime.datetime.now(tz=tz) + (
            random.choice([-1, +1]) * relativedelta(years=years, months=months, weeks=weeks, days=days)
        )
    return date + (random.choice([-1, +1]) * relativedelta(years=years, months=months, weeks=weeks, days=days))


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


class ContractTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.ContractType"

    name = factory.Faker(
        "random_element", elements=["Contract Type 1", "Contract Type 2", "Contract Type 3", "Contract Type 4"]
    )


class SourcesCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.SourcesCategory"

    name = "Default Source Category"


class SourcesFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Sources"

    # class Params:
    #     number_of_categories = 5

    @factory.lazy_attribute
    def name(self):
        # Prefer to choose existing subsidiary instead of defaulting to creating a new one each time
        if Subsidiary.objects.all().count() == 0:
            SubsidiaryFactory()
        return random.choice(Subsidiary.objects.values_list("name", flat=True))

    @factory.lazy_attribute
    def category(self):
        # generate sources categories if the table wasn't populated
        if SourcesCategory.objects.all().count() == 0:
            for i in range(1, 5):
                SourcesCategoryFactory(name="Source Category {no}".format(no=i))
        return random.choice(SourcesCategory.objects.all())


class OfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Offer"

    name = factory.Sequence(lambda n: "Offer {offer_number}".format(offer_number=n))

    @factory.lazy_attribute
    def subsidiary(self):
        # Prefer to choose existing subsidiary instead of defaulting to creating a new one
        if Subsidiary.objects.all().count() == 0:
            SubsidiaryFactory()

        return random.choice(Subsidiary.objects.all())


class ProcessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Process"

    candidate = factory.SubFactory(CandidateFactory)

    contract_type = factory.LazyFunction(
        lambda: factory.SubFactory(ContractTypeFactory)
        if ContractType.objects.all().count() == 0
        else random.choice(ContractType.objects.all())
    )

    # default
    offer = factory.SubFactory(OfferFactory)

    # default
    sources = factory.LazyFunction(
        lambda: factory.SubFactory(SourcesFactory)
        if Sources.objects.all().count() == 0
        else random.choice(Sources.objects.all())
    )

    subsidiary = factory.LazyAttribute(lambda process: process.offer.subsidiary)

    # default
    closed_comment = factory.Faker("text")

    # default (length varies between 2 month and 3 years)
    contract_duration = factory.Faker("random_int", min=2, max=36)

    # default (start contract in between 1 and 6 months from now)
    contract_start_date = factory.LazyFunction(lambda: date_minus_time_ago(months=random.randrange(1, 6)))

    # end_date is set when process is closed
    # end_date = factory.LazyAttribute(
    #     lambda process: process.start_date + relativedelta(months=process.contract_duration)
    # )

    # default
    other_informations = factory.Faker("text")

    # default (between 30k and 70k)
    salary_expectation = factory.Faker("random_int", min=30, max=70)

    # FIXME: when process was created
    start_date = factory.fuzzy.FuzzyDateTime(date_minus_time_ago(years=2))


class InterviewKindFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.InterviewKind"

    name = factory.Faker(
        "random_element", elements=["Interview Kind 1", "Interview Kind 2", "Interview Kind 3", "Interview Kind 4"]
    )


class InterviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Interview"

    kind_of_interview = factory.LazyFunction(
        lambda: factory.SubFactory(InterviewKindFactory)
        if InterviewKind.objects.all().count == 0
        else random.choice(InterviewKind.objects.all())
    )

    # default
    process = factory.SubFactory(ProcessFactory)

    # FIXME: add suggested_interviewer(s) MUST BE SOMEONE THAT'S NOT BEEN IN THE PROCESS YET
    @factory.lazy_attribute
    def suggested_interviewer(self):
        # FIXME: needs test (w/ more than 1 subsidiary + check suggested interviewers + check all interviewers are
        #  distinct
        all_itw_given_process = Interview.objects.filter(process=self.process)
        q = (
            Consultant.objects.filter(company=self.process.subsidiary)
            .exclude(id__in=all_itw_given_process.values_list("interviewers", flat=True))
            .distinct()
        )
        if q.count() == 0:
            return None
        return random.choice(q)

    minute = factory.Faker("text")

    # default
    minute_format = "md"

    # default
    next_interview_goal = factory.Faker("text")

    planned_date = factory.fuzzy.FuzzyDateTime(date_minus_time_ago(years=2))

    # prequal if it's first interview
    prequalification = factory.LazyAttribute(
        lambda itw: Interview.objects.filter(process=itw.process).values_list("rank", flat=True).last() is None
    )
