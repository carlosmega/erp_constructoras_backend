"""
Pagination utilities for CRM Backend Foundation.

Provides consistent pagination across all list endpoints.
"""

from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response format for list endpoints.

    Attributes:
        count: Total number of records matching the query
        next: URL to next page (null if last page)
        previous: URL to previous page (null if first page)
        results: List of records for current page
    """

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[T]

    class Config:
        from_attributes = True  # Allow ORM models


def paginate_queryset(queryset, page: int = 1, page_size: int = 50, request_url: str = ""):
    """
    Paginate a Django queryset and return standardized response.

    Args:
        queryset: Django QuerySet to paginate
        page: Page number (1-indexed)
        page_size: Number of records per page (default: 50)
        request_url: Base URL for next/previous links

    Returns:
        Dictionary with count, next, previous, and results

    Example:
        queryset = SystemUser.objects.all()
        paginated = paginate_queryset(queryset, page=1, page_size=50)
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
    total_pages = (total_count + page_size - 1) // page_size

    next_url = None
    if page < total_pages:
        next_url = f"{request_url}?page={page + 1}&page_size={page_size}"

    previous_url = None
    if page > 1:
        previous_url = f"{request_url}?page={page - 1}&page_size={page_size}"

    return {
        "count": total_count,
        "next": next_url,
        "previous": previous_url,
        "results": results
    }
