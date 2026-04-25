"""Router tests for Estimation PNT (Cashflow) endpoints — Task 17."""

import base64
import json
from decimal import Decimal

import pytest
from django.test import Client

from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.django_db
@pytest.mark.integration
class TestFinancialSettingsRoutes:
    def test_get_creates_lazily_with_defaults(self, admin_auth_client):
        project = EstimationProjectFactory()
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/financial-settings/'
        )
        assert r.status_code == 200
        body = r.json()
        # Pydantic v2 serializes Decimal preserving the value's own precision (not the
        # column's decimal_places). Defaults are stored as Decimal('0.0500') and
        # Decimal('0') respectively, which is what we assert on the wire.
        assert body['imssretentionrate'] == '0.0500'
        assert body['advanceamountnotax'] == '0'
        assert body['advanceentryperiod'] == 1

    def test_patch_updates_whitelisted_fields(self, admin_auth_client):
        project = EstimationProjectFactory()
        r = admin_auth_client.patch(
            f'/api/proyeccion/projects/{project.estimationprojectid}/financial-settings/',
            data={'imssretentionrate': '0.10', 'advanceamountnotax': '500'},
            content_type='application/json',
        )
        assert r.status_code == 200
        body = r.json()
        # Inputs are echoed at the precision they were submitted with.
        assert body['imssretentionrate'] == '0.10'
        assert body['advanceamountnotax'] == '500'

    def test_patch_round_trips(self, admin_auth_client):
        project = EstimationProjectFactory()
        admin_auth_client.patch(
            f'/api/proyeccion/projects/{project.estimationprojectid}/financial-settings/',
            data={'directpaymentlag': 3},
            content_type='application/json',
        )
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/financial-settings/'
        )
        assert r.status_code == 200
        assert r.json()['directpaymentlag'] == 3

    def test_get_unauthenticated_403_or_401(self, db):
        project = EstimationProjectFactory()
        c = Client()
        r = c.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/financial-settings/'
        )
        assert r.status_code in (401, 403)


@pytest.mark.django_db
@pytest.mark.integration
class TestBillingRulesRoutes:
    def test_get_empty_when_no_rules(self, admin_auth_client):
        project = EstimationProjectFactory()
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/billing-rules/'
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_put_creates_set(self, admin_auth_client):
        project = EstimationProjectFactory()
        r = admin_auth_client.put(
            f'/api/proyeccion/projects/{project.estimationprojectid}/billing-rules/',
            data={'rules': [
                {'sequence': 1, 'percent': '0.5', 'lagperiods': 0},
                {'sequence': 2, 'percent': '0.5', 'lagperiods': 1},
            ]},
            content_type='application/json',
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        assert body[0]['sequence'] == 1
        # Adapt the percent assertion to match actual Pydantic v2 output if needed
        assert Decimal(body[1]['percent']) == Decimal('0.5')

    def test_put_rejects_sum_not_one(self, admin_auth_client):
        project = EstimationProjectFactory()
        r = admin_auth_client.put(
            f'/api/proyeccion/projects/{project.estimationprojectid}/billing-rules/',
            data={'rules': [{'sequence': 1, 'percent': '0.4', 'lagperiods': 0}]},
            content_type='application/json',
        )
        assert r.status_code == 400
        body = r.json()
        # Service raises ValueError matching "100%" — captured by HttpError(400, str(e))
        # The body shape depends on Ninja's HttpError handler — could be {"detail": "..."}
        # or just a string. Adapt to actual.
        body_str = body.get('detail', body) if isinstance(body, dict) else body
        assert '100' in str(body_str) or '%' in str(body_str)

    def test_put_replaces_existing_set(self, admin_auth_client):
        project = EstimationProjectFactory()
        admin_auth_client.put(
            f'/api/proyeccion/projects/{project.estimationprojectid}/billing-rules/',
            data={'rules': [{'sequence': 1, 'percent': '1.0', 'lagperiods': 0}]},
            content_type='application/json',
        )
        r = admin_auth_client.put(
            f'/api/proyeccion/projects/{project.estimationprojectid}/billing-rules/',
            data={'rules': [
                {'sequence': 1, 'percent': '0.7', 'lagperiods': 0},
                {'sequence': 2, 'percent': '0.3', 'lagperiods': 2},
            ]},
            content_type='application/json',
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        assert body[1]['lagperiods'] == 2


@pytest.mark.django_db
@pytest.mark.integration
class TestPNTRoute:
    def test_returns_409_when_no_periods(self, admin_auth_client):
        project = EstimationProjectFactory()
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/pnt/'
        )
        assert r.status_code == 409
        body = r.json()
        # Body might be a JSON-decoded dict OR a string of dumped JSON, OR a
        # Ninja default {"detail": "<dumped json string>"}. Adapt to all three.
        if isinstance(body, str):
            body = json.loads(body)
        elif isinstance(body, dict) and 'code' not in body and isinstance(body.get('detail'), str):
            try:
                body = json.loads(body['detail'])
            except (ValueError, TypeError):
                pass
        assert body.get('code') == 'no_periods'

    def test_returns_report_with_periods(self, admin_auth_client):
        from apps.proyeccion.tests.factories import build_pnt_ready_project
        project, _ = build_pnt_ready_project(periods=2)
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/pnt/'
        )
        assert r.status_code == 200
        body = r.json()
        assert body['granularity'] == 'period'
        assert len(body['periods']) == 2
        assert len(body['rows']) == 22
        assert 'pnt_min' in body['stats']

    def test_granularity_month(self, admin_auth_client):
        from apps.proyeccion.tests.factories import build_pnt_ready_project
        project, _ = build_pnt_ready_project(periods=2)
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/pnt/?granularity=month'
        )
        assert r.status_code == 200
        assert r.json()['granularity'] == 'month'

    def test_invalid_granularity_400(self, admin_auth_client):
        from apps.proyeccion.tests.factories import build_pnt_ready_project
        project, _ = build_pnt_ready_project(periods=2)
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/pnt/?granularity=quarter'
        )
        assert r.status_code == 400

    def test_overrides_decoded_from_base64(self, admin_auth_client):
        from apps.proyeccion.tests.factories import build_pnt_ready_project, make_concept_for_project
        from apps.proyeccion.models import WorkPlanEntry
        project, _ = build_pnt_ready_project(periods=2)
        concept = make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('1000'),
        )
        ovr = base64.b64encode(json.dumps({'imssretentionrate': '0.20'}).encode()).decode()
        r = admin_auth_client.get(
            f'/api/proyeccion/projects/{project.estimationprojectid}/pnt/?overrides={ovr}'
        )
        assert r.status_code == 200
        body = r.json()
        ret_imss = next(r for r in body['rows'] if r['code'] == 'RET_IMSS')['values']
        # Overridden rate (20%) should give -200, not -50
        assert Decimal(ret_imss[0]) == Decimal('-200.0000')
