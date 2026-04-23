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
    """SUMPRODUCT across 2 breakdowns in 3 periods."""
    project = EstimationProjectFactory(periodcount=3)
    concept = BudgetConceptFactory(projectid=project)
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
    concept = BudgetConceptFactory(projectid=project)
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
    for p, f in zip([1, 2], [Decimal("0.6"), Decimal("0.4")]):
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=p, fraction=f,
        )
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name="Base",
        transversalpercent=Decimal("0.05"), profitpercent=Decimal("0.15"),
        ischosen=True,
    )

    rollups = CostDistributionService.compute_rollups(project)
    # direct_by_period = [600, 400]
    # retiro_by_period = [600*0.05, 400*0.05] = [30, 20]
    # utility_by_period = [600*0.15, 400*0.15] = [90, 60]
    assert rollups['retiro_by_period'] == [Decimal("30.00"), Decimal("20.00")]
    assert rollups['utility_by_period'] == [Decimal("90.00"), Decimal("60.00")]


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
