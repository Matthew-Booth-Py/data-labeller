import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_data", "0016_pdf_retrieval_entities"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("name", models.CharField(db_index=True, max_length=255, unique=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("type", models.CharField(blank=True, max_length=100, null=True)),
                ("model", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
            ],
            options={
                "db_table": "projects",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ProjectDocumentModel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        db_column="document_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_projects",
                        to="django_data.documentmodel",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        db_column="project_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_documents",
                        to="django_data.projectmodel",
                    ),
                ),
            ],
            options={
                "db_table": "project_documents",
            },
        ),
        migrations.AddIndex(
            model_name="projectmodel",
            index=models.Index(fields=["name"], name="idx_projects_name"),
        ),
        migrations.AddIndex(
            model_name="projectmodel",
            index=models.Index(fields=["created_at"], name="idx_projects_created"),
        ),
        migrations.AddConstraint(
            model_name="projectdocumentmodel",
            constraint=models.UniqueConstraint(
                fields=("project", "document"),
                name="uq_project_documents_project_document",
            ),
        ),
        migrations.AddIndex(
            model_name="projectdocumentmodel",
            index=models.Index(fields=["project", "created_at"], name="idx_project_docs_project"),
        ),
        migrations.AddIndex(
            model_name="projectdocumentmodel",
            index=models.Index(fields=["document"], name="idx_project_docs_document"),
        ),
    ]
