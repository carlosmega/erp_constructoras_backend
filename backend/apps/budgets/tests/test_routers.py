"""Router tests for Budget Management API endpoints (Operations Module)."""

import uuid
import pytest
from apps.projects.tests.factories import ConstructionProjectFactory, ProjectZoneFactory
from apps.budgets.tests.factories import (
    CostCategoryFactory, ImputationCodeFactory, ImputationPeriodFactory,
)


@pytest.mark.contract
class TestCostCategories:
    def test_list_categories(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        CostCategoryFactory(projectid=project, createdby=salesperson)
        response = auth_client.get(f'/api/categories/projects/{project.projectid}/categories/')
        assert response.status_code == 200

    def test_create_category(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'projectid': str(project.projectid),
            'costtype': 0,
            'code': 'P99',
            'name': 'Test Category',
        }
        response = auth_client.post(
            f'/api/categories/projects/{project.projectid}/categories/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201


@pytest.mark.contract
class TestImputationCodes:
    def test_list_codes(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        zone = ProjectZoneFactory(projectid=project)
        cat = CostCategoryFactory(projectid=project, createdby=salesperson)
        ImputationCodeFactory(projectid=project, categoryid=cat, zoneid=zone)
        response = auth_client.get(f'/api/codes/projects/{project.projectid}/codes/')
        assert response.status_code == 200

    def test_create_code(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        zone = ProjectZoneFactory(projectid=project)
        cat = CostCategoryFactory(projectid=project, createdby=salesperson)
        payload = {
            'projectid': str(project.projectid),
            'categoryid': str(cat.categoryid),
            'zoneid': str(zone.zoneid),
            'costtype': 0,
            'name': 'Test Imputation Code',
            'totalbudget': '10000.00',
        }
        response = auth_client.post(
            f'/api/codes/projects/{project.projectid}/codes/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_get_code(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        zone = ProjectZoneFactory(projectid=project)
        cat = CostCategoryFactory(projectid=project, createdby=salesperson)
        code = ImputationCodeFactory(projectid=project, categoryid=cat, zoneid=zone)
        response = auth_client.get(f'/api/codes/codes/{code.imputationcodeid}/')
        assert response.status_code == 200

    def test_update_code(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        zone = ProjectZoneFactory(projectid=project)
        cat = CostCategoryFactory(projectid=project, createdby=salesperson)
        code = ImputationCodeFactory(projectid=project, categoryid=cat, zoneid=zone)
        response = auth_client.patch(
            f'/api/codes/codes/{code.imputationcodeid}/',
            {'description': 'Updated Code'},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestImputationPeriods:
    def test_list_periods(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        ImputationPeriodFactory(projectid=project, createdby=salesperson)
        response = auth_client.get(f'/api/periods/projects/{project.projectid}/periods/')
        assert response.status_code == 200

    def test_initialize_periods(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/periods/projects/{project.projectid}/periods/init/',
            {},
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_close_period(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        response = auth_client.patch(f'/api/periods/periods/{period.periodid}/close/')
        assert response.status_code == 200

    def test_reopen_period(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson, statecode=1)
        response = auth_client.patch(f'/api/periods/periods/{period.periodid}/reopen/')
        assert response.status_code == 200
