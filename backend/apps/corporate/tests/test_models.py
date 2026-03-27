"""Unit tests for Corporate module models."""

import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.corporate.models import (
    BudgetStateCode, BudgetVersionStateCode, ProrationMethodCode,
    AllocationStateCode, SimulationStateCode, CorporateExpenseCategoryCode,
)
from apps.corporate.tests.factories import (
    CorporateBudgetFactory, ApprovedBudgetFactory,
    CorporateBudgetVersionFactory, CorporateBudgetLineFactory,
    CorporateExpenseFactory, CorporateAllocationFactory,
    CorporateAllocationLineFactory, WhatIfSimulationFactory,
)


@pytest.mark.unit
class TestEnums:
    """Test enum values and labels."""

    def test_budget_state_values(self):
        assert BudgetStateCode.DRAFT == 0
        assert BudgetStateCode.APPROVED == 1
        assert BudgetStateCode.CLOSED == 2

    def test_proration_method_values(self):
        assert ProrationMethodCode.DIRECT_COST == 0
        assert ProrationMethodCode.CONTRACT_AMOUNT == 1
        assert ProrationMethodCode.DURATION == 2
        assert ProrationMethodCode.MANUAL == 3
        assert ProrationMethodCode.HYBRID == 4

    def test_expense_category_values(self):
        assert CorporateExpenseCategoryCode.PERSONNEL == '4.1'
        assert CorporateExpenseCategoryCode.MISCELLANEOUS == '4.9'
        assert len(CorporateExpenseCategoryCode.choices) == 9

    def test_allocation_state_values(self):
        assert AllocationStateCode.DRAFT == 0
        assert AllocationStateCode.APPLIED == 1
        assert AllocationStateCode.REVERSED == 2


@pytest.mark.unit
class TestCorporateBudgetModel:
    """Test CorporateBudget model."""

    def test_create_budget(self, db):
        budget = CorporateBudgetFactory()
        assert budget.corporatebudgetid is not None
        assert budget.fiscalyear >= 2026
        assert budget.statecode == BudgetStateCode.DRAFT

    def test_budget_str(self, db):
        budget = CorporateBudgetFactory(name='Test Budget', fiscalyear=2026)
        assert str(budget) == 'Test Budget (2026)'

    def test_budget_unique_fiscal_year(self, db):
        """Test that duplicate fiscal year is prevented (by service validation or DB constraint)."""
        CorporateBudgetFactory(fiscalyear=2026)
        # The uniqueness is enforced at the service layer, not DB constraint
        # Just verify we can't have two with same year through the service
        from apps.corporate.services import CorporateBudgetService
        from apps.corporate.schemas import CreateCorporateBudgetDto
        from core.exceptions import ValidationError
        dto = CreateCorporateBudgetDto(fiscalyear=2026, name='Dup')
        with pytest.raises(ValidationError):
            from apps.users.tests.factories import SalespersonFactory
            user = SalespersonFactory()
            CorporateBudgetService.create_budget(dto, user)

    def test_approved_budget(self, db):
        budget = ApprovedBudgetFactory()
        assert budget.statecode == BudgetStateCode.APPROVED
        assert budget.approvedby is not None
        assert budget.approveddate is not None

    def test_budget_audit_fields(self, db):
        budget = CorporateBudgetFactory()
        assert budget.createdon is not None
        assert budget.modifiedon is not None
        assert budget.createdby is not None
        assert budget.ownerid is not None


@pytest.mark.unit
class TestCorporateBudgetVersionModel:
    """Test CorporateBudgetVersion model."""

    def test_create_version(self, db):
        version = CorporateBudgetVersionFactory()
        assert version.versionid is not None
        assert version.statecode == BudgetVersionStateCode.ACTIVE

    def test_version_str(self, db):
        version = CorporateBudgetVersionFactory(versionnumber=2, label='Ajuste Q1')
        assert str(version) == 'V2 - Ajuste Q1'

    def test_version_unique_per_budget(self, db):
        budget = CorporateBudgetFactory()
        CorporateBudgetVersionFactory(corporatebudgetid=budget, versionnumber=1)
        with pytest.raises(IntegrityError):
            CorporateBudgetVersionFactory(corporatebudgetid=budget, versionnumber=1)

    def test_version_cascade_delete(self, db):
        version = CorporateBudgetVersionFactory()
        CorporateBudgetLineFactory(versionid=version)
        budget = version.corporatebudgetid
        budget.delete()
        from apps.corporate.models import CorporateBudgetVersion, CorporateBudgetLine
        assert not CorporateBudgetVersion.objects.filter(versionid=version.versionid).exists()
        assert not CorporateBudgetLine.objects.filter(versionid=version.versionid).exists()


@pytest.mark.unit
class TestCorporateBudgetLineModel:
    """Test CorporateBudgetLine model."""

    def test_create_line(self, db):
        line = CorporateBudgetLineFactory()
        assert line.budgetlineid is not None
        assert line.annualamount == Decimal('960000.00')

    def test_line_monthly_promedio(self, db):
        line = CorporateBudgetLineFactory()
        assert line.monthlypromedio == Decimal('80000.00')

    def test_line_unique_per_version_category(self, db):
        version = CorporateBudgetVersionFactory()
        CorporateBudgetLineFactory(versionid=version, categorycode='4.1')
        with pytest.raises(IntegrityError):
            CorporateBudgetLineFactory(versionid=version, categorycode='4.1')


@pytest.mark.unit
class TestCorporateExpenseModel:
    """Test CorporateExpense model."""

    def test_create_expense(self, db):
        expense = CorporateExpenseFactory()
        assert expense.corporateexpenseid is not None
        assert expense.variance == Decimal('2000.00')

    def test_expense_str(self, db):
        expense = CorporateExpenseFactory(categorycode='4.1', year=2026, month=3)
        assert str(expense) == '4.1 - 2026/3'

    def test_expense_unique_constraint(self, db):
        budget = ApprovedBudgetFactory()
        CorporateExpenseFactory(corporatebudgetid=budget, categorycode='4.1', year=2026, month=1)
        with pytest.raises(IntegrityError):
            CorporateExpenseFactory(corporatebudgetid=budget, categorycode='4.1', year=2026, month=1)


@pytest.mark.unit
class TestCorporateAllocationModel:
    """Test CorporateAllocation model."""

    def test_create_allocation(self, db):
        allocation = CorporateAllocationFactory()
        assert allocation.allocationid is not None
        assert allocation.statecode == AllocationStateCode.DRAFT

    def test_allocation_unique_per_month(self, db):
        budget = ApprovedBudgetFactory()
        CorporateAllocationFactory(corporatebudgetid=budget, year=2026, month=1)
        with pytest.raises(IntegrityError):
            CorporateAllocationFactory(corporatebudgetid=budget, year=2026, month=1)

    def test_allocation_line(self, db):
        line = CorporateAllocationLineFactory()
        assert line.allocationlineid is not None
        assert line.weightpercent == Decimal('50.0000')
        assert line.allocatedamount == Decimal('100000.00')

    def test_allocation_cascade_delete(self, db):
        allocation = CorporateAllocationFactory()
        CorporateAllocationLineFactory(allocationid=allocation)
        allocation.delete()
        from apps.corporate.models import CorporateAllocationLine
        assert not CorporateAllocationLine.objects.filter(allocationid=allocation.allocationid).exists()


@pytest.mark.unit
class TestWhatIfSimulationModel:
    """Test WhatIfSimulation model."""

    def test_create_simulation(self, db):
        sim = WhatIfSimulationFactory()
        assert sim.simulationid is not None
        assert sim.statecode == SimulationStateCode.ACTIVE
        assert sim.parameters != {}

    def test_simulation_str(self, db):
        sim = WhatIfSimulationFactory(name='Test Sim')
        assert str(sim) == 'Test Sim'

    def test_simulation_json_fields(self, db):
        sim = WhatIfSimulationFactory()
        assert 'hypotheticalprojects' in sim.parameters
        assert isinstance(sim.results, dict)
