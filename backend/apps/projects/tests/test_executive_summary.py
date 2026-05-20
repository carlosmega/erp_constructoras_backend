"""
TDD tests for PR #3 (Capa C): ExecutiveSummaryService.

RED phase — all tests must fail before implementation.

Spec: docs/superpowers/specs/2026-05-17-conversion-estudio-proyecto-design.md §5.3
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4

from apps.projects.tests.factories import ActiveProjectFactory
from apps.budgets.tests.factories import (
    CostCategoryFactory, IndirectCostCategoryFactory,
    ImputationCodeFactory, IndirectImputationCodeFactory,
)
from apps.expenses.tests.factories import ClientEstimateFactory
from apps.users.tests.factories import SalespersonFactory
from apps.budgets.models import CostTypeCode
from apps.expenses.models import PaymentStatusCode


# ============================================================================
# Helpers
# ============================================================================

def _project():
    user = SalespersonFactory()
    return ActiveProjectFactory(
        ownerid=user, createdby=user, modifiedby=user,
        contractamount_notax=Decimal('1_000_000'),
        contractamount_withtax=Decimal('1_160_000'),
        advancepayment_notax=Decimal('100_000'),
        advancepayment_withtax=Decimal('116_000'),
    )


def _direct_code(project, *, budget=Decimal('200_000'), spent=Decimal('0')):
    cat = CostCategoryFactory(projectid=project, createdby=project.ownerid, modifiedby=project.ownerid)
    return ImputationCodeFactory(
        projectid=project,
        categoryid=cat,
        totalbudget=budget,
        totalspent=spent,
        createdby=project.ownerid,
        modifiedby=project.ownerid,
    )


def _indirect_code(project, *, budget=Decimal('50_000'), spent=Decimal('0')):
    cat = IndirectCostCategoryFactory(projectid=project, createdby=project.ownerid, modifiedby=project.ownerid)
    return IndirectImputationCodeFactory(
        projectid=project,
        categoryid=cat,
        totalbudget=budget,
        totalspent=spent,
        createdby=project.ownerid,
        modifiedby=project.ownerid,
    )


def _estimate(project, *, amountnotax=Decimal('85_000'), totalinvoiced=Decimal('98_600'),
              amortization=Decimal('5_000'), guaranteefund=Decimal('5_000'),
              paid=False, overdue_days=None, estimatedamount=Decimal('100_000'),
              collectableamount=Decimal('98_600'), amountpaid=Decimal('0'),
              period_label='Q1 MAY-26'):
    from apps.budgets.tests.factories import ImputationPeriodFactory
    period = ImputationPeriodFactory(projectid=project)
    if overdue_days is not None:
        invoice_date = date.today() - timedelta(days=overdue_days + 30)
    else:
        invoice_date = date.today()
    status = PaymentStatusCode.PAID if paid else (
        PaymentStatusCode.OVERDUE if overdue_days else PaymentStatusCode.PENDING
    )
    return ClientEstimateFactory(
        projectid=project,
        periodid=period,
        estimatedamount=estimatedamount,
        amountnotax=amountnotax,
        totalinvoiced=totalinvoiced,
        advanceamortization=amortization,
        guaranteefund=guaranteefund,
        collectableamount=collectableamount,
        amountpaid=amountpaid if paid else Decimal('0'),
        paymentstatus=status,
        invoicedate=invoice_date,
        estimationperiod=period_label,
        createdby=project.ownerid,
        modifiedby=project.ownerid,
    )


# ============================================================================
# Section 1 — project_info
# ============================================================================

@pytest.mark.unit
class TestProjectInfo:
    def test_project_info_basic_fields(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        info = result['project_info']
        assert info['name'] == p.name
        assert info['contract_amount_notax'] == p.contractamount_notax
        assert info['contract_amount_withtax'] == p.contractamount_withtax
        assert info['advance_payment_notax'] == p.advancepayment_notax

    def test_project_info_includes_client_name(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        assert result['project_info']['client'] == p.accountid.name


# ============================================================================
# Section 2 — current_status (project with no estimates)
# ============================================================================

@pytest.mark.unit
class TestCurrentStatusEmpty:
    """Project with no estimates → everything is zero or None."""

    def test_advance_all_zeros(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        adv = result['current_status']['advance']
        assert adv['amortized_notax'] == Decimal('0')
        assert adv['pending_notax'] == p.advancepayment_notax

    def test_certification_all_zeros(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        cert = result['current_status']['certification']
        assert cert['invoiced_notax'] == Decimal('0')
        assert cert['debt_notax'] == Decimal('0')
        assert cert['oldest_overdue_days'] == 0

    def test_guarantee_all_zeros(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        guar = result['current_status']['guarantee_retention']
        assert guar['accumulated_notax'] == Decimal('0')
        assert guar['paid_notax'] == Decimal('0')

    def test_production_all_zeros(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        prod = result['current_status']['production']
        assert prod['accumulated'] == Decimal('0')
        assert prod['estimated'] == p.contractamount_notax

    def test_result_zero_costs(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        res = result['current_status']['result']
        # planned = contract - total planned budget (0 costs → = contract)
        assert res['actual'] == Decimal('0')


# ============================================================================
# Section 2 — current_status (1 paid estimate)
# ============================================================================

@pytest.mark.unit
class TestCurrentStatusPaidEstimate:
    """Project with 1 fully paid estimate."""

    def test_certification_invoiced_matches_estimate(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, amountnotax=Decimal('85_000'), totalinvoiced=Decimal('98_600'),
                  paid=True, amountpaid=Decimal('98_600'), collectableamount=Decimal('98_600'))
        result = ExecutiveSummaryService.compute(p.projectid)
        cert = result['current_status']['certification']
        assert cert['invoiced_notax'] == Decimal('85_000')
        assert cert['invoiced_net'] == Decimal('98_600')

    def test_certification_debt_zero_when_paid(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, amountnotax=Decimal('85_000'), totalinvoiced=Decimal('98_600'),
                  paid=True, amountpaid=Decimal('98_600'), collectableamount=Decimal('98_600'))
        result = ExecutiveSummaryService.compute(p.projectid)
        # Paid → debt = 0
        assert result['current_status']['certification']['debt_notax'] == Decimal('0')

    def test_advance_amortization_accumulates(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, amortization=Decimal('5_000'), paid=True)
        result = ExecutiveSummaryService.compute(p.projectid)
        adv = result['current_status']['advance']
        assert adv['amortized_notax'] == Decimal('5_000')
        assert adv['pending_notax'] == Decimal('95_000')  # 100k - 5k

    def test_guarantee_fund_accumulates(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, guaranteefund=Decimal('5_000'), paid=True)
        result = ExecutiveSummaryService.compute(p.projectid)
        guar = result['current_status']['guarantee_retention']
        assert guar['accumulated_notax'] == Decimal('5_000')
        assert guar['paid_notax'] == Decimal('5_000')  # paid estimate

    def test_guarantee_paid_only_counts_paid_estimates(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, guaranteefund=Decimal('5_000'), paid=True)
        _estimate(p, guaranteefund=Decimal('3_000'), paid=False)
        result = ExecutiveSummaryService.compute(p.projectid)
        guar = result['current_status']['guarantee_retention']
        assert guar['accumulated_notax'] == Decimal('8_000')
        assert guar['paid_notax'] == Decimal('5_000')  # only paid estimate


# ============================================================================
# Section 2 — current_status (overdue estimates)
# ============================================================================

@pytest.mark.unit
class TestCurrentStatusOverdue:
    """Estimates overdue: oldest_overdue_days computed correctly."""

    def test_oldest_overdue_days_zero_when_all_paid(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, paid=True, amountpaid=Decimal('98_600'))
        result = ExecutiveSummaryService.compute(p.projectid)
        assert result['current_status']['certification']['oldest_overdue_days'] == 0

    def test_oldest_overdue_days_computed_for_unpaid(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, paid=False, overdue_days=45)  # 45 days past due
        result = ExecutiveSummaryService.compute(p.projectid)
        days = result['current_status']['certification']['oldest_overdue_days']
        assert days >= 44  # allow 1-day tolerance

    def test_oldest_overdue_returns_max_days(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _estimate(p, paid=False, overdue_days=20)
        _estimate(p, paid=False, overdue_days=60)
        result = ExecutiveSummaryService.compute(p.projectid)
        days = result['current_status']['certification']['oldest_overdue_days']
        assert days >= 59


# ============================================================================
# Section 3 — technical_economic coherence
# ============================================================================

@pytest.mark.unit
class TestTechnicalEconomic:
    """result_by_family sums must match top-level totals."""

    def test_direct_cost_total_matches_sum_of_codes(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _direct_code(p, budget=Decimal('300_000'), spent=Decimal('280_000'))
        _direct_code(p, budget=Decimal('200_000'), spent=Decimal('190_000'))
        result = ExecutiveSummaryService.compute(p.projectid)
        te = result['technical_economic']
        direct = te['result_by_family']['direct_cost']
        assert direct['study'] == Decimal('500_000')
        assert direct['accumulated'] == Decimal('470_000')
        assert direct['pending'] == Decimal('30_000')

    def test_indirect_cost_total_matches_sum_of_codes(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        _indirect_code(p, budget=Decimal('80_000'), spent=Decimal('75_000'))
        result = ExecutiveSummaryService.compute(p.projectid)
        indirect = result['technical_economic']['result_by_family']['indirect_cost']
        assert indirect['study'] == Decimal('80_000')
        assert indirect['accumulated'] == Decimal('75_000')

    def test_by_category_items_present(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        cat1 = CostCategoryFactory(projectid=p, name='Pilas de Cimentación',
                                    createdby=p.ownerid, modifiedby=p.ownerid)
        cat2 = CostCategoryFactory(projectid=p, name='Mecánicas',
                                    createdby=p.ownerid, modifiedby=p.ownerid)
        ImputationCodeFactory(projectid=p, categoryid=cat1, totalbudget=Decimal('100_000'),
                               totalspent=Decimal('0'), createdby=p.ownerid, modifiedby=p.ownerid)
        ImputationCodeFactory(projectid=p, categoryid=cat2, totalbudget=Decimal('200_000'),
                               totalspent=Decimal('0'), createdby=p.ownerid, modifiedby=p.ownerid)
        result = ExecutiveSummaryService.compute(p.projectid)
        categories = result['technical_economic']['result_by_family']['by_category']
        names = [c['name'] for c in categories]
        assert 'Pilas de Cimentación' in names
        assert 'Mecánicas' in names

    def test_result_variance_pct_computed(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        # planned result: contract(1M) - budget(500k) = 500k
        # actual result: production(900k) - actual_cost(600k) = 300k
        _direct_code(p, budget=Decimal('500_000'), spent=Decimal('600_000'))
        _estimate(p, estimatedamount=Decimal('900_000'), amountnotax=Decimal('900_000'), paid=True)
        result = ExecutiveSummaryService.compute(p.projectid)
        res = result['current_status']['result']
        assert res['planned'] == Decimal('500_000')
        assert res['actual'] == Decimal('300_000')
        # variance = (300k - 500k) / 500k = -40%
        assert abs(res['variance_pct'] - Decimal('-40.00')) < Decimal('0.1')

    def test_main_items_structure(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        items = result['technical_economic']['main_items']
        types = {i['type'] for i in items}
        assert 'PRODUCTION' in types
        assert 'DIRECT_COST' in types


# ============================================================================
# Section 4 — risks
# ============================================================================

@pytest.mark.unit
class TestRisksInSummary:
    def test_risks_empty_list(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        assert result['risks'] == []

    def test_risks_included(self, db):
        from apps.projects.services import ExecutiveSummaryService
        from apps.projects.models import ProjectRisk
        p = _project()
        ProjectRisk.objects.create(
            projectid=p, description='Riesgo lluvia',
            createdby=p.ownerid, modifiedby=p.ownerid,
        )
        result = ExecutiveSummaryService.compute(p.projectid)
        assert len(result['risks']) == 1


# ============================================================================
# Section 5 — asset_usages
# ============================================================================

@pytest.mark.unit
class TestAssetUsagesInSummary:
    def test_asset_usages_empty(self, db):
        from apps.projects.services import ExecutiveSummaryService
        p = _project()
        result = ExecutiveSummaryService.compute(p.projectid)
        assert result['asset_usages'] == []

    def test_asset_usages_included_with_pending(self, db):
        from apps.projects.services import ExecutiveSummaryService
        from apps.projects.models import ProjectAssetUsage, AssetCategoryCode
        p = _project()
        ProjectAssetUsage.objects.create(
            projectid=p,
            category=AssetCategoryCode.AC3_MACHINERY_MAJOR,
            description='Excavadora',
            plannedamount=Decimal('600_000'),
            createdby=p.ownerid, modifiedby=p.ownerid,
        )
        result = ExecutiveSummaryService.compute(p.projectid)
        usages = result['asset_usages']
        assert len(usages) == 1
        assert usages[0]['planned'] == Decimal('600_000')
        assert usages[0]['pending'] == Decimal('600_000')  # no actual yet
