from django.db import migrations, models


def _add_column_idempotent(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(costcategory)")
            existing = {row[1] for row in cursor.fetchall()}
            if 'defaultpaymentlag' not in existing:
                cursor.execute(
                    "ALTER TABLE costcategory ADD COLUMN defaultpaymentlag INTEGER NOT NULL DEFAULT 0"
                )
        else:
            # PostgreSQL: ADD COLUMN IF NOT EXISTS is a no-op when column exists
            cursor.execute(
                "ALTER TABLE costcategory"
                " ADD COLUMN IF NOT EXISTS defaultpaymentlag INTEGER NOT NULL DEFAULT 0"
            )
        cursor.execute("UPDATE costcategory SET defaultpaymentlag = COALESCE(defaultpaymentlag, 0)")


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
            database_operations=[
                migrations.RunPython(_add_column_idempotent, reverse_code=migrations.RunPython.noop),
            ],
        ),
    ]
