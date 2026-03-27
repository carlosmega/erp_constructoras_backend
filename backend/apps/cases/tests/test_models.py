"""Unit tests for Case models and enums."""

import pytest
from apps.cases.models import (
    Case,
    CaseStateCode,
    CaseStatusCode,
    CasePriorityCode,
    CaseOriginCode,
    CaseTypeCode,
)
from apps.cases.tests.factories import CaseFactory
from apps.users.tests.factories import SalespersonFactory


# ============================================================================
# Enum Tests
# ============================================================================

@pytest.mark.unit
class TestCaseStateCodeEnum:
    """Tests for CaseStateCode enum values."""

    def test_active_value(self):
        assert CaseStateCode.ACTIVE.value == 0
        assert CaseStateCode.ACTIVE.label == 'Active'

    def test_resolved_value(self):
        assert CaseStateCode.RESOLVED.value == 1
        assert CaseStateCode.RESOLVED.label == 'Resolved'

    def test_cancelled_value(self):
        assert CaseStateCode.CANCELLED.value == 2
        assert CaseStateCode.CANCELLED.label == 'Cancelled'


@pytest.mark.unit
class TestCaseStatusCodeEnum:
    """Tests for CaseStatusCode enum values."""

    def test_in_progress_value(self):
        assert CaseStatusCode.IN_PROGRESS.value == 1
        assert CaseStatusCode.IN_PROGRESS.label == 'In Progress'

    def test_on_hold_value(self):
        assert CaseStatusCode.ON_HOLD.value == 2
        assert CaseStatusCode.ON_HOLD.label == 'On Hold'

    def test_problem_solved_value(self):
        assert CaseStatusCode.PROBLEM_SOLVED.value == 5
        assert CaseStatusCode.PROBLEM_SOLVED.label == 'Problem Solved'

    def test_cancelled_value(self):
        assert CaseStatusCode.CANCELLED.value == 6
        assert CaseStatusCode.CANCELLED.label == 'Cancelled'

    def test_information_provided_value(self):
        assert CaseStatusCode.INFORMATION_PROVIDED.value == 1000

    def test_merged_value(self):
        assert CaseStatusCode.MERGED.value == 2000


@pytest.mark.unit
class TestCasePriorityCodeEnum:
    """Tests for CasePriorityCode enum values."""

    def test_high_value(self):
        assert CasePriorityCode.HIGH.value == 1

    def test_normal_value(self):
        assert CasePriorityCode.NORMAL.value == 2

    def test_low_value(self):
        assert CasePriorityCode.LOW.value == 3


@pytest.mark.unit
class TestCaseOriginCodeEnum:
    """Tests for CaseOriginCode enum values."""

    def test_phone_value(self):
        assert CaseOriginCode.PHONE.value == 1

    def test_email_value(self):
        assert CaseOriginCode.EMAIL.value == 2

    def test_web_value(self):
        assert CaseOriginCode.WEB.value == 3


@pytest.mark.unit
class TestCaseTypeCodeEnum:
    """Tests for CaseTypeCode enum values."""

    def test_question_value(self):
        assert CaseTypeCode.QUESTION.value == 1

    def test_problem_value(self):
        assert CaseTypeCode.PROBLEM.value == 2

    def test_request_value(self):
        assert CaseTypeCode.REQUEST.value == 3


# ============================================================================
# Model Tests
# ============================================================================

@pytest.mark.unit
class TestCaseModel:
    """Tests for Case model creation and properties."""

    def test_create_minimal(self, db):
        """Create a case with only required fields."""
        owner = SalespersonFactory()
        case = Case.objects.create(
            title='Test Case',
            ticketnumber='CAS-2026-0001',
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )
        assert case.pk is not None
        assert case.statecode == CaseStateCode.ACTIVE
        assert case.statuscode == CaseStatusCode.IN_PROGRESS
        assert case.prioritycode == CasePriorityCode.NORMAL

    def test_factory(self, db):
        """CaseFactory should create a valid case."""
        case = CaseFactory()
        assert case.pk is not None
        assert case.title is not None
        assert case.ticketnumber is not None
        assert case.ownerid is not None

    def test_str_representation(self, db):
        """String representation should include ticket number and title."""
        case = CaseFactory(title='Login issue', ticketnumber='CAS-2026-0042')
        assert str(case) == 'CAS-2026-0042 - Login issue'

    def test_is_active_property(self, db):
        """is_active should be True for active cases."""
        case = CaseFactory(statecode=CaseStateCode.ACTIVE)
        assert case.is_active is True
        assert case.is_resolved is False
        assert case.is_cancelled is False

    def test_is_resolved_property(self, db):
        """is_resolved should be True for resolved cases."""
        case = CaseFactory(
            statecode=CaseStateCode.RESOLVED,
            statuscode=CaseStatusCode.PROBLEM_SOLVED,
        )
        assert case.is_resolved is True
        assert case.is_active is False

    def test_is_cancelled_property(self, db):
        """is_cancelled should be True for cancelled cases."""
        case = CaseFactory(
            statecode=CaseStateCode.CANCELLED,
            statuscode=CaseStatusCode.CANCELLED,
        )
        assert case.is_cancelled is True
        assert case.is_active is False

    def test_state_name_property(self, db):
        """state_name should return human-readable label."""
        case = CaseFactory(statecode=CaseStateCode.ACTIVE)
        assert case.state_name == 'Active'

    def test_status_name_property(self, db):
        """status_name should return human-readable label."""
        case = CaseFactory(statuscode=CaseStatusCode.IN_PROGRESS)
        assert case.status_name == 'In Progress'

    def test_priority_name_property(self, db):
        """priority_name should return human-readable label."""
        case = CaseFactory(prioritycode=CasePriorityCode.HIGH)
        assert case.priority_name == 'High'

    def test_origin_name_property_with_value(self, db):
        """origin_name should return label when set."""
        case = CaseFactory(caseorigincode=CaseOriginCode.EMAIL)
        assert case.origin_name == 'Email'

    def test_origin_name_property_none(self, db):
        """origin_name should return None when not set."""
        case = CaseFactory(caseorigincode=None)
        assert case.origin_name is None

    def test_type_name_property_with_value(self, db):
        """type_name should return label when set."""
        case = CaseFactory(casetypecode=CaseTypeCode.PROBLEM)
        assert case.type_name == 'Problem'

    def test_type_name_property_none(self, db):
        """type_name should return None when not set."""
        case = CaseFactory(casetypecode=None)
        assert case.type_name is None

    def test_customer_name_no_customer(self, db):
        """customer_name should return None when no customer linked."""
        case = CaseFactory(accountid=None, contactid=None)
        assert case.customer_name is None

    def test_default_ordering(self, db):
        """Cases should be ordered by -createdon by default."""
        assert Case._meta.ordering == ['-createdon']

    def test_db_table_name(self):
        """DB table should be 'incident' per CDS naming."""
        assert Case._meta.db_table == 'incident'
