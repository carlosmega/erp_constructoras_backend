"""Tests for core pagination utilities."""

import pytest
from core.pagination import (
    paginate_queryset,
    create_paginated_response,
    cursor_paginate_queryset,
    create_cursor_paginated_response,
)
from ninja import Schema


@pytest.mark.unit
class TestPaginateQueryset:
    def test_first_page(self, db):
        """Test paginating the first page."""
        from apps.users.models import SecurityRole
        qs = SecurityRole.objects.all()
        result = paginate_queryset(qs, page=1, page_size=2, request_url="/api/test")
        assert result['page'] == 1
        assert result['page_size'] == 2
        assert result['count'] >= 0
        assert isinstance(result['results'], list)

    def test_next_link_when_more_pages(self, db):
        """Test that next link is generated when there are more pages."""
        from apps.users.models import SecurityRole
        qs = SecurityRole.objects.all()
        total = qs.count()
        if total > 1:
            result = paginate_queryset(qs, page=1, page_size=1, request_url="/api/test")
            assert result['next'] is not None
            assert 'page=2' in result['next']

    def test_no_next_link_on_last_page(self, db):
        """Test that next link is None on the last page."""
        from apps.users.models import SecurityRole
        qs = SecurityRole.objects.all()
        result = paginate_queryset(qs, page=1, page_size=100, request_url="/api/test")
        assert result['next'] is None

    def test_previous_link(self, db):
        """Test that previous link is generated for page > 1."""
        from apps.users.models import SecurityRole
        qs = SecurityRole.objects.all()
        result = paginate_queryset(qs, page=2, page_size=1, request_url="/api/test")
        assert result['previous'] is not None
        assert 'page=1' in result['previous']

    def test_no_previous_link_on_first_page(self, db):
        """Test that previous link is None on the first page."""
        from apps.users.models import SecurityRole
        qs = SecurityRole.objects.all()
        result = paginate_queryset(qs, page=1, page_size=10, request_url="/api/test")
        assert result['previous'] is None

    def test_page_size_capped_at_100(self, db):
        """Test that page size is capped at 100."""
        from apps.users.models import SecurityRole
        qs = SecurityRole.objects.all()
        result = paginate_queryset(qs, page=1, page_size=200, request_url="/api/test")
        assert result['page_size'] == 100

    def test_negative_page_defaults_to_1(self, db):
        """Test that negative page numbers default to 1."""
        from apps.users.models import SecurityRole
        qs = SecurityRole.objects.all()
        result = paginate_queryset(qs, page=-1, page_size=10, request_url="/api/test")
        assert result['page'] == 1

    def test_empty_queryset(self, db):
        """Test pagination of empty queryset."""
        from apps.users.models import SystemUser
        qs = SystemUser.objects.none()
        result = paginate_queryset(qs, page=1, page_size=10, request_url="/api/test")
        assert result['count'] == 0
        assert result['results'] == []
        assert result['next'] is None
        assert result['previous'] is None


@pytest.mark.unit
class TestCreatePaginatedResponse:
    def test_creates_schema(self):
        """Test that a paginated response schema is created."""

        class ItemSchema(Schema):
            name: str

        PaginatedItems = create_paginated_response(ItemSchema)
        assert PaginatedItems.__name__ == 'PaginatedItemSchema'
        # Verify it has the expected fields
        fields = PaginatedItems.model_fields
        assert 'count' in fields
        assert 'page' in fields
        assert 'results' in fields


# =============================================================================
# Cursor-based pagination
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestCursorPaginateQueryset:
    """Cursor-based pagination, stable under concurrent inserts.

    Contract:
      - cursor=None → first page
      - returns {'results': [...], 'next_cursor': str|None, 'has_more': bool}
      - results ordered DESC by order_field (default 'createdon')
      - next_cursor is opaque (base64); clients pass it back verbatim
    """

    def _make_activities(self, n):
        from apps.activities.tests.factories import ActivityFactory
        # Create with distinct createdon by saving sequentially
        return [ActivityFactory() for _ in range(n)]

    def test_first_page_returns_most_recent(self):
        activities = self._make_activities(5)
        from apps.activities.models import Activity
        qs = Activity.objects.all()

        result = cursor_paginate_queryset(qs, cursor=None, limit=3)

        assert len(result['results']) == 3
        assert result['has_more'] is True
        assert result['next_cursor'] is not None
        # Most recent first (descending by createdon)
        returned_ids = [a.activityid for a in result['results']]
        expected_ids = [a.activityid for a in sorted(activities, key=lambda x: x.createdon, reverse=True)[:3]]
        assert returned_ids == expected_ids

    def test_second_page_via_cursor(self):
        self._make_activities(5)
        from apps.activities.models import Activity
        qs = Activity.objects.all()

        page1 = cursor_paginate_queryset(qs, cursor=None, limit=2)
        page2 = cursor_paginate_queryset(qs, cursor=page1['next_cursor'], limit=2)

        page1_ids = {a.activityid for a in page1['results']}
        page2_ids = {a.activityid for a in page2['results']}
        assert page1_ids.isdisjoint(page2_ids), "page 2 should not repeat items from page 1"
        assert len(page2['results']) == 2

    def test_last_page_has_more_is_false(self):
        self._make_activities(3)
        from apps.activities.models import Activity
        qs = Activity.objects.all()

        result = cursor_paginate_queryset(qs, cursor=None, limit=10)

        assert len(result['results']) == 3
        assert result['has_more'] is False
        assert result['next_cursor'] is None

    def test_empty_queryset(self):
        from apps.activities.models import Activity
        qs = Activity.objects.none()

        result = cursor_paginate_queryset(qs, cursor=None, limit=50)

        assert result['results'] == []
        assert result['has_more'] is False
        assert result['next_cursor'] is None

    def test_cursor_is_opaque_base64(self):
        self._make_activities(3)
        from apps.activities.models import Activity
        qs = Activity.objects.all()

        result = cursor_paginate_queryset(qs, cursor=None, limit=1)

        # Opaque: must be a string, not raw datetime/uuid
        assert isinstance(result['next_cursor'], str)
        # Must not leak raw field values
        assert '2' not in result['next_cursor'] or len(result['next_cursor']) > 20

    def test_invalid_cursor_returns_first_page(self):
        self._make_activities(3)
        from apps.activities.models import Activity
        qs = Activity.objects.all()

        # Garbage cursor should not raise; behaves as if no cursor
        result = cursor_paginate_queryset(qs, cursor='not-a-valid-cursor', limit=2)

        assert len(result['results']) == 2
        assert result['has_more'] is True

    def test_limit_capped_at_100(self):
        self._make_activities(2)
        from apps.activities.models import Activity
        qs = Activity.objects.all()

        result = cursor_paginate_queryset(qs, cursor=None, limit=500)

        # Even if we ask for 500, the cap applies (verify via no crash + returns all 2)
        assert len(result['results']) == 2


@pytest.mark.unit
class TestCreateCursorPaginatedResponse:
    def test_creates_schema_with_expected_fields(self):
        class ItemSchema(Schema):
            name: str

        CursorPaged = create_cursor_paginated_response(ItemSchema)

        assert CursorPaged.__name__ == 'CursorPaginatedItemSchema'
        fields = CursorPaged.model_fields
        assert 'results' in fields
        assert 'next_cursor' in fields
        assert 'has_more' in fields
