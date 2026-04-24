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


@pytest.mark.django_db
@pytest.mark.contract
def test_category_get_exposes_defaultpaymentlag(auth_client, salesperson):
    """defaultpaymentlag must be included in CostCategory list responses."""
    from apps.projects.tests.factories import ConstructionProjectFactory
    from apps.budgets.tests.factories import CostCategoryFactory
    project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
    cat = CostCategoryFactory(projectid=project, createdby=salesperson, defaultpaymentlag=3)
    resp = auth_client.get(f'/api/categories/projects/{project.projectid}/categories/')
    assert resp.status_code == 200
    body = resp.json()
    target = next((c for c in body if c.get('categoryid') == str(cat.categoryid)), None)
    assert target is not None, f'Category not found in response; got codes: {[c.get("categoryid") for c in body]}'
    assert target['defaultpaymentlag'] == 3


@pytest.mark.django_db
@pytest.mark.contract
def test_imputationcode_patch_updates_paymentlag(auth_client, salesperson):
    """paymentlagperiods must round-trip through PATCH /api/codes/codes/{id}/."""
    from apps.projects.tests.factories import ConstructionProjectFactory, ProjectZoneFactory
    from apps.budgets.tests.factories import CostCategoryFactory, ImputationCodeFactory
    project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
    zone = ProjectZoneFactory(projectid=project)
    cat = CostCategoryFactory(projectid=project, createdby=salesperson)
    code = ImputationCodeFactory(projectid=project, categoryid=cat, zoneid=zone)
    # Initial state: paymentlagperiods is nullable, typically None
    resp = auth_client.patch(
        f'/api/codes/codes/{code.imputationcodeid}/',
        data={'paymentlagperiods': 2},
        content_type='application/json',
    )
    assert resp.status_code == 200, f'PATCH failed: {resp.status_code} {resp.content.decode() if resp.content else ""}'
    body = resp.json()
    assert body['paymentlagperiods'] == 2


@pytest.mark.django_db
@pytest.mark.contract
def test_imputationcode_get_exposes_paymentlag(auth_client, salesperson):
    """paymentlagperiods must appear in ImputationCode list responses when set."""
    from apps.projects.tests.factories import ConstructionProjectFactory, ProjectZoneFactory
    from apps.budgets.tests.factories import CostCategoryFactory, ImputationCodeFactory
    project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
    zone = ProjectZoneFactory(projectid=project)
    cat = CostCategoryFactory(projectid=project, createdby=salesperson)
    code = ImputationCodeFactory(
        projectid=project, categoryid=cat, zoneid=zone,
        paymentlagperiods=1,
    )
    resp = auth_client.get(f'/api/codes/projects/{project.projectid}/codes/')
    assert resp.status_code == 200
    body = resp.json()
    target = next((c for c in body if c.get('imputationcodeid') == str(code.imputationcodeid)), None)
    assert target is not None
    assert target['paymentlagperiods'] == 1
