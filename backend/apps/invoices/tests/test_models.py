"""
Unit tests for Invoice models.

Tests Invoice and InvoiceDetail entities including state management,
validation, payment tracking, and business rules.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.invoices.models import (
    Invoice,
    InvoiceDetail,
    InvoiceStateCode,
    InvoiceStatusCode,
)
from apps.invoices.tests.factories import (
    InvoiceFactory,
    InvoiceDetailFactory,
    PaidInvoiceFactory,
    PartiallyPaidInvoiceFactory,
    CanceledInvoiceFactory,
    OverdueInvoiceFactory,
)
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestInvoiceEnums:
    """Tests for Invoice enum definitions."""

    def test_invoice_state_code_values(self):
        """Test InvoiceStateCode enum values."""
        assert InvoiceStateCode.ACTIVE.value == 0
        assert InvoiceStateCode.PAID.value == 1
        assert InvoiceStateCode.CANCELED.value == 2

    def test_invoice_status_code_values(self):
        """Test InvoiceStatusCode enum values."""
        assert InvoiceStatusCode.NEW.value == 1
        assert InvoiceStatusCode.PARTIAL.value == 2
        assert InvoiceStatusCode.COMPLETE.value == 3
        assert InvoiceStatusCode.CANCELED.value == 4


@pytest.mark.unit
class TestInvoiceModel:
    """Tests for Invoice model creation and basic operations."""

    def test_create_invoice_minimal(self, db):
        """Test creating invoice with minimal required fields."""
        owner = SalespersonFactory()

        invoice = Invoice.objects.create(
            name='Test Invoice',
            invoicenumber='INV-2024-001',
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )

        assert invoice.invoiceid is not None
        assert invoice.name == 'Test Invoice'
        assert invoice.statecode == InvoiceStateCode.ACTIVE
        assert invoice.totalamount == Decimal('0.00')
        assert invoice.totalpaid == Decimal('0.00')

    def test_invoice_factory(self, db):
        """Test InvoiceFactory creates valid invoices."""
        invoice = InvoiceFactory()

        assert invoice.invoiceid is not None
        assert invoice.invoicenumber is not None
        assert invoice.ownerid is not None

    def test_invoice_str_representation(self, db):
        """Test __str__ method."""
        invoice = InvoiceFactory(invoicenumber='INV-2024-001', name='Test Invoice')

        assert 'INV-2024-001' in str(invoice)
        assert 'Test Invoice' in str(invoice)


@pytest.mark.unit
class TestInvoiceProperties:
    """Tests for Invoice computed properties."""

    def test_customer_name_property_from_account(self, db, salesperson):
        """Test customer_name property from account."""
        from apps.accounts.models import Account
        account = Account.objects.create(name='Acme Corp', ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        invoice = InvoiceFactory(accountid=account, contactid=None, ownerid=salesperson)

        assert invoice.customer_name == 'Acme Corp'

    def test_customer_name_property_none(self, db):
        """Test customer_name property returns None."""
        invoice = InvoiceFactory(accountid=None, contactid=None)

        assert invoice.customer_name is None

    def test_is_overdue_property_true(self, db):
        """Test is_overdue property when invoice is overdue."""
        invoice = OverdueInvoiceFactory()

        assert invoice.is_overdue is True

    def test_is_overdue_property_false(self, db):
        """Test is_overdue property when invoice is not overdue."""
        invoice = InvoiceFactory(
            duedate=date.today() + timedelta(days=30),
            statecode=InvoiceStateCode.ACTIVE
        )

        assert invoice.is_overdue is False

    def test_is_overdue_property_false_when_paid(self, db):
        """Test is_overdue property false when invoice is paid."""
        invoice = PaidInvoiceFactory()

        assert invoice.is_overdue is False


@pytest.mark.unit
class TestInvoiceTotalsCalculation:
    """Tests for Invoice totals calculation."""

    def test_calculate_totals_no_items(self, db):
        """Test calculate_totals with no line items."""
        invoice = InvoiceFactory()

        total = invoice.calculate_totals()

        assert total == Decimal('0.00')
        assert invoice.totallineitemamount == Decimal('0.00')
        assert invoice.totalamount == Decimal('0.00')

    def test_calculate_totals_with_items(self, db):
        """Test calculate_totals with line items."""
        invoice = InvoiceFactory()

        InvoiceDetailFactory(
            invoiceid=invoice,
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00')
        )
        InvoiceDetailFactory(
            invoiceid=invoice,
            quantity=Decimal('5.00'),
            priceperunit=Decimal('200.00')
        )

        total = invoice.calculate_totals()

        # 10*100 + 5*200 = 1000 + 1000 = 2000
        assert invoice.totallineitemamount == Decimal('2000.00')
        assert invoice.totalamount == Decimal('2000.00')

    def test_calculate_totals_with_payment(self, db):
        """Test calculate_totals updates amount due."""
        invoice = InvoiceFactory(totalpaid=Decimal('500.00'))

        InvoiceDetailFactory(
            invoiceid=invoice,
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00')
        )

        invoice.calculate_totals()

        # Total 1000, paid 500, due 500
        assert invoice.totalamount == Decimal('1000.00')
        assert invoice.totalpaid == Decimal('500.00')
        assert invoice.totalamountdue == Decimal('500.00')


@pytest.mark.unit
class TestInvoiceDetail:
    """Tests for InvoiceDetail model."""

    def test_create_invoice_detail(self, db):
        """Test creating invoice detail."""
        invoice = InvoiceFactory()

        detail = InvoiceDetail.objects.create(
            invoiceid=invoice,
            productname='Test Product',
            quantity=Decimal('5.00'),
            priceperunit=Decimal('100.00'),
        )

        # Auto-calculated on save
        assert detail.baseamount == Decimal('500.00')
        assert detail.extendedamount == Decimal('500.00')

    def test_invoice_detail_with_tax(self, db):
        """Test invoice detail with tax."""
        invoice = InvoiceFactory()

        detail = InvoiceDetail.objects.create(
            invoiceid=invoice,
            productname='Test Product',
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00'),
            tax=Decimal('100.00'),
        )

        # 10*100 = 1000, plus tax 100 = 1100
        assert detail.baseamount == Decimal('1000.00')
        assert detail.extendedamount == Decimal('1100.00')


@pytest.mark.unit
class TestInvoiceFactories:
    """Tests for Invoice factories."""

    def test_paid_invoice_factory(self, db):
        """Test PaidInvoiceFactory creates paid invoices."""
        invoice = PaidInvoiceFactory()

        assert invoice.statecode == InvoiceStateCode.PAID
        assert invoice.statuscode == InvoiceStatusCode.COMPLETE
        assert invoice.totalpaid == invoice.totalamount
        assert invoice.totalamountdue == Decimal('0.00')
        assert invoice.paidon is not None

    def test_partially_paid_invoice_factory(self, db):
        """Test PartiallyPaidInvoiceFactory creates partially paid invoices."""
        invoice = PartiallyPaidInvoiceFactory()

        assert invoice.statecode == InvoiceStateCode.ACTIVE
        assert invoice.statuscode == InvoiceStatusCode.PARTIAL
        assert invoice.totalpaid > Decimal('0.00')
        assert invoice.totalpaid < invoice.totalamount

    def test_canceled_invoice_factory(self, db):
        """Test CanceledInvoiceFactory creates canceled invoices."""
        invoice = CanceledInvoiceFactory()

        assert invoice.statecode == InvoiceStateCode.CANCELED
        assert invoice.statuscode == InvoiceStatusCode.CANCELED

    def test_overdue_invoice_factory(self, db):
        """Test OverdueInvoiceFactory creates overdue invoices."""
        invoice = OverdueInvoiceFactory()

        assert invoice.duedate < date.today()
        assert invoice.statecode == InvoiceStateCode.ACTIVE
        assert invoice.is_overdue is True
