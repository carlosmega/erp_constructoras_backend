import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command
from apps.proyeccion.models import DistributionPresence
from apps.proyeccion.tests.factories import EstimationProjectFactory
from apps.users.tests.factories import SystemUserFactory


@pytest.mark.django_db
@pytest.mark.unit
def test_distribution_presence_upsert():
    project = EstimationProjectFactory()
    user = SystemUserFactory()
    p = DistributionPresence.objects.create(
        projectid=project, userid=user, mode='viewing',
    )
    assert p.presenceid is not None


@pytest.mark.django_db
@pytest.mark.unit
def test_distribution_presence_unique_per_user_project():
    project = EstimationProjectFactory()
    user = SystemUserFactory()
    DistributionPresence.objects.create(projectid=project, userid=user, mode='viewing')
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        DistributionPresence.objects.create(projectid=project, userid=user, mode='editing')


@pytest.mark.django_db
@pytest.mark.unit
def test_cleanup_presence_command_removes_zombies():
    project = EstimationProjectFactory()
    user_fresh = SystemUserFactory()
    user_zombie = SystemUserFactory()

    fresh = DistributionPresence.objects.create(projectid=project, userid=user_fresh, mode='viewing')
    zombie = DistributionPresence.objects.create(projectid=project, userid=user_zombie, mode='viewing')
    # Artificially age the zombie (bypass auto_now)
    DistributionPresence.objects.filter(pk=zombie.pk).update(
        last_seen=timezone.now() - timedelta(days=8)
    )

    call_command('cleanup_presence')
    assert DistributionPresence.objects.filter(pk=fresh.pk).exists()
    assert not DistributionPresence.objects.filter(pk=zombie.pk).exists()


from decimal import Decimal
from apps.proyeccion.models import CostDistribution, CostLineType
from apps.proyeccion.services import CostDistributionService, VersionConflict
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory, BudgetConceptFactory, UnitCostBreakdownFactory,
    ProjectionPeriodFactory, IndirectCostDetailFactory, CostDistributionFactory,
)


@pytest.mark.django_db
@pytest.mark.unit
def test_bulk_edits_success_increments_version():
    project = EstimationProjectFactory(periodcount=3)
    concept = BudgetConceptFactory(projectid=project)
    bd = UnitCostBreakdownFactory(conceptid=concept)
    dist = CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN,
        breakdownid=bd, periodnumber=1, fraction=Decimal("0.3"),
    )
    assert dist.version == 0

    user = SystemUserFactory()
    result = CostDistributionService.apply_bulk_edits(project, user=user, edits=[{
        'lineid': str(bd.breakdownid), 'linetype': 'BREAKDOWN',
        'periodnumber': 1, 'fraction': Decimal("0.5"), 'expected_version': 0,
    }])
    dist.refresh_from_db()
    assert dist.fraction == Decimal("0.5")
    assert dist.version == 1
    assert dist.isderived is False
    assert dist.modifiedby == user


@pytest.mark.django_db
@pytest.mark.unit
def test_bulk_edits_conflict_aborts_all():
    project = EstimationProjectFactory(periodcount=3)
    concept = BudgetConceptFactory(projectid=project)
    bd = UnitCostBreakdownFactory(conceptid=concept)
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN, breakdownid=bd,
        periodnumber=1, fraction=Decimal("0.3"), version=5,
    )
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN, breakdownid=bd,
        periodnumber=2, fraction=Decimal("0.7"), version=3,
    )

    user = SystemUserFactory()
    with pytest.raises(VersionConflict) as exc:
        CostDistributionService.apply_bulk_edits(project, user=user, edits=[
            {'lineid': str(bd.breakdownid), 'linetype': 'BREAKDOWN',
             'periodnumber': 1, 'fraction': Decimal("0.4"), 'expected_version': 5},
            {'lineid': str(bd.breakdownid), 'linetype': 'BREAKDOWN',
             'periodnumber': 2, 'fraction': Decimal("0.6"), 'expected_version': 2},  # STALE
        ])
    assert len(exc.value.conflicts) == 1
    assert exc.value.conflicts[0]['periodnumber'] == 2

    # Verify P1 was NOT saved (atomic abort)
    p1 = CostDistribution.objects.get(breakdownid=bd, periodnumber=1)
    assert p1.fraction == Decimal("0.3")
    assert p1.version == 5


from apps.proyeccion.services import PresenceService
from datetime import timedelta
from django.utils import timezone


@pytest.mark.django_db
@pytest.mark.unit
def test_presence_heartbeat_upsert():
    project = EstimationProjectFactory()
    user = SystemUserFactory()
    PresenceService.heartbeat(project, user, mode='viewing')
    p = DistributionPresence.objects.get(projectid=project, userid=user)
    assert p.mode == 'viewing'
    # Second heartbeat updates mode
    PresenceService.heartbeat(project, user, mode='editing')
    p.refresh_from_db()
    assert p.mode == 'editing'


@pytest.mark.django_db
@pytest.mark.unit
def test_presence_list_excludes_stale_over_2min():
    project = EstimationProjectFactory()
    u_fresh = SystemUserFactory()
    u_stale = SystemUserFactory()
    DistributionPresence.objects.create(projectid=project, userid=u_fresh, mode='viewing')
    stale = DistributionPresence.objects.create(projectid=project, userid=u_stale, mode='viewing')
    DistributionPresence.objects.filter(pk=stale.pk).update(
        last_seen=timezone.now() - timedelta(minutes=5)
    )

    active = PresenceService.list_active(project)
    assert len(active) == 1
    assert active[0].userid == u_fresh


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_bulk_edits_persists_lag_on_breakdown():
    """A lag_edit with valid expected_lineversion updates the line and bumps lineversion."""
    project = EstimationProjectFactory()
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    concept = BudgetConceptFactory(projectid=project)
    line = UnitCostBreakdownFactory(conceptid=concept, paymentlagperiods=None, lineversion=0)
    user = SystemUserFactory()

    result = CostDistributionService.apply_bulk_edits(
        project, user=user,
        edits=[],
        lag_edits=[{
            'lineid': str(line.breakdownid),
            'linetype': 'BREAKDOWN',
            'paymentlagperiods': 3,
            'expected_lineversion': 0,
        }],
    )
    line.refresh_from_db()
    assert line.paymentlagperiods == 3
    assert line.lineversion == 1
    assert result['lag_updated'] == 1
    assert result['new_lineversions'] == {str(line.breakdownid): 1}


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_bulk_edits_lag_version_conflict():
    """If expected_lineversion mismatches, raises VersionConflict and does NOT mutate."""
    project = EstimationProjectFactory()
    line = IndirectCostDetailFactory(projectid=project, paymentlagperiods=2, lineversion=5)
    user = SystemUserFactory()
    with pytest.raises(VersionConflict) as exc:
        CostDistributionService.apply_bulk_edits(
            project, user=user, edits=[],
            lag_edits=[{
                'lineid': str(line.indirectcostid),
                'linetype': 'INDIRECT',
                'paymentlagperiods': 7,
                'expected_lineversion': 4,   # actual is 5
            }],
        )
    line.refresh_from_db()
    assert line.paymentlagperiods == 2
    assert line.lineversion == 5
    assert any(c.get('lineid') == str(line.indirectcostid) for c in exc.value.conflicts)


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_bulk_edits_lag_clear_to_null():
    """paymentlagperiods=None clears the override (back to global)."""
    project = EstimationProjectFactory()
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    concept = BudgetConceptFactory(projectid=project)
    line = UnitCostBreakdownFactory(conceptid=concept, paymentlagperiods=4, lineversion=2)
    user = SystemUserFactory()
    CostDistributionService.apply_bulk_edits(
        project, user=user, edits=[],
        lag_edits=[{
            'lineid': str(line.breakdownid),
            'linetype': 'BREAKDOWN',
            'paymentlagperiods': None,
            'expected_lineversion': 2,
        }],
    )
    line.refresh_from_db()
    assert line.paymentlagperiods is None
    assert line.lineversion == 3


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_bulk_edits_atomic_with_cell_and_lag():
    """If a cell conflict and a lag edit are submitted together, neither is applied."""
    project = EstimationProjectFactory()
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    concept = BudgetConceptFactory(projectid=project)
    line = UnitCostBreakdownFactory(conceptid=concept, paymentlagperiods=None, lineversion=0)
    cell = CostDistributionFactory(
        projectid=project, breakdownid=line,
        linetype=CostLineType.BREAKDOWN, periodnumber=1, fraction=Decimal('0.50'),
    )
    cell.version = 5
    cell.save()
    user = SystemUserFactory()
    with pytest.raises(VersionConflict):
        CostDistributionService.apply_bulk_edits(
            project, user=user,
            edits=[{
                'lineid': str(line.breakdownid), 'linetype': 'BREAKDOWN',
                'periodnumber': 1, 'fraction': Decimal('0.75'),
                'expected_version': 4,   # mismatch — actual is 5
            }],
            lag_edits=[{
                'lineid': str(line.breakdownid), 'linetype': 'BREAKDOWN',
                'paymentlagperiods': 2, 'expected_lineversion': 0,
            }],
        )
    line.refresh_from_db()
    cell.refresh_from_db()
    assert line.paymentlagperiods is None
    assert line.lineversion == 0
    assert cell.fraction == Decimal('0.50000000')
