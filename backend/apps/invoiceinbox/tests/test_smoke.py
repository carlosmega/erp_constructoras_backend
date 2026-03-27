"""Smoke tests for InvoiceInbox module."""

import pytest
from apps.invoiceinbox.tests.factories import IncomingInvoiceFactory
from apps.projects.tests.factories import ConstructionProjectFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeInvoiceInbox:
    """Quick sanity checks for invoiceinbox module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        obj = IncomingInvoiceFactory(projectid=project, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.invoiceinbox.services import IncomingInvoiceService
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        IncomingInvoiceFactory(projectid=project, createdby=salesperson, modifiedby=salesperson)
        result = IncomingInvoiceService.list_invoices(user=salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, admin_auth_client, system_admin, salesperson):
        """Test that the list endpoint returns 200."""
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        IncomingInvoiceFactory(projectid=project, createdby=salesperson, modifiedby=salesperson)
        response = admin_auth_client.get('/api/invoice-inbox/inbox/')
        assert response.status_code == 200
