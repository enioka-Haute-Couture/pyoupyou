import factory
import factory.faker

from ref.models import Subsidiary, Consultant


class PyouPyouUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'ref.PyouPyouUser'

    full_name = factory.Faker('name')
    trigramme = factory.LazyAttribute(lambda n: n.full_name[0:1].upper() + n.full_name.split(' ')[1][0:2].upper())
    email = factory.LazyAttribute(lambda u: u.trigramme.lower() + "@mail.com")


class ConsultantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'ref.Consultant'

    user = factory.SubFactory(PyouPyouUserFactory)
    company = factory.Iterator(Subsidiary.objects.all())
    productive = True


class SubsidiaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'ref.Subsidiary'

    name = factory.Faker('company')
    code = factory.LazyAttribute(lambda n: n.name[0:3].upper())
