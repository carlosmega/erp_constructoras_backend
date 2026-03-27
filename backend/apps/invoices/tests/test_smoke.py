"""Smoke tests for Invoices module."""

import pytest
from apps.invoices.tests.factories import InvoiceFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeInvoices:
    """Quick sanity checks for invoices module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.invoices.models import Invoice
        from core.permissions import filter_by_ownership
        InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = filter_by_ownership(Invoice.objects.all(), salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/invoices/')
        assert response.status_code == 200
