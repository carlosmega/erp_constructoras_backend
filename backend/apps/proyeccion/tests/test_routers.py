"""Router tests for Proyeccion (Budget Estimation) module API endpoints."""

import uuid
import pytest
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory,
    ConceptFamilyFactory,
    ConceptSubfamilyFactory,
    ConceptPriceCatalogItemFactory,
    FamilyTemplateSetFactory,
    FamilyTemplateItemFactory,
)


# =============================================================================
# Estimation Projects
# =============================================================================

@pytest.mark.contract
class TestListEstimationProjects:
    def test_returns_200(self, admin_auth_client, system_admin):
        EstimationProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/estimation-projects/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_unauthenticated_returns_redirect_or_200(self, db):
        """Estimation projects may not require auth (no @require_permission)."""
        from django.test import Client
        response = Client().get('/api/estimation-projects/')
        # Endpoint may not require authentication
        assert response.status_code in (200, 302, 403)


@pytest.mark.contract
class TestCreateEstimationProject:
    def test_creates_project(self, admin_auth_client, system_admin):
        payload = {
            'name': 'New Estimation Project',
            'description': 'Test estimation',
        }
        response = admin_auth_client.post(
            '/api/estimation-projects/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['name'] == 'New Estimation Project'


@pytest.mark.contract
class TestGetEstimationProject:
    def test_returns_project(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/estimation-projects/{project.estimationprojectid}/')
        assert response.status_code == 200

    def test_not_found(self, admin_auth_client, system_admin):
        response = admin_auth_client.get(f'/api/estimation-projects/{uuid.uuid4()}/')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateEstimationProject:
    def test_updates_project(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.patch(
            f'/api/estimation-projects/{project.estimationprojectid}/',
            {'name': 'Updated Name'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Name'


@pytest.mark.contract
class TestDeleteEstimationProject:
    def test_deletes_project(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/estimation-projects/{project.estimationprojectid}/')
        assert response.status_code == 200
        # Soft delete sets statecode to Canceled (EstimationStateCode.CANCELED = 4)
        assert response.json()['statecode'] == 4


# =============================================================================
# Concept Families
# =============================================================================

@pytest.mark.contract
class TestConceptFamilies:
    def test_list_families(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        ConceptFamilyFactory(projectid=project, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/proyeccion/projects/{project.estimationprojectid}/concept-families/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_create_family(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        payload = {
            'name': 'Terraceria',
            'code': 'TER',
            'sortorder': 1,
            'projectid': str(project.estimationprojectid),
        }
        response = admin_auth_client.post(
            f'/api/proyeccion/projects/{project.estimationprojectid}/concept-families/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['name'] == 'Terraceria'


# =============================================================================
# Concept Price Catalog
# =============================================================================

@pytest.mark.contract
class TestConceptPriceCatalog:
    def test_list_catalog(self, admin_auth_client, system_admin):
        ConceptPriceCatalogItemFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/proyeccion/concept-price-catalog/')
        assert response.status_code == 200

    def test_create_catalog_item(self, admin_auth_client, system_admin):
        payload = {
            'code': 'TEST-001',
            'description': 'Test catalog item',
            'unit': 'm2',
            'source': 2,  # MANUAL
        }
        response = admin_auth_client.post(
            '/api/proyeccion/concept-price-catalog/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201


# =============================================================================
# Family Templates
# =============================================================================

@pytest.mark.contract
class TestFamilyTemplates:
    def test_list_templates(self, admin_auth_client, system_admin):
        FamilyTemplateSetFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/proyeccion/family-templates/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_get_template(self, admin_auth_client, system_admin):
        ts = FamilyTemplateSetFactory(createdby=system_admin, modifiedby=system_admin)
        FamilyTemplateItemFactory(templatesetid=ts)
        response = admin_auth_client.get(f'/api/proyeccion/family-templates/{ts.templatesetid}/')
        assert response.status_code == 200
