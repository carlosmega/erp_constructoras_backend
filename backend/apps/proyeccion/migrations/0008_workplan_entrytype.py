from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyeccion', '0007_increase_code_max_length'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='workplanentry',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='workplanentry',
            name='entrytype',
            field=models.IntegerField(
                choices=[(0, 'Planned'), (1, 'Actual')],
                default=0,
                db_column='entrytype',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='workplanentry',
            unique_together={('conceptid', 'periodnumber', 'entrytype')},
        ),
        migrations.AddIndex(
            model_name='workplanentry',
            index=models.Index(
                fields=['projectid', 'entrytype'],
                name='workplanent_project_etype_idx',
            ),
        ),
        migrations.AlterModelOptions(
            name='workplanentry',
            options={'ordering': ['entrytype', 'periodnumber']},
        ),
    ]
