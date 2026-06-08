"""
Record-level ownership tests for invoice LINE endpoints.

Before this refactor, the flat /details/{detail_id} router handlers fetched an
InvoiceDetail with a bare get_object_or_404 and never verified the requesting
user owned the parent invoice — so a Salesperson could read/edit/delete another
owner's invoice lines (and the by-id delete left the parent totals stale). These
tests pin the service-layer ownership gate (can_modify_record against
detail.invoiceid.ownerid), the PAID/CANCELED state guard the refactor added, and
the totals recalculation on remove-by-id.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from core.exceptions import PermissionDenied, NotFound, ValidationError
from apps.invoices.services import InvoiceService
from apps.invoices.schemas import UpdateInvoiceDetailDto
from apps.invoices.tests.factories import (
    InvoiceFactory, InvoiceDetailFactory, PaidInvoiceFactory, CanceledInvoiceFactory,
)


@pytest.mark.permissions
@pytest.mark.django_db
class TestInvoiceLineOwnership:
    """Ownership enforcement on invoice line (InvoiceDetail) operations."""

    def test_owner_reads_own_invoice_line(self, salesperson):
        invoice = InvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        got = InvoiceService.get_invoice_detail(detail.invoicedetailid, salesperson)

        assert got.invoicedetailid == detail.invoicedetailid

    def test_salesperson_cannot_read_another_users_invoice_line(self, salesperson, salesperson2):
        invoice = InvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        # match= pins the denial to the ownership message, not a stray NotFound/crash
        with pytest.raises(PermissionDenied, match='permission'):
            InvoiceService.get_invoice_detail(detail.invoicedetailid, salesperson2)

    def test_salesperson_cannot_update_another_users_invoice_line(self, salesperson, salesperson2):
        invoice = InvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        with pytest.raises(PermissionDenied, match='permission'):
            InvoiceService.update_invoice_detail(
                detail.invoicedetailid, UpdateInvoiceDetailDto(quantity=Decimal('5')), salesperson2
            )

    def test_salesperson_cannot_remove_another_users_invoice_line(self, salesperson, salesperson2):
        invoice = InvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        with pytest.raises(PermissionDenied, match='permission'):
            InvoiceService.remove_invoice_detail_by_id(detail.invoicedetailid, salesperson2)

    def test_salesperson_cannot_list_another_users_invoice_details(self, salesperson, salesperson2):
        invoice = InvoiceFactory(ownerid=salesperson)
        InvoiceDetailFactory(invoiceid=invoice)

        with pytest.raises(PermissionDenied, match='permission'):
            InvoiceService.list_invoice_details(invoice.invoiceid, salesperson2)

    def test_admin_can_read_any_invoice_line(self, salesperson, system_admin):
        invoice = InvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        got = InvoiceService.get_invoice_detail(detail.invoicedetailid, system_admin)

        assert got.invoicedetailid == detail.invoicedetailid

    def test_manager_can_remove_any_invoice_line(self, salesperson, sales_manager):
        invoice = InvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        InvoiceService.remove_invoice_detail_by_id(detail.invoicedetailid, sales_manager)

        from apps.invoices.models import InvoiceDetail
        assert not InvoiceDetail.objects.filter(invoicedetailid=detail.invoicedetailid).exists()

    def test_owner_updates_own_invoice_line(self, salesperson):
        invoice = InvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(
            invoiceid=invoice, quantity=Decimal('2'), priceperunit=Decimal('100')
        )
        invoice.calculate_totals()
        invoice.save()
        invoice.refresh_from_db()
        before = invoice.totalamount

        updated = InvoiceService.update_invoice_detail(
            detail.invoicedetailid, UpdateInvoiceDetailDto(quantity=Decimal('5')), salesperson
        )

        assert updated.quantity == Decimal('5')
        invoice.refresh_from_db()
        assert invoice.totalamount > before

    def test_remove_by_id_recalculates_invoice_totals(self, salesperson):
        invoice = InvoiceFactory(ownerid=salesperson)
        InvoiceDetailFactory(invoiceid=invoice, quantity=Decimal('1'), priceperunit=Decimal('100'))
        removable = InvoiceDetailFactory(
            invoiceid=invoice, quantity=Decimal('1'), priceperunit=Decimal('50')
        )
        invoice.calculate_totals()
        invoice.save()
        before = invoice.totalamount

        InvoiceService.remove_invoice_detail_by_id(removable.invoicedetailid, salesperson)
        invoice.refresh_from_db()

        # Old flat handler deleted the line but never recalculated → totals stayed stale.
        assert invoice.totalamount < before

    def test_owner_cannot_update_paid_invoice_line(self, salesperson):
        # The refactor added this PAID/CANCELED guard (the old flat handler had none).
        invoice = PaidInvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        with pytest.raises(ValidationError, match='paid or canceled'):
            InvoiceService.update_invoice_detail(
                detail.invoicedetailid, UpdateInvoiceDetailDto(quantity=Decimal('3')), salesperson
            )

    def test_owner_cannot_remove_canceled_invoice_line(self, salesperson):
        invoice = CanceledInvoiceFactory(ownerid=salesperson)
        detail = InvoiceDetailFactory(invoiceid=invoice)

        with pytest.raises(ValidationError, match='paid or canceled'):
            InvoiceService.remove_invoice_detail_by_id(detail.invoicedetailid, salesperson)

    def test_get_invoice_detail_not_found_raises_notfound(self, salesperson):
        with pytest.raises(NotFound):
            InvoiceService.get_invoice_detail(uuid4(), salesperson)

    def test_update_invoice_detail_not_found_raises_notfound(self, salesperson):
        with pytest.raises(NotFound):
            InvoiceService.update_invoice_detail(
                uuid4(), UpdateInvoiceDetailDto(quantity=Decimal('1')), salesperson
            )
