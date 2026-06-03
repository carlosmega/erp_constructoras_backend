"""TDD tests for AlternativeCostAdjustment recalculation logic (Task 4)."""

import pytest
from decimal import Decimal

from apps.proyeccion.models import OfferAlternative, AlternativeCostAdjustment, AdjustmentCostType
from apps.proyeccion.schemas import (
    CreateOfferAlternativeDto, UpdateOfferAlternativeDto, AlternativeCostAdjustmentInputDto,
)
from apps.proyeccion.services import OfferAlternativeService
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory, ConceptFamilyFactory, ConceptSubfamilyFactory, BudgetConceptFactory,
)
from apps.users.tests.factories import SystemUserFactory


@pytest.fixture
def user(db):
    return SystemUserFactory()


@pytest.fixture
def project(db, user):
    """Project with durationmonths=3 and one concept: directunitcost=2000000, qty=1."""
    p = EstimationProjectFactory(durationmonths=3, ownerid=user)
    family = ConceptFamilyFactory(projectid=p)
    subfamily = ConceptSubfamilyFactory(familyid=family, projectid=p)
    BudgetConceptFactory(
        subfamilyid=subfamily,
        projectid=p,
        directunitcost=Decimal('2000000'),
        quantity=Decimal('1'),
    )
    return p


def _adj(costtype, monthly, months=None, desc='x'):
    return AlternativeCostAdjustmentInputDto(
        costtype=costtype, description=desc, monthlyamount=Decimal(monthly), months=months, sortorder=0)


@pytest.mark.integration
def test_amount_is_monthly_times_months(project, user):
    dto = CreateOfferAlternativeDto(
        projectid=project.estimationprojectid, name='A', transversalpercent=Decimal('0'),
        profitpercent=Decimal('0'), adjustments=[_adj(AdjustmentCostType.DIRECT, '-10000', months=3, desc='excavadora')])
    alt = OfferAlternativeService.create_alternative(dto, user)
    adj = alt.cost_adjustments.get()
    assert adj.amount == Decimal('-30000.00')


@pytest.mark.integration
def test_months_defaults_to_project_duration(project, user):
    dto = CreateOfferAlternativeDto(
        projectid=project.estimationprojectid, name='A',
        adjustments=[_adj(AdjustmentCostType.DIRECT, '-10000')])
    alt = OfferAlternativeService.create_alternative(dto, user)
    adj = alt.cost_adjustments.get()
    assert adj.months == 3
    assert adj.amount == Decimal('-30000.00')


@pytest.mark.integration
def test_rollup_with_adjustments(project, user):
    dto = CreateOfferAlternativeDto(
        projectid=project.estimationprojectid, name='A',
        transversalpercent=Decimal('5'), profitpercent=Decimal('15'),
        adjustments=[_adj(AdjustmentCostType.DIRECT, '-10000', months=3)])
    alt = OfferAlternativeService.create_alternative(dto, user)
    assert alt.directcosttotal == Decimal('2000000.00')
    assert alt.directadjustmenttotal == Decimal('-30000.00')
    assert alt.constructioncost == Decimal('1970000.00')
    assert alt.salepricenet == Decimal('2364000.00')
    assert alt.taxamount == Decimal('378240.00')
    assert alt.salepricetotal == Decimal('2742240.00')


@pytest.mark.integration
def test_cap_three_per_type(project, user):
    adjustments = [_adj(AdjustmentCostType.DIRECT, '-1000', months=1) for _ in range(4)]
    dto = CreateOfferAlternativeDto(projectid=project.estimationprojectid, name='A', adjustments=adjustments)
    with pytest.raises(Exception):
        OfferAlternativeService.create_alternative(dto, user)


@pytest.mark.integration
def test_update_replaces_adjustments(project, user):
    dto = CreateOfferAlternativeDto(
        projectid=project.estimationprojectid, name='A',
        adjustments=[_adj(AdjustmentCostType.DIRECT, '-10000', months=3)])
    alt = OfferAlternativeService.create_alternative(dto, user)
    upd = UpdateOfferAlternativeDto(
        adjustments=[_adj(AdjustmentCostType.INDIRECT, '-5000', months=3, desc='camioneta')])
    alt = OfferAlternativeService.update_alternative(alt.alternativeid, upd, user)
    assert alt.cost_adjustments.count() == 1
    assert alt.indirectadjustmenttotal == Decimal('-15000.00')
    assert alt.directadjustmenttotal == Decimal('0.00')


@pytest.mark.integration
def test_choosing_does_not_rewrite_concepts(project, user):
    from apps.proyeccion.models import BudgetConcept
    dto = CreateOfferAlternativeDto(
        projectid=project.estimationprojectid, name='A', profitpercent=Decimal('10'),
        adjustments=[_adj(AdjustmentCostType.DIRECT, '-10000', months=3)])
    alt = OfferAlternativeService.create_alternative(dto, user)
    before = BudgetConcept.objects.get(projectid=project).directunitcost
    OfferAlternativeService.choose_alternative(alt.alternativeid, user)
    after = BudgetConcept.objects.get(projectid=project).directunitcost
    assert after == before == Decimal('2000000')


@pytest.mark.integration
def test_get_base_costs(project, user):
    base = OfferAlternativeService.get_base_costs(project.estimationprojectid)
    assert base['directcosttotal'] == Decimal('2000000.00')
    assert base['indirectcosttotal'] == Decimal('0.00')
