import datetime

import factory.fuzzy
import pytz

from ref.models import Subsidiary, PyouPyouUser

test_tz = pytz.timezone("Europe/Paris")

from itertools import permutations


class PyouPyouUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "ref.PyouPyouUser"

    full_name = factory.Faker("name")
    trigramme = factory.LazyAttribute(lambda n: n.full_name[0:1].upper() + n.full_name.split(" ")[1][0:2].upper())
    email = factory.LazyAttribute(lambda u: u.trigramme.lower() + "@mail.com")
    company = factory.Iterator(Subsidiary.objects.all())

    date_joined = factory.fuzzy.FuzzyDateTime(
        start_dt=datetime.datetime(2010, 1, 1, tzinfo=test_tz), end_dt=datetime.datetime(2020, 1, 1, tzinfo=test_tz)
    )
    password = factory.Faker("password")


def compute_subsidiary_code(name):
    all_codes = Subsidiary.objects.values_list("code", flat=True)
    for c in ["".join(perm).upper() for perm in permutations(name, 3)]:
        if c.isalpha() and c not in all_codes:
            return c
    return ""  # will break at insertion as no combination is available


class SubsidiaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "ref.Subsidiary"

    name = factory.Faker("company")
    code = factory.LazyAttribute(lambda n: compute_subsidiary_code(n.name))
