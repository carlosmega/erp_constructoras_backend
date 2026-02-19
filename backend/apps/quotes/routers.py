"""
Quote API routers.

Phase 8 Implementation: Quote Management
"""

from ninja import Router
from django.http import HttpRequest
from typing import List
from uuid import UUID

from apps.quotes.services import QuoteService
from apps.quotes.schemas import (
    QuoteSchema, QuoteListItemSchema, CreateQuoteDto, UpdateQuoteDto,
    CreateQuoteDetailDto, UpdateQuoteDetailDto, QuoteDetailSchema,
    ActivateQuoteDto, CloseQuoteDto, QuoteStatsSchema
)
from core.permissions import require_permission, Permission

quotes_router = Router(tags=['Quotes'])


@quotes_router.get('/', response=List[QuoteListItemSchema])
@require_permission(Permission.QUOTE_READ)
def list_quotes(request: HttpRequest, state: int = None, statecode: int = None, owner: UUID = None):
    """
    List all quotes with optional filtering.

    Filters:
    - state/statecode: Filter by statecode (0=Draft, 1=Active, 2=Won, 3=Closed)
    - owner: Filter by owner ID
    """
    from apps.quotes.models import Quote
    from core.permissions import filter_by_ownership

    queryset = filter_by_ownership(Quote.objects.all(), request.user)

    effective_state = statecode if statecode is not None else state
    if effective_state is not None:
        queryset = queryset.filter(statecode=effective_state)
    if owner:
        queryset = queryset.filter(ownerid=owner)

    queryset = queryset.select_related('accountid', 'contactid', 'ownerid')
    return list(queryset)


@quotes_router.post('/', response={201: QuoteSchema})
@require_permission(Permission.QUOTE_CREATE)
def create_quote(request: HttpRequest, payload: CreateQuoteDto):
    """Create a new quote with optional line items."""
    quote = QuoteService.create_quote(payload, request.user)
    return 201, quote


@quotes_router.post('/from-opportunity/{opportunity_id}', response={201: QuoteSchema})
@require_permission(Permission.QUOTE_CREATE)
def create_quote_from_opportunity(request: HttpRequest, opportunity_id: UUID):
    """Create a quote from an existing opportunity."""
    quote = QuoteService.create_quote_from_opportunity(opportunity_id, request.user)
    return 201, quote


@quotes_router.get('/{quote_id}', response=QuoteSchema)
@require_permission(Permission.QUOTE_READ)
def get_quote(request: HttpRequest, quote_id: UUID):
    """Get a single quote by ID."""
    quote = QuoteService.get_quote_by_id(quote_id, request.user)
    return quote


@quotes_router.patch('/{quote_id}', response=QuoteSchema)
@require_permission(Permission.QUOTE_UPDATE)
def update_quote(request: HttpRequest, quote_id: UUID, payload: UpdateQuoteDto):
    """Update a quote."""
    quote = QuoteService.update_quote(quote_id, payload, request.user)
    return quote


@quotes_router.delete('/{quote_id}', response={204: None})
@require_permission(Permission.QUOTE_DELETE)
def delete_quote(request: HttpRequest, quote_id: UUID):
    """Delete a quote (only draft quotes)."""
    QuoteService.delete_quote(quote_id, request.user)
    return 204, None


# ============ Quote Detail Endpoints ============

@quotes_router.get('/{quote_id}/details', response=List[QuoteDetailSchema])
@require_permission(Permission.QUOTE_READ)
def list_quote_details(request: HttpRequest, quote_id: UUID):
    """List all line items for a quote."""
    from apps.quotes.models import QuoteDetail as QuoteDetailModel
    details = QuoteDetailModel.objects.filter(quoteid_id=quote_id).order_by('sequencenumber')
    return list(details)


@quotes_router.post('/{quote_id}/details', response={201: QuoteDetailSchema})
@require_permission(Permission.QUOTE_UPDATE)
def add_quote_detail(request: HttpRequest, quote_id: UUID, payload: CreateQuoteDetailDto):
    """Add a line item to a quote."""
    detail = QuoteService.add_quote_detail(quote_id, payload, request.user)
    return 201, detail


@quotes_router.get('/details/{detail_id}', response=QuoteDetailSchema)
@require_permission(Permission.QUOTE_READ)
def get_quote_detail(request: HttpRequest, detail_id: UUID):
    """Get a single quote detail by ID."""
    from apps.quotes.models import QuoteDetail as QuoteDetailModel
    from django.shortcuts import get_object_or_404
    detail = get_object_or_404(QuoteDetailModel, quotedetailid=detail_id)
    return detail


@quotes_router.patch('/details/{detail_id}', response=QuoteDetailSchema)
@require_permission(Permission.QUOTE_UPDATE)
def update_quote_detail(request: HttpRequest, detail_id: UUID, payload: UpdateQuoteDetailDto):
    """Update a quote detail line item."""
    from apps.quotes.models import QuoteDetail as QuoteDetailModel
    from django.shortcuts import get_object_or_404
    detail = get_object_or_404(QuoteDetailModel, quotedetailid=detail_id)

    if payload.productname is not None:
        detail.productname = payload.productname
    if payload.productdescription is not None:
        detail.productdescription = payload.productdescription
    if payload.quantity is not None:
        detail.quantity = payload.quantity
    if payload.priceperunit is not None:
        detail.priceperunit = payload.priceperunit
    if payload.manualdiscountamount is not None:
        detail.manualdiscountamount = payload.manualdiscountamount
    if payload.tax is not None:
        detail.tax = payload.tax
    if payload.sequencenumber is not None:
        detail.sequencenumber = payload.sequencenumber

    detail.save()

    # Recalculate quote totals
    detail.quoteid.calculate_totals()

    return detail


@quotes_router.delete('/details/{detail_id}', response={204: None})
@require_permission(Permission.QUOTE_UPDATE)
def remove_quote_detail(request: HttpRequest, detail_id: UUID):
    """Remove a line item from a quote."""
    QuoteService.remove_quote_detail(detail_id, request.user)
    return 204, None


# ============ Quote Actions ============

@quotes_router.post('/{quote_id}/activate', response=QuoteSchema)
@require_permission(Permission.QUOTE_UPDATE)
def activate_quote(request: HttpRequest, quote_id: UUID, payload: ActivateQuoteDto):
    """
    Activate a quote (change from Draft to Active).
    Makes quote ready for customer review.
    """
    quote = QuoteService.activate_quote(quote_id, payload, request.user)
    return quote


@quotes_router.post('/{quote_id}/close', response=QuoteSchema)
@require_permission(Permission.QUOTE_UPDATE)
def close_quote(request: HttpRequest, quote_id: UUID, payload: CloseQuoteDto):
    """
    Close a quote as Won/Lost/Canceled.

    Status codes:
    - 3: Won
    - 4: Lost
    - 5: Canceled
    """
    quote = QuoteService.close_quote(quote_id, payload, request.user)
    return quote


# ============ Statistics ============

@quotes_router.get('/stats/summary', response=QuoteStatsSchema)
@require_permission(Permission.QUOTE_READ)
def get_quote_stats(request: HttpRequest):
    """Get statistics about quotes."""
    stats = QuoteService.get_quote_stats(request.user)
    return stats
