"""
Unit tests for Quote models.

Tests Quote and QuoteDetail entities including state management,
validation, computed properties, and totals calculation.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.quotes.models import (
    Quote,
    QuoteDetail,
    QuoteStateCode,
    QuoteStatusCode,
)
from apps.quotes.tests.factories import (
    QuoteFactory,
    QuoteDetailFactory,
    ActiveQuoteFactory,
    WonQuoteFactory,
    ClosedQuoteFactory,
    QuoteWithDiscountFactory,
    ExpiredQuoteFactory,
)
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestQuoteEnums:
    """Tests for Quote enum definitions."""

    def test_quote_state_code_values(self):
        """Test QuoteStateCode enum values."""
        assert QuoteStateCode.DRAFT.value == 0
        assert QuoteStateCode.ACTIVE.value == 1
        assert QuoteStateCode.WON.value == 2
        assert QuoteStateCode.CLOSED.value == 3

    def test_quote_status_code_values(self):
        """Test QuoteStatusCode enum values."""
        assert QuoteStatusCode.IN_PROGRESS.value == 1
        assert QuoteStatusCode.IN_REVIEW.value == 2
        assert QuoteStatusCode.WON.value == 3
        assert QuoteStatusCode.LOST.value == 4


@pytest.mark.unit
class TestQuoteModel:
    """Tests for Quote model creation and basic operations."""

    def test_create_quote_minimal(self, db):
        """Test creating quote with minimal required fields."""
        owner = SalespersonFactory()

        quote = Quote.objects.create(
            name='Test Quote',
            quotenumber='Q-2024-001',
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )

        assert quote.quoteid is not None
        assert quote.name == 'Test Quote'
        assert quote.statecode == QuoteStateCode.DRAFT
        assert quote.totalamount == Decimal('0.00')

    def test_quote_factory(self, db):
        """Test QuoteFactory creates valid quotes."""
        quote = QuoteFactory()

        assert quote.quoteid is not None
        assert quote.quotenumber is not None
        assert quote.ownerid is not None

    def test_quote_str_representation(self, db):
        """Test __str__ method."""
        quote = QuoteFactory(quotenumber='Q-2024-001', name='Test Quote')
        assert 'Q-2024-001' in str(quote)
        assert 'Test Quote' in str(quote)


@pytest.mark.unit
class TestQuoteProperties:
    """Tests for Quote computed properties."""

    def test_customer_name_property_from_account(self, db, salesperson):
        """Test customer_name property from account."""
        from apps.accounts.models import Account
        account = Account.objects.create(name='Acme Corp', ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        quote = QuoteFactory(accountid=account, contactid=None, ownerid=salesperson)

        assert quote.customer_name == 'Acme Corp'

    def test_customer_name_property_none(self, db):
        """Test customer_name property returns None."""
        quote = QuoteFactory(accountid=None, contactid=None)
        assert quote.customer_name is None


@pytest.mark.unit
class TestQuoteTotalsCalculation:
    """Tests for Quote totals calculation."""

    def test_calculate_totals_no_items(self, db):
        """Test calculate_totals with no line items."""
        quote = QuoteFactory()

        total = quote.calculate_totals()

        assert total == Decimal('0.00')
        assert quote.totallineitemamount == Decimal('0.00')
        assert quote.totalamount == Decimal('0.00')

    def test_calculate_totals_with_items(self, db):
        """Test calculate_totals with line items."""
        quote = QuoteFactory()

        # Create line items
        QuoteDetailFactory(
            quoteid=quote,
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00')
        )
        QuoteDetailFactory(
            quoteid=quote,
            quantity=Decimal('5.00'),
            priceperunit=Decimal('200.00')
        )

        total = quote.calculate_totals()

        # 10*100 + 5*200 = 1000 + 1000 = 2000
        assert quote.totallineitemamount == Decimal('2000.00')
        assert quote.totalamount == Decimal('2000.00')

    def test_calculate_totals_with_discount(self, db):
        """Test calculate_totals with discount percentage."""
        quote = QuoteFactory(discountpercentage=Decimal('10.00'))

        QuoteDetailFactory(
            quoteid=quote,
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00')
        )

        total = quote.calculate_totals()

        # 10*100 = 1000, discount = 10% = 100, total = 900
        assert quote.totallineitemamount == Decimal('1000.00')
        assert quote.totaldiscountamount == Decimal('100.00')
        assert quote.totalamount == Decimal('900.00')


@pytest.mark.unit
class TestQuoteDetail:
    """Tests for QuoteDetail model."""

    def test_create_quote_detail(self, db):
        """Test creating quote detail."""
        quote = QuoteFactory()

        detail = QuoteDetail.objects.create(
            quoteid=quote,
            productname='Test Product',
            quantity=Decimal('5.00'),
            priceperunit=Decimal('100.00'),
        )

        # Auto-calculated on save
        assert detail.baseamount == Decimal('500.00')
        assert detail.extendedamount == Decimal('500.00')

    def test_quote_detail_with_discount(self, db):
        """Test quote detail with manual discount."""
        quote = QuoteFactory()

        detail = QuoteDetail.objects.create(
            quoteid=quote,
            productname='Test Product',
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00'),
            manualdiscountamount=Decimal('50.00'),
        )

        # 10*100 = 1000, minus 50 = 950
        assert detail.baseamount == Decimal('1000.00')
        assert detail.extendedamount == Decimal('950.00')

    def test_quote_detail_str_representation(self, db):
        """Test __str__ method."""
        quote = QuoteFactory()
        detail = QuoteDetailFactory(quoteid=quote, productname='Widget', quantity=Decimal('5.00'))

        assert 'Widget' in str(detail)
        assert '5' in str(detail)


@pytest.mark.unit
class TestQuoteFactories:
    """Tests for Quote factories."""

    def test_active_quote_factory(self, db):
        """Test ActiveQuoteFactory creates active quotes."""
        quote = ActiveQuoteFactory()

        assert quote.statecode == QuoteStateCode.ACTIVE
        assert quote.statuscode == QuoteStatusCode.IN_REVIEW

    def test_won_quote_factory(self, db):
        """Test WonQuoteFactory creates won quotes."""
        quote = WonQuoteFactory()

        assert quote.statecode == QuoteStateCode.WON
        assert quote.statuscode == QuoteStatusCode.WON
        assert quote.closedon is not None

    def test_closed_quote_factory(self, db):
        """Test ClosedQuoteFactory creates closed quotes."""
        quote = ClosedQuoteFactory()

        assert quote.statecode == QuoteStateCode.CLOSED
        assert quote.closedon is not None
