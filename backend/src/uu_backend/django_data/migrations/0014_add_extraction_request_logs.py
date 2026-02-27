from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_data", "0013_remove_documentmodel_azure_di_analysis_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="extractionmodel",
            name="request_logs",
            field=models.JSONField(default=list),
        ),
    ]
