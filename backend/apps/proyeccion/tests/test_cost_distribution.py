import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.proyeccion.models import CostDistribution, CostLineType
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory, BudgetConceptFactory, UnitCostBreakdownFactory,
    IndirectCostDetailFactory,
)


@pytest.mark.django_db
@pytest.mark.unit
def test_cost_distribution_breakdown_create():
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project)
    breakdown = UnitCostBreakdownFactory(conceptid=concept)
    dist = CostDistribution.objects.create(
        projectid=project,
        linetype=CostLineType.BREAKDOWN,
        breakdownid=breakdown,
        periodnumber=1,
        fraction=Decimal("0.25"),
    )
    assert dist.distributionid is not None
    assert dist.isderived is True
    assert dist.version == 0


@pytest.mark.django_db
@pytest.mark.unit
def test_cost_distribution_exactly_one_fk_violation():
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project)
    breakdown = UnitCostBreakdownFactory(conceptid=concept)
    indirect = IndirectCostDetailFactory(projectid=project)
    with pytest.raises(IntegrityError):
        CostDistribution.objects.create(
            projectid=project,
            linetype=CostLineType.BREAKDOWN,
            breakdownid=breakdown,
            indirectcostid=indirect,  # violation: both set
            periodnumber=1,
            fraction=Decimal("0.25"),
        )


@pytest.mark.django_db
@pytest.mark.unit
def test_cost_distribution_fraction_out_of_range():
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project)
    breakdown = UnitCostBreakdownFactory(conceptid=concept)
    with pytest.raises(IntegrityError):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN, breakdownid=breakdown,
            periodnumber=1, fraction=Decimal("1.5"),  # > 1
        )


@pytest.mark.django_db
@pytest.mark.unit
def test_cost_distribution_unique_per_line_period():
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project)
    breakdown = UnitCostBreakdownFactory(conceptid=concept)
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN,
        breakdownid=breakdown, periodnumber=1, fraction=Decimal("0.5"),
    )
    with pytest.raises(IntegrityError):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=breakdown, periodnumber=1, fraction=Decimal("0.3"),
        )


from django.core.exceptions import ValidationError
from apps.proyeccion.models import IndirectCostDetail


@pytest.mark.django_db
@pytest.mark.unit
def test_indirect_cost_startmonth_endmonth_valid():
    project = EstimationProjectFactory(periodcount=24)
    detail = IndirectCostDetailFactory(projectid=project, startmonth=3, endmonth=10)
    detail.full_clean()  # should not raise
    assert detail.startmonth == 3
    assert detail.endmonth == 10


@pytest.mark.django_db
@pytest.mark.unit
def test_indirect_cost_startmonth_greater_than_endmonth_raises():
    project = EstimationProjectFactory(periodcount=24)
    detail = IndirectCostDetailFactory.build(projectid=project, startmonth=10, endmonth=3)
    with pytest.raises(ValidationError, match="startmonth"):
        detail.full_clean()


@pytest.mark.django_db
@pytest.mark.unit
def test_indirect_cost_endmonth_out_of_range():
    project = EstimationProjectFactory(periodcount=10)
    detail = IndirectCostDetailFactory.build(projectid=project, startmonth=1, endmonth=999)
    with pytest.raises(ValidationError, match="endmonth"):
        detail.full_clean()


from decimal import Decimal
from apps.proyeccion.services import CostDistributionService


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rollups_direct_sumproduct():
    """SUMPRODUCT across 2 breakdowns in 3 periods.

    Uses ``concept.quantity = 1`` so ``breakdown.amount`` reads as the
    project-level cost contribution. Multiplication by concept.quantity is
    covered by ``test_compute_rollups_scales_by_concept_quantity``.
    """
    project = EstimationProjectFactory(periodcount=3)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    bd1 = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
    bd2 = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("2000"))

    # bd1 distributed 0.3, 0.5, 0.2 across P1-P3
    for p, f in zip([1, 2, 3], [Decimal("0.3"), Decimal("0.5"), Decimal("0.2")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd1, periodnumber=p, fraction=f,
        )
    # bd2 distributed 0.1, 0.4, 0.5
    for p, f in zip([1, 2, 3], [Decimal("0.1"), Decimal("0.4"), Decimal("0.5")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd2, periodnumber=p, fraction=f,
        )

    rollups = CostDistributionService.compute_rollups(project)
    # direct_by_period[0] = 1000*0.3 + 2000*0.1 = 300 + 200 = 500
    # direct_by_period[1] = 1000*0.5 + 2000*0.4 = 500 + 800 = 1300
    # direct_by_period[2] = 1000*0.2 + 2000*0.5 = 200 + 1000 = 1200
    assert rollups['direct_by_period'] == [Decimal("500"), Decimal("1300"), Decimal("1200")]
    assert rollups['direct_total'] == Decimal("3000")


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rollups_with_chosen_alternative_retiros():
    from apps.proyeccion.models import OfferAlternative
    project = EstimationProjectFactory(periodcount=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
    for p, f in zip([1, 2], [Decimal("0.6"), Decimal("0.4")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=p, fraction=f,
        )
    # Stored as raw percentages (5 = 5%), matching OfferAlternativeService.
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name="Base",
        transversalpercent=Decimal("5"), profitpercent=Decimal("15"),
        ischosen=True,
    )

    rollups = CostDistributionService.compute_rollups(project)
    # direct_by_period = [600, 400]
    # retiro_by_period  = [600 * 5/100,  400 * 5/100]  = [30, 20]
    # utility_by_period = [600 * 15/100, 400 * 15/100] = [90, 60]
    assert rollups['retiro_by_period'] == [Decimal("30.00"), Decimal("20.00")]
    assert rollups['utility_by_period'] == [Decimal("90.00"), Decimal("60.00")]


@pytest.mark.django_db
@pytest.mark.unit
def test_retiro_distribution_manual_override_redistributes_keeping_total():
    """Manual utility rows re-time the retiro; the pinned total (=%xbase) is preserved
    when the fractions sum to 1. Transversal (untouched) stays cost-proportional."""
    from apps.proyeccion.models import OfferAlternative, RetiroDistribution, RetiroKind
    project = EstimationProjectFactory(periodcount=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
    for p, f in zip([1, 2], [Decimal("0.6"), Decimal("0.4")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=p, fraction=f,
        )
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name="Base",
        transversalpercent=Decimal("5"), profitpercent=Decimal("15"), ischosen=True,
    )
    # Move ALL utility to P1 (fractions sum to 1 -> total preserved).
    for p, f in zip([1, 2], [Decimal("1"), Decimal("0")]):
        RetiroDistribution.objects.create(
            projectid=project, kind=RetiroKind.UTILIDAD,
            periodnumber=p, fraction=f, isderived=False,
        )
    rollups = CostDistributionService.compute_rollups(project)
    # utility pinned_total = 15% x 1000 = 150 -> all in P1
    assert rollups['utility_by_period'] == [Decimal("150.00"), Decimal("0.00")]
    assert sum(rollups['utility_by_period']) == Decimal("150.00")  # total preserved
    # transversal untouched -> legacy cost-proportional
    assert rollups['retiro_by_period'] == [Decimal("30.00"), Decimal("20.00")]


@pytest.mark.django_db
@pytest.mark.unit
def test_retiro_distribution_partial_override_falls_back_to_derived():
    """A period without a manual row keeps its derived (cost-proportional) share; the
    distributed total may then drift from the pinned total (surfaced by the checksum)."""
    from apps.proyeccion.models import OfferAlternative, RetiroDistribution, RetiroKind
    project = EstimationProjectFactory(periodcount=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
    for p, f in zip([1, 2], [Decimal("0.6"), Decimal("0.4")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=p, fraction=f,
        )
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name="Base",
        transversalpercent=Decimal("5"), profitpercent=Decimal("15"), ischosen=True,
    )
    # Only P1 overridden (0.5); P2 has no row -> derived share 0.4.
    RetiroDistribution.objects.create(
        projectid=project, kind=RetiroKind.UTILIDAD,
        periodnumber=1, fraction=Decimal("0.5"), isderived=False,
    )
    rollups = CostDistributionService.compute_rollups(project)
    # pinned_total = 150 -> P1 = 150*0.5 = 75 ; P2 = 150*0.4 (derived) = 60
    assert rollups['utility_by_period'] == [Decimal("75.00"), Decimal("60.00")]


def _setup_retiro_project():
    """project(periodcount=2) with 1 breakdown of 1000 distributed [0.6,0.4] and a chosen
    alternative transv=5% / profit=15% -> base=[600,400], pinned util=150, transv=50."""
    from apps.proyeccion.models import OfferAlternative
    project = EstimationProjectFactory(periodcount=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
    for p, f in zip([1, 2], [Decimal("0.6"), Decimal("0.4")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=p, fraction=f,
        )
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name="Base",
        transversalpercent=Decimal("5"), profitpercent=Decimal("15"), ischosen=True,
    )
    return project


@pytest.mark.django_db
@pytest.mark.unit
def test_apply_bulk_edits_retiro_cell_creates_rows_and_redistributes():
    from apps.proyeccion.models import RetiroDistribution, RetiroKind
    from apps.users.tests.factories import SystemUserFactory
    user = SystemUserFactory()
    project = _setup_retiro_project()

    result = CostDistributionService.apply_bulk_edits(project, user=user, edits=[
        {'lineid': None, 'linetype': 'RETIRO_UTILIDAD', 'periodnumber': 1,
         'fraction': Decimal("1"), 'expected_version': 0},
        {'lineid': None, 'linetype': 'RETIRO_UTILIDAD', 'periodnumber': 2,
         'fraction': Decimal("0"), 'expected_version': 0},
    ])
    assert result['updated'] == 2
    assert result['new_versions']['RETIRO_UTILIDAD:1'] == 1
    assert RetiroDistribution.objects.filter(
        projectid=project, kind=RetiroKind.UTILIDAD, isderived=False).count() == 2
    rollups = CostDistributionService.compute_rollups(project)
    assert rollups['utility_by_period'] == [Decimal("150.00"), Decimal("0.00")]


@pytest.mark.django_db
@pytest.mark.unit
def test_reset_line_retiro_returns_to_derived():
    from apps.proyeccion.models import RetiroDistribution, RetiroKind
    project = _setup_retiro_project()
    for p, f in zip([1, 2], [Decimal("1"), Decimal("0")]):
        RetiroDistribution.objects.create(
            projectid=project, kind=RetiroKind.UTILIDAD,
            periodnumber=p, fraction=f, isderived=False,
        )
    result = CostDistributionService.reset_line(project, lineid=None, linetype='RETIRO_UTILIDAD')
    assert result['reset'] is True
    assert RetiroDistribution.objects.filter(projectid=project, kind=RetiroKind.UTILIDAD).count() == 0
    rollups = CostDistributionService.compute_rollups(project)
    assert rollups['utility_by_period'] == [Decimal("90.00"), Decimal("60.00")]  # derived


@pytest.mark.django_db
@pytest.mark.unit
def test_build_payload_includes_retiro_rows():
    project = _setup_retiro_project()
    payload = CostDistributionService.build_payload(project)
    retiros = {r['kind']: r for r in payload['retiros']}
    assert set(retiros) == {'RETIRO_TRANSVERSAL', 'RETIRO_UTILIDAD'}
    util = retiros['RETIRO_UTILIDAD']
    assert util['pinned_total'] == 150.0   # 15% x 1000
    assert util['percent'] == 15.0
    assert len(util['cells']) == 2
    assert util['cells'][0]['isderived'] is True
    assert util['cells'][0]['amount'] == 90.0   # 150 x 0.6
    assert util['cells'][1]['amount'] == 60.0   # 150 x 0.4
    transv = retiros['RETIRO_TRANSVERSAL']
    assert transv['pinned_total'] == 50.0       # 5% x 1000


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rollups_sale_is_live_and_scaled_to_chosen_salepricenet():
    """'Venta Plan' must reflect the chosen alternative's salepricenet (incl.
    transversal), distributed by the work-plan timing computed LIVE from
    distributedquantity × current unitprice -- never the stale stored
    distributedamount snapshot."""
    from apps.proyeccion.models import OfferAlternative, WorkPlanEntry, WorkPlanEntryType
    project = EstimationProjectFactory(periodcount=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("10"), unitprice=Decimal("100"))
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name="Base", ischosen=True,
        salepricenet=Decimal("2000"), transversalpercent=Decimal("0"), profitpercent=Decimal("0"),
    )
    # Stored distributedamount is STALE (snapshot from when unitprice == directcost).
    WorkPlanEntry.objects.create(
        projectid=project, conceptid=concept, periodnumber=1, periodlabel="P1",
        entrytype=WorkPlanEntryType.PLANNED,
        distributedquantity=Decimal("4"), distributedamount=Decimal("999"),
    )
    WorkPlanEntry.objects.create(
        projectid=project, conceptid=concept, periodnumber=2, periodlabel="P2",
        entrytype=WorkPlanEntryType.PLANNED,
        distributedquantity=Decimal("6"), distributedamount=Decimal("999"),
    )

    rollups = CostDistributionService.compute_rollups(project)
    # live shape: p1 = 4×100 = 400, p2 = 6×100 = 600 (total 1000)
    # scaled to salepricenet 2000 -> factor 2 -> [800, 1200]
    assert rollups['sale_total'] == Decimal("2000")
    assert rollups['sale_by_period'] == [Decimal("800"), Decimal("1200")]


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rollups_sale_live_without_chosen_alternative():
    """No chosen alternative -> Venta Plan = live concept venta (distributedquantity
    × current unitprice), still not the stale stored amount."""
    from apps.proyeccion.models import WorkPlanEntry, WorkPlanEntryType
    project = EstimationProjectFactory(periodcount=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("10"), unitprice=Decimal("100"))
    WorkPlanEntry.objects.create(
        projectid=project, conceptid=concept, periodnumber=1, periodlabel="P1",
        entrytype=WorkPlanEntryType.PLANNED,
        distributedquantity=Decimal("4"), distributedamount=Decimal("999"),
    )
    rollups = CostDistributionService.compute_rollups(project)
    assert rollups['sale_by_period'][0] == Decimal("400")
    assert rollups['sale_total'] == Decimal("400")


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rollups_excludes_soft_deleted_cost_lines():
    """Soft-deleted (statecode=1) breakdown and indirect lines must NOT inflate
    the distributed cost. Same bug class as the indirect-cost list: compute_rollups
    queried these models without filtering statecode."""
    project = EstimationProjectFactory(periodcount=1)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    bd_active = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"), statecode=0)
    bd_deleted = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("500"), statecode=1)
    for bd in (bd_active, bd_deleted):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=1, fraction=Decimal("1"),
        )
    ind_active = IndirectCostDetailFactory(projectid=project, amount=Decimal("100"), statecode=0)
    ind_deleted = IndirectCostDetailFactory(projectid=project, amount=Decimal("50"), statecode=1)
    for ind in (ind_active, ind_deleted):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.INDIRECT,
            indirectcostid=ind, periodnumber=1, fraction=Decimal("1"),
        )

    rollups = CostDistributionService.compute_rollups(project)
    assert rollups['direct_total'] == Decimal("1000")   # not 1500 (excludes soft-deleted 500)
    assert rollups['indirect_total'] == Decimal("100")  # not 150 (excludes soft-deleted 50)


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rollups_scales_by_concept_quantity():
    """``UnitCostBreakdown.amount`` is per-unit-of-concept (Σ quantity × unitprice
    × yieldvalue of an APU ingredient line). The project-level cost a breakdown
    contributes is ``amount × concept.quantity`` — same scale used by
    ``OfferAlternativeService.regenerate_alternatives``. ``compute_rollups``
    must apply this multiplication so the PNT rollups match the alternative
    totals that drive retiros and the financial summary.
    """
    project = EstimationProjectFactory(periodcount=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("200"))
    # Per-unit cost = $50 → project-level cost = 200 × $50 = $10,000.
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("50"))
    for p, f in zip([1, 2], [Decimal("0.4"), Decimal("0.6")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=p, fraction=f,
        )

    rollups = CostDistributionService.compute_rollups(project)
    # P1: 0.4 × 10,000 = 4,000;  P2: 0.6 × 10,000 = 6,000.
    assert rollups['direct_by_period'] == [Decimal("4000.0"), Decimal("6000.0")]
    assert rollups['direct_total'] == Decimal("10000.0")


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rollups_empty_project():
    project = EstimationProjectFactory(periodcount=3)
    rollups = CostDistributionService.compute_rollups(project)
    assert rollups['direct_by_period'] == [Decimal("0")] * 3
    assert rollups['indirect_by_period'] == [Decimal("0")] * 3
    assert rollups['total_cost_by_period'] == [Decimal("0")] * 3


@pytest.mark.django_db
@pytest.mark.unit
def test_autofill_uniform_distributes_1_over_N():
    from apps.proyeccion.tests.factories import ProjectionPeriodFactory
    project = EstimationProjectFactory(periodcount=4)
    # Seed periods
    for i in range(1, 5):
        ProjectionPeriodFactory(projectid=project, periodnumber=i)
    concept = BudgetConceptFactory(projectid=project)
    bd = UnitCostBreakdownFactory(conceptid=concept)

    result = CostDistributionService.autofill(
        project, strategy='uniform', only_empty=False, scope='all',
    )

    dists = CostDistribution.objects.filter(breakdownid=bd).order_by('periodnumber')
    assert dists.count() == 4
    for d in dists:
        assert d.fraction == Decimal("0.25")
        assert d.isderived is True


@pytest.mark.django_db
@pytest.mark.unit
def test_autofill_only_empty_preserves_manual_edits():
    from apps.proyeccion.tests.factories import ProjectionPeriodFactory
    project = EstimationProjectFactory(periodcount=3)
    for i in range(1, 4):
        ProjectionPeriodFactory(projectid=project, periodnumber=i)
    concept = BudgetConceptFactory(projectid=project)
    bd = UnitCostBreakdownFactory(conceptid=concept)

    # Manual edit in P2
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN,
        breakdownid=bd, periodnumber=2, fraction=Decimal("0.8"), isderived=False,
    )

    result = CostDistributionService.autofill(
        project, strategy='uniform', only_empty=True, scope='all',
    )

    p2 = CostDistribution.objects.get(breakdownid=bd, periodnumber=2)
    assert p2.fraction == Decimal("0.8")  # preserved
    assert p2.isderived is False

    # P1 and P3 got derived values (uniform 0.333)
    p1 = CostDistribution.objects.get(breakdownid=bd, periodnumber=1)
    assert p1.isderived is True


@pytest.mark.django_db
@pytest.mark.unit
def test_autofill_indirect_uses_startmonth_endmonth():
    from apps.proyeccion.tests.factories import ProjectionPeriodFactory
    project = EstimationProjectFactory(periodcount=6)
    for i in range(1, 7):
        ProjectionPeriodFactory(projectid=project, periodnumber=i)
    ind = IndirectCostDetailFactory(
        projectid=project, startmonth=3, endmonth=5,
    )

    CostDistributionService.autofill(
        project, strategy='uniform', only_empty=False, scope='indirect_only',
    )

    # P1, P2: 0;  P3, P4, P5: 1/3;  P6: 0
    dists = {d.periodnumber: d.fraction for d in CostDistribution.objects.filter(indirectcostid=ind)}
    assert dists[1] == Decimal("0")
    assert dists[2] == Decimal("0")
    assert abs(dists[3] - Decimal("0.33333333")) < Decimal("0.00001")
    assert abs(dists[5] - Decimal("0.33333333")) < Decimal("0.00001")
    assert dists[6] == Decimal("0")


@pytest.mark.django_db
@pytest.mark.unit
def test_autofill_proportional_workplan():
    from apps.proyeccion.models import WorkPlanEntry, WorkPlanEntryType
    from apps.proyeccion.tests.factories import ProjectionPeriodFactory
    project = EstimationProjectFactory(periodcount=3)
    for i in range(1, 4):
        ProjectionPeriodFactory(projectid=project, periodnumber=i)
    concept = BudgetConceptFactory(projectid=project, totalamount=Decimal("10000"))
    bd = UnitCostBreakdownFactory(conceptid=concept)

    # Workplan distributes concept 20%, 50%, 30%
    for p, amt in zip([1, 2, 3], [Decimal("2000"), Decimal("5000"), Decimal("3000")]):
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project,
            periodnumber=p, periodlabel=f"P{p}",
            entrytype=WorkPlanEntryType.PLANNED,
            distributedamount=amt,
        )

    CostDistributionService.autofill(
        project, strategy='proportional_workplan', only_empty=False, scope='all',
    )

    dists = {d.periodnumber: d.fraction for d in CostDistribution.objects.filter(breakdownid=bd)}
    assert dists[1] == Decimal("0.2")
    assert dists[2] == Decimal("0.5")
    assert dists[3] == Decimal("0.3")


@pytest.mark.django_db
@pytest.mark.unit
def test_reset_line_clears_manual_edits_and_regenerates():
    from apps.proyeccion.tests.factories import ProjectionPeriodFactory
    project = EstimationProjectFactory(periodcount=3)
    for i in range(1, 4):
        ProjectionPeriodFactory(projectid=project, periodnumber=i)
    concept = BudgetConceptFactory(projectid=project)
    bd = UnitCostBreakdownFactory(conceptid=concept)

    # Simulate user edits
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN,
        breakdownid=bd, periodnumber=1, fraction=Decimal("0.9"), isderived=False,
    )

    CostDistributionService.reset_line(project, lineid=str(bd.breakdownid), linetype='BREAKDOWN')
    dists = list(CostDistribution.objects.filter(breakdownid=bd).order_by('periodnumber'))
    assert len(dists) == 3
    for d in dists:
        assert d.fraction == Decimal("0.33333333")  # uniform fallback (no workplan)
        assert d.isderived is True


@pytest.mark.unit
@pytest.mark.django_db
def test_compute_rollups_emits_by_line_and_lag_by_line():
    """compute_rollups returns direct_by_period_by_line, indirect_by_period_by_line,
    and lag_by_line in addition to existing aggregate vectors."""
    from apps.proyeccion.services import CostDistributionService
    from apps.proyeccion.tests.factories import (
        EstimationProjectFactory, ProjectionPeriodFactory,
        BudgetConceptFactory, UnitCostBreakdownFactory, IndirectCostDetailFactory,
    )
    from apps.proyeccion.models import CostLineType, CostDistribution
    from decimal import Decimal

    project = EstimationProjectFactory(periodcount=2)
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    ProjectionPeriodFactory(projectid=project, periodnumber=2)

    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    breakdown = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal('1000.00'), paymentlagperiods=2)
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN,
        breakdownid=breakdown, periodnumber=1, fraction=Decimal('1.0'),
    )

    indirect = IndirectCostDetailFactory(projectid=project, amount=Decimal('500.00'))
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.INDIRECT,
        indirectcostid=indirect, periodnumber=1, fraction=Decimal('1.0'),
    )

    rollups = CostDistributionService.compute_rollups(project)

    # Existing aggregate vectors still present
    assert 'direct_by_period' in rollups
    assert 'indirect_by_period' in rollups

    # New per-line dicts present
    assert 'direct_by_period_by_line' in rollups
    assert 'indirect_by_period_by_line' in rollups
    assert 'lag_by_line' in rollups

    # Per-line vectors keyed by string UUID
    direct_by_line = rollups['direct_by_period_by_line']
    indirect_by_line = rollups['indirect_by_period_by_line']
    assert str(breakdown.breakdownid) in direct_by_line
    assert str(indirect.indirectcostid) in indirect_by_line

    # Vector lengths == number of periods (2)
    assert len(direct_by_line[str(breakdown.breakdownid)]) == 2
    assert direct_by_line[str(breakdown.breakdownid)][0] == Decimal('1000.00')

    # lag_by_line: breakdown has 2, indirect has None
    lag_by_line = rollups['lag_by_line']
    assert lag_by_line[str(breakdown.breakdownid)] == 2
    assert lag_by_line[str(indirect.indirectcostid)] is None


@pytest.mark.django_db
@pytest.mark.unit
def test_build_payload_excludes_soft_deleted_lines():
    """Las líneas soft-deleted (statecode=1) no deben aparecer como filas en el
    payload de Distribución Temporal — misma clase de bug que compute_rollups:
    el CDU las filtra pero _build_families_hierarchy las seguía listando
    (visto en prod: 'DIESEL EXCAVADORA 366D' en EST-2026-004)."""
    from apps.proyeccion.tests.factories import ProjectionPeriodFactory
    project = EstimationProjectFactory(periodcount=1)
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    UnitCostBreakdownFactory(conceptid=concept, description="LINEA VIVA", statecode=0)
    UnitCostBreakdownFactory(conceptid=concept, description="LINEA FANTASMA", statecode=1)
    IndirectCostDetailFactory(projectid=project, description="IND VIVA", statecode=0)
    IndirectCostDetailFactory(projectid=project, description="IND FANTASMA", statecode=1)

    payload = CostDistributionService.build_payload(project)
    descs = [line['description'] for fam in payload['families'] for line in fam['lines']]
    assert "LINEA VIVA" in descs
    assert "IND VIVA" in descs
    assert "LINEA FANTASMA" not in descs
    assert "IND FANTASMA" not in descs


@pytest.mark.django_db
@pytest.mark.unit
def test_autofill_skips_soft_deleted_lines():
    """Autofill no debe crear celdas de distribución para líneas soft-deleted."""
    from apps.proyeccion.tests.factories import ProjectionPeriodFactory
    project = EstimationProjectFactory(periodcount=2)
    for i in (1, 2):
        ProjectionPeriodFactory(projectid=project, periodnumber=i)
    concept = BudgetConceptFactory(projectid=project)
    bd_deleted = UnitCostBreakdownFactory(conceptid=concept, statecode=1)
    ind_deleted = IndirectCostDetailFactory(projectid=project, statecode=1)

    CostDistributionService.autofill(
        project, strategy='uniform', only_empty=False, scope='all',
    )

    assert CostDistribution.objects.filter(breakdownid=bd_deleted).count() == 0
    assert CostDistribution.objects.filter(indirectcostid=ind_deleted).count() == 0


@pytest.mark.unit
@pytest.mark.django_db
def test_compute_rollups_no_longer_emits_by_category():
    """The old direct_by_period_by_category / indirect_by_period_by_category keys are gone."""
    from apps.proyeccion.services import CostDistributionService
    from apps.proyeccion.tests.factories import EstimationProjectFactory, ProjectionPeriodFactory
    project = EstimationProjectFactory()
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    rollups = CostDistributionService.compute_rollups(project)
    assert 'direct_by_period_by_category' not in rollups
    assert 'indirect_by_period_by_category' not in rollups


from core.exceptions import NotFound
from apps.proyeccion.models import WorkPlanEntry, WorkPlanEntryType
from apps.proyeccion.tests.factories import ProjectionPeriodFactory


@pytest.mark.django_db
@pytest.mark.unit
class TestPreviewLineFractions:
    @pytest.fixture
    def project_with_workplan_breakdown(self):
        """Project with N=3 periods, one breakdown whose concept has PLANNED
        WorkPlanEntry rows concentrated 20%/50%/30% across the periods."""
        project = EstimationProjectFactory(periodcount=3)
        for i in range(1, 4):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        concept = BudgetConceptFactory(projectid=project, totalamount=Decimal("10000"))
        bd = UnitCostBreakdownFactory(conceptid=concept)
        for p, amt in zip([1, 2, 3], [Decimal("2000"), Decimal("5000"), Decimal("3000")]):
            WorkPlanEntry.objects.create(
                conceptid=concept, projectid=project,
                periodnumber=p, periodlabel=f"P{p}",
                entrytype=WorkPlanEntryType.PLANNED,
                distributedamount=amt,
            )
        return project, bd

    @pytest.fixture
    def project_with_breakdown_no_workplan(self):
        """Project with N=4 periods, one breakdown with NO WorkPlanEntry rows."""
        project = EstimationProjectFactory(periodcount=4)
        for i in range(1, 5):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        concept = BudgetConceptFactory(projectid=project)
        bd = UnitCostBreakdownFactory(conceptid=concept)
        return project, bd

    @pytest.fixture
    def project_with_ranged_indirect(self):
        """Project with N=4 periods, one indirect with startmonth=2, endmonth=3."""
        project = EstimationProjectFactory(periodcount=4)
        for i in range(1, 5):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        ind = IndirectCostDetailFactory(projectid=project, startmonth=2, endmonth=3)
        return project, ind

    @pytest.fixture
    def project_no_periods(self):
        return EstimationProjectFactory(periodcount=0)

    def test_breakdown_proportional_to_workplan_sums_to_one(self, project_with_workplan_breakdown):
        project, bd = project_with_workplan_breakdown
        result = CostDistributionService.preview_line_fractions(
            project, lineid=str(bd.breakdownid), linetype='BREAKDOWN',
        )
        assert len(result['fractions']) == project.periodcount
        assert sum(result['fractions']) == pytest.approx(Decimal('1'), abs=Decimal('0.0001'))
        assert result['warnings'] == []  # has a workplan → no fallback

    def test_breakdown_without_workplan_falls_back_uniform_with_warning(self, project_with_breakdown_no_workplan):
        project, bd = project_with_breakdown_no_workplan
        N = project.periodcount
        result = CostDistributionService.preview_line_fractions(
            project, lineid=str(bd.breakdownid), linetype='BREAKDOWN',
        )
        assert result['fractions'] == [Decimal(1) / Decimal(N)] * N
        assert any('no workplan' in w for w in result['warnings'])

    def test_indirect_uniform_within_range(self, project_with_ranged_indirect):
        project, ind = project_with_ranged_indirect
        result = CostDistributionService.preview_line_fractions(
            project, lineid=str(ind.indirectcostid), linetype='INDIRECT',
        )
        assert result['fractions'] == [Decimal(0), Decimal('0.5'), Decimal('0.5'), Decimal(0)]

    def test_unknown_line_raises_not_found(self, project_with_workplan_breakdown):
        project, _bd = project_with_workplan_breakdown
        with pytest.raises(NotFound):
            CostDistributionService.preview_line_fractions(
                project, lineid='00000000-0000-0000-0000-000000000000', linetype='BREAKDOWN',
            )

    def test_no_periods_raises_value_error(self, project_no_periods):
        with pytest.raises(ValueError):
            CostDistributionService.preview_line_fractions(
                project_no_periods, lineid='00000000-0000-0000-0000-000000000000', linetype='INDIRECT',
            )
