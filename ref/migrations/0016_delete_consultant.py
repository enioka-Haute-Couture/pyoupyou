# Generated by Django 4.2.4 on 2024-10-23 13:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ref", "0015_move_consultant_data"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Consultant",
        ),
    ]
