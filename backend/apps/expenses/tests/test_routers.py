"""Router tests for Expense Management API endpoints (Operations Module)."""

import uuid
import pytest
from apps.projects.tests.factories import ConstructionProjectFactory, ProjectZoneFactory
from apps.budgets.tests.factories import (
    CostCategoryFactory, ImputationCodeFactory, ImputationPeriodFactory,
)
from apps.expenses.tests.factories import (
    ProjectExpenseFactory, ExpenseLineFactory, ExpenseAttachmentFactory,
    ClientEstimateFactory,
)


@pytest.mark.contract
class TestListExpenses:
    def test_returns_200(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        ProjectExpenseFactory(projectid=project, periodid=period, ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/expenses/projects/{project.projectid}/expenses/')
        assert response.status_code == 200


@pytest.mark.contract
class TestListExpensesPaginated:
    """Offset-based paginated listing (opt-in; legacy endpoint unchanged)."""

    def _setup(self, salesperson, count=3):
        project = ConstructionProjectFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        for _ in range(count):
            ProjectExpenseFactory(
                projectid=project, periodid=period,
                ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
            )
        return project

    def test_returns_paginated_shape(self, auth_client, salesperson):
        project = self._setup(salesperson, count=3)

        response = auth_client.get(
            f'/api/expenses/projects/{project.projectid}/expenses/paginated/?page=1&page_size=2'
        )
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 3
        assert body['page'] == 1
        assert body['page_size'] == 2
        assert len(body['results']) == 2
        assert body['next'] is not None
        assert body['previous'] is None

    def test_second_page(self, auth_client, salesperson):
        project = self._setup(salesperson, count=3)

        response = auth_client.get(
            f'/api/expenses/projects/{project.projectid}/expenses/paginated/?page=2&page_size=2'
        )
        body = response.json()
        assert len(body['results']) == 1
        assert body['next'] is None
        assert body['previous'] is not None

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        fake_id = uuid.uuid4()
        response = Client().get(f'/api/expenses/projects/{fake_id}/expenses/paginated/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateExpense:
    def test_creates_expense(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        payload = {
            'projectid': str(project.projectid),
            'periodid': str(period.periodid),
            'documenttype': 0,
            'suppliername': 'Supplier ABC',
            'subtotal': '1000.00',
            'taxamount': '160.00',
            'netamount': '1160.00',
        }
        response = auth_client.post(
            f'/api/expenses/projects/{project.projectid}/expenses/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201


@pytest.mark.contract
class TestGetExpense:
    def test_returns_expense(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        response = auth_client.get(f'/api/expenses/expenses/{expense.expenseid}/')
        assert response.status_code == 200


@pytest.mark.contract
class TestUpdateExpense:
    def test_updates_expense(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        response = auth_client.patch(
            f'/api/expenses/expenses/{expense.expenseid}/',
            {'suppliername': 'Updated Supplier'},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestCancelExpense:
    def test_cancels_expense(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        period = ImputationPeriodFactory(projectid=project, createdby=system_admin)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.patch(f'/api/expenses/expenses/{expense.expenseid}/cancel/')
        assert response.status_code == 200


@pytest.mark.contract
class TestExpenseClassification:
    def test_classify_expense(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        zone = ProjectZoneFactory(projectid=project)
        cat = CostCategoryFactory(projectid=project, createdby=salesperson)
        code = ImputationCodeFactory(projectid=project, categoryid=cat, zoneid=zone)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        payload = {'imputationcodeid': str(code.imputationcodeid)}
        response = auth_client.post(
            f'/api/expenses/expenses/{expense.expenseid}/classify/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_list_unclassified(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/expenses/projects/{project.projectid}/expenses/unclassified/')
        assert response.status_code == 200


@pytest.mark.contract
class TestExpenseVerification:
    def test_verify_expense(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        period = ImputationPeriodFactory(projectid=project, createdby=system_admin)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.patch(
            f'/api/expenses/expenses/{expense.expenseid}/verify/',
            {'verificationstatus': 1},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestExpenseSummary:
    def test_returns_summary(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/expenses/projects/{project.projectid}/expenses/summary/')
        assert response.status_code == 200


@pytest.mark.contract
class TestClassificationLogs:
    def test_list_logs(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        response = auth_client.get(f'/api/expenses/expenses/{expense.expenseid}/logs/')
        assert response.status_code == 200


@pytest.mark.contract
class TestExpenseLines:
    def test_list_lines(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        ExpenseLineFactory(expenseid=expense)
        response = auth_client.get(f'/api/expense-lines/expenses/{expense.expenseid}/lines/')
        assert response.status_code == 200

    def test_add_line(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        payload = {
            'description': 'Concrete bags',
            'quantity': 50,
            'unitprice': '25.00',
        }
        response = auth_client.post(
            f'/api/expense-lines/expenses/{expense.expenseid}/lines/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_delete_line(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        period = ImputationPeriodFactory(projectid=project, createdby=system_admin)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        line = ExpenseLineFactory(expenseid=expense)
        response = admin_auth_client.delete(f'/api/expense-lines/expense-lines/{line.expenselineid}/')
        assert response.status_code == 204


@pytest.mark.contract
class TestExpenseAttachments:
    def test_list_attachments(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        ExpenseAttachmentFactory(expenseid=expense)
        response = auth_client.get(f'/api/attachments/expenses/{expense.expenseid}/attachments/')
        assert response.status_code == 200


@pytest.mark.contract
class TestClientEstimates:
    def test_list_estimates(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        ClientEstimateFactory(projectid=project, createdby=salesperson)
        response = auth_client.get(f'/api/estimates/projects/{project.projectid}/estimates/')
        assert response.status_code == 200

    def test_create_estimate(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        payload = {
            'projectid': str(project.projectid),
            'periodid': str(period.periodid),
            'estimatetype': 0,
            'estimatedamount': '100000.00',
        }
        response = auth_client.post(
            f'/api/estimates/projects/{project.projectid}/estimates/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_delete_estimate(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        estimate = ClientEstimateFactory(projectid=project, createdby=system_admin)
        response = admin_auth_client.delete(f'/api/estimates/estimates/{estimate.estimateid}/')
        assert response.status_code == 204
