"""
Lead business logic service layer.

Handles lead operations, state transitions, and qualification workflow.

Phase 5 Implementation (User Story 3)
"""

import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from django.db.models import Q, Count, Sum, Avg, QuerySet
from django.db import transaction

from apps.leads.models import (
    Lead,
    LeadStateCode,
    LeadStatusCode,
    LeadQualityCode,
    LeadSourceCode,
)
from apps.leads.schemas import (
    CreateLeadDto,
    UpdateLeadDto,
    QualifyLeadDto,
    DisqualifyLeadDto,
    LeadStatsSchema,
)
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.roles import ADMIN_ROLES
from core.permissions import filter_by_ownership
from core.services import BaseReadService
from apps.audit.services import audit_action

logger = logging.getLogger(__name__)


class LeadService(BaseReadService[Lead]):
    """
    Service class for Lead entity business logic.
    """

    model = Lead
    pk_field = 'leadid'
    select_related_fields = ('ownerid', 'createdby', 'modifiedby')
    not_found_message = "Lead not found"
    access_denied_message = "You don't have access to this lead"

    @staticmethod
    def list_leads(
        user: SystemUser,
        statecode: Optional[int] = None,
        statuscode: Optional[int] = None,
        leadqualitycode: Optional[int] = None,
        leadsourcecode: Optional[int] = None,
        search: Optional[str] = None,
        ownerid: Optional[UUID] = None,
    ) -> QuerySet[Lead]:
        """
        List leads with filtering and ownership rules.

        Args:
            user: Current user (for ownership filtering)
            statecode: Filter by state code
            statuscode: Filter by status code
            leadqualitycode: Filter by quality code
            leadsourcecode: Filter by source code
            search: Search in fullname, email, company
            ownerid: Filter by owner (System Administrator/Manager only)

        Returns:
            QuerySet of Lead objects
        """
        # Start with all leads
        queryset = Lead.objects.all()

        # Apply ownership filtering based on user role
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        # Apply filters
        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)

        if statuscode is not None:
            queryset = queryset.filter(statuscode=statuscode)

        if leadqualitycode is not None:
            queryset = queryset.filter(leadqualitycode=leadqualitycode)

        if leadsourcecode is not None:
            queryset = queryset.filter(leadsourcecode=leadsourcecode)

        if ownerid:
            # Only System Administrator and Sales Manager can filter by other owners
            if user.role_name not in ADMIN_ROLES:
                raise PermissionDenied("You cannot view other users' leads")
            queryset = queryset.filter(ownerid=ownerid)

        if search:
            queryset = queryset.filter(
                Q(fullname__icontains=search) |
                Q(emailaddress1__icontains=search) |
                Q(companyname__icontains=search) |
                Q(subject__icontains=search)
            )

        # Optimize query with select_related
        queryset = queryset.select_related('ownerid', 'createdby', 'modifiedby')

        return queryset

    @staticmethod
    @audit_action(action='create', entity='lead')
    def create_lead(dto: CreateLeadDto, user: SystemUser) -> Lead:
        """
        Create a new lead.

        Args:
            dto: Lead creation data
            user: Current user (will be set as createdby and modifiedby)

        Returns:
            Created Lead instance

        Raises:
            ValidationError: If validation fails
        """
        # Validate owner exists (if specified)
        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        # Create lead
        lead = Lead(
            firstname=dto.firstname,
            lastname=dto.lastname,
            emailaddress1=dto.emailaddress1,
            telephone1=dto.telephone1,
            mobilephone=dto.mobilephone,
            companyname=dto.companyname,
            jobtitle=dto.jobtitle,
            subject=dto.subject,
            description=dto.description,
            leadqualitycode=dto.leadqualitycode,
            leadsourcecode=dto.leadsourcecode,
            estimatedvalue=dto.estimatedvalue,
            estimatedclosedate=dto.estimatedclosedate,
            ownerid=owner,
            statecode=LeadStateCode.OPEN,
            statuscode=LeadStatusCode.NEW,
            createdby=user,
            modifiedby=user,
        )

        lead.save()

        from apps.notifications.signals import record_assigned
        record_assigned.send(
            sender=Lead,
            entity_type='lead',
            entity_id=lead.leadid,
            entity_name=lead.fullname or lead.lastname,
            new_owner=lead.ownerid,
            actor=user,
        )

        return lead

    @classmethod
    def get_lead_by_id(cls, lead_id: UUID, user: SystemUser) -> Lead:
        """Get lead by ID with ownership check (delegates to BaseReadService)."""
        return cls.get_by_id(lead_id, user)

    @staticmethod
    @audit_action(action='update', entity='lead', record_arg='lead_id')
    def update_lead(lead_id: UUID, dto: UpdateLeadDto, user: SystemUser) -> Lead:
        """
        Update an existing lead.

        Args:
            lead_id: Lead UUID
            dto: Update data (partial)
            user: Current user

        Returns:
            Updated Lead instance

        Raises:
            NotFound: If lead doesn't exist
            PermissionDenied: If user doesn't have access
            ValidationError: If validation fails
        """
        lead = LeadService.get_lead_by_id(lead_id, user)

        # Check if lead is still open (can't update qualified/disqualified leads)
        if lead.statecode != LeadStateCode.OPEN:
            raise ValidationError(
                f"Cannot update lead in '{lead.state_name}' state. "
                "Only open leads can be updated."
            )

        # Update fields (only if provided)
        update_fields = [
            'firstname', 'lastname', 'emailaddress1', 'telephone1', 'mobilephone',
            'companyname', 'jobtitle', 'subject', 'description',
            'leadqualitycode', 'leadsourcecode', 'estimatedvalue', 'estimatedclosedate',
            'statuscode'
        ]

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(lead, field, value)

        # Handle owner change (if specified)
        old_owner_id = lead.ownerid_id
        if dto.ownerid:
            try:
                new_owner = SystemUser.objects.get(systemuserid=dto.ownerid)
                lead.ownerid = new_owner
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        # Validate status code is valid for Open state
        if dto.statuscode and dto.statuscode not in [
            LeadStatusCode.NEW,
            LeadStatusCode.CONTACTED
        ]:
            raise ValidationError(
                f"Invalid status code for open lead. "
                f"Must be {LeadStatusCode.NEW} (New) or {LeadStatusCode.CONTACTED} (Contacted)"
            )

        lead.modifiedby = user
        lead.save()

        if dto.ownerid and lead.ownerid_id != old_owner_id:
            from apps.notifications.signals import record_assigned
            record_assigned.send(
                sender=Lead,
                entity_type='lead',
                entity_id=lead.leadid,
                entity_name=lead.fullname or lead.lastname,
                new_owner=lead.ownerid,
                actor=user,
            )

        return lead

    @staticmethod
    @transaction.atomic
    @audit_action(action='qualify', entity='lead', record_arg='lead_id')
    def qualify_lead(lead_id: UUID, dto: QualifyLeadDto, user: SystemUser) -> dict:
        """
        Qualify a lead (convert to Opportunity).

        Creates or links Account and/or Contact, then creates Opportunity.
        Sets lead state to Qualified.

        Returns:
            Dict matching QualifyLeadResponse schema with created/linked entity info.
        """
        lead = LeadService.get_lead_by_id(lead_id, user)

        # Validate lead is open
        if lead.statecode != LeadStateCode.OPEN:
            raise ValidationError(
                f"Cannot qualify lead in '{lead.state_name}' state. "
                "Only open leads can be qualified."
            )

        # Resolve Account: link existing or create new
        account = None
        if dto.existingAccountId:
            from apps.accounts.models import Account
            try:
                account = Account.objects.get(accountid=dto.existingAccountId)
            except Account.DoesNotExist:
                raise NotFound(f"Account with ID {dto.existingAccountId} not found")
        elif dto.createAccount and lead.companyname:
            from apps.accounts.models import Account
            account = Account.objects.create(
                name=lead.companyname,
                emailaddress1=lead.emailaddress1,
                telephone1=lead.telephone1,
                ownerid=lead.ownerid,
                createdby=user,
                modifiedby=user,
            )

        # Resolve Contact: link existing or create new
        contact = None
        if dto.existingContactId:
            from apps.contacts.models import Contact
            try:
                contact = Contact.objects.get(contactid=dto.existingContactId)
            except Contact.DoesNotExist:
                raise NotFound(f"Contact with ID {dto.existingContactId} not found")
        elif dto.createContact:
            from apps.contacts.models import Contact
            contact = Contact.objects.create(
                firstname=lead.firstname,
                lastname=lead.lastname,
                emailaddress1=lead.emailaddress1,
                telephone1=lead.telephone1,
                mobilephone=lead.mobilephone,
                jobtitle=lead.jobtitle,
                parentcustomerid=account if account else None,
                ownerid=lead.ownerid,
                createdby=user,
                modifiedby=user,
            )

        # Create Opportunity
        from apps.opportunities.models import Opportunity, OpportunityStateCode, OpportunityStatusCode
        opportunity_name = dto.opportunityName or f"{lead.fullname} - {lead.companyname or 'Opportunity'}"
        opportunity = Opportunity.objects.create(
            name=opportunity_name,
            description=dto.description,
            accountid=account,
            contactid=contact,
            estimatedrevenue=dto.estimatedValue or lead.estimatedvalue,
            estimatedclosedate=dto.estimatedCloseDate or lead.estimatedclosedate,
            originatingleadid=lead,
            ownerid=lead.ownerid,
            createdby=user,
            modifiedby=user,
            statecode=OpportunityStateCode.OPEN,
            statuscode=OpportunityStatusCode.IN_PROGRESS,
            probability=50,
        )

        # Update lead state to Qualified
        lead.qualifyingopportunityid = opportunity.opportunityid
        lead.statecode = LeadStateCode.QUALIFIED
        lead.statuscode = LeadStatusCode.QUALIFIED
        lead.modifiedby = user
        lead.save()

        from apps.notifications.signals import lead_qualified as lead_qualified_signal
        lead_qualified_signal.send(
            sender=Lead, lead=lead, opportunity=opportunity, actor=user,
        )

        # Build response matching QualifyLeadResponse schema
        response = {
            'leadId': str(lead.leadid),
            'opportunityId': str(opportunity.opportunityid),
            'opportunity': {
                'opportunityid': str(opportunity.opportunityid),
                'name': opportunity.name,
            },
        }

        if account:
            response['accountId'] = str(account.accountid)
            response['account'] = {
                'accountid': str(account.accountid),
                'name': account.name,
            }

        if contact:
            response['contactId'] = str(contact.contactid)
            response['contact'] = {
                'contactid': str(contact.contactid),
                'fullname': contact.fullname,
            }

        return response

    @staticmethod
    @audit_action(action='cancel', entity='lead', record_arg='lead_id')
    def disqualify_lead(lead_id: UUID, dto: DisqualifyLeadDto, user: SystemUser) -> Lead:
        """
        Disqualify a lead.

        Frontend sends just an optional reason. Defaults statuscode to LOST (4).
        """
        lead = LeadService.get_lead_by_id(lead_id, user)

        # Validate lead is open
        if lead.statecode != LeadStateCode.OPEN:
            raise ValidationError(
                f"Cannot disqualify lead in '{lead.state_name}' state. "
                "Only open leads can be disqualified."
            )

        # Update lead state (default to LOST)
        lead.statecode = LeadStateCode.DISQUALIFIED
        lead.statuscode = LeadStatusCode.LOST

        # Add reason to description if provided
        if dto.reason:
            lead.description = (lead.description or '') + f"\n\nDisqualification reason: {dto.reason}"

        lead.modifiedby = user
        lead.save()

        return lead

    @staticmethod
    @audit_action(action='delete', entity='lead', record_arg='lead_id')
    def delete_lead(lead_id: UUID, user: SystemUser) -> Lead:
        """
        Delete (disqualify) a lead.

        Soft delete by marking as disqualified with 'Lost' status.

        Args:
            lead_id: Lead UUID
            user: Current user

        Returns:
            Updated Lead instance

        Raises:
            NotFound: If lead doesn't exist
            PermissionDenied: If user doesn't have access
        """
        disqualify_dto = DisqualifyLeadDto(
            reason="Deleted by user"
        )

        return LeadService.disqualify_lead(lead_id, disqualify_dto, user)

    @staticmethod
    def get_lead_stats(user: SystemUser) -> LeadStatsSchema:
        """
        Get lead statistics for dashboard.

        Args:
            user: Current user (for ownership filtering)

        Returns:
            LeadStatsSchema with aggregated statistics
        """
        # Get leads visible to user
        queryset = filter_by_ownership(Lead.objects.all(), user, owner_field='ownerid')

        # Count by state
        total_leads = queryset.count()
        open_leads = queryset.filter(statecode=LeadStateCode.OPEN).count()
        qualified_leads = queryset.filter(statecode=LeadStateCode.QUALIFIED).count()
        disqualified_leads = queryset.filter(statecode=LeadStateCode.DISQUALIFIED).count()

        # Count by quality — single GROUP BY instead of one COUNT per enum value
        quality_counts = {
            row['leadqualitycode']: row['count']
            for row in queryset.values('leadqualitycode').annotate(count=Count('leadid'))
        }
        leads_by_quality = {
            quality_code.label: quality_counts.get(quality_code.value, 0)
            for quality_code in LeadQualityCode
        }

        # Count by source — single GROUP BY
        source_counts = {
            row['leadsourcecode']: row['count']
            for row in queryset.values('leadsourcecode').annotate(count=Count('leadid'))
        }
        leads_by_source = {
            source_code.label: source_counts.get(source_code.value, 0)
            for source_code in LeadSourceCode
        }

        # Calculate value metrics
        value_aggregation = queryset.aggregate(
            total_value=Sum('estimatedvalue'),
            avg_value=Avg('estimatedvalue')
        )

        return LeadStatsSchema(
            total_leads=total_leads,
            open_leads=open_leads,
            qualified_leads=qualified_leads,
            disqualified_leads=disqualified_leads,
            leads_by_quality=leads_by_quality,
            leads_by_source=leads_by_source,
            total_estimated_value=value_aggregation['total_value'],
            avg_estimated_value=value_aggregation['avg_value'],
        )
