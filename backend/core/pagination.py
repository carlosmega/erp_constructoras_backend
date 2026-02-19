"""
Pagination utilities for CRM Backend Foundation.

Provides consistent pagination across all list endpoints.
"""

from typing import Generic, TypeVar, List, Optional, Type
from ninja import Schema


def create_paginated_response(item_schema: Type):
    """
    Factory to create a paginated response schema for a given item schema.

    Usage:
        PaginatedLeadList = create_paginated_response(LeadListSchema)

        @router.get("/", response=PaginatedLeadList)
        def list_items(request, page: int = 1, page_size: int = 50):
            queryset = ...
            return paginate_queryset(queryset, page, page_size, request.path)
    """
    class PaginatedResponse(Schema):
        count: int
        page: int
        page_size: int
        next: Optional[str] = None
        previous: Optional[str] = None
        results: List[item_schema]

    PaginatedResponse.__qualname__ = f'Paginated{item_schema.__name__}'
    PaginatedResponse.__name__ = f'Paginated{item_schema.__name__}'
    return PaginatedResponse


def paginate_queryset(queryset, page: int = 1, page_size: int = 50, request_url: str = ""):
    """
    Paginate a Django queryset and return standardized response.

    Args:
        queryset: Django QuerySet to paginate
        page: Page number (1-indexed)
        page_size: Number of records per page (default: 50, max: 100)
        request_url: Base URL for next/previous links

    Returns:
        Dictionary with count, page, page_size, next, previous, and results
    """
    # Ensure positive values
    page = max(1, page)
    page_size = min(max(1, page_size), 100)  # Max 100 per page

    # Get total count
    total_count = queryset.count()

    # Calculate pagination
    start = (page - 1) * page_size
    end = start + page_size

    # Get page results
    results = list(queryset[start:end])

    # Calculate next/previous URLs
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    next_url = None
    if page < total_pages:
        next_url = f"{request_url}?page={page + 1}&page_size={page_size}"

    previous_url = None
    if page > 1:
        previous_url = f"{request_url}?page={page - 1}&page_size={page_size}"

    return {
        "count": total_count,
        "page": page,
        "page_size": page_size,
        "next": next_url,
        "previous": previous_url,
        "results": results,
    }
