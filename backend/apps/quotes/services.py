"""
Quote business logic services.

Phase 8 Implementation: Quote Management
"""

from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal
from datetime import datetime
from uuid import UUID

from apps.quotes.models import Quote, QuoteDetail, QuoteStateCode, QuoteStatusCode
from apps.quotes.schemas import (
    CreateQuoteDto, UpdateQuoteDto, CreateQuoteDetailDto,
    ActivateQuoteDto, CloseQuoteDto, ReviseQuoteDto
)
from apps.users.models import SystemUser
from apps.opportunities.models import Opportunity
from core.permissions import can_modify_record


class QuoteService:
    """Service class for Quote operations."""

    @staticmethod
    def generate_quote_number():
        """Generate unique quote number (Q-YYYY-NNN)."""
        from datetime import date
        year = date.today().year
        # Get last quote number for this year
        last_quote = Quote.objects.filter(
            quotenumber__startswith=f'Q-{year}-'
        ).order_by('-quotenumber').first()

        if last_quote:
            # Extract number and increment
            last_num = int(last_quote.quotenumber.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1

        return f'Q-{year}-{next_num:04d}'

    @staticmethod
    @transaction.atomic
    def create_quote(dto: CreateQuoteDto, user: SystemUser) -> Quote:
        """Create a new quote with optional line items."""
        # Generate quote number
        quotenumber = QuoteService.generate_quote_number()

        # Get related entities if provided
        opportunity = None
        account = None
        contact = None

        if dto.opportunityid:
            from apps.opportunities.models import Opportunity
            try:
                opportunity = Opportunity.objects.get(opportunityid=dto.opportunityid)
                # Inherit customer from opportunity
                account = opportunity.accountid
                contact = opportunity.contactid
            except Opportunity.DoesNotExist:
                raise ValidationError('Opportunity not found')

        # Override with explicit account/contact if provided
        if dto.accountid:
            from apps.accounts.models import Account
            try:
                account = Account.objects.get(accountid=dto.accountid)
            except Account.DoesNotExist:
                raise ValidationError('Account not found')

        if dto.contactid:
            from apps.contacts.models import Contact
            try:
                contact = Contact.objects.get(contactid=dto.contactid)
            except Contact.DoesNotExist:
                raise ValidationError('Contact not found')

        # Create quote
        quote = Quote.objects.create(
            name=dto.name,
            quotenumber=quotenumber,
            opportunityid=opportunity,
            accountid=account,
            contactid=contact,
            discountpercentage=dto.discountpercentage,
            effectivefrom=dto.effectivefrom,
            effectiveto=dto.effectiveto,
            description=dto.description,
            statecode=QuoteStateCode.DRAFT,
            statuscode=QuoteStatusCode.IN_PROGRESS,
            ownerid=user,
            createdby=user,
            modifiedby=user
        )

        # Add line items if provided
        for detail_dto in dto.quote_details:
            QuoteService.add_quote_detail(quote.quoteid, detail_dto, user)

        # Calculate totals
        quote.calculate_totals()
        quote.save()

        return quote

    @staticmethod
    @transaction.atomic
    def create_quote_from_opportunity(opportunity_id: UUID, user: SystemUser) -> Quote:
        """Create a quote from an opportunity."""
        from apps.opportunities.models import Opportunity

        try:
            opportunity = Opportunity.objects.get(opportunityid=opportunity_id)
        except Opportunity.DoesNotExist:
            raise ValidationError('Opportunity not found')

        # Create quote with opportunity data
        dto = CreateQuoteDto(
            name=f"{opportunity.name} - Quote",
            opportunityid=opportunity.opportunityid,
            description=f"Quote for opportunity: {opportunity.name}"
        )

        return QuoteService.create_quote(dto, user)

    @staticmethod
    def get_quote_by_id(quote_id: UUID, user: SystemUser) -> Quote:
        """Get quote by ID with permission check."""
        try:
            quote = Quote.objects.select_related(
                'opportunityid', 'accountid', 'contactid', 'ownerid'
            ).prefetch_related('quote_details').get(quoteid=quote_id)
        except Quote.DoesNotExist:
            raise ValidationError('Quote not found')

        # Permission check
        if not can_modify_record(user, quote.ownerid):
            raise PermissionDenied('You do not have permission to view this quote')

        return quote

    @staticmethod
    @transaction.atomic
    def update_quote(quote_id: UUID, dto: UpdateQuoteDto, user: SystemUser) -> Quote:
        """Update quote."""
        quote = QuoteService.get_quote_by_id(quote_id, user)

        # Cannot update if quote is won or closed
        if quote.statecode in [QuoteStateCode.WON, QuoteStateCode.CLOSED]:
            raise ValidationError('Cannot update a won or closed quote')

        # Update fields
        if dto.name is not None:
            quote.name = dto.name
        if dto.discountpercentage is not None:
            quote.discountpercentage = dto.discountpercentage
        if dto.effectivefrom is not None:
            quote.effectivefrom = dto.effectivefrom
        if dto.effectiveto is not None:
            quote.effectiveto = dto.effectiveto
        if dto.description is not None:
            quote.description = dto.description
        if dto.statecode is not None:
            quote.statecode = dto.statecode
        if dto.statuscode is not None:
            quote.statuscode = dto.statuscode

        quote.modifiedby = user
        quote.save()

        # Recalculate totals if discount changed
        if dto.discountpercentage is not None:
            quote.calculate_totals()
            quote.save()

        return quote

    @staticmethod
    @transaction.atomic
    def delete_quote(quote_id: UUID, user: SystemUser):
        """Delete (soft delete) a quote."""
        quote = QuoteService.get_quote_by_id(quote_id, user)

        # Can only delete draft quotes
        if quote.statecode != QuoteStateCode.DRAFT:
            raise ValidationError('Can only delete draft quotes')

        quote.delete()

    @staticmethod
    @transaction.atomic
    def add_quote_detail(quote_id: UUID, dto: CreateQuoteDetailDto, user: SystemUser) -> QuoteDetail:
        """Add a line item to a quote."""
        quote = QuoteService.get_quote_by_id(quote_id, user)

        # Cannot modify if quote is won or closed
        if quote.statecode in [QuoteStateCode.WON, QuoteStateCode.CLOSED]:
            raise ValidationError('Cannot modify a won or closed quote')

        # Create detail
        detail = QuoteDetail.objects.create(
            quoteid=quote,
            productname=dto.productname,
            productdescription=dto.productdescription,
            quantity=dto.quantity,
            priceperunit=dto.priceperunit,
            manualdiscountamount=dto.manualdiscountamount,
            tax=dto.tax,
            sequencenumber=dto.sequencenumber
        )

        # Recalculate quote totals
        quote.calculate_totals()
        quote.modifiedby = user
        quote.save()

        return detail

    @staticmethod
    @transaction.atomic
    def remove_quote_detail(detail_id: UUID, user: SystemUser):
        """Remove a line item from a quote."""
        try:
            detail = QuoteDetail.objects.select_related('quoteid').get(quotedetailid=detail_id)
        except QuoteDetail.DoesNotExist:
            raise ValidationError('Quote detail not found')

        quote = detail.quoteid

        # Permission check
        if not can_modify_record(user, quote.ownerid):
            raise PermissionDenied('You do not have permission to modify this quote')

        # Cannot modify if quote is won or closed
        if quote.statecode in [QuoteStateCode.WON, QuoteStateCode.CLOSED]:
            raise ValidationError('Cannot modify a won or closed quote')

        detail.delete()

        # Recalculate quote totals
        quote.calculate_totals()
        quote.modifiedby = user
        quote.save()

    @staticmethod
    @transaction.atomic
    def activate_quote(quote_id: UUID, dto: ActivateQuoteDto, user: SystemUser) -> Quote:
        """Activate a quote (ready for customer review)."""
        quote = QuoteService.get_quote_by_id(quote_id, user)

        # Must be in draft state
        if quote.statecode != QuoteStateCode.DRAFT:
            raise ValidationError('Can only activate draft quotes')

        # Must have at least one line item
        if not quote.quote_details.exists():
            raise ValidationError('Quote must have at least one line item')

        # Update dates if provided
        if dto.effectivefrom:
            quote.effectivefrom = dto.effectivefrom
        if dto.effectiveto:
            quote.effectiveto = dto.effectiveto

        # Set to active state
        quote.statecode = QuoteStateCode.ACTIVE
        quote.statuscode = QuoteStatusCode.IN_REVIEW
        quote.modifiedby = user
        quote.save()

        return quote

    @staticmethod
    @transaction.atomic
    def close_quote(quote_id: UUID, dto: CloseQuoteDto, user: SystemUser) -> Quote:
        """Close a quote (won/lost/canceled)."""
        quote = QuoteService.get_quote_by_id(quote_id, user)

        # Validate status code
        valid_close_statuses = [
            QuoteStatusCode.WON,
            QuoteStatusCode.LOST,
            QuoteStatusCode.CANCELED
        ]
        if dto.statuscode not in valid_close_statuses:
            raise ValidationError('Invalid close status code')

        # Set appropriate state
        if dto.statuscode == QuoteStatusCode.WON:
            quote.statecode = QuoteStateCode.WON
        else:
            quote.statecode = QuoteStateCode.CLOSED

        quote.statuscode = dto.statuscode
        quote.closedon = dto.closedon or timezone.now()

        if dto.description:
            quote.description = (quote.description or '') + f"\n\nClose Reason: {dto.description}"

        quote.modifiedby = user
        quote.save()

        return quote

    @staticmethod
    def get_quote_stats(user: SystemUser):
        """Get statistics about quotes."""
        # Base queryset (filtered by user permissions)
        from core.permissions import filter_by_ownership

        # Base queryset filtered by ownership (System Admin/Sales Manager see all)
        queryset = filter_by_ownership(Quote.objects.all(), user)

        # Calculate stats
        total = queryset.count()
        draft = queryset.filter(statecode=QuoteStateCode.DRAFT).count()
        active = queryset.filter(statecode=QuoteStateCode.ACTIVE).count()
        won = queryset.filter(statecode=QuoteStateCode.WON).count()
        closed = queryset.filter(statecode=QuoteStateCode.CLOSED).count()

        total_value = queryset.aggregate(total=Sum('totalamount'))['total'] or Decimal('0')
        won_value = queryset.filter(statecode=QuoteStateCode.WON).aggregate(
            total=Sum('totalamount')
        )['total'] or Decimal('0')

        # Calculate win rate
        total_closed = won + closed
        win_rate = (won / total_closed * 100) if total_closed > 0 else 0

        return {
            'total_quotes': total,
            'draft_quotes': draft,
            'active_quotes': active,
            'won_quotes': won,
            'closed_quotes': closed,
            'total_value': total_value,
            'won_value': won_value,
            'win_rate': round(win_rate, 2)
        }
