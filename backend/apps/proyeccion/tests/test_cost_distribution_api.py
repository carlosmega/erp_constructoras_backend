"""Contract tests for distribution API endpoints."""
from datetime import date
import pytest
from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.django_db
@pytest.mark.contract
class TestListProjectionPeriods:
    def test_returns_empty_initially(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/projection-periods/'
        )
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.django_db
@pytest.mark.contract
class TestRegenerateProjectionPeriods:
    def test_creates_rows_when_dates_set(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            estimatedstartdate=date(2026, 1, 1),
            estimatedenddate=date(2026, 2, 28),
            periodtype=1,  # fortnightly
        )
        r = admin_auth_client.post(
            f'/api/proyeccion/projects/{project.estimationprojectid}/projection-periods/regenerate/'
        )
        assert r.status_code == 200
        body = r.json()
        assert body['created'] >= 3

        # GET now returns the created periods
        r2 = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/projection-periods/'
        )
        assert r2.status_code == 200
        assert len(r2.json()) == body['created']

    def test_returns_400_without_dates(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            estimatedstartdate=None, estimatedenddate=None,
        )
        r = admin_auth_client.post(
            f'/api/proyeccion/projects/{project.estimationprojectid}/projection-periods/regenerate/'
        )
        assert r.status_code == 400


from decimal import Decimal
from apps.proyeccion.models import CostDistribution, CostLineType
from apps.proyeccion.tests.factories import (
    BudgetConceptFactory, UnitCostBreakdownFactory, ProjectionPeriodFactory,
)


@pytest.mark.django_db
@pytest.mark.contract
class TestGetCostDistribution:
    def test_payload_shape(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            periodcount=2,
        )
        for i in range(1, 3):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
        bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=1, fraction=Decimal("0.4"),
        )

        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/'
        )
        assert r.status_code == 200
        body = r.json()
        assert 'periods' in body
        assert 'families' in body
        assert 'rollups' in body
        assert 'totals' in body
        assert len(body['periods']) == 2
        # direct_by_period[0] = 1000 * 0.4 = 400
        assert float(body['rollups']['direct_by_period'][0]) == pytest.approx(400.0)


@pytest.mark.django_db
@pytest.mark.contract
class TestPatchBulkEdits:
    def test_success_returns_200(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            periodcount=2,
        )
        for i in range(1, 3):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        concept = BudgetConceptFactory(projectid=project)
        bd = UnitCostBreakdownFactory(conceptid=concept)

        r = admin_auth_client.patch(
            f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/bulk/',
            data={'edits': [{
                'lineid': str(bd.breakdownid), 'linetype': 'BREAKDOWN',
                'periodnumber': 1, 'fraction': '0.6', 'expected_version': 0,
            }]},
            content_type='application/json',
        )
        assert r.status_code == 200
        body = r.json()
        assert body['updated'] == 1

    def test_version_conflict_returns_409(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            periodcount=2,
        )
        for i in range(1, 3):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        concept = BudgetConceptFactory(projectid=project)
        bd = UnitCostBreakdownFactory(conceptid=concept)
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN,
            breakdownid=bd, periodnumber=1, fraction=Decimal("0.3"), version=5,
        )

        r = admin_auth_client.patch(
            f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/bulk/',
            data={'edits': [{
                'lineid': str(bd.breakdownid), 'linetype': 'BREAKDOWN',
                'periodnumber': 1, 'fraction': '0.5', 'expected_version': 3,
            }]},
            content_type='application/json',
        )
        assert r.status_code == 409
        assert r.json()['error'] == 'version_conflict'


@pytest.mark.django_db
@pytest.mark.contract
class TestAutofill:
    def test_uniform_creates_cells(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            periodcount=4,
        )
        for i in range(1, 5):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        concept = BudgetConceptFactory(projectid=project)
        UnitCostBreakdownFactory(conceptid=concept)

        r = admin_auth_client.post(
            f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/autofill/',
            data={'strategy': 'uniform', 'only_empty': False, 'scope': 'all'},
            content_type='application/json',
        )
        assert r.status_code == 200
        body = r.json()
        assert body['lines_affected'] >= 4


@pytest.mark.django_db
@pytest.mark.contract
class TestResetLine:
    def test_reset_line_endpoint(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            periodcount=2,
        )
        for i in range(1, 3):
            ProjectionPeriodFactory(projectid=project, periodnumber=i)
        concept = BudgetConceptFactory(projectid=project)
        bd = UnitCostBreakdownFactory(conceptid=concept)
        CostDistribution.objects.create(
            projectid=project, linetype=CostLineType.BREAKDOWN, breakdownid=bd,
            periodnumber=1, fraction=Decimal("0.9"), isderived=False,
        )

        r = admin_auth_client.post(
            f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/reset-line/',
            data={'lineid': str(bd.breakdownid), 'linetype': 'BREAKDOWN'},
            content_type='application/json',
        )
        assert r.status_code == 200


@pytest.mark.integration
@pytest.mark.django_db
def test_patch_bulk_accepts_lag_edits(admin_auth_client, system_admin):
    """PATCH /cost-distribution/bulk/ accepts lag_edits and persists them."""
    from apps.proyeccion.tests.factories import (
        EstimationProjectFactory, ProjectionPeriodFactory,
        BudgetConceptFactory, UnitCostBreakdownFactory,
    )
    project = EstimationProjectFactory(
        ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
    )
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    concept = BudgetConceptFactory(projectid=project)
    line = UnitCostBreakdownFactory(conceptid=concept, paymentlagperiods=None, lineversion=0)

    response = admin_auth_client.patch(
        f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/bulk/',
        data={
            'edits': [],
            'lag_edits': [{
                'lineid': str(line.breakdownid),
                'linetype': 'BREAKDOWN',
                'paymentlagperiods': 5,
                'expected_lineversion': 0,
            }],
        },
        content_type='application/json',
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body['lag_updated'] == 1
    assert body['new_lineversions'] == {str(line.breakdownid): 1}

    line.refresh_from_db()
    assert line.paymentlagperiods == 5
    assert line.lineversion == 1


@pytest.mark.integration
@pytest.mark.django_db
def test_patch_bulk_lag_conflict_returns_409(admin_auth_client, system_admin):
    """A lag_edit with stale expected_lineversion returns 409 with lag conflict info."""
    from apps.proyeccion.tests.factories import (
        EstimationProjectFactory, IndirectCostDetailFactory,
    )
    project = EstimationProjectFactory(
        ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
    )
    line = IndirectCostDetailFactory(projectid=project, paymentlagperiods=3, lineversion=7)

    response = admin_auth_client.patch(
        f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/bulk/',
        data={
            'edits': [],
            'lag_edits': [{
                'lineid': str(line.indirectcostid),
                'linetype': 'INDIRECT',
                'paymentlagperiods': 9,
                'expected_lineversion': 6,
            }],
        },
        content_type='application/json',
    )
    assert response.status_code == 409
    body = response.json()
    assert body['error'] == 'version_conflict'
    assert any(c.get('kind') == 'lag' and c['lineid'] == str(line.indirectcostid)
               for c in body['conflicts'])


@pytest.mark.integration
@pytest.mark.django_db
def test_patch_bulk_lag_out_of_range_returns_400(admin_auth_client, system_admin):
    """paymentlagperiods > 120 returns 400."""
    from apps.proyeccion.tests.factories import (
        EstimationProjectFactory, IndirectCostDetailFactory,
    )
    project = EstimationProjectFactory(
        ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
    )
    line = IndirectCostDetailFactory(projectid=project, lineversion=0)
    response = admin_auth_client.patch(
        f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/bulk/',
        data={
            'edits': [],
            'lag_edits': [{
                'lineid': str(line.indirectcostid),
                'linetype': 'INDIRECT',
                'paymentlagperiods': 200,
                'expected_lineversion': 0,
            }],
        },
        content_type='application/json',
    )
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.django_db
def test_get_cost_distribution_includes_lag_and_lineversion(admin_auth_client, system_admin):
    """GET /cost-distribution/ exposes paymentlagperiods and lineversion per line."""
    from apps.proyeccion.tests.factories import (
        EstimationProjectFactory, ProjectionPeriodFactory,
        BudgetConceptFactory, UnitCostBreakdownFactory,
    )
    project = EstimationProjectFactory(
        ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        periodcount=1,
    )
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    concept = BudgetConceptFactory(projectid=project)
    line = UnitCostBreakdownFactory(conceptid=concept, paymentlagperiods=4, lineversion=2)

    response = admin_auth_client.get(
        f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/'
    )
    assert response.status_code == 200
    body = response.json()

    # The payload shape is: families[].lines[] (flat list of DistributionLineDto)
    found = False
    for family in body.get('families', []):
        for ln in family.get('lines', []):
            if isinstance(ln, dict) and ln.get('lineid') == str(line.breakdownid):
                assert ln['paymentlagperiods'] == 4, f"got {ln.get('paymentlagperiods')!r}"
                assert ln['lineversion'] == 2, f"got {ln.get('lineversion')!r}"
                found = True
    assert found, (
        f"breakdown line not found in payload — actual structure: {list(body.keys())}, "
        f"families[0] keys: {list(body['families'][0].keys()) if body.get('families') else 'no families'}"
    )


@pytest.mark.django_db
@pytest.mark.contract
class TestPresence:
    def test_heartbeat_and_list(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        r = admin_auth_client.post(
            f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/presence/heartbeat/',
            data={'mode': 'viewing'},
            content_type='application/json',
        )
        assert r.status_code == 200

        r2 = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/cost-distribution/presence/'
        )
        assert r2.status_code == 200
        users = r2.json()['active_users']
        assert len(users) == 1
        assert users[0]['mode'] == 'viewing'
