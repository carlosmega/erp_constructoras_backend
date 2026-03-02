"""Tests for core pagination utilities."""

import pytest
from core.pagination import paginate_queryset, create_paginated_response
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
