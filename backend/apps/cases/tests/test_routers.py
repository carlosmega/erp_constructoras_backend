"""Router tests for Case Management API endpoints."""

import uuid
import pytest
from apps.cases.tests.factories import CaseFactory
from apps.accounts.tests.factories import AccountFactory


@pytest.mark.contract
class TestListCases:
    def test_returns_200(self, auth_client, salesperson):
        CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/cases/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/cases/?statecode=0')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/cases/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateCase:
    def test_creates_case(self, auth_client, salesperson):
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'title': 'Login Issue',
            'description': 'Cannot login to portal',
            'customerid': str(account.accountid),
            'customerid_type': 'account',
            'caseorigincode': 1,
            'ownerid': str(salesperson.systemuserid),
        }
        response = auth_client.post('/api/cases/', payload, content_type='application/json')
        assert response.status_code == 201
        assert response.json()['title'] == 'Login Issue'

    def test_readonly_denied(self, readonly_auth_client, readonly_user):
        account = AccountFactory(ownerid=readonly_user, createdby=readonly_user, modifiedby=readonly_user)
        payload = {
            'title': 'Blocked',
            'customerid': str(account.accountid),
            'customerid_type': 'account',
            'caseorigincode': 1,
            'ownerid': str(readonly_user.systemuserid),
        }
        response = readonly_auth_client.post('/api/cases/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetCase:
    def test_returns_case(self, auth_client, salesperson):
        case = CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/cases/{case.incidentid}')
        assert response.status_code == 200
        assert response.json()['incidentid'] == str(case.incidentid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/cases/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateCase:
    def test_updates_case(self, auth_client, salesperson):
        case = CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/cases/{case.incidentid}',
            {'title': 'Updated Case'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['title'] == 'Updated Case'


@pytest.mark.contract
class TestDeleteCase:
    def test_deletes_case(self, admin_auth_client, system_admin):
        case = CaseFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/cases/{case.incidentid}')
        assert response.status_code == 204

    def test_readonly_cannot_delete(self, readonly_auth_client, readonly_user):
        case = CaseFactory(ownerid=readonly_user, createdby=readonly_user, modifiedby=readonly_user)
        response = readonly_auth_client.delete(f'/api/cases/{case.incidentid}')
        assert response.status_code == 403


@pytest.mark.contract
class TestCaseActions:
    def test_resolve_case(self, auth_client, salesperson):
        case = CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/cases/{case.incidentid}/resolve',
            {'resolutiontype': 'Problem Solved', 'resolutionsummary': 'Fixed the issue'},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_cancel_case(self, auth_client, salesperson):
        case = CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/cases/{case.incidentid}/cancel',
            {'reason': 'Duplicate'},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_reopen_case(self, auth_client, salesperson):
        from apps.cases.models import CaseStateCode, CaseStatusCode
        case = CaseFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
            statecode=CaseStateCode.RESOLVED, statuscode=CaseStatusCode.PROBLEM_SOLVED,
        )
        response = auth_client.post(f'/api/cases/{case.incidentid}/reopen')
        assert response.status_code == 200
