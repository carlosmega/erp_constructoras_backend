from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0006_add_expense_scope'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectexpense',
            name='accountingaccount',
            field=models.CharField(
                blank=True,
                db_column='accountingaccount',
                help_text='Cuenta contable (e.g. VIATICOS, COMBUSTIBLES)',
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='projectexpense',
            name='subaccount',
            field=models.CharField(
                blank=True,
                db_column='subaccount',
                help_text='Subcuenta contable (e.g. TRASLADO, ALIMENTOS)',
                max_length=100,
                null=True,
            ),
        ),
    ]
