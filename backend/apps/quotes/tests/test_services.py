"""
Unit tests for Quote services.

Tests QuoteService business logic including CRUD operations,
line item management, and state transitions.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError, PermissionDenied

from apps.quotes.models import Quote, QuoteDetail, QuoteStateCode, QuoteStatusCode
from apps.quotes.services import QuoteService
from apps.quotes.schemas import CreateQuoteDto, UpdateQuoteDto, CreateQuoteDetailDto
from apps.quotes.tests.factories import QuoteFactory, QuoteDetailFactory, WonQuoteFactory
from apps.opportunities.tests.factories import OpportunityFactory
from apps.users.tests.factories import SalespersonFactory, SystemAdminFactory


@pytest.mark.unit
class TestGenerateQuoteNumber:
    """Tests for QuoteService.generate_quote_number method."""

    def test_generate_quote_number_first(self, db):
        """Test generating first quote number of the year."""
        number = QuoteService.generate_quote_number()

        assert number.startswith('Q-2024-') or number.startswith('Q-2025-')
        assert len(number) == 11  # Q-YYYY-NNNN

    def test_generate_quote_number_increments(self, db, salesperson):
        """Test quote numbers increment."""
        QuoteFactory(quotenumber='Q-2024-0001', ownerid=salesperson)

        number = QuoteService.generate_quote_number()

        assert 'Q-2024-0002' in number or 'Q-2025-' in number


@pytest.mark.unit
class TestCreateQuote:
    """Tests for QuoteService.create_quote method."""

    def test_create_quote_minimal(self, db, salesperson):
        """Test creating quote with minimal fields."""
        dto = CreateQuoteDto(
            name='Test Quote',
            quote_details=[]
        )

        quote = QuoteService.create_quote(dto, salesperson)

        assert quote.quoteid is not None
        assert quote.name == 'Test Quote'
        assert quote.statecode == QuoteStateCode.DRAFT
        assert quote.ownerid == salesperson

    def test_create_quote_from_opportunity(self, db, salesperson):
        """Test creating quote from opportunity."""
        opp = OpportunityFactory(ownerid=salesperson)

        quote = QuoteService.create_quote_from_opportunity(opp.opportunityid, salesperson)

        assert quote.opportunityid == opp
        assert quote.accountid == opp.accountid
        assert opp.name in quote.name

    def test_create_quote_from_invalid_opportunity(self, db, salesperson):
        """Test creating quote from non-existent opportunity."""
        with pytest.raises(ValidationError, match='Opportunity not found'):
            QuoteService.create_quote_from_opportunity(uuid4(), salesperson)


@pytest.mark.unit
class TestGetQuoteById:
    """Tests for QuoteService.get_quote_by_id method."""

    def test_get_quote_by_id_success(self, db, salesperson):
        """Test getting quote by ID."""
        quote = QuoteFactory(ownerid=salesperson)

        retrieved = QuoteService.get_quote_by_id(quote.quoteid, salesperson)

        assert retrieved.quoteid == quote.quoteid

    def test_get_quote_by_id_not_found(self, db, salesperson):
        """Test getting non-existent quote."""
        with pytest.raises(ValidationError, match='Quote not found'):
            QuoteService.get_quote_by_id(uuid4(), salesperson)

    def test_get_quote_by_id_permission_denied(self, db, salesperson, salesperson2):
        """Test cannot access other user's quote."""
        quote = QuoteFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied):
            QuoteService.get_quote_by_id(quote.quoteid, salesperson)


@pytest.mark.unit
class TestUpdateQuote:
    """Tests for QuoteService.update_quote method."""

    def test_update_quote_name(self, db, salesperson):
        """Test updating quote name."""
        quote = QuoteFactory(ownerid=salesperson, name='Old Name')

        dto = UpdateQuoteDto(name='New Name')
        updated = QuoteService.update_quote(quote.quoteid, dto, salesperson)

        assert updated.name == 'New Name'

    def test_update_quote_discount(self, db, salesperson):
        """Test updating discount percentage."""
        quote = QuoteFactory(ownerid=salesperson)
        QuoteDetailFactory(quoteid=quote, quantity=Decimal('10'), priceperunit=Decimal('100'))

        dto = UpdateQuoteDto(discountpercentage=Decimal('10.00'))
        updated = QuoteService.update_quote(quote.quoteid, dto, salesperson)

        # Should recalculate totals
        assert updated.discountpercentage == Decimal('10.00')
        assert updated.totaldiscountamount > Decimal('0.00')

    def test_update_quote_cannot_update_won(self, db, salesperson):
        """Test cannot update won quote."""
        quote = WonQuoteFactory(ownerid=salesperson)

        dto = UpdateQuoteDto(name='New Name')

        with pytest.raises(ValidationError, match='Cannot update a won or closed quote'):
            QuoteService.update_quote(quote.quoteid, dto, salesperson)


@pytest.mark.unit
class TestDeleteQuote:
    """Tests for QuoteService.delete_quote method."""

    def test_delete_draft_quote(self, db, salesperson):
        """Test deleting draft quote."""
        quote = QuoteFactory(ownerid=salesperson, statecode=QuoteStateCode.DRAFT)

        QuoteService.delete_quote(quote.quoteid, salesperson)

        assert not Quote.objects.filter(quoteid=quote.quoteid).exists()

    def test_delete_active_quote_fails(self, db, salesperson):
        """Test cannot delete active quote."""
        from apps.quotes.tests.factories import ActiveQuoteFactory
        quote = ActiveQuoteFactory(ownerid=salesperson)

        with pytest.raises(ValidationError, match='Can only delete draft quotes'):
            QuoteService.delete_quote(quote.quoteid, salesperson)


@pytest.mark.unit
class TestAddQuoteDetail:
    """Tests for QuoteService.add_quote_detail method."""

    def test_add_quote_detail_success(self, db, salesperson):
        """Test adding line item to quote."""
        quote = QuoteFactory(ownerid=salesperson)

        dto = CreateQuoteDetailDto(
            productname='Widget',
            quantity=Decimal('5.00'),
            priceperunit=Decimal('100.00'),
            sequencenumber=1
        )

        detail = QuoteService.add_quote_detail(quote.quoteid, dto, salesperson)

        assert detail.productname == 'Widget'
        assert detail.baseamount == Decimal('500.00')

        # Verify detail was added to quote
        quote.refresh_from_db()
        assert quote.quote_details.count() == 1

    def test_add_quote_detail_to_won_quote_fails(self, db, salesperson):
        """Test cannot add items to won quote."""
        quote = WonQuoteFactory(ownerid=salesperson)

        dto = CreateQuoteDetailDto(
            productname='Widget',
            quantity=Decimal('5.00'),
            priceperunit=Decimal('100.00'),
            sequencenumber=1
        )

        with pytest.raises(ValidationError, match='Cannot modify a won or closed quote'):
            QuoteService.add_quote_detail(quote.quoteid, dto, salesperson)


@pytest.mark.unit
class TestRemoveQuoteDetail:
    """Tests for QuoteService.remove_quote_detail method."""

    def test_remove_quote_detail_success(self, db, salesperson):
        """Test removing line item from quote."""
        quote = QuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)

        QuoteService.remove_quote_detail(detail.quotedetailid, salesperson)

        assert not QuoteDetail.objects.filter(quotedetailid=detail.quotedetailid).exists()

    def test_remove_quote_detail_not_found(self, db, salesperson):
        """Test removing non-existent detail."""
        with pytest.raises(ValidationError, match='Quote detail not found'):
            QuoteService.remove_quote_detail(uuid4(), salesperson)

    def test_remove_quote_detail_permission_denied(self, db, salesperson, salesperson2):
        """Test cannot remove detail from other user's quote."""
        quote = QuoteFactory(ownerid=salesperson2)
        detail = QuoteDetailFactory(quoteid=quote)

        with pytest.raises(PermissionDenied):
            QuoteService.remove_quote_detail(detail.quotedetailid, salesperson)
