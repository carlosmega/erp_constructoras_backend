"""
Quote Template schemas (DTOs) for API requests and responses.

Implements QuoteTemplate entity following Dynamics CDS patterns.
"""

from ninja import ModelSchema, Schema
from typing import Optional, List, Any
from uuid import UUID

from apps.quotes.models import QuoteTemplate


class QuoteTemplateSchema(ModelSchema):
    """Full QuoteTemplate response schema."""

    class Meta:
        model = QuoteTemplate
        fields = '__all__'


class CreateQuoteTemplateDto(Schema):
    """DTO for creating a new quote template."""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    templatedata: dict
    ownerid: Optional[UUID] = None
    isshared: bool = False


class UpdateQuoteTemplateDto(Schema):
    """DTO for updating a quote template."""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    templatedata: Optional[dict] = None
    isshared: Optional[bool] = None


class UseQuoteTemplateDto(Schema):
    """DTO for using a template to create quote data."""
    overrides: Optional[dict] = None


class CreateFromQuoteDto(Schema):
    """DTO for creating a template from an existing quote."""
    quote_id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    isshared: bool = False
