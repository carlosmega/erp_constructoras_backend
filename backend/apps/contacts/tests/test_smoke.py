"""Smoke tests for Contacts module."""

import pytest
from apps.contacts.tests.factories import ContactFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeContacts:
    """Quick sanity checks for contacts module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.contacts.services import ContactService
        ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = ContactService.list_contacts(salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/contacts/')
        assert response.status_code == 200
