"""Router integration tests for cashflow module."""
import pytest
from decimal import Decimal

from apps.projects.tests.factories import ConstructionProjectFactory


@pytest.mark.django_db
@pytest.mark.integration
def test_get_financial_settings_materializes_defaults(admin_auth_client):
    """GET should materialize defaults on first read."""
    project = ConstructionProjectFactory()
    resp = admin_auth_client.get(
        f'/api/cashflow/projects/{project.pk}/financial-settings/'
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['imssretentionrate'] == '0.0500'
    assert body['anticipoentryperiod'] == 1


@pytest.mark.django_db
@pytest.mark.integration
def test_patch_financial_settings_updates_fields(admin_auth_client):
    """PATCH should apply partial updates and return the persisted values."""
    project = ConstructionProjectFactory()
    resp = admin_auth_client.patch(
        f'/api/cashflow/projects/{project.pk}/financial-settings/',
        data={'imssretentionrate': '0.06', 'financecostrate': '0.002'},
        content_type='application/json',
    )
    assert resp.status_code == 200
    # Pydantic v2 preserves the input Decimal's precision in JSON output,
    # not the model field's decimal_places. So '0.06' stays '0.06'.
    assert resp.json()['imssretentionrate'] == '0.06'
    assert resp.json()['financecostrate'] == '0.002'
