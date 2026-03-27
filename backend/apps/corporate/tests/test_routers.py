"""Router tests for Corporate module API endpoints."""

import uuid
import pytest
from apps.corporate.tests.factories import (
    CorporateBudgetFactory,
    ApprovedBudgetFactory,
    CorporateBudgetVersionFactory,
    CorporateBudgetLineFactory,
    CorporateExpenseFactory,
    CorporateAllocationFactory,
    WhatIfSimulationFactory,
)


# =============================================================================
# Budget CRUD
# =============================================================================

@pytest.mark.contract
class TestListCorporateBudgets:
    def test_returns_200(self, admin_auth_client, system_admin):
        CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/corporate/budgets/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_filter_by_fiscal_year(self, admin_auth_client, system_admin):
        CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin, fiscalyear=2030)
        response = admin_auth_client.get('/api/corporate/budgets/?fiscal_year=2030')
        assert response.status_code == 200
        data = response.json()
        assert all(item['fiscalyear'] == 2030 for item in data)

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/corporate/budgets/')
        assert response.status_code == 403

    def test_readonly_can_read(self, readonly_auth_client, readonly_user):
        CorporateBudgetFactory()
        response = readonly_auth_client.get('/api/corporate/budgets/')
        assert response.status_code == 200


@pytest.mark.contract
class TestCreateCorporateBudget:
    def test_creates_budget(self, admin_auth_client, system_admin):
        payload = {
            'fiscalyear': 2099,
            'name': 'Test Budget 2099',
            'description': 'Test description',
            'currency': 'MXN',
        }
        response = admin_auth_client.post(
            '/api/corporate/budgets/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201
        data = response.json()
        assert data['name'] == 'Test Budget 2099'
        assert data['fiscalyear'] == 2099

    def test_readonly_denied(self, readonly_auth_client):
        payload = {'fiscalyear': 2099, 'name': 'Blocked'}
        response = readonly_auth_client.post(
            '/api/corporate/budgets/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 403


@pytest.mark.contract
class TestGetCorporateBudget:
    def test_returns_budget(self, admin_auth_client, system_admin):
        budget = CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/corporate/budgets/{budget.corporatebudgetid}/')
        assert response.status_code == 200
        assert response.json()['corporatebudgetid'] == str(budget.corporatebudgetid)

    def test_not_found(self, admin_auth_client, system_admin):
        response = admin_auth_client.get(f'/api/corporate/budgets/{uuid.uuid4()}/')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateCorporateBudget:
    def test_updates_budget(self, admin_auth_client, system_admin):
        budget = CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.patch(
            f'/api/corporate/budgets/{budget.corporatebudgetid}/',
            {'name': 'Updated Name'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Name'


@pytest.mark.contract
class TestApproveCorporateBudget:
    def test_approve_budget(self, admin_auth_client, system_admin):
        budget = CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        # Create a version with lines so approval can compute totals
        version = CorporateBudgetVersionFactory(
            corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin,
        )
        CorporateBudgetLineFactory(versionid=version, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.post(f'/api/corporate/budgets/{budget.corporatebudgetid}/approve/')
        assert response.status_code == 200
        assert response.json()['statecode'] == 1  # APPROVED


# =============================================================================
# Budget Versions
# =============================================================================

@pytest.mark.contract
class TestBudgetVersions:
    def test_list_versions(self, admin_auth_client, system_admin):
        budget = CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        CorporateBudgetVersionFactory(corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/corporate/budgets/{budget.corporatebudgetid}/versions/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_create_version(self, admin_auth_client, system_admin):
        budget = CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        # Need an existing active version to copy from
        CorporateBudgetVersionFactory(
            corporatebudgetid=budget, versionnumber=1,
            createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.post(
            f'/api/corporate/budgets/{budget.corporatebudgetid}/versions/',
            {'label': 'V2 - Revised'},
            content_type='application/json',
        )
        assert response.status_code == 201


# =============================================================================
# Budget Lines
# =============================================================================

@pytest.mark.contract
class TestBudgetLines:
    def test_get_budget_lines(self, admin_auth_client, system_admin):
        budget = CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        version = CorporateBudgetVersionFactory(
            corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin,
        )
        CorporateBudgetLineFactory(versionid=version, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/corporate/budgets/{budget.corporatebudgetid}/lines/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_update_budget_line(self, admin_auth_client, system_admin):
        budget = CorporateBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        version = CorporateBudgetVersionFactory(
            corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin,
        )
        line = CorporateBudgetLineFactory(versionid=version, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.patch(
            f'/api/corporate/budget-lines/{line.budgetlineid}/',
            {'jan': '100000.00', 'feb': '100000.00'},
            content_type='application/json',
        )
        assert response.status_code == 200


# =============================================================================
# Corporate Expenses
# =============================================================================

@pytest.mark.contract
class TestCorporateExpenses:
    def test_list_expenses(self, admin_auth_client, system_admin):
        budget = ApprovedBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        CorporateExpenseFactory(corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/corporate/budgets/{budget.corporatebudgetid}/expenses/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_record_expense(self, admin_auth_client, system_admin):
        budget = ApprovedBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        # Need version + lines for expense recording
        version = CorporateBudgetVersionFactory(
            corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin,
        )
        CorporateBudgetLineFactory(versionid=version, createdby=system_admin, modifiedby=system_admin)
        payload = {
            'categorycode': '4.1',
            'year': 2026,
            'month': 3,
            'actualamount': '85000.00',
        }
        response = admin_auth_client.post(
            f'/api/corporate/budgets/{budget.corporatebudgetid}/expenses/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_budget_vs_actual(self, admin_auth_client, system_admin):
        budget = ApprovedBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/corporate/budgets/{budget.corporatebudgetid}/budget-vs-actual/')
        assert response.status_code == 200
        data = response.json()
        assert 'rows' in data
        assert 'totalbudgeted' in data


# =============================================================================
# Allocations
# =============================================================================

@pytest.mark.contract
class TestCorporateAllocations:
    def test_list_allocations(self, admin_auth_client, system_admin):
        budget = ApprovedBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        CorporateAllocationFactory(corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(
            f'/api/corporate/allocations/?budget_id={budget.corporatebudgetid}',
        )
        assert response.status_code == 200

    def test_get_allocation(self, admin_auth_client, system_admin):
        budget = ApprovedBudgetFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        allocation = CorporateAllocationFactory(
            corporatebudgetid=budget, createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.get(f'/api/corporate/allocations/{allocation.allocationid}/')
        assert response.status_code == 200

    def test_unauthenticated_allocation_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/corporate/allocations/?budget_id=' + str(uuid.uuid4()))
        assert response.status_code == 403


# =============================================================================
# Portfolio & Capacity
# =============================================================================

@pytest.mark.contract
class TestCorporatePortfolio:
    def test_get_portfolio(self, admin_auth_client, system_admin):
        response = admin_auth_client.get('/api/corporate/portfolio/')
        assert response.status_code == 200
        data = response.json()
        assert 'projects' in data

    def test_get_capacity(self, admin_auth_client, system_admin):
        response = admin_auth_client.get('/api/corporate/capacity/')
        assert response.status_code == 200
        data = response.json()
        assert 'corporatebudgetannual' in data

    def test_get_timeline(self, admin_auth_client, system_admin):
        response = admin_auth_client.get('/api/corporate/timeline/')
        assert response.status_code == 200
        data = response.json()
        assert 'months' in data


# =============================================================================
# Simulations
# =============================================================================

@pytest.mark.contract
class TestCorporateSimulations:
    def test_list_simulations(self, admin_auth_client, system_admin):
        WhatIfSimulationFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/corporate/simulations/')
        assert response.status_code == 200

    def test_create_simulation(self, admin_auth_client, system_admin):
        payload = {
            'name': 'Test Simulation',
            'fiscalyear': 2026,
            'parameters': {},
        }
        response = admin_auth_client.post(
            '/api/corporate/simulations/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['name'] == 'Test Simulation'

    def test_get_simulation(self, admin_auth_client, system_admin):
        sim = WhatIfSimulationFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/corporate/simulations/{sim.simulationid}/')
        assert response.status_code == 200

    def test_delete_simulation(self, admin_auth_client, system_admin):
        sim = WhatIfSimulationFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/corporate/simulations/{sim.simulationid}/')
        assert response.status_code == 204

    def test_readonly_cannot_create_simulation(self, readonly_auth_client):
        payload = {'name': 'Blocked', 'fiscalyear': 2026, 'parameters': {}}
        response = readonly_auth_client.post(
            '/api/corporate/simulations/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 403
