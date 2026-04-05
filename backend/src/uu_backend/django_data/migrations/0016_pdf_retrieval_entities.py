# Generated manually for PDF-only intelligent retrieval

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_data", "0015_add_extraction_request_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentmodel",
            name="retrieval_index_backend",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.CreateModel(
            name="RetrievalArtifactModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("media_type", models.CharField(max_length=128)),
                ("relative_path", models.CharField(max_length=512, unique=True)),
                ("byte_size", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        db_column="document_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieval_artifacts",
                        to="django_data.documentmodel",
                    ),
                ),
            ],
            options={
                "db_table": "retrieval_artifacts",
                "indexes": [
                    models.Index(
                        fields=["document", "created_at"], name="idx_retrieval_artifact_doc"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="RetrievalPageModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("page_number", models.IntegerField()),
                ("width", models.FloatField()),
                ("height", models.FloatField()),
                ("source_width", models.FloatField(default=0.0)),
                ("source_height", models.FloatField(default=0.0)),
                ("rotation", models.IntegerField(default=0)),
                ("text", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        db_column="document_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieval_pages",
                        to="django_data.documentmodel",
                    ),
                ),
            ],
            options={
                "db_table": "retrieval_pages",
                "indexes": [
                    models.Index(
                        fields=["document", "page_number"],
                        name="idx_retrieval_page_doc_num",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("document", "page_number"),
                        name="uq_retrieval_pages_document_page",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="RetrievalAssetModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("asset_type", models.CharField(max_length=32)),
                ("label", models.TextField()),
                ("bbox", models.JSONField(default=list)),
                ("text_content", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        db_column="document_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieval_assets",
                        to="django_data.documentmodel",
                    ),
                ),
                (
                    "page",
                    models.ForeignKey(
                        db_column="page_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assets",
                        to="django_data.retrievalpagemodel",
                    ),
                ),
                (
                    "preview_artifact",
                    models.ForeignKey(
                        blank=True,
                        db_column="preview_artifact_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="preview_assets",
                        to="django_data.retrievalartifactmodel",
                    ),
                ),
            ],
            options={
                "db_table": "retrieval_assets",
                "indexes": [
                    models.Index(
                        fields=["document", "asset_type"], name="idx_retrieval_asset_doc_type"
                    ),
                    models.Index(
                        fields=["page", "asset_type"], name="idx_retrieval_asset_page_type"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="RetrievalChunkModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("chunk_index", models.IntegerField()),
                ("chunk_type", models.CharField(max_length=32)),
                ("content", models.TextField()),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        blank=True,
                        db_column="asset_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="chunks",
                        to="django_data.retrievalassetmodel",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        db_column="document_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieval_chunks",
                        to="django_data.documentmodel",
                    ),
                ),
                (
                    "page",
                    models.ForeignKey(
                        db_column="page_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="django_data.retrievalpagemodel",
                    ),
                ),
            ],
            options={
                "db_table": "retrieval_chunks",
                "indexes": [
                    models.Index(
                        fields=["document", "chunk_index"],
                        name="idx_retrieval_chunk_doc_idx",
                    ),
                    models.Index(fields=["page"], name="idx_retrieval_chunk_page"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("document", "chunk_index"),
                        name="uq_retrieval_chunks_document_index",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="RetrievalCitationModel",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("label", models.TextField(blank=True, default="")),
                ("bbox", models.JSONField(default=list)),
                ("regions", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        blank=True,
                        db_column="asset_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="citations",
                        to="django_data.retrievalassetmodel",
                    ),
                ),
                (
                    "chunk",
                    models.OneToOneField(
                        db_column="chunk_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="citation",
                        to="django_data.retrievalchunkmodel",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        db_column="document_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieval_citations",
                        to="django_data.documentmodel",
                    ),
                ),
                (
                    "page",
                    models.ForeignKey(
                        db_column="page_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="citations",
                        to="django_data.retrievalpagemodel",
                    ),
                ),
                (
                    "preview_artifact",
                    models.ForeignKey(
                        blank=True,
                        db_column="preview_artifact_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="preview_citations",
                        to="django_data.retrievalartifactmodel",
                    ),
                ),
            ],
            options={
                "db_table": "retrieval_citations",
                "indexes": [
                    models.Index(fields=["document", "page"], name="idx_ret_cite_doc_page")
                ],
            },
        ),
    ]
