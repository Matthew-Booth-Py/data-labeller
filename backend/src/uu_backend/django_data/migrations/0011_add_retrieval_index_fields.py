# Generated manually for contextual retrieval integration

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "django_data",
            "0010_rename_evaluation__documen_idx_evaluation__documen_72f2a2_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="documentmodel",
            name="retrieval_index_status",
            field=models.CharField(default="pending", max_length=20),
        ),
        migrations.AddField(
            model_name="documentmodel",
            name="retrieval_chunks_count",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
