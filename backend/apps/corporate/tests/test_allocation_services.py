"""Unit tests for Corporate allocation, portfolio, and simulation services."""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import patch, MagicMock

from apps.corporate.allocation_services import (
    CorporateAllocationService,
    PortfolioService,
    SimulationService,
    MONTH_FIELDS,
    MONTH_LABELS,
)
from apps.corporate.models import (
    CorporateAllocation,
    CorporateAllocationLine,
    WhatIfSimulation,
    AllocationStateCode,
    BudgetStateCode,
    ProrationMethodCode,
    SimulationStateCode,
)
from apps.corporate.tests.factories import (
    ApprovedBudgetFactory,
    CorporateBudgetFactory,
    CorporateBudgetVersionFactory,
    CorporateBudgetLineFactory,
    CorporateAllocationFactory,
    CorporateAllocationLineFactory,
    AppliedAllocationFactory,
    WhatIfSimulationFactory,
)
from apps.projects.tests.factories import ActiveProjectFactory
from apps.budgets.models import CostCategory, ImputationCode, CostTypeCode
from core.exceptions import ValidationError, NotFound


# ============================================================================
# CorporateAllocationService Tests
# ============================================================================


@pytest.mark.unit
class TestGetActiveProjects:
    """Test CorporateAllocationService.get_active_projects."""

    def test_returns_projects_active_in_month(self, db, salesperson):
        project = ActiveProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 1, 1),
            contractenddate=date(2026, 12, 31),
        )
        result = CorporateAllocationService.get_active_projects(2026, 6)
        assert project in result

    def test_excludes_projects_ending_before_month(self, db, salesperson):
        ActiveProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 1, 1),
            contractenddate=date(2026, 3, 15),
        )
        result = CorporateAllocationService.get_active_projects(2026, 6)
        assert result.count() == 0

    def test_excludes_projects_starting_after_month(self, db, salesperson):
        ActiveProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 9, 1),
            contractenddate=date(2026, 12, 31),
        )
        result = CorporateAllocationService.get_active_projects(2026, 6)
        assert result.count() == 0

    def test_december_boundary(self, db, salesperson):
        project = ActiveProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 12, 1),
            contractenddate=date(2027, 3, 31),
        )
        result = CorporateAllocationService.get_active_projects(2026, 12)
        assert project in result


@pytest.mark.unit
class TestGetMonthlyBudget:
    """Test CorporateAllocationService._get_monthly_budget."""

    def test_returns_sum_for_month(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        version = CorporateBudgetVersionFactory(corporatebudgetid=budget)
        CorporateBudgetLineFactory(versionid=version, jan=Decimal('50000.00'))
        CorporateBudgetLineFactory(
            versionid=version,
            categorycode='4.2',
            categoryname='Infraestructura',
            jan=Decimal('30000.00'),
        )

        total = CorporateAllocationService._get_monthly_budget(budget, 1)
        assert total == Decimal('80000.00')

    def test_returns_zero_without_active_version(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        total = CorporateAllocationService._get_monthly_budget(budget, 1)
        assert total == Decimal('0')


@pytest.mark.unit
class TestCalculateWeights:
    """Test CorporateAllocationService._calculate_weights."""

    def test_contract_amount_method(self, db, salesperson):
        p1 = ActiveProjectFactory(ownerid=salesperson, contractamount_notax=Decimal('1000000'))
        p2 = ActiveProjectFactory(ownerid=salesperson, contractamount_notax=Decimal('3000000'))
        projects = [p1, p2]

        weights, total = CorporateAllocationService._calculate_weights(
            projects, ProrationMethodCode.CONTRACT_AMOUNT
        )
        assert total == Decimal('4000000')
        assert weights[0] == (p1, Decimal('1000000'))
        assert weights[1] == (p2, Decimal('3000000'))

    def test_duration_method(self, db, salesperson):
        p1 = ActiveProjectFactory(ownerid=salesperson, durationmonths=6)
        p2 = ActiveProjectFactory(ownerid=salesperson, durationmonths=12)
        projects = [p1, p2]

        weights, total = CorporateAllocationService._calculate_weights(
            projects, ProrationMethodCode.DURATION
        )
        assert total == Decimal('18')

    def test_manual_method(self, db, salesperson):
        p1 = ActiveProjectFactory(ownerid=salesperson)
        p2 = ActiveProjectFactory(ownerid=salesperson)
        manual = {
            str(p1.projectid): Decimal('60'),
            str(p2.projectid): Decimal('40'),
        }

        weights, total = CorporateAllocationService._calculate_weights(
            [p1, p2], ProrationMethodCode.MANUAL, manual
        )
        assert total == Decimal('100')
        assert weights[0][1] == Decimal('60')

    def test_manual_method_requires_weights(self, db, salesperson):
        p1 = ActiveProjectFactory(ownerid=salesperson)
        with pytest.raises(ValidationError, match="Manual weights are required"):
            CorporateAllocationService._calculate_weights(
                [p1], ProrationMethodCode.MANUAL
            )

    def test_hybrid_method_requires_weights(self, db, salesperson):
        p1 = ActiveProjectFactory(ownerid=salesperson)
        with pytest.raises(ValidationError, match="Manual weights are required"):
            CorporateAllocationService._calculate_weights(
                [p1], ProrationMethodCode.HYBRID
            )


@pytest.mark.unit
class TestCalculateAllocation:
    """Test CorporateAllocationService.calculate_allocation."""

    def _make_budget_with_version(self, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        version = CorporateBudgetVersionFactory(corporatebudgetid=budget)
        CorporateBudgetLineFactory(versionid=version, jan=Decimal('100000.00'))
        return budget

    def test_requires_approved_budget(self, db, salesperson):
        budget = CorporateBudgetFactory(ownerid=salesperson, statecode=BudgetStateCode.DRAFT)
        dto = MagicMock(year=2026, month=1, prorationmethod=ProrationMethodCode.CONTRACT_AMOUNT, manualweights=None)

        with pytest.raises(ValidationError, match="must be approved"):
            CorporateAllocationService.calculate_allocation(budget.corporatebudgetid, dto, salesperson)

    def test_budget_not_found(self, db, salesperson):
        dto = MagicMock(year=2026, month=1)
        with pytest.raises(NotFound):
            CorporateAllocationService.calculate_allocation(uuid4(), dto, salesperson)

    def test_no_active_projects_raises(self, db, salesperson):
        budget = self._make_budget_with_version(salesperson)
        dto = MagicMock(
            year=2026, month=1,
            prorationmethod=ProrationMethodCode.CONTRACT_AMOUNT,
            manualweights=None,
        )
        with pytest.raises(ValidationError, match="No active projects"):
            CorporateAllocationService.calculate_allocation(budget.corporatebudgetid, dto, salesperson)

    def test_creates_allocation_and_lines(self, db, salesperson):
        budget = self._make_budget_with_version(salesperson)
        ActiveProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 1, 1),
            contractenddate=date(2026, 12, 31),
            contractamount_notax=Decimal('500000'),
        )
        ActiveProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 1, 1),
            contractenddate=date(2026, 12, 31),
            contractamount_notax=Decimal('500000'),
        )

        dto = MagicMock(
            year=2026, month=1,
            prorationmethod=ProrationMethodCode.CONTRACT_AMOUNT,
            manualweights=None,
        )
        allocation = CorporateAllocationService.calculate_allocation(
            budget.corporatebudgetid, dto, salesperson
        )

        assert allocation.statecode == AllocationStateCode.DRAFT
        assert allocation.lines.count() == 2
        # Equal contract amounts -> equal allocation
        line_amounts = list(allocation.lines.values_list('allocatedamount', flat=True))
        assert all(a == Decimal('50000.00') for a in line_amounts)

    def test_duplicate_allocation_raises(self, db, salesperson):
        budget = self._make_budget_with_version(salesperson)
        ActiveProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 1, 1),
            contractenddate=date(2026, 12, 31),
        )
        dto = MagicMock(
            year=2026, month=1,
            prorationmethod=ProrationMethodCode.CONTRACT_AMOUNT,
            manualweights=None,
        )
        CorporateAllocationService.calculate_allocation(budget.corporatebudgetid, dto, salesperson)

        with pytest.raises(ValidationError, match="already exists"):
            CorporateAllocationService.calculate_allocation(budget.corporatebudgetid, dto, salesperson)


@pytest.mark.unit
class TestListAndGetAllocation:
    """Test list_allocations and get_allocation."""

    def test_list_allocations(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        CorporateAllocationFactory(corporatebudgetid=budget, year=2026, month=1)
        CorporateAllocationFactory(corporatebudgetid=budget, year=2026, month=2)

        result = CorporateAllocationService.list_allocations(budget.corporatebudgetid, salesperson)
        assert result.count() == 2

    def test_list_allocations_filter_by_year(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        CorporateAllocationFactory(corporatebudgetid=budget, year=2026, month=1)
        CorporateAllocationFactory(corporatebudgetid=budget, year=2027, month=1)

        result = CorporateAllocationService.list_allocations(
            budget.corporatebudgetid, salesperson, year=2026
        )
        assert result.count() == 1

    def test_get_allocation_not_found(self, db, salesperson):
        with pytest.raises(NotFound):
            CorporateAllocationService.get_allocation(uuid4(), salesperson)

    def test_get_allocation_success(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        allocation = CorporateAllocationFactory(corporatebudgetid=budget)

        result = CorporateAllocationService.get_allocation(allocation.allocationid, salesperson)
        assert result.allocationid == allocation.allocationid


@pytest.mark.unit
class TestApplyAllocation:
    """Test CorporateAllocationService.apply_allocation."""

    def test_apply_creates_c4_category_and_imputation(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        allocation = CorporateAllocationFactory(
            corporatebudgetid=budget, statecode=AllocationStateCode.DRAFT
        )
        project = ActiveProjectFactory(ownerid=salesperson)
        CorporateAllocationLineFactory(
            allocationid=allocation,
            projectid=project,
            allocatedamount=Decimal('50000.00'),
        )

        result = CorporateAllocationService.apply_allocation(allocation.allocationid, salesperson)

        assert result.statecode == AllocationStateCode.APPLIED
        assert result.appliedon is not None

        # C4 category should have been created
        c4 = CostCategory.objects.filter(projectid=project, code='C4').first()
        assert c4 is not None
        assert c4.name == 'Gastos de Oficina Central'

    def test_apply_only_draft(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        allocation = AppliedAllocationFactory(corporatebudgetid=budget)

        with pytest.raises(ValidationError, match="Only DRAFT"):
            CorporateAllocationService.apply_allocation(allocation.allocationid, salesperson)


@pytest.mark.unit
class TestReverseAllocation:
    """Test CorporateAllocationService.reverse_allocation."""

    def test_reverse_resets_imputation_budget(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        allocation = CorporateAllocationFactory(
            corporatebudgetid=budget, statecode=AllocationStateCode.DRAFT
        )
        project = ActiveProjectFactory(ownerid=salesperson)
        CorporateAllocationLineFactory(
            allocationid=allocation,
            projectid=project,
            allocatedamount=Decimal('50000.00'),
        )

        # Apply first
        CorporateAllocationService.apply_allocation(allocation.allocationid, salesperson)

        # Then reverse
        result = CorporateAllocationService.reverse_allocation(allocation.allocationid, salesperson)
        assert result.statecode == AllocationStateCode.REVERSED

        # Lines should have imputationcodeid cleared
        for line in result.lines.all():
            assert line.imputationcodeid is None

    def test_reverse_only_applied(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        allocation = CorporateAllocationFactory(
            corporatebudgetid=budget, statecode=AllocationStateCode.DRAFT
        )

        with pytest.raises(ValidationError, match="Only APPLIED"):
            CorporateAllocationService.reverse_allocation(allocation.allocationid, salesperson)


# ============================================================================
# SimulationService Tests
# ============================================================================


@pytest.mark.unit
class TestSimulationService:
    """Test SimulationService CRUD."""

    def test_create_simulation(self, db, salesperson):
        budget = ApprovedBudgetFactory(ownerid=salesperson)
        dto = type('Dto', (), {
            'name': 'Test Sim',
            'description': 'A test simulation',
            'fiscalyear': 2026,
            'corporatebudgetid': budget.corporatebudgetid,
            'parameters': {'prorationmethod': 0, 'hypotheticalprojects': []},
        })()

        sim = SimulationService.create_simulation(dto, salesperson)
        assert sim.name == 'Test Sim'
        assert sim.statecode == SimulationStateCode.ACTIVE
        assert sim.ownerid == salesperson
        assert sim.results == {}

    def test_get_simulation_not_found(self, db, salesperson):
        with pytest.raises(NotFound):
            SimulationService.get_simulation(uuid4(), salesperson)

    def test_get_simulation_success(self, db, salesperson):
        sim = WhatIfSimulationFactory(ownerid=salesperson)
        result = SimulationService.get_simulation(sim.simulationid, salesperson)
        assert result.simulationid == sim.simulationid

    def test_delete_simulation(self, db, salesperson):
        sim = WhatIfSimulationFactory(ownerid=salesperson)
        SimulationService.delete_simulation(sim.simulationid, salesperson)
        assert not WhatIfSimulation.objects.filter(simulationid=sim.simulationid).exists()

    def test_list_simulations(self, db, system_admin):
        WhatIfSimulationFactory(ownerid=system_admin)
        WhatIfSimulationFactory(ownerid=system_admin)
        result = SimulationService.list_simulations(system_admin)
        assert result.count() >= 2

    def test_run_simulation_populates_results(self, db, salesperson):
        budget = ApprovedBudgetFactory(
            ownerid=salesperson,
            monthlypromedio=Decimal('200000.00'),
        )
        project = ActiveProjectFactory(
            ownerid=salesperson,
            contractamount_notax=Decimal('5000000'),
        )
        sim = WhatIfSimulationFactory(
            ownerid=salesperson,
            corporatebudgetid=budget,
            fiscalyear=budget.fiscalyear,
            parameters={
                'prorationmethod': ProrationMethodCode.CONTRACT_AMOUNT,
                'hypotheticalprojects': [
                    {'name': 'New HQ', 'contractamount': 3000000},
                ],
                'baseprojects': [str(project.projectid)],
            },
        )

        result = SimulationService.run_simulation(sim.simulationid, salesperson)
        assert 'currentscenario' in result.results
        assert 'newscenario' in result.results
        assert len(result.results['newscenario']['projects']) == 2
