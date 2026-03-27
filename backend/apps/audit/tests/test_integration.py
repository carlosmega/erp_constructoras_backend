"""
Integration tests for @audit_action decorator with real Lead entity.

Verifies that audit log entries are created end-to-end when Lead service
methods are invoked, without mocking the audit layer.
"""

import pytest
from decimal import Decimal
from unittest import mock

from apps.audit.models import AuditLog
from apps.leads.models import Lead
from apps.leads.schemas import CreateLeadDto, UpdateLeadDto, QualifyLeadDto
from apps.leads.services import LeadService
from apps.users.tests.factories import SystemAdminFactory
from core.middleware import set_current_user


@pytest.fixture
def admin_user(db):
    """Create a System Administrator user and set in thread-local."""
    user = SystemAdminFactory(fullname="Admin Auditor")
    set_current_user(user)
    yield user
    set_current_user(None)


@pytest.fixture
def create_lead_dto():
    """Minimal DTO for creating a lead."""
    return CreateLeadDto(
        lastname="Pérez",
        firstname="Carlos",
        emailaddress1="carlos@example.com",
        companyname="Constructora ABC",
        subject="Proyecto Edificio Central",
        estimatedvalue=Decimal("50000.00"),
    )


@pytest.mark.django_db
@pytest.mark.integration
class TestAuditIntegrationWithLead:
    """Integration tests: verify audit entries are created by real service calls."""

    def test_create_lead_creates_audit_entry(self, admin_user, create_lead_dto):
        """Creating a lead via LeadService should generate a 'create' audit log."""
        lead = LeadService.create_lead(create_lead_dto, admin_user)

        entries = AuditLog.objects.filter(entity="lead", action="create")
        assert entries.count() == 1

        entry = entries.first()
        assert entry.recordid == lead.leadid
        assert entry.entity == "lead"
        assert entry.action == "create"
        assert entry.new_values is not None

    def test_update_lead_creates_audit_with_changes(self, admin_user, create_lead_dto):
        """Updating a lead should generate an 'update' audit log with field diffs."""
        lead = LeadService.create_lead(create_lead_dto, admin_user)

        update_dto = UpdateLeadDto(subject="Proyecto Modificado")
        LeadService.update_lead(lead.leadid, update_dto, admin_user)

        entries = AuditLog.objects.filter(entity="lead", action="update")
        assert entries.count() == 1

        entry = entries.first()
        assert entry.recordid == lead.leadid
        assert entry.changes is not None
        changed_fields = [c["field"] for c in entry.changes]
        assert "subject" in changed_fields

        subject_change = next(c for c in entry.changes if c["field"] == "subject")
        assert subject_change["old"] == "Proyecto Edificio Central"
        assert subject_change["new"] == "Proyecto Modificado"

    def test_qualify_lead_creates_audit_entry(self, admin_user, create_lead_dto):
        """Qualifying a lead should generate a 'qualify' audit log."""
        lead = LeadService.create_lead(create_lead_dto, admin_user)

        qualify_dto = QualifyLeadDto(
            createAccount=True,
            createContact=True,
        )
        LeadService.qualify_lead(lead.leadid, qualify_dto, admin_user)

        entries = AuditLog.objects.filter(entity="lead", action="qualify")
        assert entries.count() == 1

        entry = entries.first()
        assert entry.recordid == lead.leadid
        assert entry.entity == "lead"

    def test_delete_lead_creates_audit_entry(self, admin_user, create_lead_dto):
        """Deleting a lead should generate a 'delete' audit log."""
        lead = LeadService.create_lead(create_lead_dto, admin_user)

        LeadService.delete_lead(lead.leadid, admin_user)

        # delete_lead internally calls disqualify_lead which has action='cancel',
        # then delete_lead itself is decorated with action='delete'.
        entries = AuditLog.objects.filter(entity="lead", action="delete")
        assert entries.count() >= 1

        entry = entries.first()
        assert entry.recordid == lead.leadid

    def test_audit_captures_username(self, admin_user, create_lead_dto):
        """Audit entries should capture the username of the acting user."""
        LeadService.create_lead(create_lead_dto, admin_user)

        entry = AuditLog.objects.filter(entity="lead", action="create").first()
        assert entry is not None
        assert entry.username == "Admin Auditor"
        assert entry.userid == admin_user

    def test_audit_does_not_block_service_on_failure(self, admin_user, create_lead_dto):
        """If audit logging fails somehow, the service method should still succeed."""
        with mock.patch(
            "apps.audit.services.AuditLog.objects.create",
            side_effect=Exception("DB write failed"),
        ):
            lead = LeadService.create_lead(create_lead_dto, admin_user)

        # The lead should still be created successfully despite audit failure
        assert lead is not None
        assert Lead.objects.filter(leadid=lead.leadid).exists()

        # No audit entry should exist since we forced a failure
        assert AuditLog.objects.filter(entity="lead", action="create").count() == 0
