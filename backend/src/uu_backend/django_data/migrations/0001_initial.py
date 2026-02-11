# Generated manually for migration scaffold

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DocumentTypeModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("schema_fields", models.JSONField(default=list)),
                ("system_prompt", models.TextField(blank=True, null=True)),
                ("post_processing", models.TextField(blank=True, null=True)),
                ("extraction_model", models.CharField(blank=True, max_length=128, null=True)),
                ("ocr_engine", models.CharField(blank=True, max_length=128, null=True)),
                ("schema_version_id", models.CharField(blank=True, max_length=64, null=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
            ],
            options={"db_table": "document_types"},
        )
    ]
