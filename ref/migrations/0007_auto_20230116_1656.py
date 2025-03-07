# Generated by Django 3.2.16 on 2023-01-16 15:56

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("interview", "0025_auto_20230116_1355"),
        ("ref", "0006_alter_consultant_privilege"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="pyoupyouuser",
            options={"ordering": ("trigramme",), "verbose_name": "user", "verbose_name_plural": "users"},
        ),
        migrations.AddField(
            model_name="pyoupyouuser",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="ref.subsidiary",
                verbose_name="Subsidiary",
            ),
        ),
        migrations.AddField(
            model_name="pyoupyouuser",
            name="limited_to_source",
            field=models.ForeignKey(
                blank=True,
                default=None,
                help_text="This field must be set if user is not an internal consultant",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="interview.sources",
                verbose_name="Limit user to a source",
            ),
        ),
        migrations.AddField(
            model_name="pyoupyouuser",
            name="privilege",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "User is an insider consultant"),
                    (2, "User is an external consultant with additional rights"),
                    (3, "User is an external consultant"),
                    (4, "User is external and has only read rights"),
                ],
                default=1,
                help_text="Designates what a user can or cannot do",
                verbose_name="Authority level",
            ),
        ),
    ]
