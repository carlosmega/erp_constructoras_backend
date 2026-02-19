"""
Unit tests for Invoice services.

Tests InvoiceService business logic including invoice creation from orders,
payment processing, and state management.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from apps.invoices.models import Invoice, InvoiceStateCode, InvoiceStatusCode
from apps.invoices.services import InvoiceService
from apps.invoices.schemas import CreateInvoiceDto, RecordPaymentDto, CancelInvoiceDto
from apps.invoices.tests.factories import InvoiceFactory, PaidInvoiceFactory
from apps.orders.tests.factories import FulfilledOrderFactory, SalesOrderFactory, SalesOrderDetailFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, NotFound


@pytest.mark.unit
class TestGenerateInvoiceNumber:
    """Tests for InvoiceService.generate_invoice_number method."""

    def test_generate_invoice_number_first(self, db):
        """Test generating first invoice number of the year."""
        year = date.today().year
        number = InvoiceService.generate_invoice_number()

        assert number.startswith(f'INV-{year}-')
        assert len(number) == 13  # INV-YYYY-NNNN

    def test_generate_invoice_number_increments(self, db, salesperson):
        """Test invoice numbers increment."""
        year = date.today().year
        InvoiceFactory(invoicenumber=f'INV-{year}-0001', ownerid=salesperson)

        number = InvoiceService.generate_invoice_number()

        assert number == f'INV-{year}-0002'


@pytest.mark.unit
@pytest.mark.workflow
class TestCreateInvoiceFromOrder:
    """Tests for InvoiceService.create_invoice_from_order method."""

    def test_create_invoice_from_fulfilled_order(self, db, salesperson):
        """Test creating invoice from fulfilled order."""
        order = FulfilledOrderFactory(ownerid=salesperson)
        SalesOrderDetailFactory(salesorderid=order, quantity=Decimal('10'), priceperunit=Decimal('100'))

        invoice = InvoiceService.create_invoice_from_order(order.salesorderid, salesperson)

        assert invoice.invoiceid is not None
        assert invoice.salesorderid == order
        assert invoice.statecode == InvoiceStateCode.ACTIVE
        assert invoice.statuscode == InvoiceStatusCode.NEW

        # Verify line items were copied
        assert invoice.invoice_details.count() == 1

    def test_create_invoice_from_non_fulfilled_order_fails(self, db, salesperson):
        """Test cannot create invoice from non-fulfilled order."""
        order = SalesOrderFactory(ownerid=salesperson)  # Active order

        with pytest.raises(ValidationError, match='Can only create invoice from fulfilled orders'):
            InvoiceService.create_invoice_from_order(order.salesorderid, salesperson)

    def test_create_invoice_from_order_not_found(self, db, salesperson):
        """Test creating invoice from non-existent order."""
        from apps.orders.models import SalesOrder
        with pytest.raises(SalesOrder.DoesNotExist):
            InvoiceService.create_invoice_from_order(uuid4(), salesperson)

    def test_create_invoice_duplicate_from_same_order_fails(self, db, salesperson):
        """Test cannot create multiple invoices from same order."""
        order = FulfilledOrderFactory(ownerid=salesperson)

        # Create first invoice - this also changes order state to INVOICED
        InvoiceService.create_invoice_from_order(order.salesorderid, salesperson)

        # Refresh order from database
        order.refresh_from_db()

        # Try to create second invoice - will fail because order is now INVOICED, not FULFILLED
        with pytest.raises(ValidationError, match='Can only create invoice from fulfilled orders'):
            InvoiceService.create_invoice_from_order(order.salesorderid, salesperson)


@pytest.mark.unit
class TestGetInvoiceById:
    """Tests for InvoiceService.get_invoice_by_id method."""

    def test_get_invoice_by_id_success(self, db, salesperson):
        """Test getting invoice by ID."""
        invoice = InvoiceFactory(ownerid=salesperson)

        retrieved = InvoiceService.get_invoice_by_id(invoice.invoiceid, salesperson)

        assert retrieved.invoiceid == invoice.invoiceid

    def test_get_invoice_by_id_not_found(self, db, salesperson):
        """Test getting non-existent invoice."""
        with pytest.raises(NotFound, match='Invoice with ID .* not found'):
            InvoiceService.get_invoice_by_id(uuid4(), salesperson)


@pytest.mark.unit
@pytest.mark.workflow
class TestRecordPayment:
    """Tests for InvoiceService.record_payment method."""

    def test_record_payment_partial(self, db, salesperson):
        """Test recording partial payment."""
        from apps.invoices.tests.factories import InvoiceDetailFactory

        invoice = InvoiceFactory(ownerid=salesperson)
        InvoiceDetailFactory(invoiceid=invoice, quantity=Decimal('10'), priceperunit=Decimal('100'))
        invoice.calculate_totals()
        invoice.save()

        dto = RecordPaymentDto(payment_amount=Decimal('500.00'))
        updated = InvoiceService.record_payment(invoice.invoiceid, dto, salesperson)

        assert updated.totalpaid == Decimal('500.00')
        assert updated.totalamountdue == Decimal('500.00')
        assert updated.statecode == InvoiceStateCode.ACTIVE
        assert updated.statuscode == InvoiceStatusCode.PARTIAL

    def test_record_payment_full(self, db, salesperson):
        """Test recording full payment."""
        from apps.invoices.tests.factories import InvoiceDetailFactory

        invoice = InvoiceFactory(ownerid=salesperson)
        InvoiceDetailFactory(invoiceid=invoice, quantity=Decimal('10'), priceperunit=Decimal('100'))
        invoice.calculate_totals()
        invoice.save()

        dto = RecordPaymentDto(payment_amount=Decimal('1000.00'))
        updated = InvoiceService.record_payment(invoice.invoiceid, dto, salesperson)

        assert updated.totalpaid == Decimal('1000.00')
        assert updated.totalamountdue == Decimal('0.00')
        assert updated.statecode == InvoiceStateCode.PAID
        assert updated.statuscode == InvoiceStatusCode.COMPLETE
        assert updated.paidon is not None

    def test_record_payment_overpayment_fails(self, db, salesperson):
        """Test cannot overpay invoice."""
        from apps.invoices.tests.factories import InvoiceDetailFactory

        invoice = InvoiceFactory(ownerid=salesperson)
        InvoiceDetailFactory(invoiceid=invoice, quantity=Decimal('10'), priceperunit=Decimal('100'))
        invoice.calculate_totals()
        invoice.save()

        dto = RecordPaymentDto(payment_amount=Decimal('1500.00'))

        with pytest.raises(ValidationError, match='Payment amount .* exceeds amount due'):
            InvoiceService.record_payment(invoice.invoiceid, dto, salesperson)

    def test_record_payment_on_paid_invoice_fails(self, db, salesperson):
        """Test cannot record payment on already paid invoice."""
        invoice = PaidInvoiceFactory(ownerid=salesperson)

        dto = RecordPaymentDto(payment_amount=Decimal('100.00'))

        with pytest.raises(ValidationError, match='Payment amount .* exceeds amount due'):
            InvoiceService.record_payment(invoice.invoiceid, dto, salesperson)


@pytest.mark.unit
class TestCancelInvoice:
    """Tests for InvoiceService.cancel_invoice method."""

    def test_cancel_invoice_success(self, db, salesperson):
        """Test canceling an invoice."""
        invoice = InvoiceFactory(ownerid=salesperson)

        dto = CancelInvoiceDto(reason='Customer requested cancellation')
        canceled = InvoiceService.cancel_invoice(invoice.invoiceid, dto, salesperson)

        assert canceled.statecode == InvoiceStateCode.CANCELED
        assert canceled.statuscode == InvoiceStatusCode.CANCELED

    def test_cancel_paid_invoice_fails(self, db, salesperson):
        """Test cannot cancel paid invoice."""
        invoice = PaidInvoiceFactory(ownerid=salesperson)

        dto = CancelInvoiceDto(reason='Test')
        with pytest.raises(ValidationError, match='Cannot cancel paid invoices'):
            InvoiceService.cancel_invoice(invoice.invoiceid, dto, salesperson)

    def test_cancel_partially_paid_invoice_fails(self, db, salesperson):
        """Test cannot cancel partially paid invoice."""
        from apps.invoices.tests.factories import PartiallyPaidInvoiceFactory

        invoice = PartiallyPaidInvoiceFactory(ownerid=salesperson)

        dto = CancelInvoiceDto(reason='Test')
        with pytest.raises(ValidationError, match='Cannot cancel an invoice with payments'):
            InvoiceService.cancel_invoice(invoice.invoiceid, dto, salesperson)


@pytest.mark.unit
class TestGetOverdueInvoices:
    """Tests for InvoiceService.get_overdue_invoices method."""

    def test_get_overdue_invoices(self, db, salesperson):
        """Test getting overdue invoices."""
        from apps.invoices.tests.factories import OverdueInvoiceFactory

        # Create overdue invoices
        OverdueInvoiceFactory.create_batch(2, ownerid=salesperson)

        # Create non-overdue invoice
        InvoiceFactory(ownerid=salesperson, duedate=date.today() + timedelta(days=30))

        overdue = InvoiceService.get_overdue_invoices(salesperson)

        assert overdue.count() == 2
