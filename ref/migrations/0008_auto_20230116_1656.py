# Generated by Django 3.2.16 on 2023-01-16 15:56

from django.db import migrations


def copy_field(apps, schema):
    PyouPyouUser = apps.get_model("ref", "PyouPyouUser")
    for user in PyouPyouUser.objects.filter(consultant__isnull=False):
        user.company = user.consultant.company
        user.privilege = user.consultant.privilege
        user.limited_to_source = user.consultant.limited_to_source
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ("ref", "0007_auto_20230116_1656"),
    ]

    operations = [
        # Copy consultant fields to user
        migrations.RunPython(code=copy_field),
    ]
