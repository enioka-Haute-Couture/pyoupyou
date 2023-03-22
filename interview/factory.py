import datetime
from factory.random import random

import factory.fuzzy
from factory.faker import faker
import pytz
from dateutil.relativedelta import relativedelta

from interview.models import Interview, Sources, SourcesCategory, ContractType, InterviewKind, Process
from ref.factory import SubsidiaryFactory
from ref.models import Subsidiary, Consultant


test_tz = pytz.timezone("Europe/Paris")


def date_minus_time_ago(years=0, months=0, weeks=0, days=0, tz=test_tz):
    return datetime.datetime.now(tz=tz) - relativedelta(years=years, months=months, weeks=weeks, days=days)


def date_random_plus_minus_time(date=None, years=0, months=0, weeks=0, days=0, tz=test_tz):
    if date is None:
        return datetime.datetime.now(tz=tz) + (
            random.choice([-1, +1]) * relativedelta(years=years, months=months, weeks=weeks, days=days)
        )
    return date + (random.choice([-1, +1]) * relativedelta(years=years, months=months, weeks=weeks, days=days))


def compute_next_planned_date(current_planned_date):
    return date_random_plus_minus_time((current_planned_date + relativedelta(weeks=1)), days=5)


def negative_end_process(process, itw, next_planned_date):
    process.contract_start_date = next_planned_date + relativedelta(weeks=2)
    process.end_date = next_planned_date
    process.state = random.choices([Process.NO_GO, Process.CANDIDATE_DECLINED], weights=(80, 20), k=1)[0]

    if process.state == Process.NO_GO:
        itw.state = Interview.NO_GO
    else:
        # if candidate declined then we were a go
        itw.state = Interview.GO

    process.save()
    itw.save()

    return process, itw


def get_available_consultants_for_itw(subsidiary, all_itw_given_process):
    # retrieve available consultants that have not yet been involved in the process
    possible_interviewer = Consultant.objects.filter(company=subsidiary).exclude(
        id__in=list(all_itw_given_process.values_list("interviewers", flat=True))
    )
    # if all consultants were already involved in the process, choose one at random
    if not possible_interviewer:
        possible_interviewer = Consultant.objects.filter(company=subsidiary)

    return possible_interviewer


class CandidateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Candidate"

    name = factory.Faker("name")
    email = factory.LazyAttribute(
        lambda candidate: "{candidate_name}@mail.com".format(candidate_name=candidate.name.replace(" ", "_").lower())
    )
    phone = factory.LazyFunction(
        lambda: "+336{random_digits}".format(random_digits=faker.Faker().random_number(fix_len=True, digits=8))
    )


class ContractTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.ContractType"

    # name = "Default Contract Type"
    name = factory.Faker("text", max_nb_chars=20)


class SourcesCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.SourcesCategory"

    # name = "Default Source Category"
    name = factory.Faker("text", max_nb_chars=20)


class SourcesFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Sources"

    name = factory.Faker("company")


class OfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Offer"

    name = factory.Sequence(lambda n: "Offer {offer_number}".format(offer_number=n))

    subsidiary = factory.SubFactory(SubsidiaryFactory)

    @staticmethod
    def create_processes(offer, subsidiary, min_number_of_process=9, max_number_of_process=12):
        processes = []
        for k in range(random.randrange(start=min_number_of_process, stop=max_number_of_process)):
            process = ProcessFactory(
                offer=offer,
                subsidiary=subsidiary,
                contract_type=random.choice(ContractType.objects.all()),
                sources=random.choice(Sources.objects.all()),
            )

            process.responsible.set([subsidiary.responsible])
            process.save()

            processes.append(process)
        return processes


class ProcessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Process"

    candidate = factory.SubFactory(CandidateFactory)

    subsidiary = factory.SubFactory(SubsidiaryFactory)

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

    # (when process was created)
    start_date = factory.fuzzy.FuzzyDateTime(date_minus_time_ago(years=2))

    @staticmethod
    def create_interviews(process, min_number_of_itw=1, max_number_of_itw=5, start_date=None):
        # will create interviews in the last two years until now (excluded)

        number_of_itw = random.randrange(min_number_of_itw, max_number_of_itw)

        process.start_date = start_date

        # generate random date if start_date isn't specified
        fake = faker.Faker()
        if not start_date:
            process.start_date = fake.date_time_between(
                start_date=date_minus_time_ago(years=2, tz=test_tz),
                end_date=date_minus_time_ago(weeks=(2 + 2 * number_of_itw), tz=test_tz),
                tzinfo=test_tz,
            )
        process.save()

        # first itw around a week after +|- 5 days
        next_planned_date = compute_next_planned_date(current_planned_date=process.start_date)

        # generate itws for process
        for itw_number in range(number_of_itw):
            all_itw = Interview.objects.filter(process=process)

            itw = InterviewFactory(
                process=process,
                planned_date=next_planned_date,
                kind_of_interview=random.choice(InterviewKind.objects.all()),
            )
            prequal = Interview.objects.filter(process=itw.process).values_list("rank", flat=True).last() == 1

            # if this itw could be a prequal
            if prequal:
                # choose randomly if this interview is a prequal or not
                prequal = random.choice([True, False])
            itw.prequalification = prequal

            # if there are more interview then the last ones were a GO
            if itw_number + 1 < number_of_itw:
                itw.state = Interview.GO
            elif not next_planned_date >= datetime.datetime.now(tz=test_tz):
                # by default all process end negatively
                process, itw = negative_end_process(process=process, itw=itw, next_planned_date=next_planned_date)

            # retrieve consultants to do the itw
            possible_interviewer = get_available_consultants_for_itw(
                subsidiary=process.subsidiary, all_itw_given_process=all_itw
            )

            # never more than 3 interviewers
            number_of_interviewers = len(possible_interviewer) if len(possible_interviewer) < 4 else 4

            # add one or more interviewers
            itw.interviewers.set(
                random.choices(
                    possible_interviewer,
                    k=random.randrange(1, number_of_interviewers) if number_of_interviewers > 1 else 1,
                )
            )
            itw.save()

            # if the next interview is in the future
            if next_planned_date >= datetime.datetime.now(tz=test_tz):
                itw.state = random.choice([Interview.WAITING_PLANIFICATION_RESPONSE, Interview.PLANNED])
                itw.save()
                break  # stop creating new interviews for process as this one hasn't happened yet

            # compute next planned date
            next_planned_date = compute_next_planned_date(current_planned_date=next_planned_date)


class InterviewKindFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.InterviewKind"

    # name = "Default Interview Kind"
    name = factory.Faker("text", max_nb_chars=20)
    medium = factory.Faker("url")


class InterviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "interview.Interview"

    # default
    process = factory.SubFactory(ProcessFactory)

    minute = factory.Faker("text")

    # default
    minute_format = "md"

    # default
    next_interview_goal = factory.Faker("text")

    planned_date = factory.fuzzy.FuzzyDateTime(date_minus_time_ago(years=2))
