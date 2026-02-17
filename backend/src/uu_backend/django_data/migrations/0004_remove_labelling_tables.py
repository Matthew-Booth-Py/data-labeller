# Generated migration to remove labelling/annotation/evaluation tables

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_data', '0003_documentmodel'),
    ]

    operations = [
        # Drop annotation and label tables
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS annotations CASCADE;',
            reverse_sql='-- Cannot reverse drop table',
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS labels CASCADE;',
            reverse_sql='-- Cannot reverse drop table',
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS feedback CASCADE;',
            reverse_sql='-- Cannot reverse drop table',
        ),
        # Drop evaluation tables
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS evaluations CASCADE;',
            reverse_sql='-- Cannot reverse drop table',
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS benchmark_datasets CASCADE;',
            reverse_sql='-- Cannot reverse drop table',
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS benchmark_dataset_documents CASCADE;',
            reverse_sql='-- Cannot reverse drop table',
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS benchmark_runs CASCADE;',
            reverse_sql='-- Cannot reverse drop table',
        ),
    ]
