from django.core.management import BaseCommand
from ref.models import PyouPyouUser, Consultant, Subsidiary
from django.conf import settings
import json
import os
from django.core.mail import mail_admins
import requests
from requests.auth import HTTPBasicAuth
from operator import itemgetter


class Command(BaseCommand):
    help = "Create accounts"
    profil_accepted = ["Consultant", "Directeur", "Administratif", "Manager"]

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument("user", nargs="+", type=str)
        parser.add_argument("password", nargs="+", type=str)

    def ApiCall(self, **options):
        response = requests.get(
            "https://pydici.enioka.com/people/consultant_list", auth=HTTPBasicAuth(*options["user"], *options["password"])
        )
        if response.status_code == 200:
            return response.json()
        raise Exception("Api Error status code : {status_code}".format(status_code=response.status_code))

    def handle(self, *args, **options):
        person_added = []
        try:
            data = self.ApiCall(**options)
            for profil in data:
                name, trigramme, profil__name, company__name, subcontracor, active, productive = itemgetter(
                    "name", "trigramme", "profil__name", "company__name", "subcontractor", "active", "productive"
                )(profil)
                if active and not subcontracor:
                    if profil__name in self.profil_accepted:
                        email = "{trigramme}@enioka.com".format(trigramme=trigramme.lower())
                        subsidiary = Subsidiary.objects.get(name=company__name)
                        try:
                            consultant = Consultant.objects.create_consultant(
                                trigramme=trigramme.lower(), email=email, company=subsidiary, full_name=name
                            )
                            person_added.append(consultant.user.trigramme)
                        except:
                            continue
            if person_added:
                mail_admins("Compte(s) pyoupyou crée(s)", ",".join(person_added))
        except Exception as e:
            print(e)
