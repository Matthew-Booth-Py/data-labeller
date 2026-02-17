# Manual migration to add file_path field to documents

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_data', '0006_delete_annotationmodel_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentmodel',
            name='file_path',
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
    ]
