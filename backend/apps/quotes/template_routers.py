"""
Quote Template API routers.

Implements CRUD and special actions for QuoteTemplate entity.
"""

from ninja import Router
from django.http import HttpRequest
from typing import List
from uuid import UUID

from apps.quotes.template_services import QuoteTemplateService
from apps.quotes.template_schemas import (
    QuoteTemplateSchema,
    CreateQuoteTemplateDto,
    UpdateQuoteTemplateDto,
    UseQuoteTemplateDto,
    CreateFromQuoteDto,
)
from core.permissions import require_permission, Permission

quote_templates_router = Router(tags=['Quote Templates'])


@quote_templates_router.get('/', response=List[QuoteTemplateSchema])
@require_permission(Permission.QUOTE_READ)
def list_templates(request: HttpRequest, shared: bool = None, owner: UUID = None):
    """
    List quote templates with optional filtering.

    Filters:
    - shared: If true, return all shared templates
    - owner: Filter by owner ID
    """
    templates = QuoteTemplateService.list_templates(request.user, shared=shared, owner=owner)
    return templates


@quote_templates_router.post('/', response={201: QuoteTemplateSchema})
@require_permission(Permission.QUOTE_CREATE)
def create_template(request: HttpRequest, payload: CreateQuoteTemplateDto):
    """Create a new quote template."""
    template = QuoteTemplateService.create_template(payload, request.user)
    return 201, template


# Static path routes MUST come before dynamic /{template_id} routes
@quote_templates_router.post('/from-quote', response={201: QuoteTemplateSchema})
@require_permission(Permission.QUOTE_CREATE)
def create_from_quote(request: HttpRequest, payload: CreateFromQuoteDto):
    """
    Create a quote template from an existing quote.

    Copies the quote's details (line items) into templatedata format.
    """
    template = QuoteTemplateService.create_from_quote(
        quote_id=payload.quote_id,
        name=payload.name,
        user=request.user,
        description=payload.description,
        category=payload.category,
        isshared=payload.isshared,
    )
    return 201, template


@quote_templates_router.get('/{template_id}', response=QuoteTemplateSchema)
@require_permission(Permission.QUOTE_READ)
def get_template(request: HttpRequest, template_id: UUID):
    """Get a single quote template by ID."""
    template = QuoteTemplateService.get_template_by_id(template_id, request.user)
    return template


@quote_templates_router.patch('/{template_id}', response=QuoteTemplateSchema)
@require_permission(Permission.QUOTE_UPDATE)
def update_template(request: HttpRequest, template_id: UUID, payload: UpdateQuoteTemplateDto):
    """Update a quote template."""
    template = QuoteTemplateService.update_template(template_id, payload, request.user)
    return template


@quote_templates_router.delete('/{template_id}', response={204: None})
@require_permission(Permission.QUOTE_DELETE)
def delete_template(request: HttpRequest, template_id: UUID):
    """Delete a quote template."""
    QuoteTemplateService.delete_template(template_id, request.user)
    return 204, None


@quote_templates_router.post('/{template_id}/use', response=dict)
@require_permission(Permission.QUOTE_CREATE)
def use_template(request: HttpRequest, template_id: UUID, payload: UseQuoteTemplateDto = None):
    """
    Use a template to generate quote creation data.

    Increments the template's usage count and returns the template data
    merged with any provided overrides, ready for quote creation.
    """
    overrides = payload.overrides if payload and payload.overrides else {}
    quote_data = QuoteTemplateService.use_template(template_id, overrides, request.user)
    return quote_data
