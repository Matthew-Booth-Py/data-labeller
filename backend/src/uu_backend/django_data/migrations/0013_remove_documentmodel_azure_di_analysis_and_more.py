from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("django_data", "0012_add_retrieval_progress_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="documentmodel",
            name="azure_di_analysis",
        ),
        migrations.RemoveField(
            model_name="documentmodel",
            name="azure_di_status",
        ),
    ]
