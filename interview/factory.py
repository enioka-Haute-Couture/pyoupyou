import factory
import factory.faker

from ref.factory import SubsidiaryFactory


class CandidateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'interview.Candidate'

    name = factory.Faker('name')


class ProcessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'interview.Process'

    candidate = factory.SubFactory(CandidateFactory)
    start_date = factory.Faker('date')
    subsidiary = factory.SubFactory(SubsidiaryFactory)


class InterviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'interview.Interview'

    planned_date = factory.Faker('date')
