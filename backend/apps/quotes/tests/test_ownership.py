"""
Record-level ownership tests for quote LINE endpoints.

Before this refactor, the flat /details/{detail_id} router handlers fetched a
QuoteDetail with a bare get_object_or_404 and never verified the requesting
user owned the parent quote — so a Salesperson could read/edit another owner's
quote lines. These tests pin the service-layer ownership gate
(can_modify_record against detail.quoteid.ownerid): a non-owner Salesperson is
denied, while the owner, a System Administrator and a Sales Manager succeed.
They also pin the WON/CLOSED state guard the refactor added to line updates.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from core.exceptions import PermissionDenied, NotFound, ValidationError
from apps.quotes.services import QuoteService
from apps.quotes.schemas import UpdateQuoteDetailDto
from apps.quotes.tests.factories import QuoteFactory, QuoteDetailFactory, WonQuoteFactory


@pytest.mark.permissions
@pytest.mark.django_db
class TestQuoteLineOwnership:
    """Ownership enforcement on quote line (QuoteDetail) operations."""

    def test_owner_reads_own_quote_line(self, salesperson):
        quote = QuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)

        got = QuoteService.get_quote_detail(detail.quotedetailid, salesperson)

        assert got.quotedetailid == detail.quotedetailid

    def test_salesperson_cannot_read_another_users_quote_line(self, salesperson, salesperson2):
        quote = QuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)

        # match= pins the denial to the ownership message, not a stray NotFound/crash
        with pytest.raises(PermissionDenied, match='permission'):
            QuoteService.get_quote_detail(detail.quotedetailid, salesperson2)

    def test_salesperson_cannot_update_another_users_quote_line(self, salesperson, salesperson2):
        quote = QuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)

        with pytest.raises(PermissionDenied, match='permission'):
            QuoteService.update_quote_detail(
                detail.quotedetailid, UpdateQuoteDetailDto(quantity=Decimal('9')), salesperson2
            )

    def test_salesperson_cannot_list_another_users_quote_details(self, salesperson, salesperson2):
        quote = QuoteFactory(ownerid=salesperson)
        QuoteDetailFactory(quoteid=quote)

        with pytest.raises(PermissionDenied, match='permission'):
            QuoteService.list_quote_details(quote.quoteid, salesperson2)

    def test_admin_can_read_any_quote_line(self, salesperson, system_admin):
        quote = QuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)

        got = QuoteService.get_quote_detail(detail.quotedetailid, system_admin)

        assert got.quotedetailid == detail.quotedetailid

    def test_manager_can_update_any_quote_line(self, salesperson, sales_manager):
        quote = QuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote, quantity=Decimal('1'), priceperunit=Decimal('100'))

        updated = QuoteService.update_quote_detail(
            detail.quotedetailid, UpdateQuoteDetailDto(quantity=Decimal('4')), sales_manager
        )

        assert updated.quantity == Decimal('4')

    def test_owner_update_recalculates_quote_totals(self, salesperson):
        quote = QuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote, quantity=Decimal('2'), priceperunit=Decimal('100'))
        # Establish a baseline total reflecting the line (factories don't recalc the parent).
        quote.calculate_totals()
        quote.save()
        quote.refresh_from_db()
        before = quote.totalamount

        QuoteService.update_quote_detail(
            detail.quotedetailid, UpdateQuoteDetailDto(quantity=Decimal('5')), salesperson
        )
        quote.refresh_from_db()

        assert quote.totalamount > before

    def test_owner_cannot_update_won_quote_line(self, salesperson):
        # The refactor added this WON/CLOSED guard (the old flat handler had none).
        quote = WonQuoteFactory(ownerid=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)

        with pytest.raises(ValidationError, match='won or closed'):
            QuoteService.update_quote_detail(
                detail.quotedetailid, UpdateQuoteDetailDto(quantity=Decimal('3')), salesperson
            )

    def test_get_quote_detail_not_found_raises_notfound(self, salesperson):
        with pytest.raises(NotFound):
            QuoteService.get_quote_detail(uuid4(), salesperson)

    def test_update_quote_detail_not_found_raises_notfound(self, salesperson):
        with pytest.raises(NotFound):
            QuoteService.update_quote_detail(
                uuid4(), UpdateQuoteDetailDto(quantity=Decimal('1')), salesperson
            )
