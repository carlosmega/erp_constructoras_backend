import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('budgets', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImputationCodeBudget',
            fields=[
                ('budgetlineid', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    primary_key=True,
                    serialize=False,
                    db_column='budgetlineid',
                )),
                ('imputationcodeid', models.ForeignKey(
                    db_column='imputationcodeid',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='budget_lines',
                    to='budgets.imputationcode',
                )),
                ('periodid', models.ForeignKey(
                    blank=True,
                    db_column='periodid',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='code_budgets',
                    to='budgets.imputationperiod',
                )),
                ('periodlabel', models.CharField(
                    db_column='periodlabel',
                    max_length=30,
                )),
                ('plannedamount', models.DecimalField(
                    db_column='plannedamount',
                    decimal_places=2,
                    default=0,
                    max_digits=19,
                )),
                ('actualamount', models.DecimalField(
                    db_column='actualamount',
                    decimal_places=2,
                    default=0,
                    max_digits=19,
                )),
                ('createdon', models.DateTimeField(
                    auto_now_add=True,
                    db_column='createdon',
                )),
                ('modifiedon', models.DateTimeField(
                    auto_now=True,
                    db_column='modifiedon',
                )),
            ],
            options={
                'db_table': 'imputationcodebudget',
                'ordering': ['imputationcodeid', 'periodlabel'],
            },
        ),
        migrations.AddConstraint(
            model_name='imputationcodebudget',
            constraint=models.UniqueConstraint(
                fields=['imputationcodeid', 'periodlabel'],
                name='unique_code_period_budget',
            ),
        ),
        migrations.AddIndex(
            model_name='imputationcodebudget',
            index=models.Index(
                fields=['imputationcodeid', 'periodlabel'],
                name='idx_codebudget_code_period',
            ),
        ),
        migrations.AddIndex(
            model_name='imputationcodebudget',
            index=models.Index(
                fields=['periodid'],
                name='idx_codebudget_period',
            ),
        ),
    ]
