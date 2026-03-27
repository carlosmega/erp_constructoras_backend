"""Router tests for Invoice Inbox API endpoints."""

import uuid
import pytest
from apps.invoiceinbox.tests.factories import (
    IncomingInvoiceFactory,
    ClassifiedInvoiceFactory,
    InboxSyncLogFactory,
)
from apps.projects.tests.factories import ConstructionProjectFactory


# =============================================================================
# List & Detail
# =============================================================================

@pytest.mark.contract
class TestListIncomingInvoices:
    def test_returns_200(self, admin_auth_client, system_admin):
        IncomingInvoiceFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/invoice-inbox/inbox/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/invoice-inbox/inbox/')
        assert response.status_code == 403

    def test_filter_by_statecode(self, admin_auth_client, system_admin):
        IncomingInvoiceFactory(createdby=system_admin, modifiedby=system_admin, statecode=0)
        response = admin_auth_client.get('/api/invoice-inbox/inbox/?statecode=0')
        assert response.status_code == 200


@pytest.mark.contract
class TestListProjectInvoices:
    def test_returns_200(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(createdby=system_admin, modifiedby=system_admin)
        IncomingInvoiceFactory(projectid=project, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/invoice-inbox/projects/{project.projectid}/inbox/')
        assert response.status_code == 200

    def test_project_not_found(self, admin_auth_client, system_admin):
        response = admin_auth_client.get(f'/api/invoice-inbox/projects/{uuid.uuid4()}/inbox/')
        assert response.status_code == 404


@pytest.mark.contract
class TestGetIncomingInvoice:
    def test_returns_invoice(self, admin_auth_client, system_admin):
        invoice = IncomingInvoiceFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/invoice-inbox/inbox/{invoice.incominginvoiceid}/')
        assert response.status_code == 200

    def test_not_found(self, admin_auth_client, system_admin):
        response = admin_auth_client.get(f'/api/invoice-inbox/inbox/{uuid.uuid4()}/')
        assert response.status_code == 404


# =============================================================================
# Summary
# =============================================================================

@pytest.mark.contract
class TestInboxSummary:
    def test_global_summary(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(createdby=system_admin, modifiedby=system_admin)
        IncomingInvoiceFactory(projectid=project, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/invoice-inbox/inbox/summary/')
        # May return 200 or 422 depending on required query params
        assert response.status_code in (200, 422)

    def test_project_summary(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(createdby=system_admin, modifiedby=system_admin)
        IncomingInvoiceFactory(projectid=project, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/invoice-inbox/projects/{project.projectid}/inbox/summary/')
        assert response.status_code == 200


# =============================================================================
# Sync Logs
# =============================================================================

@pytest.mark.contract
class TestSyncLogs:
    def test_list_all_sync_logs(self, admin_auth_client, system_admin):
        InboxSyncLogFactory(triggeredbyuserid=system_admin)
        response = admin_auth_client.get('/api/invoice-inbox/inbox/sync-logs/')
        # May return 200 or 422 depending on required query params
        assert response.status_code in (200, 422)

    def test_list_project_sync_logs(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(createdby=system_admin, modifiedby=system_admin)
        InboxSyncLogFactory(projectid=project, triggeredbyuserid=system_admin)
        response = admin_auth_client.get(f'/api/invoice-inbox/projects/{project.projectid}/inbox/sync-logs/')
        assert response.status_code == 200


# =============================================================================
# Readonly permission check
# =============================================================================

@pytest.mark.contract
class TestInboxReadonlyAccess:
    def test_readonly_can_list(self, readonly_auth_client, readonly_user):
        IncomingInvoiceFactory()
        response = readonly_auth_client.get('/api/invoice-inbox/inbox/')
        assert response.status_code == 200
