from django.db import migrations


def transfer_consultant_data(apps, schema_editor):
    Consultant = apps.get_model("ref", "Consultant")

    for consultant in Consultant.objects.all():
        user = consultant.user
        user.company = consultant.company
        user.limited_to_source = consultant.limited_to_source
        user.privilege = consultant.privilege
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ("interview", "0028_merge_20241021_1741"),
        ("ref", "0012_merge_20241021_1741"),
    ]

    operations = [
        migrations.RunPython(transfer_consultant_data),
    ]
