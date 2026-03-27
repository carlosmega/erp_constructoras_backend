"""Management command to seed corporate module with sample data."""

from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.corporate.models import (
    CorporateBudget, CorporateBudgetVersion, CorporateBudgetLine,
    CorporateExpense,
    BudgetStateCode, BudgetVersionStateCode,
    CorporateExpenseCategoryCode,
)
from apps.users.models import SystemUser


# Monthly budget data per category (realistic for a Mexican construction company)
BUDGET_DATA = {
    CorporateExpenseCategoryCode.PERSONNEL: {
        'name': 'Personal Directivo y Administrativo',
        'monthly': [80000, 80000, 80000, 80000, 80000, 80000, 80000, 80000, 80000, 80000, 80000, 80000],
    },
    CorporateExpenseCategoryCode.INFRASTRUCTURE: {
        'name': 'Infraestructura de Oficina',
        'monthly': [25000, 25000, 25000, 25000, 25000, 25000, 25000, 25000, 25000, 25000, 25000, 25000],
    },
    CorporateExpenseCategoryCode.TECHNOLOGY: {
        'name': 'Equipamiento y Tecnología',
        'monthly': [12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000],
    },
    CorporateExpenseCategoryCode.VEHICLES: {
        'name': 'Vehículos y Transporte',
        'monthly': [18000, 18000, 18000, 18000, 18000, 18000, 18000, 18000, 18000, 18000, 18000, 18000],
    },
    CorporateExpenseCategoryCode.INSURANCE: {
        'name': 'Seguros y Obligaciones',
        'monthly': [15000, 15000, 15000, 15000, 15000, 15000, 15000, 15000, 15000, 15000, 15000, 15000],
    },
    CorporateExpenseCategoryCode.COMMERCIAL: {
        'name': 'Desarrollo Comercial y Licitaciones',
        'monthly': [20000, 20000, 20000, 25000, 25000, 20000, 20000, 20000, 25000, 25000, 20000, 20000],
    },
    CorporateExpenseCategoryCode.TRAINING: {
        'name': 'Capacitación y Desarrollo',
        'monthly': [8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000, 8000],
    },
    CorporateExpenseCategoryCode.FINANCIAL: {
        'name': 'Gastos Financieros',
        'monthly': [12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000, 12000],
    },
    CorporateExpenseCategoryCode.MISCELLANEOUS: {
        'name': 'Varios / No Clasificados',
        'monthly': [10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000],
    },
}

# Actual expenses (simulated for Jan-Mar 2026)
ACTUAL_EXPENSES = {
    CorporateExpenseCategoryCode.PERSONNEL:      [80000, 80000, 82000],
    CorporateExpenseCategoryCode.INFRASTRUCTURE:  [25000, 27500, 26000],
    CorporateExpenseCategoryCode.TECHNOLOGY:      [12000, 11500, 14800],
    CorporateExpenseCategoryCode.VEHICLES:        [18000, 16200, 17500],
    CorporateExpenseCategoryCode.INSURANCE:       [15000, 15000, 15000],
    CorporateExpenseCategoryCode.COMMERCIAL:      [20000, 22000, 28000],
    CorporateExpenseCategoryCode.TRAINING:        [8000, 3000, 5000],
    CorporateExpenseCategoryCode.FINANCIAL:       [12000, 11500, 12500],
    CorporateExpenseCategoryCode.MISCELLANEOUS:   [10000, 8000, 9500],
}

MONTH_FIELDS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


class Command(BaseCommand):
    help = 'Seed corporate module with sample budget and expense data for 2026'

    @transaction.atomic
    def handle(self, *args, **options):
        # Get or create admin user as owner
        owner = SystemUser.objects.filter(
            securityroleid__name='System Administrator'
        ).first()

        if not owner:
            owner = SystemUser.objects.first()

        if not owner:
            self.stderr.write(self.style.ERROR('No users found. Create a user first.'))
            return

        fiscal_year = 2026

        # Check if budget already exists
        if CorporateBudget.objects.filter(fiscalyear=fiscal_year).exists():
            self.stdout.write(self.style.WARNING(f'Budget for {fiscal_year} already exists. Skipping.'))
            return

        self.stdout.write(f'Creating corporate budget for {fiscal_year}...')

        # 1. Create budget
        budget = CorporateBudget(
            fiscalyear=fiscal_year,
            name=f'Presupuesto Corporativo {fiscal_year}',
            description='Presupuesto anual de operación de oficina central DIMOVERE',
            currency='MXN',
            statecode=BudgetStateCode.APPROVED,
            approvedby=owner,
            approveddate=date(fiscal_year, 1, 15),
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )
        budget.save()

        # 2. Create version V1
        version = CorporateBudgetVersion(
            corporatebudgetid=budget,
            versionnumber=1,
            label='V1 - Original',
            approveddate=date(fiscal_year, 1, 15),
            statecode=BudgetVersionStateCode.ACTIVE,
            createdby=owner,
            modifiedby=owner,
        )
        version.save()

        # 3. Create budget lines (9 categories x 12 months)
        total_annual = Decimal('0')
        for cat_code, cat_data in BUDGET_DATA.items():
            monthly_values = cat_data['monthly']
            line_kwargs = {}
            annual = Decimal('0')

            for i, field in enumerate(MONTH_FIELDS):
                val = Decimal(str(monthly_values[i]))
                line_kwargs[field] = val
                annual += val

            line = CorporateBudgetLine(
                versionid=version,
                categorycode=cat_code.value,
                categoryname=cat_data['name'],
                annualamount=annual,
                createdby=owner,
                modifiedby=owner,
                **line_kwargs,
            )
            line.save()
            total_annual += annual
            self.stdout.write(f'  {cat_code.value} {cat_data["name"]}: ${annual:,.0f}')

        # 4. Update budget totals
        budget.totalbudget = total_annual
        budget.monthlypromedio = total_annual / 12
        budget.save()

        self.stdout.write(f'\n  Total anual: ${total_annual:,.0f}')
        self.stdout.write(f'  Promedio mensual: ${budget.monthlypromedio:,.0f}')

        # 5. Create expense rows (budgeted for 12 months + actuals for Jan-Mar)
        expense_count = 0
        for cat_code, cat_data in BUDGET_DATA.items():
            actuals = ACTUAL_EXPENSES.get(cat_code, [])

            for month_idx in range(12):
                budgeted = Decimal(str(cat_data['monthly'][month_idx]))
                actual = Decimal(str(actuals[month_idx])) if month_idx < len(actuals) else Decimal('0')
                variance = actual - budgeted
                variance_pct = (variance / budgeted * 100) if budgeted else Decimal('0')

                CorporateExpense(
                    corporatebudgetid=budget,
                    categorycode=cat_code.value,
                    year=fiscal_year,
                    month=month_idx + 1,
                    budgetedamount=budgeted,
                    actualamount=actual,
                    variance=variance,
                    variancepercent=variance_pct,
                    createdby=owner,
                    modifiedby=owner,
                ).save()
                expense_count += 1

        self.stdout.write(f'  Created {expense_count} expense rows (budgeted + actuals Ene-Mar)')

        self.stdout.write(self.style.SUCCESS(
            f'\nCorporate budget {fiscal_year} seeded successfully!'
            f'\n  Budget ID: {budget.corporatebudgetid}'
            f'\n  Status: Approved'
            f'\n  Total: ${total_annual:,.0f} MXN'
        ))
