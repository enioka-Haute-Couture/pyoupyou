# Generated by Django 3.1.13 on 2021-11-28 11:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("interview", "0018_interview_prequalification")]

    operations = [
        migrations.CreateModel(
            name="InterviewKind",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name="interview",
            name="kind_of_interview",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="interview.interviewkind",
                verbose_name="Kind of interview",
            ),
        ),
    ]
