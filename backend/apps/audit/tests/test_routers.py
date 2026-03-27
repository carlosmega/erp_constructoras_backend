"""Router tests for Audit Log API endpoints."""

import uuid
import pytest
from apps.audit.tests.factories import AuditLogFactory


# =============================================================================
# List Audit Logs
# =============================================================================

@pytest.mark.contract
class TestListAuditLogs:
    def test_returns_200_for_admin(self, admin_auth_client, system_admin):
        AuditLogFactory(userid=system_admin, username=system_admin.fullname)
        response = admin_auth_client.get('/api/audit-logs/')
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert 'total' in data
        assert data['total'] >= 1

    def test_filter_by_entity(self, admin_auth_client, system_admin):
        AuditLogFactory(userid=system_admin, username=system_admin.fullname, entity='lead')
        AuditLogFactory(userid=system_admin, username=system_admin.fullname, entity='opportunity')
        response = admin_auth_client.get('/api/audit-logs/?entity=lead')
        assert response.status_code == 200
        data = response.json()
        assert all(item['entity'] == 'lead' for item in data['items'])

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/audit-logs/')
        assert response.status_code in (401, 403)

    def test_regular_user_sees_only_own_logs(self, auth_client, salesperson, system_admin):
        AuditLogFactory(userid=salesperson, username=salesperson.fullname, entity='lead')
        AuditLogFactory(userid=system_admin, username=system_admin.fullname, entity='lead')
        response = auth_client.get('/api/audit-logs/')
        assert response.status_code == 200
        data = response.json()
        # Salesperson should only see their own logs
        for item in data['items']:
            assert item['userid'] == str(salesperson.systemuserid)


# =============================================================================
# Record Audit Trail
# =============================================================================

@pytest.mark.contract
class TestGetRecordAuditTrail:
    def test_returns_trail(self, admin_auth_client, system_admin):
        record_id = uuid.uuid4()
        AuditLogFactory(userid=system_admin, username=system_admin.fullname, entity='lead', recordid=record_id)
        AuditLogFactory(userid=system_admin, username=system_admin.fullname, entity='lead', recordid=record_id, action='update')
        response = admin_auth_client.get(f'/api/audit-logs/entity/lead/{record_id}/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    def test_empty_trail_returns_200(self, admin_auth_client, system_admin):
        response = admin_auth_client.get(f'/api/audit-logs/entity/lead/{uuid.uuid4()}/')
        assert response.status_code == 200
        assert response.json() == []
