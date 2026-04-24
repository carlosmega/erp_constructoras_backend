"""Overrides (simulation) tests — results change but DB does not."""
import json
import base64
import pytest
from decimal import Decimal

from apps.cashflow.tests.factories import build_simple_project_fixture
from apps.cashflow.services.financial_settings import FinancialSettingsService


@pytest.mark.django_db
@pytest.mark.integration
def test_overrides_change_result_but_do_not_persist(admin_auth_client):
    fx = build_simple_project_fixture(periods=2, produccion_per_period=1000)
    project_id = fx['project'].pk

    overrides = {'imssretentionrate': 0.10}
    encoded = base64.b64encode(json.dumps(overrides).encode()).decode()

    resp = admin_auth_client.get(
        f'/api/cashflow/projects/{project_id}/pnt/?overrides={encoded}'
    )
    assert resp.status_code == 200
    rows = {r['code']: r['values'] for r in resp.json()['rows']}
    # IMSS retention at 10% of cobro (=produccion with default 100%/0 rule):
    # -Decimal('0.1') * Decimal('1000') == Decimal('-100.0'),
    # Pydantic v2 preserves input-decimal precision → serializes as '-100.0'.
    assert rows['RET_IMSS'][0].startswith('-100')
    assert rows['RET_IMSS'][1].startswith('-100')
    assert len(rows['RET_IMSS']) == 2

    # Persisted settings unchanged
    persisted = FinancialSettingsService.get_or_create(project_id)
    assert persisted.imssretentionrate == Decimal('0.0500')
