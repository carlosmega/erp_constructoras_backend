"""Router tests for Project Management API endpoints (Operations Module)."""

import uuid
import pytest
from apps.projects.tests.factories import (
    ConstructionProjectFactory, ActiveProjectFactory,
    ProjectZoneFactory, ProjectSupplierFactory, ProjectTeamMemberFactory,
)
from apps.accounts.tests.factories import AccountFactory


@pytest.mark.contract
class TestListProjects:
    def test_returns_200(self, auth_client, salesperson):
        ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/projects/')
        assert response.status_code == 200
        assert len(response.json()) >= 1


@pytest.mark.contract
class TestCreateProject:
    def test_creates_project(self, auth_client, salesperson):
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'name': 'Highway Bridge Project',
            'accountid': str(account.accountid),
            'startdate': '2026-04-01',
            'contractenddate': '2027-03-31',
            'durationmonths': 12,
            'projecttype': 0,
            'biddingtype': 0,
            'contractamount_notax': '1500000.00',
            'contractamount_withtax': '1740000.00',
        }
        response = auth_client.post('/api/projects/', payload, content_type='application/json')
        assert response.status_code == 201


@pytest.mark.contract
class TestGetProject:
    def test_returns_project(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/projects/{project.projectid}')
        assert response.status_code == 200

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/projects/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateProject:
    def test_updates_project(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/projects/{project.projectid}',
            {'name': 'Updated Project'},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestDeleteProject:
    def test_deletes_project(self, admin_auth_client, system_admin):
        project = ConstructionProjectFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/projects/{project.projectid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestSearchProjects:
    def test_search_projects(self, auth_client, salesperson):
        ConstructionProjectFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
            name='Alpha Bridge',
        )
        response = auth_client.get('/api/projects/search/?search=Alpha')
        assert response.status_code == 200


@pytest.mark.contract
class TestProjectZones:
    def test_list_zones(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        ProjectZoneFactory(projectid=project)
        response = auth_client.get(f'/api/projects/{project.projectid}/zones/')
        assert response.status_code == 200

    def test_create_zone(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'projectid': str(project.projectid),
            'name': 'North Zone',
            'prefix': 'NOR',
        }
        response = auth_client.post(
            f'/api/projects/{project.projectid}/zones/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_update_zone(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        zone = ProjectZoneFactory(projectid=project)
        response = auth_client.patch(
            f'/api/zones/{zone.zoneid}',
            {'name': 'Updated Zone'},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_delete_zone(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        zone = ProjectZoneFactory(projectid=project)
        response = auth_client.delete(f'/api/zones/{zone.zoneid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestProjectSuppliers:
    def test_list_suppliers(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        ProjectSupplierFactory(projectid=project, accountid=account)
        response = auth_client.get(f'/api/projects/{project.projectid}/suppliers/')
        assert response.status_code == 200

    def test_add_supplier(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'projectid': str(project.projectid),
            'accountid': str(account.accountid),
            'businessname': 'Supplier Co',
            'rfc': 'RFC1234567890',
        }
        response = auth_client.post(
            f'/api/projects/{project.projectid}/suppliers/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_remove_supplier(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        supplier = ProjectSupplierFactory(projectid=project, accountid=account)
        response = auth_client.delete(f'/api/suppliers/{supplier.projectsupplierid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestProjectTeamMembers:
    def test_list_members(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        ProjectTeamMemberFactory(projectid=project)
        response = auth_client.get(f'/api/projects/{project.projectid}/team-members/')
        assert response.status_code == 200

    def test_add_member(self, auth_client, salesperson):
        from apps.users.tests.factories import SalespersonFactory
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        target_user = SalespersonFactory()
        payload = {
            'projectid': str(project.projectid),
            'systemuserid': str(target_user.systemuserid),
            'role': 'SiteEngineer',
        }
        response = auth_client.post(
            f'/api/projects/{project.projectid}/team-members/',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_delete_member(self, auth_client, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        member = ProjectTeamMemberFactory(projectid=project)
        response = auth_client.delete(f'/api/team-members/{member.teammemberid}')
        assert response.status_code == 204
