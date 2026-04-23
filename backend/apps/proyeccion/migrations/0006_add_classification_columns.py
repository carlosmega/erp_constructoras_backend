# Classification hierarchy columns for ConceptPriceCatalogItem
# SICT:     L1=Libro, L2=Título, L3=Capítulo
# Dimovere: L1=(vacío), L2=Familia, L3=Subfamilia

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyeccion', '0005_add_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='conceptpricecatalogitem',
            name='classificationl1',
            field=models.CharField(
                blank=True,
                db_column='classificationl1',
                default='',
                help_text='Level 1: Libro (SICT) — empty for Dimovere',
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='conceptpricecatalogitem',
            name='classificationl2',
            field=models.CharField(
                blank=True,
                db_column='classificationl2',
                default='',
                help_text='Level 2: Título (SICT) / Familia (Dimovere)',
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name='conceptpricecatalogitem',
            name='classificationl3',
            field=models.CharField(
                blank=True,
                db_column='classificationl3',
                default='',
                help_text='Level 3: Capítulo (SICT) / Subfamilia (Dimovere)',
                max_length=100,
            ),
        ),
        migrations.AddIndex(
            model_name='conceptpricecatalogitem',
            index=models.Index(
                fields=['classificationl2'],
                name='conceptpric_classif_l2_idx',
            ),
        ),
    ]
