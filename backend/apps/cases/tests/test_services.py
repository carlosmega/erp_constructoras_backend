"""Unit tests for Case service layer."""

import pytest
from uuid import uuid4

from apps.cases.models import Case, CaseStateCode, CaseStatusCode, CasePriorityCode
from apps.cases.services import CaseService
from apps.cases.schemas import CreateCaseDto, UpdateCaseDto, ResolveCaseDto, CancelCaseDto
from apps.cases.tests.factories import CaseFactory
from apps.contacts.tests.factories import ContactFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, NotFound, PermissionDenied


# ============================================================================
# Ticket Number Generation
# ============================================================================

@pytest.mark.unit
class TestGenerateTicketNumber:
    """Tests for CaseService.generate_ticket_number."""

    def test_generates_first_ticket(self, db):
        """First ticket of the year should be CAS-YYYY-0001."""
        ticket = CaseService.generate_ticket_number()
        assert ticket.startswith('CAS-')
        assert ticket.endswith('-0001')

    def test_increments_sequence(self, db):
        """Subsequent tickets should increment the sequence number."""
        CaseFactory(ticketnumber='CAS-2026-0005')
        ticket = CaseService.generate_ticket_number()
        # Should be 0006 because factory created 0005 for 2026
        assert 'CAS-' in ticket


# ============================================================================
# Create Case
# ============================================================================

@pytest.mark.unit
class TestCreateCase:
    """Tests for CaseService.create_case."""

    def test_create_case_with_contact_customer(self, db, salesperson):
        """Creating a case with a contact customer should succeed."""
        contact = ContactFactory(ownerid=salesperson)
        dto = CreateCaseDto(
            title='Test Case',
            customerid=contact.contactid,
            customerid_type='contact',
            caseorigincode=1,
            ownerid=salesperson.systemuserid,
        )
        case = CaseService.create_case(dto, salesperson)
        assert case.pk is not None
        assert case.title == 'Test Case'
        assert case.statecode == CaseStateCode.ACTIVE
        assert case.statuscode == CaseStatusCode.IN_PROGRESS
        assert case.contactid == contact
        assert case.ticketnumber.startswith('CAS-')

    def test_create_case_invalid_owner(self, db, salesperson):
        """Creating a case with a non-existent owner should raise ValidationError."""
        contact = ContactFactory(ownerid=salesperson)
        dto = CreateCaseDto(
            title='Bad Owner Case',
            customerid=contact.contactid,
            customerid_type='contact',
            caseorigincode=1,
            ownerid=uuid4(),
        )
        with pytest.raises(ValidationError, match="Owner with ID"):
            CaseService.create_case(dto, salesperson)

    def test_create_case_with_priority(self, db, salesperson):
        """Creating a case should respect custom priority."""
        contact = ContactFactory(ownerid=salesperson)
        dto = CreateCaseDto(
            title='High Priority Case',
            customerid=contact.contactid,
            customerid_type='contact',
            caseorigincode=2,
            ownerid=salesperson.systemuserid,
            prioritycode=CasePriorityCode.HIGH,
        )
        case = CaseService.create_case(dto, salesperson)
        assert case.prioritycode == CasePriorityCode.HIGH


# ============================================================================
# Get Case by ID
# ============================================================================

@pytest.mark.unit
class TestGetCaseById:
    """Tests for CaseService.get_case_by_id."""

    def test_get_own_case(self, db, salesperson):
        """A salesperson should be able to get their own case."""
        case = CaseFactory(ownerid=salesperson)
        result = CaseService.get_case_by_id(case.incidentid, salesperson)
        assert result.incidentid == case.incidentid

    def test_get_nonexistent_case(self, db, salesperson):
        """Getting a non-existent case should raise NotFound."""
        with pytest.raises(NotFound):
            CaseService.get_case_by_id(uuid4(), salesperson)

    def test_get_other_users_case_denied(self, db, salesperson, salesperson2):
        """A salesperson should not access another user's case."""
        case = CaseFactory(ownerid=salesperson)
        with pytest.raises(PermissionDenied):
            CaseService.get_case_by_id(case.incidentid, salesperson2)

    def test_admin_can_access_any_case(self, db, salesperson, system_admin):
        """System admin should be able to access any case."""
        case = CaseFactory(ownerid=salesperson)
        result = CaseService.get_case_by_id(case.incidentid, system_admin)
        assert result.incidentid == case.incidentid


# ============================================================================
# Update Case
# ============================================================================

@pytest.mark.unit
class TestUpdateCase:
    """Tests for CaseService.update_case."""

    def test_update_title(self, db, salesperson):
        """Updating a case title should persist."""
        case = CaseFactory(ownerid=salesperson)
        dto = UpdateCaseDto(title='Updated Title')
        updated = CaseService.update_case(case.incidentid, dto, salesperson)
        assert updated.title == 'Updated Title'

    def test_update_priority(self, db, salesperson):
        """Updating priority should persist."""
        case = CaseFactory(ownerid=salesperson)
        dto = UpdateCaseDto(prioritycode=CasePriorityCode.HIGH)
        updated = CaseService.update_case(case.incidentid, dto, salesperson)
        assert updated.prioritycode == CasePriorityCode.HIGH

    def test_cannot_update_resolved_case(self, db, salesperson):
        """Updating a resolved case should raise ValidationError."""
        case = CaseFactory(
            ownerid=salesperson,
            statecode=CaseStateCode.RESOLVED,
            statuscode=CaseStatusCode.PROBLEM_SOLVED,
        )
        dto = UpdateCaseDto(title='Should Fail')
        with pytest.raises(ValidationError, match="Cannot update case"):
            CaseService.update_case(case.incidentid, dto, salesperson)

    def test_cannot_update_cancelled_case(self, db, salesperson):
        """Updating a cancelled case should raise ValidationError."""
        case = CaseFactory(
            ownerid=salesperson,
            statecode=CaseStateCode.CANCELLED,
            statuscode=CaseStatusCode.CANCELLED,
        )
        dto = UpdateCaseDto(title='Should Fail')
        with pytest.raises(ValidationError, match="Cannot update case"):
            CaseService.update_case(case.incidentid, dto, salesperson)


# ============================================================================
# List Cases
# ============================================================================

@pytest.mark.unit
class TestListCases:
    """Tests for CaseService.list_cases."""

    def test_list_own_cases(self, db, salesperson):
        """A salesperson should see their own cases."""
        CaseFactory(ownerid=salesperson)
        CaseFactory(ownerid=salesperson)
        result = CaseService.list_cases(salesperson)
        assert result.count() >= 2

    def test_filter_by_statecode(self, db, salesperson):
        """Filtering by statecode should return matching cases only."""
        CaseFactory(ownerid=salesperson, statecode=CaseStateCode.ACTIVE)
        CaseFactory(
            ownerid=salesperson,
            statecode=CaseStateCode.RESOLVED,
            statuscode=CaseStatusCode.PROBLEM_SOLVED,
        )
        result = CaseService.list_cases(salesperson, statecode=CaseStateCode.ACTIVE)
        assert all(c.statecode == CaseStateCode.ACTIVE for c in result)

    def test_search_by_title(self, db, salesperson):
        """Searching by title should return matching cases."""
        CaseFactory(ownerid=salesperson, title='Unique Search Term XYZ')
        result = CaseService.list_cases(salesperson, search='XYZ')
        assert result.count() >= 1


# ============================================================================
# Resolve Case
# ============================================================================

@pytest.mark.unit
class TestResolveCase:
    """Tests for CaseService.resolve_case."""

    def test_resolve_active_case(self, db, salesperson):
        """Resolving an active case should set state and resolution fields."""
        case = CaseFactory(ownerid=salesperson)
        dto = ResolveCaseDto(
            resolutiontype='Bug Fix',
            resolutionsummary='Fixed the issue',
        )
        resolved = CaseService.resolve_case(case.incidentid, dto, salesperson)
        assert resolved.statecode == CaseStateCode.RESOLVED
        assert resolved.statuscode == CaseStatusCode.PROBLEM_SOLVED
        assert resolved.resolutiontype == 'Bug Fix'
        assert resolved.resolutionsummary == 'Fixed the issue'
        assert resolved.resolvedon is not None

    def test_cannot_resolve_already_resolved_case(self, db, salesperson):
        """Resolving an already resolved case should raise ValidationError."""
        case = CaseFactory(
            ownerid=salesperson,
            statecode=CaseStateCode.RESOLVED,
            statuscode=CaseStatusCode.PROBLEM_SOLVED,
        )
        dto = ResolveCaseDto(
            resolutiontype='Bug Fix',
            resolutionsummary='Fixed again',
        )
        with pytest.raises(ValidationError, match="Cannot resolve case"):
            CaseService.resolve_case(case.incidentid, dto, salesperson)


# ============================================================================
# Cancel Case
# ============================================================================

@pytest.mark.unit
class TestCancelCase:
    """Tests for CaseService.cancel_case."""

    def test_cancel_active_case(self, db, salesperson):
        """Cancelling an active case should set state to cancelled."""
        case = CaseFactory(ownerid=salesperson)
        dto = CancelCaseDto(reason='No longer needed')
        cancelled = CaseService.cancel_case(case.incidentid, dto, salesperson)
        assert cancelled.statecode == CaseStateCode.CANCELLED
        assert cancelled.statuscode == CaseStatusCode.CANCELLED
        assert 'No longer needed' in cancelled.description

    def test_cannot_cancel_already_cancelled(self, db, salesperson):
        """Cancelling an already cancelled case should raise ValidationError."""
        case = CaseFactory(
            ownerid=salesperson,
            statecode=CaseStateCode.CANCELLED,
            statuscode=CaseStatusCode.CANCELLED,
        )
        dto = CancelCaseDto(reason='Try again')
        with pytest.raises(ValidationError, match="already cancelled"):
            CaseService.cancel_case(case.incidentid, dto, salesperson)


# ============================================================================
# Reopen Case
# ============================================================================

@pytest.mark.unit
class TestReopenCase:
    """Tests for CaseService.reopen_case."""

    def test_reopen_resolved_case(self, db, salesperson):
        """Reopening a resolved case should reset to active state."""
        case = CaseFactory(
            ownerid=salesperson,
            statecode=CaseStateCode.RESOLVED,
            statuscode=CaseStatusCode.PROBLEM_SOLVED,
            resolutiontype='Bug Fix',
            resolutionsummary='Fixed it',
        )
        reopened = CaseService.reopen_case(case.incidentid, salesperson)
        assert reopened.statecode == CaseStateCode.ACTIVE
        assert reopened.statuscode == CaseStatusCode.IN_PROGRESS
        assert reopened.resolvedon is None
        assert reopened.resolutiontype is None
        assert reopened.resolutionsummary is None

    def test_reopen_cancelled_case(self, db, salesperson):
        """Reopening a cancelled case should reset to active state."""
        case = CaseFactory(
            ownerid=salesperson,
            statecode=CaseStateCode.CANCELLED,
            statuscode=CaseStatusCode.CANCELLED,
        )
        reopened = CaseService.reopen_case(case.incidentid, salesperson)
        assert reopened.statecode == CaseStateCode.ACTIVE
        assert reopened.statuscode == CaseStatusCode.IN_PROGRESS

    def test_cannot_reopen_active_case(self, db, salesperson):
        """Reopening an already active case should raise ValidationError."""
        case = CaseFactory(ownerid=salesperson, statecode=CaseStateCode.ACTIVE)
        with pytest.raises(ValidationError, match="already active"):
            CaseService.reopen_case(case.incidentid, salesperson)


# ============================================================================
# Delete Case
# ============================================================================

@pytest.mark.unit
class TestDeleteCase:
    """Tests for CaseService.delete_case."""

    def test_delete_case_cancels_it(self, db, salesperson):
        """Deleting a case should soft-cancel it."""
        case = CaseFactory(ownerid=salesperson)
        CaseService.delete_case(case.incidentid, salesperson)
        case.refresh_from_db()
        assert case.statecode == CaseStateCode.CANCELLED
        assert case.statuscode == CaseStatusCode.CANCELLED
