# Generated by Django 3.1.13 on 2021-10-19 08:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interview', '0016_auto_20210916_1808'),
    ]

    operations = [
        migrations.AlterField(
            model_name='candidate',
            name='anonymized_hashed_email',
            field=models.CharField(blank=True, max_length=64, verbose_name='Anonymized Hashed Email'),
        ),
        migrations.AlterField(
            model_name='candidate',
            name='anonymized_hashed_name',
            field=models.CharField(blank=True, max_length=64, verbose_name='Anonymized Hashed Name'),
        ),
    ]
