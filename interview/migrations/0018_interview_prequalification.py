# Generated by Django 3.1.13 on 2021-11-18 08:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("interview", "0017_auto_20210916_1808")]

    operations = [
        migrations.AddField(
            model_name="interview",
            name="prequalification",
            field=models.BooleanField(default=False, verbose_name="Prequalification"),
        )
    ]