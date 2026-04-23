"""Seed default FinancialSettings and a 100%/0 BillingRule for existing projects."""
from decimal import Decimal
from django.db import migrations


def seed_defaults(apps, schema_editor):
    ConstructionProject = apps.get_model('projects', 'ConstructionProject')
    ProjectFinancialSettings = apps.get_model('cashflow', 'ProjectFinancialSettings')
    ProjectBillingRule = apps.get_model('cashflow', 'ProjectBillingRule')

    for project in ConstructionProject.objects.all():
        ProjectFinancialSettings.objects.get_or_create(
            projectid=project,
            defaults={
                'imssretentionrate': Decimal('0.0500'),
                'otherretentionrate': Decimal('0'),
                'retentionreturnperiod': None,
                'advanceamortizationrate': Decimal('0'),
                'anticipoentryperiod': 1,
                'transversalcost': Decimal('0'),
                'transversalwithdrawalperiod': 1,
                'utilitycost': Decimal('0'),
                'utilitywithdrawalperiod': 1,
                'financecostrate': Decimal('0.001000'),
            },
        )
        if not ProjectBillingRule.objects.filter(projectid=project).exists():
            ProjectBillingRule.objects.create(
                projectid=project,
                sequence=1,
                percent=Decimal('1.0000'),
                lagperiods=0,
            )


def noop_reverse(apps, schema_editor):
    # Reversible by schema; we don't delete rows in reverse.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('cashflow', '0002_projectbillingrule'),
        ('projects', '0004_alter_projectsupplier_rfc'),
    ]

    operations = [
        migrations.RunPython(seed_defaults, noop_reverse),
    ]
