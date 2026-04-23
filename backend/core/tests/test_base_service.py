"""Tests for core.services.base.BaseReadService.

Uses Lead as the concrete model because it has the standard shape:
UUID pk, ownerid FK, audit fields.
"""

import pytest
from uuid import uuid4

from core.exceptions import NotFound, PermissionDenied
from core.services.base import BaseReadService


@pytest.fixture
def lead_read_service():
    from apps.leads.models import Lead

    class LeadReadService(BaseReadService):
        model = Lead
        pk_field = 'leadid'
        select_related_fields = ('ownerid', 'createdby', 'modifiedby')
        not_found_message = "Lead not found"
        access_denied_message = "You don't have access to this lead"

    return LeadReadService


@pytest.mark.unit
@pytest.mark.django_db
class TestBaseReadService:

    def test_get_by_id_returns_record_for_owner(self, lead_read_service, salesperson):
        from apps.leads.tests.factories import LeadFactory
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)

        result = lead_read_service.get_by_id(lead.leadid, salesperson)
        assert result.leadid == lead.leadid

    def test_get_by_id_raises_not_found(self, lead_read_service, salesperson):
        with pytest.raises(NotFound):
            lead_read_service.get_by_id(uuid4(), salesperson)

    def test_get_by_id_denies_non_owner_non_system_admin(self, lead_read_service, salesperson, salesperson2):
        from apps.leads.tests.factories import LeadFactory
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)

        with pytest.raises(PermissionDenied):
            lead_read_service.get_by_id(lead.leadid, salesperson2)

    def test_get_by_id_allows_system_admin_on_other_owner(self, lead_read_service, salesperson, system_admin):
        from apps.leads.tests.factories import LeadFactory
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)

        # system_admin bypasses ownership
        result = lead_read_service.get_by_id(lead.leadid, system_admin)
        assert result.leadid == lead.leadid

    def test_base_queryset_filters_by_ownership(self, lead_read_service, salesperson, salesperson2):
        from apps.leads.tests.factories import LeadFactory
        LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        LeadFactory(ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2)

        # salesperson only sees own leads
        own = lead_read_service.base_queryset(salesperson)
        assert all(l.ownerid_id == salesperson.systemuserid for l in own)

    def test_base_queryset_system_admin_sees_all(self, lead_read_service, salesperson, salesperson2, system_admin):
        from apps.leads.tests.factories import LeadFactory
        LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        LeadFactory(ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2)

        all_leads = list(lead_read_service.base_queryset(system_admin))
        owners = {l.ownerid_id for l in all_leads}
        assert salesperson.systemuserid in owners
        assert salesperson2.systemuserid in owners
