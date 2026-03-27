"""Smoke tests for Audit module."""

import pytest
from apps.audit.tests.factories import AuditLogFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAudit:
    """Quick sanity checks for audit module."""

    def test_model_creation(self):
        """Test that the primary model can be created via factory."""
        obj = AuditLogFactory()
        assert obj.pk is not None

    def test_service_query(self):
        """Test that the service query method works."""
        from apps.audit.services import AuditLogService
        AuditLogFactory()
        result = AuditLogService.query_logs()
        assert result.count() >= 1

    def test_router_list_200(self, admin_auth_client, system_admin):
        """Test that the list endpoint returns 200."""
        AuditLogFactory()
        response = admin_auth_client.get('/api/audit-logs/')
        assert response.status_code == 200
