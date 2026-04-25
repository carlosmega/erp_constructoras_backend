"""Router tests for Estimation PNT (Cashflow) endpoints — Task 17."""

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
