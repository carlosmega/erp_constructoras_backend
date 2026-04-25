"""Router tests for Estimation PNT (Cashflow) endpoints — Task 17."""

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
