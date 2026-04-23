"""
Pagination utilities for CRM Backend Foundation.

Two strategies are supported:

1. **Offset-based** (`paginate_queryset` + `create_paginated_response`)
   Classic page/page_size pagination. Best for admin tables where users expect
   page numbers ("page 3 of 12"). Downside: unstable under concurrent inserts.

2. **Cursor-based** (`cursor_paginate_queryset` + `create_cursor_paginated_response`)
   Opaque-cursor pagination ordered DESC by a datetime field (default
   `createdon`). Stable under concurrent inserts. Best for feeds, timelines,
   activities, notifications — anywhere `useInfiniteQuery` is natural.

Both helpers are opt-in — the rest of the codebase continues to return plain
arrays until a specific endpoint adopts pagination.
"""

import base64
import binascii
from datetime import datetime
from typing import Generic, TypeVar, List, Optional, Type
from django.db.models import Q
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


# =============================================================================
# Cursor-based pagination (for timelines, feeds, notifications)
# =============================================================================

_CURSOR_SEP = '|'


def _encode_cursor(order_value, pk_value) -> str:
    raw = f"{order_value.isoformat()}{_CURSOR_SEP}{pk_value}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str):
    """Return (datetime, pk_str) or None if cursor is malformed."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        dt_str, pk_str = raw.split(_CURSOR_SEP, 1)
        return datetime.fromisoformat(dt_str), pk_str
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error):
        return None


def cursor_paginate_queryset(
    queryset,
    cursor: Optional[str] = None,
    limit: int = 50,
    order_field: str = 'createdon',
):
    """
    Paginate `queryset` using an opaque cursor ordered DESC by `order_field`.

    Tie-breaking uses the model's primary key, so ordering is stable even when
    multiple rows share the same datetime. Invalid cursors are treated as
    "no cursor" (first page).

    Args:
        queryset: Django QuerySet to paginate.
        cursor: Opaque cursor from a previous call's `next_cursor`, or None.
        limit: Page size (clamped to 1..100).
        order_field: Datetime field to order DESC by (default 'createdon').

    Returns:
        dict with keys:
            results (List): up to `limit` model instances
            next_cursor (Optional[str]): cursor for next page, None on last page
            has_more (bool): True if more pages exist
    """
    limit = min(max(1, limit), 100)
    pk_name = queryset.model._meta.pk.attname

    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            cursor_dt, cursor_pk = decoded
            queryset = queryset.filter(
                Q(**{f'{order_field}__lt': cursor_dt})
                | Q(**{order_field: cursor_dt, f'{pk_name}__lt': cursor_pk})
            )

    queryset = queryset.order_by(f'-{order_field}', f'-{pk_name}')
    # Fetch limit+1 to know whether there's another page
    items = list(queryset[:limit + 1])

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = _encode_cursor(
            getattr(last, order_field),
            getattr(last, pk_name),
        )

    return {
        'results': items,
        'next_cursor': next_cursor,
        'has_more': has_more,
    }


def create_cursor_paginated_response(item_schema: Type):
    """
    Factory for cursor-paginated response schemas.

    Usage:
        CursorActivityList = create_cursor_paginated_response(ActivityListItemSchema)

        @router.get("/", response=CursorActivityList)
        def list_items(request, cursor: Optional[str] = None, limit: int = 50):
            qs = ...
            return cursor_paginate_queryset(qs, cursor, limit)
    """
    class CursorPaginatedResponse(Schema):
        results: List[item_schema]
        next_cursor: Optional[str] = None
        has_more: bool = False

    CursorPaginatedResponse.__qualname__ = f'CursorPaginated{item_schema.__name__}'
    CursorPaginatedResponse.__name__ = f'CursorPaginated{item_schema.__name__}'
    return CursorPaginatedResponse
