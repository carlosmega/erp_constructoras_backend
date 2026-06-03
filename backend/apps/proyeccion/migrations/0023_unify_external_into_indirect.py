from django.db import migrations, models


def migrate_external_to_indirect(apps, schema_editor):
    ExternalCostItem = apps.get_model('proyeccion', 'ExternalCostItem')
    IndirectCostDetail = apps.get_model('proyeccion', 'IndirectCostDetail')

    def name_to_cat(name):
        n = (name or '').lower()
        if 'fianza' in n or 'seguro' in n or 'financ' in n or 'licitaci' in n:
            return 'C7'
        return 'C8'

    for ext in ExternalCostItem.objects.all():
        cat = name_to_cat(ext.itemname)
        exists = IndirectCostDetail.objects.filter(
            projectid_id=ext.projectid_id, categorycode=cat,
            description=ext.itemname).exists()
        if exists:
            continue
        agg = IndirectCostDetail.objects.filter(
            projectid_id=ext.projectid_id, categorycode=cat,
        ).aggregate(m=models.Max('linenumber'))
        next_line = (agg['m'] or 0) + 1
        IndirectCostDetail.objects.create(
            projectid_id=ext.projectid_id, categorycode=cat, linenumber=next_line,
            imputationcode='', area='', description=ext.itemname,
            monthlycost=0, units=1, months=1, applies=ext.applies,
            percentofsale=ext.percentofsale, amount=ext.amount, formulakey='',
            statecode=ext.statecode, createdby_id=ext.createdby_id,
            modifiedby_id=ext.modifiedby_id)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('proyeccion', '0022_indirectcost_applies_percentofsale'),
    ]
    operations = [
        migrations.RunPython(migrate_external_to_indirect, noop_reverse),
        migrations.DeleteModel(name='ExternalCostItem'),
    ]
