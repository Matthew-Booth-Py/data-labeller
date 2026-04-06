from django.db import migrations, models


def ensure_request_metadata_column(apps, schema_editor):
    table_name = "extractions"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    if "request_metadata" not in columns:
        if connection.vendor == "postgresql":
            schema_editor.execute(
                'ALTER TABLE "extractions" '
                "ADD COLUMN \"request_metadata\" jsonb NOT NULL DEFAULT '{}'::jsonb"
            )
        else:
            schema_editor.execute(
                'ALTER TABLE "extractions" '
                "ADD COLUMN \"request_metadata\" TEXT NOT NULL DEFAULT '{}'"
            )
        return

    if connection.vendor == "postgresql":
        schema_editor.execute(
            'UPDATE "extractions" '
            "SET \"request_metadata\" = '{}'::jsonb "
            'WHERE "request_metadata" IS NULL'
        )
        schema_editor.execute(
            'ALTER TABLE "extractions" ' "ALTER COLUMN \"request_metadata\" SET DEFAULT '{}'::jsonb"
        )
        schema_editor.execute(
            'ALTER TABLE "extractions" ' 'ALTER COLUMN "request_metadata" SET NOT NULL'
        )
    else:
        schema_editor.execute(
            'UPDATE "extractions" '
            "SET \"request_metadata\" = '{}' "
            'WHERE "request_metadata" IS NULL'
        )


class Migration(migrations.Migration):
    dependencies = [
        ("django_data", "0014_add_extraction_request_logs"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_request_metadata_column,
                    reverse_code=migrations.RunPython.noop,
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="extractionmodel",
                    name="request_metadata",
                    field=models.JSONField(default=dict),
                )
            ],
        )
    ]
