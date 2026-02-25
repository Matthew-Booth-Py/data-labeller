# Manual migration to add EvaluationRunModel

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_data", "0007_add_file_path_to_documents"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvaluationRunModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("document_id", models.CharField(db_index=True, max_length=64)),
                (
                    "project_id",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True),
                ),
                ("metrics", models.JSONField()),
                ("field_comparisons", models.JSONField()),
                ("instance_comparisons", models.JSONField(default=dict)),
                ("extraction_time_ms", models.FloatField(blank=True, null=True)),
                ("evaluation_time_ms", models.FloatField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("evaluated_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "evaluation_runs",
                "ordering": ["-evaluated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="evaluationrunmodel",
            index=models.Index(
                fields=["document_id", "-evaluated_at"], name="evaluation__documen_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="evaluationrunmodel",
            index=models.Index(
                fields=["project_id", "-evaluated_at"], name="evaluation__project_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="evaluationrunmodel",
            index=models.Index(fields=["-evaluated_at"], name="evaluation__evaluat_idx"),
        ),
    ]
