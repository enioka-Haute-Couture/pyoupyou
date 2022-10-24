from django.core.management import BaseCommand
from django.core.management import call_command

from ref.factory import SubsidiaryFactory, PyouPyouUserFactory, ConsultantFactory

"""
Create some data and load them

Empty db: ./manage.py flush [--no-input]

For now 2 subsidiaries
            5 users per subsidiary
            around 100 process per subsidiary in the last 2 years
                an average of 3 itw per process
"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        call_command("delete_dataset")
        subsidiary = SubsidiaryFactory(name="HauteCouture")
        subsidiary_consultants = []

        for _ in range(5):
            subsidiary_consultants.append(ConsultantFactory(company=subsidiary))

        subsidiary.responsible = subsidiary_consultants[0]
        subsidiary.save()
