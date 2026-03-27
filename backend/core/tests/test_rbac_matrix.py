"""
Comprehensive RBAC Permission Matrix Tests.

Tests the full permission matrix: 5 roles x CRUD operations for each
sales pipeline entity. Verifies that the @require_permission decorators
on API endpoints correctly enforce the role-based access control defined
in core.permissions.ROLE_PERMISSIONS.

Entities covered:
  1. Leads         /api/leads/
  2. Opportunities  /api/opportunities/
  3. Accounts       /api/accounts/
  4. Contacts       /api/contacts/
  5. Quotes         /api/quotes/
  6. Orders         /api/orders/
  7. Invoices       /api/invoices/
  8. Products       /api/products/
  9. Cases          /api/cases/
 10. Activities     /api/activities/
"""

import pytest
from django.test import Client

from apps.leads.tests.factories import LeadFactory
from apps.opportunities.tests.factories import OpportunityFactory
from apps.accounts.tests.factories import AccountFactory
from apps.contacts.tests.factories import ContactFactory
from apps.quotes.tests.factories import QuoteFactory
from apps.orders.tests.factories import SalesOrderFactory
from apps.invoices.tests.factories import InvoiceFactory
from apps.products.tests.factories import ProductFactory
from apps.cases.tests.factories import CaseFactory
from apps.activities.tests.factories import ActivityFactory


# ---------------------------------------------------------------------------
# Inline fixture: marketing_auth_client
# ---------------------------------------------------------------------------

@pytest.fixture
def marketing_auth_client(db, marketing_user):
    """Django test client authenticated as Marketing User."""
    client = Client()
    client.force_login(marketing_user)
    return client


@pytest.fixture
def anon_client(db):
    """Unauthenticated Django test client."""
    return Client()


# ===========================================================================
# 1. LEAD PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestLeadPermissions:
    """Test RBAC for Lead entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client, system_admin):
        LeadFactory(ownerid=system_admin)
        assert admin_auth_client.get('/api/leads/').status_code == 200

    def test_manager_can_list(self, manager_auth_client, sales_manager):
        LeadFactory(ownerid=sales_manager)
        assert manager_auth_client.get('/api/leads/').status_code == 200

    def test_salesperson_can_list(self, auth_client, salesperson):
        LeadFactory(ownerid=salesperson)
        assert auth_client.get('/api/leads/').status_code == 200

    def test_marketing_can_list(self, marketing_auth_client, marketing_user):
        LeadFactory(ownerid=marketing_user)
        assert marketing_auth_client.get('/api/leads/').status_code == 200

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/leads/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/leads/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'lastname': 'Admin Lead'}
        resp = admin_auth_client.post('/api/leads/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_manager_can_create(self, manager_auth_client):
        payload = {'lastname': 'Manager Lead'}
        resp = manager_auth_client.post('/api/leads/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client):
        payload = {'lastname': 'Sales Lead'}
        resp = auth_client.post('/api/leads/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_marketing_can_create(self, marketing_auth_client):
        payload = {'lastname': 'Marketing Lead'}
        resp = marketing_auth_client.post('/api/leads/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'lastname': 'Test'}
        resp = readonly_auth_client.post('/api/leads/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        lead = LeadFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/leads/{lead.leadid}',
            {'firstname': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_manager_can_update(self, manager_auth_client, sales_manager):
        lead = LeadFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        resp = manager_auth_client.patch(
            f'/api/leads/{lead.leadid}',
            {'firstname': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_can_update_own(self, auth_client, salesperson):
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/leads/{lead.leadid}',
            {'firstname': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_cannot_update_others(self, auth_client, salesperson2):
        lead = LeadFactory(ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2)
        resp = auth_client.patch(
            f'/api/leads/{lead.leadid}',
            {'firstname': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        lead = LeadFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/leads/{lead.leadid}',
            {'firstname': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        lead = LeadFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/leads/{lead.leadid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        lead = LeadFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/leads/{lead.leadid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/leads/{lead.leadid}').status_code == 403

    def test_marketing_cannot_delete(self, marketing_auth_client, marketing_user):
        lead = LeadFactory(ownerid=marketing_user, createdby=marketing_user, modifiedby=marketing_user)
        assert marketing_auth_client.delete(f'/api/leads/{lead.leadid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        lead = LeadFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/leads/{lead.leadid}').status_code == 403


# ===========================================================================
# 2. OPPORTUNITY PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestOpportunityPermissions:
    """Test RBAC for Opportunity entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/opportunities/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        assert manager_auth_client.get('/api/opportunities/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/opportunities/').status_code == 200

    def test_marketing_cannot_list(self, marketing_auth_client):
        """Marketing User does NOT have OPPORTUNITY_READ."""
        assert marketing_auth_client.get('/api/opportunities/').status_code == 403

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/opportunities/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/opportunities/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'name': 'Opp Admin'}
        resp = admin_auth_client.post('/api/opportunities/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_manager_can_create(self, manager_auth_client):
        payload = {'name': 'Opp Manager'}
        resp = manager_auth_client.post('/api/opportunities/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client):
        payload = {'name': 'Opp Sales'}
        resp = auth_client.post('/api/opportunities/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'name': 'Opp Readonly'}
        resp = readonly_auth_client.post('/api/opportunities/', payload, content_type='application/json')
        assert resp.status_code == 403

    def test_marketing_cannot_create(self, marketing_auth_client):
        payload = {'name': 'Opp Marketing'}
        resp = marketing_auth_client.post('/api/opportunities/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        opp = OpportunityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/opportunities/{opp.opportunityid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_can_update_own(self, auth_client, salesperson):
        opp = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/opportunities/{opp.opportunityid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        opp = OpportunityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/opportunities/{opp.opportunityid}',
            {'name': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        opp = OpportunityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/opportunities/{opp.opportunityid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        opp = OpportunityFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/opportunities/{opp.opportunityid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        opp = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/opportunities/{opp.opportunityid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        opp = OpportunityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/opportunities/{opp.opportunityid}').status_code == 403


# ===========================================================================
# 3. ACCOUNT PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestAccountPermissions:
    """Test RBAC for Account entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/accounts/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        assert manager_auth_client.get('/api/accounts/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/accounts/').status_code == 200

    def test_marketing_can_list(self, marketing_auth_client):
        """Marketing User has ACCOUNT_READ."""
        assert marketing_auth_client.get('/api/accounts/').status_code == 200

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/accounts/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/accounts/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'name': 'Acme Corp'}
        resp = admin_auth_client.post('/api/accounts/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client):
        payload = {'name': 'Sales Corp'}
        resp = auth_client.post('/api/accounts/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_marketing_cannot_create(self, marketing_auth_client):
        """Marketing User does NOT have ACCOUNT_CREATE."""
        payload = {'name': 'MktCorp'}
        resp = marketing_auth_client.post('/api/accounts/', payload, content_type='application/json')
        assert resp.status_code == 403

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'name': 'RO Corp'}
        resp = readonly_auth_client.post('/api/accounts/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        acct = AccountFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/accounts/{acct.accountid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_can_update_own(self, auth_client, salesperson):
        acct = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/accounts/{acct.accountid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        acct = AccountFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/accounts/{acct.accountid}',
            {'name': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        acct = AccountFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/accounts/{acct.accountid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        acct = AccountFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/accounts/{acct.accountid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        acct = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/accounts/{acct.accountid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        acct = AccountFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/accounts/{acct.accountid}').status_code == 403


# ===========================================================================
# 4. CONTACT PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestContactPermissions:
    """Test RBAC for Contact entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/contacts/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/contacts/').status_code == 200

    def test_marketing_can_list(self, marketing_auth_client):
        """Marketing User has CONTACT_READ."""
        assert marketing_auth_client.get('/api/contacts/').status_code == 200

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/contacts/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/contacts/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'lastname': 'Doe'}
        resp = admin_auth_client.post('/api/contacts/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client):
        payload = {'lastname': 'Smith'}
        resp = auth_client.post('/api/contacts/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_marketing_can_create(self, marketing_auth_client):
        """Marketing User has CONTACT_CREATE."""
        payload = {'lastname': 'MktContact'}
        resp = marketing_auth_client.post('/api/contacts/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'lastname': 'Test'}
        resp = readonly_auth_client.post('/api/contacts/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        contact = ContactFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/contacts/{contact.contactid}',
            {'firstname': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_can_update_own(self, auth_client, salesperson):
        contact = ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/contacts/{contact.contactid}',
            {'firstname': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        contact = ContactFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/contacts/{contact.contactid}',
            {'firstname': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        contact = ContactFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/contacts/{contact.contactid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        contact = ContactFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/contacts/{contact.contactid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        contact = ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/contacts/{contact.contactid}').status_code == 403

    def test_marketing_cannot_delete(self, marketing_auth_client, marketing_user):
        contact = ContactFactory(ownerid=marketing_user, createdby=marketing_user, modifiedby=marketing_user)
        assert marketing_auth_client.delete(f'/api/contacts/{contact.contactid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        contact = ContactFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/contacts/{contact.contactid}').status_code == 403


# ===========================================================================
# 5. QUOTE PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestQuotePermissions:
    """Test RBAC for Quote entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/quotes/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        assert manager_auth_client.get('/api/quotes/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/quotes/').status_code == 200

    def test_marketing_cannot_list(self, marketing_auth_client):
        """Marketing User does NOT have QUOTE_READ."""
        assert marketing_auth_client.get('/api/quotes/').status_code == 403

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/quotes/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/quotes/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'name': 'Quote Admin'}
        resp = admin_auth_client.post('/api/quotes/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_manager_can_create(self, manager_auth_client):
        payload = {'name': 'Quote Manager'}
        resp = manager_auth_client.post('/api/quotes/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client):
        payload = {'name': 'Quote Sales'}
        resp = auth_client.post('/api/quotes/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'name': 'Quote RO'}
        resp = readonly_auth_client.post('/api/quotes/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        quote = QuoteFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/quotes/{quote.quoteid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_can_update_own(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/quotes/{quote.quoteid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        quote = QuoteFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/quotes/{quote.quoteid}',
            {'name': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        quote = QuoteFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/quotes/{quote.quoteid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        quote = QuoteFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/quotes/{quote.quoteid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/quotes/{quote.quoteid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        quote = QuoteFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/quotes/{quote.quoteid}').status_code == 403


# ===========================================================================
# 6. ORDER PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestOrderPermissions:
    """Test RBAC for SalesOrder entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/orders/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        assert manager_auth_client.get('/api/orders/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/orders/').status_code == 200

    def test_marketing_cannot_list(self, marketing_auth_client):
        """Marketing User does NOT have ORDER_READ."""
        assert marketing_auth_client.get('/api/orders/').status_code == 403

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/orders/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/orders/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'name': 'Order Admin'}
        resp = admin_auth_client.post('/api/orders/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_manager_can_create(self, manager_auth_client):
        payload = {'name': 'Order Manager'}
        resp = manager_auth_client.post('/api/orders/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client):
        payload = {'name': 'Order Sales'}
        resp = auth_client.post('/api/orders/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'name': 'Order RO'}
        resp = readonly_auth_client.post('/api/orders/', payload, content_type='application/json')
        assert resp.status_code == 403

    def test_marketing_cannot_create(self, marketing_auth_client):
        payload = {'name': 'Order Mkt'}
        resp = marketing_auth_client.post('/api/orders/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/orders/{order.salesorderid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_cannot_update(self, auth_client, salesperson):
        """Salesperson does NOT have ORDER_UPDATE."""
        order = SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/orders/{order.salesorderid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/orders/{order.salesorderid}',
            {'name': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/orders/{order.salesorderid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        order = SalesOrderFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/orders/{order.salesorderid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        """Salesperson does NOT have ORDER_DELETE."""
        order = SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/orders/{order.salesorderid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/orders/{order.salesorderid}').status_code == 403


# ===========================================================================
# 7. INVOICE PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestInvoicePermissions:
    """Test RBAC for Invoice entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/invoices/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        assert manager_auth_client.get('/api/invoices/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/invoices/').status_code == 200

    def test_marketing_cannot_list(self, marketing_auth_client):
        """Marketing User does NOT have INVOICE_READ."""
        assert marketing_auth_client.get('/api/invoices/').status_code == 403

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/invoices/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/invoices/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'name': 'Invoice Admin'}
        resp = admin_auth_client.post('/api/invoices/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_manager_can_create(self, manager_auth_client):
        payload = {'name': 'Invoice Manager'}
        resp = manager_auth_client.post('/api/invoices/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_cannot_create(self, auth_client):
        """Salesperson does NOT have INVOICE_CREATE."""
        payload = {'name': 'Invoice Sales'}
        resp = auth_client.post('/api/invoices/', payload, content_type='application/json')
        assert resp.status_code == 403

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'name': 'Invoice RO'}
        resp = readonly_auth_client.post('/api/invoices/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        invoice = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/invoices/{invoice.invoiceid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_cannot_update(self, auth_client, salesperson):
        """Salesperson does NOT have INVOICE_UPDATE."""
        invoice = InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/invoices/{invoice.invoiceid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        invoice = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/invoices/{invoice.invoiceid}',
            {'name': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        invoice = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/invoices/{invoice.invoiceid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        invoice = InvoiceFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/invoices/{invoice.invoiceid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        """Salesperson does NOT have INVOICE_DELETE."""
        invoice = InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/invoices/{invoice.invoiceid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        invoice = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/invoices/{invoice.invoiceid}').status_code == 403


# ===========================================================================
# 8. PRODUCT PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestProductPermissions:
    """Test RBAC for Product entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/products/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        """Sales Manager has PRODUCT_READ."""
        assert manager_auth_client.get('/api/products/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        """Salesperson has PRODUCT_READ."""
        assert auth_client.get('/api/products/').status_code == 200

    def test_marketing_cannot_list(self, marketing_auth_client):
        """Marketing User does NOT have PRODUCT_READ."""
        assert marketing_auth_client.get('/api/products/').status_code == 403

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/products/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/products/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client):
        payload = {'name': 'Widget', 'price': '10.00'}
        resp = admin_auth_client.post('/api/products/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_manager_cannot_create(self, manager_auth_client):
        """Sales Manager does NOT have PRODUCT_CREATE (only PRODUCT_READ)."""
        payload = {'name': 'Widget', 'price': '10.00'}
        resp = manager_auth_client.post('/api/products/', payload, content_type='application/json')
        assert resp.status_code == 403

    def test_salesperson_cannot_create(self, auth_client):
        """Salesperson does NOT have PRODUCT_CREATE."""
        payload = {'name': 'Widget', 'price': '10.00'}
        resp = auth_client.post('/api/products/', payload, content_type='application/json')
        assert resp.status_code == 403

    def test_readonly_cannot_create(self, readonly_auth_client):
        payload = {'name': 'Widget', 'price': '10.00'}
        resp = readonly_auth_client.post('/api/products/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/products/{product.productid}',
            {'name': 'Updated Widget'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_manager_cannot_update(self, manager_auth_client, sales_manager):
        """Sales Manager does NOT have PRODUCT_UPDATE."""
        product = ProductFactory(createdby=sales_manager, modifiedby=sales_manager)
        resp = manager_auth_client.patch(
            f'/api/products/{product.productid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_salesperson_cannot_update(self, auth_client, salesperson):
        """Salesperson does NOT have PRODUCT_UPDATE."""
        product = ProductFactory(createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/products/{product.productid}',
            {'name': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/products/{product.productid}',
            {'name': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/products/{product.productid}').status_code == 204

    def test_manager_cannot_delete(self, manager_auth_client, sales_manager):
        """Sales Manager does NOT have PRODUCT_DELETE."""
        product = ProductFactory(createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/products/{product.productid}').status_code == 403

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        product = ProductFactory(createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/products/{product.productid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/products/{product.productid}').status_code == 403


# ===========================================================================
# 9. CASE PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestCasePermissions:
    """Test RBAC for Case entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/cases/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        assert manager_auth_client.get('/api/cases/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/cases/').status_code == 200

    def test_marketing_can_list(self, marketing_auth_client):
        """Marketing User has CASE_READ."""
        assert marketing_auth_client.get('/api/cases/').status_code == 200

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/cases/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/cases/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client, system_admin):
        acct = AccountFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        payload = {
            'title': 'Case Admin',
            'customerid': str(acct.accountid),
            'customerid_type': 'account',
            'caseorigincode': 1,
            'ownerid': str(system_admin.systemuserid),
        }
        resp = admin_auth_client.post('/api/cases/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client, salesperson):
        acct = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'title': 'Case Sales',
            'customerid': str(acct.accountid),
            'customerid_type': 'account',
            'caseorigincode': 1,
            'ownerid': str(salesperson.systemuserid),
        }
        resp = auth_client.post('/api/cases/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_marketing_cannot_create(self, marketing_auth_client, marketing_user):
        """Marketing User does NOT have CASE_CREATE."""
        acct = AccountFactory(ownerid=marketing_user, createdby=marketing_user, modifiedby=marketing_user)
        payload = {
            'title': 'Case Mkt',
            'customerid': str(acct.accountid),
            'customerid_type': 'account',
            'caseorigincode': 1,
            'ownerid': str(marketing_user.systemuserid),
        }
        resp = marketing_auth_client.post('/api/cases/', payload, content_type='application/json')
        assert resp.status_code == 403

    def test_readonly_cannot_create(self, readonly_auth_client, readonly_user):
        acct = AccountFactory(ownerid=readonly_user, createdby=readonly_user, modifiedby=readonly_user)
        payload = {
            'title': 'Case RO',
            'customerid': str(acct.accountid),
            'customerid_type': 'account',
            'caseorigincode': 1,
            'ownerid': str(readonly_user.systemuserid),
        }
        resp = readonly_auth_client.post('/api/cases/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        case = CaseFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/cases/{case.incidentid}',
            {'title': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_can_update_own(self, auth_client, salesperson):
        case = CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/cases/{case.incidentid}',
            {'title': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_marketing_cannot_update(self, marketing_auth_client, marketing_user):
        """Marketing User does NOT have CASE_UPDATE."""
        case = CaseFactory(ownerid=marketing_user, createdby=marketing_user, modifiedby=marketing_user)
        resp = marketing_auth_client.patch(
            f'/api/cases/{case.incidentid}',
            {'title': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        case = CaseFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/cases/{case.incidentid}',
            {'title': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        case = CaseFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/cases/{case.incidentid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        case = CaseFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/cases/{case.incidentid}').status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        """Salesperson does NOT have CASE_DELETE."""
        case = CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/cases/{case.incidentid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        case = CaseFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/cases/{case.incidentid}').status_code == 403


# ===========================================================================
# 10. ACTIVITY PERMISSIONS
# ===========================================================================

@pytest.mark.permissions
@pytest.mark.django_db
class TestActivityPermissions:
    """Test RBAC for Activity entity across all 5 roles + unauthenticated."""

    # -- LIST ---------------------------------------------------------------

    def test_admin_can_list(self, admin_auth_client):
        assert admin_auth_client.get('/api/activities/').status_code == 200

    def test_manager_can_list(self, manager_auth_client):
        assert manager_auth_client.get('/api/activities/').status_code == 200

    def test_salesperson_can_list(self, auth_client):
        assert auth_client.get('/api/activities/').status_code == 200

    def test_marketing_can_list(self, marketing_auth_client):
        """Marketing User has ACTIVITY_READ."""
        assert marketing_auth_client.get('/api/activities/').status_code == 200

    def test_readonly_can_list(self, readonly_auth_client):
        assert readonly_auth_client.get('/api/activities/').status_code == 200

    def test_anon_cannot_list(self, anon_client):
        assert anon_client.get('/api/activities/').status_code == 403

    # -- CREATE -------------------------------------------------------------

    def test_admin_can_create(self, admin_auth_client, system_admin):
        payload = {
            'activitytypecode': 3,
            'subject': 'Admin Task',
            'ownerid': str(system_admin.systemuserid),
        }
        resp = admin_auth_client.post('/api/activities/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_manager_can_create(self, manager_auth_client, sales_manager):
        payload = {
            'activitytypecode': 3,
            'subject': 'Manager Task',
            'ownerid': str(sales_manager.systemuserid),
        }
        resp = manager_auth_client.post('/api/activities/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_salesperson_can_create(self, auth_client, salesperson):
        payload = {
            'activitytypecode': 3,
            'subject': 'Sales Task',
            'ownerid': str(salesperson.systemuserid),
        }
        resp = auth_client.post('/api/activities/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_marketing_can_create(self, marketing_auth_client, marketing_user):
        """Marketing User has ACTIVITY_CREATE."""
        payload = {
            'activitytypecode': 3,
            'subject': 'Marketing Task',
            'ownerid': str(marketing_user.systemuserid),
        }
        resp = marketing_auth_client.post('/api/activities/', payload, content_type='application/json')
        assert resp.status_code == 201

    def test_readonly_cannot_create(self, readonly_auth_client, readonly_user):
        payload = {
            'activitytypecode': 3,
            'subject': 'RO Task',
            'ownerid': str(readonly_user.systemuserid),
        }
        resp = readonly_auth_client.post('/api/activities/', payload, content_type='application/json')
        assert resp.status_code == 403

    # -- UPDATE -------------------------------------------------------------

    def test_admin_can_update(self, admin_auth_client, system_admin):
        activity = ActivityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = admin_auth_client.patch(
            f'/api/activities/{activity.activityid}',
            {'subject': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_salesperson_can_update_own(self, auth_client, salesperson):
        activity = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        resp = auth_client.patch(
            f'/api/activities/{activity.activityid}',
            {'subject': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_marketing_can_update(self, marketing_auth_client, marketing_user):
        """Marketing User has ACTIVITY_UPDATE."""
        activity = ActivityFactory(ownerid=marketing_user, createdby=marketing_user, modifiedby=marketing_user)
        resp = marketing_auth_client.patch(
            f'/api/activities/{activity.activityid}',
            {'subject': 'Updated'},
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_readonly_cannot_update(self, readonly_auth_client, system_admin):
        activity = ActivityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        resp = readonly_auth_client.patch(
            f'/api/activities/{activity.activityid}',
            {'subject': 'Hacked'},
            content_type='application/json',
        )
        assert resp.status_code == 403

    # -- DELETE -------------------------------------------------------------

    def test_admin_can_delete(self, admin_auth_client, system_admin):
        activity = ActivityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert admin_auth_client.delete(f'/api/activities/{activity.activityid}').status_code == 204

    def test_manager_can_delete(self, manager_auth_client, sales_manager):
        activity = ActivityFactory(ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)
        assert manager_auth_client.delete(f'/api/activities/{activity.activityid}').status_code == 204

    def test_salesperson_can_delete(self, auth_client, salesperson):
        """Salesperson HAS ACTIVITY_DELETE (exception to usual pattern)."""
        activity = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert auth_client.delete(f'/api/activities/{activity.activityid}').status_code == 204

    def test_marketing_cannot_delete(self, marketing_auth_client, marketing_user):
        """Marketing User does NOT have ACTIVITY_DELETE."""
        activity = ActivityFactory(ownerid=marketing_user, createdby=marketing_user, modifiedby=marketing_user)
        assert marketing_auth_client.delete(f'/api/activities/{activity.activityid}').status_code == 403

    def test_readonly_cannot_delete(self, readonly_auth_client, system_admin):
        activity = ActivityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        assert readonly_auth_client.delete(f'/api/activities/{activity.activityid}').status_code == 403
