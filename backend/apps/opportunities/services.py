"""
Opportunity business logic service layer.
Phase 6 Implementation
"""

from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from django.db.models import Q, Count, Sum, Avg, QuerySet
from django.db import transaction

from apps.opportunities.models import Opportunity, OpportunityStateCode, OpportunityStatusCode, SalesStage
from apps.opportunities.schemas import CreateOpportunityDto, UpdateOpportunityDto, CloseOpportunityDto, OpportunityStatsSchema
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import filter_by_ownership
from apps.audit.services import audit_action


class OpportunityService:
    """Service class for Opportunity entity business logic."""

    @staticmethod
    def list_opportunities(
        user: SystemUser,
        statecode: Optional[int] = None,
        salesstage: Optional[int] = None,
        search: Optional[str] = None,
        ownerid: Optional[UUID] = None,
    ) -> QuerySet[Opportunity]:
        """List opportunities with filtering and ownership rules."""
        queryset = Opportunity.objects.all()
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        if salesstage is not None:
            queryset = queryset.filter(salesstage=salesstage)
        if ownerid:
            if user.role_name not in ["System Administrator", "Sales Manager"]:
                raise PermissionDenied("You cannot view other users' opportunities")
            queryset = queryset.filter(ownerid=ownerid)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(customername__icontains=search) |
                Q(description__icontains=search)
            )

        return queryset.select_related('ownerid', 'originatingleadid', 'createdby', 'modifiedby')

    @staticmethod
    @audit_action(action='create', entity='opportunity')
    def create_opportunity(dto: CreateOpportunityDto, user: SystemUser) -> Opportunity:
        """Create a new opportunity."""
        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        # Resolve field aliases (frontend sends estimatedvalue, backend uses estimatedrevenue)
        estimated_revenue = dto.estimatedrevenue or dto.estimatedvalue
        probability = dto.probability if dto.probability != 0 else (dto.closeprobability or 0)

        # Validate probability range
        if probability is not None and (probability < 0 or probability > 100):
            raise ValidationError("Probability must be between 0 and 100")

        # Resolve polymorphic customer
        account, contact = None, None
        if dto.customerid and dto.customeridtype:
            from core.customers import resolve_customer
            account, contact = resolve_customer(dto.customerid, dto.customeridtype)

        opportunity = Opportunity(
            name=dto.name,
            description=dto.description,
            customername=dto.customername,
            accountid=account,
            contactid=contact,
            estimatedrevenue=estimated_revenue,
            estimatedclosedate=dto.estimatedclosedate,
            salesstage=dto.salesstage,
            probability=probability,
            originatingleadid_id=dto.originatingleadid,
            ownerid=owner,
            statecode=OpportunityStateCode.OPEN,
            statuscode=OpportunityStatusCode.IN_PROGRESS,
            createdby=user,
            modifiedby=user,
        )
        opportunity.save()
        return opportunity

    @staticmethod
    def get_opportunity_by_id(opportunity_id: UUID, user: SystemUser) -> Opportunity:
        """Get opportunity by ID with ownership check."""
        try:
            opp = Opportunity.objects.select_related(
                'ownerid', 'originatingleadid', 'createdby', 'modifiedby'
            ).get(opportunityid=opportunity_id)
        except Opportunity.DoesNotExist:
            raise NotFound(f"Opportunity with ID {opportunity_id} not found")

        if user.role_name not in ["System Administrator", "Sales Manager"]:
            if opp.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this opportunity")

        return opp

    @staticmethod
    @audit_action(action='update', entity='opportunity', record_arg='opportunity_id')
    def update_opportunity(opportunity_id: UUID, dto: UpdateOpportunityDto, user: SystemUser) -> Opportunity:
        """Update an existing opportunity."""
        opp = OpportunityService.get_opportunity_by_id(opportunity_id, user)

        if opp.statecode != OpportunityStateCode.OPEN:
            raise ValidationError(f"Cannot update opportunity in '{opp.state_name}' state")

        old_salesstage = opp.salesstage

        # Resolve field aliases
        if dto.estimatedvalue is not None and dto.estimatedrevenue is None:
            dto.estimatedrevenue = dto.estimatedvalue
        if dto.closeprobability is not None and dto.probability is None:
            dto.probability = dto.closeprobability

        # Update fields
        update_fields = ['name', 'description', 'customername', 'estimatedrevenue',
                        'estimatedclosedate', 'salesstage', 'probability', 'statuscode']

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                if field == 'probability' and (value < 0 or value > 100):
                    raise ValidationError("Probability must be between 0 and 100")
                setattr(opp, field, value)

        # Handle polymorphic customer update
        if dto.customerid is not None and dto.customeridtype is not None:
            from core.customers import resolve_customer
            account, contact = resolve_customer(dto.customerid, dto.customeridtype)
            opp.accountid = account
            opp.contactid = contact

        opp.modifiedby = user
        opp.save()

        # Notification: stage changed
        if dto.salesstage is not None and dto.salesstage != old_salesstage:
            try:
                from apps.notifications.services import NotificationService
                stage_label = SalesStage(opp.salesstage).label if opp.salesstage else 'Unknown'
                NotificationService.notify_state_changed(
                    entity_type='opportunity',
                    entity_id=str(opp.opportunityid),
                    entity_name=opp.name,
                    new_state=stage_label,
                    owner=opp.ownerid,
                    actor=user,
                )
            except Exception:
                pass

        return opp

    @staticmethod
    @audit_action(action='close', entity='opportunity', record_arg='opportunity_id')
    def close_opportunity(opportunity_id: UUID, dto: CloseOpportunityDto, user: SystemUser) -> Opportunity:
        """Close opportunity as Won or Lost."""
        opp = OpportunityService.get_opportunity_by_id(opportunity_id, user)

        if opp.statecode != OpportunityStateCode.OPEN:
            raise ValidationError(f"Opportunity is already closed as '{opp.state_name}'")

        # Determine Won or Lost based on status code
        if dto.status == OpportunityStatusCode.WON:
            opp.statecode = OpportunityStateCode.WON
            opp.statuscode = OpportunityStatusCode.WON
            opp.actualrevenue = dto.actualrevenue or opp.estimatedrevenue
            opp.probability = 100
        elif dto.status in [OpportunityStatusCode.CANCELED, OpportunityStatusCode.OUT_SOLD]:
            opp.statecode = OpportunityStateCode.LOST
            opp.statuscode = dto.status
            opp.actualrevenue = Decimal('0.00')
            opp.probability = 0
        else:
            raise ValidationError(f"Invalid closing status code: {dto.status}")

        opp.actualclosedate = dto.actualclosedate or date.today()
        opp.salesstage = SalesStage.CLOSE

        if dto.closingnotes:
            opp.description = (opp.description or '') + f"\n\nClosing notes: {dto.closingnotes}"

        opp.modifiedby = user
        opp.save()

        # Notification: opportunity won or lost
        try:
            from apps.notifications.services import NotificationService
            if opp.statecode == OpportunityStateCode.WON:
                NotificationService.notify_opportunity_won(opp, actor=user)
            elif opp.statecode == OpportunityStateCode.LOST:
                NotificationService.notify_opportunity_lost(opp, actor=user)
        except Exception:
            pass

        return opp

    @staticmethod
    @audit_action(action='delete', entity='opportunity', record_arg='opportunity_id')
    def delete_opportunity(opportunity_id: UUID, user: SystemUser) -> Opportunity:
        """Delete (cancel) an opportunity."""
        close_dto = CloseOpportunityDto(
            status=OpportunityStatusCode.CANCELED,
            closingnotes="Deleted by user"
        )
        return OpportunityService.close_opportunity(opportunity_id, close_dto, user)

    @staticmethod
    def get_opportunity_stats(user: SystemUser) -> OpportunityStatsSchema:
        """Get opportunity statistics."""
        queryset = filter_by_ownership(Opportunity.objects.all(), user, owner_field='ownerid')

        total_opps = queryset.count()
        open_opps = queryset.filter(statecode=OpportunityStateCode.OPEN).count()
        won_opps = queryset.filter(statecode=OpportunityStateCode.WON).count()
        lost_opps = queryset.filter(statecode=OpportunityStateCode.LOST).count()

        aggregation = queryset.aggregate(
            total_estimated=Sum('estimatedrevenue'),
            total_actual=Sum('actualrevenue'),
            avg_prob=Avg('probability')
        )

        # Calculate weighted revenue
        weighted_revenue = Decimal('0.00')
        for opp in queryset.filter(statecode=OpportunityStateCode.OPEN):
            if opp.weighted_revenue:
                weighted_revenue += opp.weighted_revenue

        # Calculate win rate
        win_rate = None
        closed_opps = won_opps + lost_opps
        if closed_opps > 0:
            win_rate = (won_opps / closed_opps) * 100

        return OpportunityStatsSchema(
            total_opportunities=total_opps,
            open_opportunities=open_opps,
            won_opportunities=won_opps,
            lost_opportunities=lost_opps,
            total_estimated_revenue=aggregation['total_estimated'],
            total_actual_revenue=aggregation['total_actual'],
            total_weighted_revenue=weighted_revenue,
            avg_probability=aggregation['avg_prob'],
            win_rate=win_rate,
        )
