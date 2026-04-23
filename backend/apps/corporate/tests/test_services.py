"""Unit tests for Corporate module services."""

import pytest
from decimal import Decimal
from datetime import date

from apps.corporate.models import (
    CorporateBudget, CorporateBudgetVersion, CorporateBudgetLine,
    BudgetStateCode, BudgetVersionStateCode,
    CorporateExpenseCategoryCode,
)
from apps.expenses.models import ProjectExpense, ExpenseScopeCode, ExpenseStateCode
from apps.corporate.services import CorporateBudgetService, CorporateExpenseService
from apps.corporate.schemas import CreateCorporateBudgetDto, UpdateCorporateBudgetDto, CreateBudgetVersionDto, RecordExpenseDto
from apps.corporate.tests.factories import (
    CorporateBudgetFactory, ApprovedBudgetFactory,
    CorporateBudgetVersionFactory, CorporateBudgetLineFactory,
)
from core.exceptions import ValidationError, NotFound


@pytest.mark.unit
class TestCorporateBudgetServiceCreate:
    """Test CorporateBudgetService.create_budget."""

    def test_create_budget_minimal(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2030, name='Test Budget 2030')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        assert budget.corporatebudgetid is not None
        assert budget.fiscalyear == 2030
        assert budget.name == 'Test Budget 2030'
        assert budget.statecode == BudgetStateCode.DRAFT
        assert budget.ownerid == salesperson

    def test_create_budget_creates_v1(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2031, name='Budget 2031')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        versions = CorporateBudgetVersion.objects.filter(corporatebudgetid=budget)
        assert versions.count() == 1
        assert versions.first().versionnumber == 1
        assert versions.first().label == 'V1 - Original'

    def test_create_budget_creates_9_lines(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2032, name='Budget 2032')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        version = CorporateBudgetVersion.objects.get(corporatebudgetid=budget)
        lines = CorporateBudgetLine.objects.filter(versionid=version)
        assert lines.count() == 9

        # Check all 9 categories exist
        categories = set(lines.values_list('categorycode', flat=True))
        expected = {c.value for c in CorporateExpenseCategoryCode}
        assert categories == expected

    def test_create_budget_duplicate_year_fails(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2033, name='Budget A')
        CorporateBudgetService.create_budget(dto, salesperson)

        dto2 = CreateCorporateBudgetDto(fiscalyear=2033, name='Budget B')
        with pytest.raises(ValidationError):
            CorporateBudgetService.create_budget(dto2, salesperson)


@pytest.mark.unit
class TestCorporateBudgetServiceGet:
    """Test CorporateBudgetService.get/list."""

    def test_get_budget_by_id(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2034, name='Get Test')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        result = CorporateBudgetService.get_budget(budget.corporatebudgetid, salesperson)
        assert result.corporatebudgetid == budget.corporatebudgetid
        assert result._active_version is not None

    def test_get_budget_not_found(self, db, salesperson):
        from uuid import uuid4
        with pytest.raises(NotFound):
            CorporateBudgetService.get_budget(uuid4(), salesperson)

    def test_list_budgets(self, db, salesperson):
        dto1 = CreateCorporateBudgetDto(fiscalyear=2035, name='Budget A')
        dto2 = CreateCorporateBudgetDto(fiscalyear=2036, name='Budget B')
        CorporateBudgetService.create_budget(dto1, salesperson)
        CorporateBudgetService.create_budget(dto2, salesperson)

        budgets = CorporateBudgetService.list_budgets(salesperson)
        assert budgets.count() >= 2

    def test_list_budgets_filter_by_year(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2037, name='Filter Test')
        CorporateBudgetService.create_budget(dto, salesperson)

        budgets = CorporateBudgetService.list_budgets(salesperson, fiscal_year=2037)
        assert budgets.count() == 1


@pytest.mark.unit
class TestCorporateBudgetServiceApprove:
    """Test budget approval workflow."""

    def test_approve_budget(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2038, name='Approve Test')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        # Set some amounts on budget lines first
        version = budget.versions.first()
        line = version.lines.first()
        line.jan = Decimal('10000')
        line.feb = Decimal('10000')
        line.annualamount = Decimal('20000')
        line.save()

        result = CorporateBudgetService.approve_budget(budget.corporatebudgetid, salesperson)
        assert result.statecode == BudgetStateCode.APPROVED
        assert result.approvedby == salesperson
        assert result.approveddate == date.today()

    def test_approve_does_not_create_legacy_expense_rows(self, db, salesperson):
        """Approve no longer creates CorporateExpense rows.
        Budgeted amounts live in CorporateBudgetLine and actuals
        come from ProjectExpense records with expensescope=CORPORATE."""
        dto = CreateCorporateBudgetDto(fiscalyear=2039, name='Expense Snapshot')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        # Set amounts
        version = budget.versions.first()
        line = version.lines.first()
        line.jan = Decimal('10000')
        line.annualamount = Decimal('10000')
        line.save()

        CorporateBudgetService.approve_budget(budget.corporatebudgetid, salesperson)

        # No ProjectExpense rows created by approval (they come from recording)
        corporate_expenses = ProjectExpense.objects.filter(
            expensescope=ExpenseScopeCode.CORPORATE,
            corporatebudgetid=budget,
        )
        assert corporate_expenses.count() == 0

    def test_approve_already_approved_fails(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2040, name='Already Approved')
        budget = CorporateBudgetService.create_budget(dto, salesperson)
        CorporateBudgetService.approve_budget(budget.corporatebudgetid, salesperson)

        with pytest.raises(ValidationError, match='already approved'):
            CorporateBudgetService.approve_budget(budget.corporatebudgetid, salesperson)


@pytest.mark.unit
class TestCorporateBudgetServiceVersions:
    """Test version management."""

    def test_create_new_version(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2041, name='Version Test')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        v_dto = CreateBudgetVersionDto(label='V2 - Ajuste Q1')
        new_version = CorporateBudgetService.create_new_version(
            budget.corporatebudgetid, v_dto, salesperson
        )

        assert new_version.versionnumber == 2
        assert new_version.label == 'V2 - Ajuste Q1'
        assert new_version.statecode == BudgetVersionStateCode.ACTIVE

        # Old version should be superseded
        old_version = CorporateBudgetVersion.objects.get(
            corporatebudgetid=budget, versionnumber=1
        )
        assert old_version.statecode == BudgetVersionStateCode.SUPERSEDED

    def test_new_version_copies_lines(self, db, salesperson):
        dto = CreateCorporateBudgetDto(fiscalyear=2042, name='Copy Lines Test')
        budget = CorporateBudgetService.create_budget(dto, salesperson)

        v_dto = CreateBudgetVersionDto(label='V2')
        new_version = CorporateBudgetService.create_new_version(
            budget.corporatebudgetid, v_dto, salesperson
        )

        assert new_version.lines.count() == 9


@pytest.mark.unit
class TestCorporateExpenseService:
    """Test CorporateExpenseService.

    Corporate expenses are now stored as ProjectExpense records
    with expensescope=CORPORATE.
    """

    def test_record_expense_creates_project_expense(self, db, salesperson):
        dto_b = CreateCorporateBudgetDto(fiscalyear=2043, name='Expense Test')
        budget = CorporateBudgetService.create_budget(dto_b, salesperson)
        CorporateBudgetService.approve_budget(budget.corporatebudgetid, salesperson)

        exp_dto = RecordExpenseDto(
            categorycode='4.1', year=2043, month=1, actualamount=Decimal('85000')
        )
        expense = CorporateExpenseService.record_expense(
            budget.corporatebudgetid, exp_dto, salesperson
        )

        assert expense.netamount == Decimal('85000')
        assert expense.expensescope == ExpenseScopeCode.CORPORATE
        assert expense.corporatebudgetid == budget
        assert expense.corporatecategory == '4.1'
        assert expense.projectid is None

    def test_record_multiple_expenses_creates_separate_records(self, db, salesperson):
        dto_b = CreateCorporateBudgetDto(fiscalyear=2044, name='Multi Test')
        budget = CorporateBudgetService.create_budget(dto_b, salesperson)
        CorporateBudgetService.approve_budget(budget.corporatebudgetid, salesperson)

        exp_dto1 = RecordExpenseDto(
            categorycode='4.1', year=2044, month=1, actualamount=Decimal('50000')
        )
        CorporateExpenseService.record_expense(budget.corporatebudgetid, exp_dto1, salesperson)

        exp_dto2 = RecordExpenseDto(
            categorycode='4.1', year=2044, month=1, actualamount=Decimal('75000')
        )
        CorporateExpenseService.record_expense(budget.corporatebudgetid, exp_dto2, salesperson)

        # Each record_expense creates a NEW ProjectExpense record
        count = ProjectExpense.objects.filter(
            expensescope=ExpenseScopeCode.CORPORATE,
            corporatebudgetid=budget,
            corporatecategory='4.1',
            invoicedate__year=2044,
            invoicedate__month=1,
        ).count()
        assert count == 2

    def test_budget_vs_actual(self, db, salesperson):
        dto_b = CreateCorporateBudgetDto(fiscalyear=2045, name='BvA Test')
        budget = CorporateBudgetService.create_budget(dto_b, salesperson)
        CorporateBudgetService.approve_budget(budget.corporatebudgetid, salesperson)

        # Record some actual expenses
        exp_dto = RecordExpenseDto(
            categorycode='4.1', year=2045, month=1, actualamount=Decimal('90000')
        )
        CorporateExpenseService.record_expense(budget.corporatebudgetid, exp_dto, salesperson)

        summary = CorporateExpenseService.get_budget_vs_actual(
            budget.corporatebudgetid, 2045, salesperson
        )

        assert 'rows' in summary
        assert len(summary['rows']) == 9
        assert summary['totalactual'] >= Decimal('90000')

    def test_budget_not_found(self, db, salesperson):
        from uuid import uuid4
        exp_dto = RecordExpenseDto(
            categorycode='4.1', year=2046, month=1, actualamount=Decimal('10000')
        )
        with pytest.raises(NotFound):
            CorporateExpenseService.record_expense(uuid4(), exp_dto, salesperson)
