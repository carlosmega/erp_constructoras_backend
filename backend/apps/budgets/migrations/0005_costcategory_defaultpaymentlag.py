from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('budgets', '0004_remove_imputationcodebudget_unique_code_period_budget_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='costcategory',
                    name='defaultpaymentlag',
                    field=models.IntegerField(default=0, db_column='defaultpaymentlag'),
                ),
            ],
            # Column already exists in DB with NOT NULL; ensure all rows have default=0.
            database_operations=[
                migrations.RunSQL(
                    sql="UPDATE costcategory SET defaultpaymentlag = COALESCE(defaultpaymentlag, 0)",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
