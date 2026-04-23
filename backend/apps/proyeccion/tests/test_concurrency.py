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
    ProjectionPeriodFactory,
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
