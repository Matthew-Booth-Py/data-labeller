# Generated manually for contextual retrieval progress tracking

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_data", "0011_add_retrieval_index_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentmodel",
            name="retrieval_index_progress",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="documentmodel",
            name="retrieval_index_total",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
