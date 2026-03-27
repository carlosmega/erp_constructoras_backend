"""Corporate module business logic services."""

from decimal import Decimal
from datetime import date
from uuid import UUID
from typing import Optional

from django.db import models, transaction
from django.db.models import Sum, Prefetch

from apps.corporate.models import (
    CorporateBudget,
    CorporateBudgetVersion,
    CorporateBudgetLine,
    CorporateExpense,
    BudgetStateCode,
    BudgetVersionStateCode,
    CorporateExpenseCategoryCode,
)
from core.exceptions import ValidationError, NotFound
from core.permissions import filter_by_ownership


MONTH_FIELDS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
MONTH_LABELS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


class CorporateBudgetService:
    """Service for corporate budget CRUD and version management."""

    @staticmethod
    def list_budgets(user, fiscal_year: Optional[int] = None, statecode: Optional[int] = None):
        qs = CorporateBudget.objects.all()
        qs = filter_by_ownership(qs, user)
        if fiscal_year is not None:
            qs = qs.filter(fiscalyear=fiscal_year)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs.select_related('ownerid', 'approvedby').prefetch_related('versions')

    @staticmethod
    def get_budget(budget_id: UUID, user):
        try:
            budget = CorporateBudget.objects.select_related(
                'ownerid', 'approvedby'
            ).prefetch_related(
                Prefetch(
                    'versions',
                    queryset=CorporateBudgetVersion.objects.prefetch_related('lines')
                )
            ).get(corporatebudgetid=budget_id)
        except CorporateBudget.DoesNotExist:
            raise NotFound(f"Corporate budget {budget_id} not found")
        # Cache active version
        active_versions = [v for v in budget.versions.all() if v.statecode == BudgetVersionStateCode.ACTIVE]
        budget._active_version = active_versions[0] if active_versions else None
        return budget

    @staticmethod
    @transaction.atomic
    def create_budget(dto, user):
        # Check uniqueness based on period type
        period = getattr(dto, 'periodtype', 0)  # 0 = ANNUAL
        quarter = getattr(dto, 'quarter', None)

        existing = CorporateBudget.objects.filter(
            fiscalyear=dto.fiscalyear,
            periodtype=period,
        )
        if quarter is not None:
            existing = existing.filter(quarter=quarter)
        else:
            existing = existing.filter(quarter__isnull=True)

        if existing.exists():
            if period == 0:
                raise ValidationError(
                    f"Ya existe un presupuesto anual para el año fiscal {dto.fiscalyear}. "
                    f"Solo puede haber un presupuesto anual por año."
                )
            else:
                quarter_labels = {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'}
                q_label = quarter_labels.get(quarter, f'Q{quarter}')
                raise ValidationError(
                    f"Ya existe un presupuesto para {q_label} del año fiscal {dto.fiscalyear}."
                )

        budget = CorporateBudget(
            fiscalyear=dto.fiscalyear,
            periodtype=period,
            quarter=quarter,
            name=dto.name,
            description=dto.description,
            currency=getattr(dto, 'currency', 'MXN'),
            statecode=BudgetStateCode.DRAFT,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        budget.save()

        # Create initial version V1
        version = CorporateBudgetVersion(
            corporatebudgetid=budget,
            versionnumber=1,
            label='V1 - Original',
            statecode=BudgetVersionStateCode.ACTIVE,
            createdby=user,
            modifiedby=user,
        )
        version.save()

        # Create 9 empty budget lines (one per category)
        for choice in CorporateExpenseCategoryCode:
            CorporateBudgetLine(
                versionid=version,
                categorycode=choice.value,
                categoryname=choice.label,
                createdby=user,
                modifiedby=user,
            ).save()

        return budget

    @staticmethod
    def update_budget(budget_id: UUID, dto, user):
        budget = CorporateBudgetService.get_budget(budget_id, user)
        if budget.statecode == BudgetStateCode.CLOSED:
            raise ValidationError("Cannot update a closed budget")

        if dto.name is not None:
            budget.name = dto.name
        if dto.description is not None:
            budget.description = dto.description
        budget.modifiedby = user
        budget.save()
        return budget

    @staticmethod
    @transaction.atomic
    def approve_budget(budget_id: UUID, user):
        budget = CorporateBudgetService.get_budget(budget_id, user)
        if budget.statecode == BudgetStateCode.APPROVED:
            raise ValidationError("Budget is already approved")

        # Get active version and compute totals
        active_version = budget._active_version
        if not active_version:
            raise ValidationError("No active version found to approve")

        lines = list(active_version.lines.all())
        total_annual = sum(line.annualamount for line in lines)
        monthly_avg = total_annual / 12 if total_annual else Decimal('0')

        budget.statecode = BudgetStateCode.APPROVED
        budget.totalbudget = total_annual
        budget.monthlypromedio = monthly_avg
        budget.approvedby = user
        budget.approveddate = date.today()
        budget.modifiedby = user
        budget.save()

        # Snapshot budgeted amounts to CorporateExpense rows (12 months)
        for line in lines:
            for month_idx, field in enumerate(MONTH_FIELDS, start=1):
                budgeted = getattr(line, field, Decimal('0'))
                CorporateExpense.objects.update_or_create(
                    corporatebudgetid=budget,
                    categorycode=line.categorycode,
                    year=budget.fiscalyear,
                    month=month_idx,
                    defaults={
                        'budgetedamount': budgeted,
                        'modifiedby': user,
                    }
                )

        return budget

    @staticmethod
    @transaction.atomic
    def create_new_version(budget_id: UUID, dto, user):
        budget = CorporateBudgetService.get_budget(budget_id, user)
        if budget.statecode == BudgetStateCode.CLOSED:
            raise ValidationError("Cannot create versions for a closed budget")

        # Supersede current active version
        active_version = budget._active_version
        if active_version:
            active_version.statecode = BudgetVersionStateCode.SUPERSEDED
            active_version.save()

        # Determine next version number
        max_version = budget.versions.aggregate(max_v=models.Max('versionnumber'))['max_v'] or 0
        new_number = max_version + 1

        new_version = CorporateBudgetVersion(
            corporatebudgetid=budget,
            versionnumber=new_number,
            label=dto.label,
            notes=dto.notes,
            statecode=BudgetVersionStateCode.ACTIVE,
            createdby=user,
            modifiedby=user,
        )
        new_version.save()

        # Copy lines from previous active version
        if active_version:
            for old_line in active_version.lines.all():
                CorporateBudgetLine(
                    versionid=new_version,
                    categorycode=old_line.categorycode,
                    categoryname=old_line.categoryname,
                    jan=old_line.jan, feb=old_line.feb, mar=old_line.mar,
                    apr=old_line.apr, may=old_line.may, jun=old_line.jun,
                    jul=old_line.jul, aug=old_line.aug, sep=old_line.sep,
                    oct=old_line.oct, nov=old_line.nov, dec=old_line.dec,
                    annualamount=old_line.annualamount,
                    notes=old_line.notes,
                    createdby=user,
                    modifiedby=user,
                ).save()
        else:
            # Create empty lines if no previous version
            for choice in CorporateExpenseCategoryCode:
                CorporateBudgetLine(
                    versionid=new_version,
                    categorycode=choice.value,
                    categoryname=choice.label,
                    createdby=user,
                    modifiedby=user,
                ).save()

        return new_version

    @staticmethod
    def get_budget_lines(budget_id: UUID, user):
        budget = CorporateBudgetService.get_budget(budget_id, user)
        active_version = budget._active_version
        if not active_version:
            return []
        return list(active_version.lines.all())

    @staticmethod
    def update_budget_line(line_id: UUID, dto, user):
        try:
            line = CorporateBudgetLine.objects.get(budgetlineid=line_id)
        except CorporateBudgetLine.DoesNotExist:
            raise NotFound(f"Budget line {line_id} not found")

        for field in MONTH_FIELDS:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(line, field, value)

        if dto.notes is not None:
            line.notes = dto.notes

        # Recalculate annual amount
        line.annualamount = sum(getattr(line, f) for f in MONTH_FIELDS)
        line.modifiedby = user
        line.save()
        return line

    @staticmethod
    @transaction.atomic
    def bulk_update_lines(budget_id: UUID, dto, user):
        results = []
        for line_data in dto.lines:
            line_id = line_data.get('budgetlineid')
            if not line_id:
                continue
            try:
                line = CorporateBudgetLine.objects.get(budgetlineid=line_id)
            except CorporateBudgetLine.DoesNotExist:
                continue

            for field in MONTH_FIELDS:
                value = line_data.get(field)
                if value is not None:
                    setattr(line, field, Decimal(str(value)))

            if 'notes' in line_data:
                line.notes = line_data['notes']

            line.annualamount = sum(getattr(line, f) for f in MONTH_FIELDS)
            line.modifiedby = user
            line.save()
            results.append(line)
        return results


class CorporateExpenseService:
    """Service for tracking real corporate expenses vs budget."""

    @staticmethod
    def list_expenses(budget_id: UUID, user, year: Optional[int] = None, month: Optional[int] = None):
        qs = CorporateExpense.objects.filter(corporatebudgetid=budget_id)
        if year is not None:
            qs = qs.filter(year=year)
        if month is not None:
            qs = qs.filter(month=month)
        return qs

    @staticmethod
    def record_expense(budget_id: UUID, dto, user):
        """Upsert an actual expense amount for a category/month."""
        try:
            budget = CorporateBudget.objects.get(corporatebudgetid=budget_id)
        except CorporateBudget.DoesNotExist:
            raise NotFound(f"Corporate budget {budget_id} not found")

        expense, created = CorporateExpense.objects.get_or_create(
            corporatebudgetid=budget,
            categorycode=dto.categorycode,
            year=dto.year,
            month=dto.month,
            defaults={
                'actualamount': dto.actualamount,
                'notes': dto.notes,
                'createdby': user,
                'modifiedby': user,
            }
        )

        if not created:
            expense.actualamount = dto.actualamount
            if dto.notes is not None:
                expense.notes = dto.notes
            expense.modifiedby = user

        # Calculate variance
        if expense.budgetedamount and expense.budgetedamount != 0:
            expense.variance = expense.actualamount - expense.budgetedamount
            expense.variancepercent = (expense.variance / expense.budgetedamount) * 100
        else:
            expense.variance = expense.actualamount
            expense.variancepercent = Decimal('0')

        expense.save()
        return expense

    @staticmethod
    @transaction.atomic
    def bulk_record_expenses(budget_id: UUID, dto, user):
        results = []
        for exp_dto in dto.expenses:
            result = CorporateExpenseService.record_expense(budget_id, exp_dto, user)
            results.append(result)
        return results

    @staticmethod
    def get_budget_vs_actual(budget_id: UUID, year: int, user):
        """Build the full semaphore dashboard data."""
        expenses = CorporateExpense.objects.filter(
            corporatebudgetid=budget_id,
            year=year,
        ).order_by('categorycode', 'month')

        # Group by category
        from collections import defaultdict
        by_category = defaultdict(list)
        for exp in expenses:
            by_category[exp.categorycode].append(exp)

        def get_semaphore(budgeted, actual):
            if budgeted and budgeted > 0:
                pct = abs(float((actual - budgeted) / budgeted * 100))
                if pct > 20:
                    return 'red'
                elif pct > 10:
                    return 'yellow'
            return 'green'

        rows = []
        total_budgeted = Decimal('0')
        total_actual = Decimal('0')
        ytd_budgeted = Decimal('0')
        ytd_actual = Decimal('0')
        current_month = date.today().month

        for choice in CorporateExpenseCategoryCode:
            cat_expenses = by_category.get(choice.value, [])
            months_data = []
            annual_budgeted = Decimal('0')
            annual_actual = Decimal('0')

            for m in range(1, 13):
                exp = next((e for e in cat_expenses if e.month == m), None)
                budgeted = exp.budgetedamount if exp else Decimal('0')
                actual = exp.actualamount if exp else Decimal('0')
                variance = actual - budgeted
                vpct = (variance / budgeted * 100) if budgeted else Decimal('0')

                months_data.append({
                    'month': m,
                    'budgeted': budgeted,
                    'actual': actual,
                    'variance': variance,
                    'variancepercent': vpct,
                    'semaphore': get_semaphore(budgeted, actual),
                })

                annual_budgeted += budgeted
                annual_actual += actual
                if m <= current_month:
                    ytd_budgeted += budgeted
                    ytd_actual += actual

            annual_variance = annual_actual - annual_budgeted
            annual_vpct = (annual_variance / annual_budgeted * 100) if annual_budgeted else Decimal('0')

            rows.append({
                'categorycode': choice.value,
                'categoryname': choice.label,
                'months': months_data,
                'annualbudgeted': annual_budgeted,
                'annualactual': annual_actual,
                'annualvariance': annual_variance,
                'annualvariancepercent': annual_vpct,
                'annualsemaphore': get_semaphore(annual_budgeted, annual_actual),
            })

            total_budgeted += annual_budgeted
            total_actual += annual_actual

        total_variance = total_actual - total_budgeted
        total_vpct = (total_variance / total_budgeted * 100) if total_budgeted else Decimal('0')
        ytd_variance = ytd_actual - ytd_budgeted

        # Project annual based on YTD
        if current_month > 0 and ytd_actual > 0:
            projected = ytd_actual / current_month * 12
        else:
            projected = Decimal('0')

        return {
            'rows': rows,
            'totalbudgeted': total_budgeted,
            'totalactual': total_actual,
            'totalvariance': total_variance,
            'totalvariancepercent': total_vpct,
            'totalsemaphore': get_semaphore(total_budgeted, total_actual),
            'ytdbudgeted': ytd_budgeted,
            'ytdactual': ytd_actual,
            'ytdvariance': ytd_variance,
            'projectedannual': projected,
        }
