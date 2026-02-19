"""
Quote Template business logic services.

Implements QuoteTemplate operations following the same patterns
as QuoteService for ownership, permissions, and data access.
"""

from django.db import transaction
from django.db.models import Q, F
from uuid import UUID

from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import can_modify_record, filter_by_ownership
from apps.quotes.models import QuoteTemplate, Quote, QuoteDetail
from apps.quotes.template_schemas import (
    CreateQuoteTemplateDto,
    UpdateQuoteTemplateDto,
)
from apps.users.models import SystemUser


class QuoteTemplateService:
    """Service class for QuoteTemplate operations."""

    @staticmethod
    def list_templates(user: SystemUser, shared: bool = None, owner: UUID = None):
        """
        List quote templates with optional filtering.

        If shared=True, return all shared templates regardless of ownership.
        Otherwise, filter by ownership using standard RBAC rules.
        Optionally filter by a specific owner UUID.
        """
        if shared is True:
            # Shared templates are visible to all authenticated users
            queryset = QuoteTemplate.objects.filter(isshared=True)
        else:
            # Apply standard ownership filtering
            queryset = filter_by_ownership(QuoteTemplate.objects.all(), user)

        if owner is not None:
            queryset = queryset.filter(ownerid=owner)

        queryset = queryset.select_related('ownerid', 'createdby', 'modifiedby')
        return list(queryset)

    @staticmethod
    def get_template_by_id(template_id: UUID, user: SystemUser) -> QuoteTemplate:
        """
        Get a quote template by ID.

        Shared templates are visible to all authenticated users.
        Non-shared templates require ownership check.
        """
        try:
            template = QuoteTemplate.objects.select_related(
                'ownerid', 'createdby', 'modifiedby'
            ).get(quotetemplateid=template_id)
        except QuoteTemplate.DoesNotExist:
            raise NotFound('Quote template not found')

        # Shared templates are visible to everyone
        if template.isshared:
            return template

        # Non-shared templates require ownership check
        if not can_modify_record(user, template.ownerid):
            raise PermissionDenied('You do not have permission to view this template')

        return template

    @staticmethod
    @transaction.atomic
    def create_template(dto: CreateQuoteTemplateDto, user: SystemUser) -> QuoteTemplate:
        """Create a new quote template."""
        # Resolve owner
        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise NotFound('Owner not found')

        template = QuoteTemplate.objects.create(
            name=dto.name,
            description=dto.description,
            category=dto.category,
            templatedata=dto.templatedata,
            isshared=dto.isshared,
            ownerid=owner,
            createdby=user,
            modifiedby=user,
        )

        return template

    @staticmethod
    @transaction.atomic
    def update_template(
        template_id: UUID, dto: UpdateQuoteTemplateDto, user: SystemUser
    ) -> QuoteTemplate:
        """Update a quote template (ownership check)."""
        try:
            template = QuoteTemplate.objects.select_related('ownerid').get(
                quotetemplateid=template_id
            )
        except QuoteTemplate.DoesNotExist:
            raise NotFound('Quote template not found')

        if not can_modify_record(user, template.ownerid):
            raise PermissionDenied('You do not have permission to modify this template')

        if dto.name is not None:
            template.name = dto.name
        if dto.description is not None:
            template.description = dto.description
        if dto.category is not None:
            template.category = dto.category
        if dto.templatedata is not None:
            template.templatedata = dto.templatedata
        if dto.isshared is not None:
            template.isshared = dto.isshared

        template.modifiedby = user
        template.save()

        return template

    @staticmethod
    @transaction.atomic
    def delete_template(template_id: UUID, user: SystemUser):
        """Delete a quote template (ownership check)."""
        try:
            template = QuoteTemplate.objects.select_related('ownerid').get(
                quotetemplateid=template_id
            )
        except QuoteTemplate.DoesNotExist:
            raise NotFound('Quote template not found')

        if not can_modify_record(user, template.ownerid):
            raise PermissionDenied('You do not have permission to delete this template')

        template.delete()

    @staticmethod
    @transaction.atomic
    def use_template(template_id: UUID, overrides: dict, user: SystemUser) -> dict:
        """
        Use a template to generate quote creation data.

        Increments usagecount and returns the template data merged with
        any provided overrides, formatted for quote creation.
        """
        try:
            template = QuoteTemplate.objects.select_related('ownerid').get(
                quotetemplateid=template_id
            )
        except QuoteTemplate.DoesNotExist:
            raise NotFound('Quote template not found')

        # Shared templates can be used by anyone; non-shared require ownership
        if not template.isshared and not can_modify_record(user, template.ownerid):
            raise PermissionDenied('You do not have permission to use this template')

        # Increment usage count
        QuoteTemplate.objects.filter(quotetemplateid=template_id).update(
            usagecount=F('usagecount') + 1
        )

        # Build quote creation data from template
        quote_data = dict(template.templatedata)

        # Apply overrides
        if overrides:
            quote_data.update(overrides)

        # Ensure ownerid is set to current user if not overridden
        if 'ownerid' not in quote_data:
            quote_data['ownerid'] = str(user.systemuserid)

        return quote_data

    @staticmethod
    @transaction.atomic
    def create_from_quote(
        quote_id: UUID, name: str, user: SystemUser,
        description: str = None, category: str = None, isshared: bool = False
    ) -> QuoteTemplate:
        """
        Create a template from an existing quote.

        Reads the Quote and its QuoteDetails, packaging them into
        templatedata format with quote-level fields and line items.
        """
        try:
            quote = Quote.objects.select_related(
                'opportunityid', 'accountid', 'contactid', 'ownerid'
            ).get(quoteid=quote_id)
        except Quote.DoesNotExist:
            raise NotFound('Quote not found')

        # Permission check on the source quote
        if not can_modify_record(user, quote.ownerid):
            raise PermissionDenied('You do not have permission to access this quote')

        # Read quote details (line items)
        details = QuoteDetail.objects.filter(quoteid=quote).order_by('sequencenumber')

        # Build line items from quote details
        lines = []
        for detail in details:
            lines.append({
                'productname': detail.productname,
                'productdescription': detail.productdescription or '',
                'quantity': str(detail.quantity),
                'priceperunit': str(detail.priceperunit),
                'manualdiscountamount': str(detail.manualdiscountamount),
                'tax': str(detail.tax),
                'sequencenumber': detail.sequencenumber,
            })

        # Package templatedata
        templatedata = {
            'name': quote.name,
            'description': quote.description or '',
            'discountpercentage': str(quote.discountpercentage),
            'lines': lines,
        }

        template = QuoteTemplate.objects.create(
            name=name,
            description=description,
            category=category,
            templatedata=templatedata,
            isshared=isshared,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        return template
