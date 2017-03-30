import factory
import factory.faker

from ref.models import Subsidiary


class SubsidiaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'ref.Subsidiary'

    name = factory.Faker('company')
    code = factory.LazyAttribute(lambda n: n.name[0:3].upper())


class ConsultantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'ref.Consultant'

    name = factory.Faker('name')
    trigramme = factory.LazyAttribute(lambda n: n.name[0:1].upper() + n.name.split(' ')[1][0:2].upper())
    company = factory.Iterator(Subsidiary.objects.all())
    productive = True
    active = True
