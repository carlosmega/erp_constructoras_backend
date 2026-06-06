"""
Business logic for Invoice management.

Phase 10 Implementation: Invoice Management
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from django.db import transaction
from django.db.models import Sum, Q

from apps.audit.services import audit_action
from apps.invoices.models import Invoice, InvoiceDetail, InvoiceStateCode, InvoiceStatusCode
from apps.invoices.schemas import (
    CreateInvoiceDto, UpdateInvoiceDto, CreateInvoiceDetailDto,
    RecordPaymentDto, CancelInvoiceDto, InvoiceStatsSchema
)
from apps.orders.models import SalesOrder, OrderStateCode
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import can_modify_record


class InvoiceService:
    """Service layer for invoice operations."""

    @staticmethod
    def generate_invoice_number():
        """
        Generate unique invoice number in format: INV-YYYY-NNNN
        Example: INV-2024-0001
        """
        year = date.today().year
        last_invoice = Invoice.objects.filter(
            invoicenumber__startswith=f'INV-{year}-'
        ).order_by('-invoicenumber').first()

        if last_invoice:
            last_num = int(last_invoice.invoicenumber.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1

        return f'INV-{year}-{next_num:04d}'

    @staticmethod
    @transaction.atomic
    @audit_action(action='create', entity='invoice')
    def create_invoice_from_order(order_id: UUID, user: SystemUser) -> Invoice:
        """
        Create an invoice from a fulfilled sales order.

        Args:
            order_id: UUID of the order
            user: SystemUser creating the invoice

        Returns:
            Created Invoice instance

        Raises:
            ValidationError: If order is not fulfilled or invoice already exists
        """
        # Get order with details
        order = SalesOrder.objects.select_related(
            'ownerid', 'accountid', 'contactid', 'opportunityid'
        ).prefetch_related('order_details').get(salesorderid=order_id)

        # Verify order is fulfilled
        if order.statecode != OrderStateCode.FULFILLED:
            raise ValidationError('Can only create invoice from fulfilled orders')

        # Check if invoice already exists
        if Invoice.objects.filter(salesorderid=order).exists():
            raise ValidationError('Invoice already exists for this order')

        # Generate invoice number
        invoicenumber = InvoiceService.generate_invoice_number()

        # Calculate due date (30 days from now by default)
        duedate = date.today() + timedelta(days=30)

        # Create invoice from order data
        invoice = Invoice.objects.create(
            name=order.name,
            invoicenumber=invoicenumber,
            salesorderid=order,
            opportunityid=order.opportunityid,
            accountid=order.accountid,
            contactid=order.contactid,
            totalamount=order.totalamount,
            totaldiscountamount=order.totaldiscountamount,
            totaltax=order.totaltax,
            totallineitemamount=order.totallineitemamount,
            totalamountless=order.totallineitemamount - order.totaldiscountamount,
            totalpaid=Decimal('0.00'),
            totalamountdue=order.totalamount,
            datedelivered=order.datefulfilled.date() if order.datefulfilled else date.today(),
            duedate=duedate,
            statecode=InvoiceStateCode.ACTIVE,
            statuscode=InvoiceStatusCode.NEW,
            description=order.description,
            ownerid=user,
            createdby=user,
            modifiedby=user
        )

        # Copy order details to invoice details
        for order_detail in order.order_details.all():
            InvoiceDetail.objects.create(
                invoiceid=invoice,
                productname=order_detail.productname,
                productdescription=order_detail.productdescription,
                quantity=order_detail.quantity,
                priceperunit=order_detail.priceperunit,
                manualdiscountamount=order_detail.manualdiscountamount,
                tax=order_detail.tax,
                sequencenumber=order_detail.sequencenumber
            )

        # Update order state to INVOICED
        order.statecode = OrderStateCode.INVOICED
        order.save(update_fields=['statecode'])

        return invoice

    @staticmethod
    @transaction.atomic
    @audit_action(action='create', entity='invoice')
    def create_invoice(dto: CreateInvoiceDto, user: SystemUser) -> Invoice:
        """
        Create a new invoice manually.

        Args:
            dto: CreateInvoiceDto with invoice data
            user: SystemUser creating the invoice

        Returns:
            Created Invoice instance
        """
        # Generate invoice number
        invoicenumber = InvoiceService.generate_invoice_number()

        # Set default due date if not provided
        duedate = dto.duedate or (date.today() + timedelta(days=30))

        # Resolve polymorphic customer
        account = None
        contact = None
        if dto.customerid and dto.customeridtype:
            from core.customers import resolve_customer
            account, contact = resolve_customer(dto.customerid, dto.customeridtype)

        invoice = Invoice.objects.create(
            name=dto.name,
            invoicenumber=invoicenumber,
            salesorderid_id=dto.salesorderid,
            opportunityid_id=dto.opportunityid,
            accountid=account,
            contactid=contact,
            datedelivered=dto.datedelivered,
            duedate=duedate,
            description=dto.description,
            statecode=InvoiceStateCode.ACTIVE,
            statuscode=InvoiceStatusCode.NEW,
            ownerid=user,
            createdby=user,
            modifiedby=user
        )

        return invoice

    @staticmethod
    def get_invoice_by_id(invoice_id: UUID, user: SystemUser) -> Invoice:
        """Get invoice by ID with permission check."""
        try:
            invoice = Invoice.objects.prefetch_related(
                'invoice_details',
                'invoice_details__imputationcodeid'
            ).get(invoiceid=invoice_id)
        except Invoice.DoesNotExist:
            raise NotFound(f"Invoice with ID {invoice_id} not found")

        # Check ownership
        if not can_modify_record(user, invoice.ownerid):
            raise PermissionDenied("You don't have permission to view this invoice")

        return invoice

    @staticmethod
    @transaction.atomic
    @audit_action(action='update', entity='invoice', record_arg='invoice_id')
    def update_invoice(invoice_id: UUID, dto: UpdateInvoiceDto, user: SystemUser) -> Invoice:
        """Update invoice details."""
        invoice = InvoiceService.get_invoice_by_id(invoice_id, user)

        # Can't update paid or canceled invoices
        if invoice.statecode in [InvoiceStateCode.PAID, InvoiceStateCode.CANCELED]:
            raise ValidationError('Cannot update paid or canceled invoices')

        # Update fields
        if dto.name is not None:
            invoice.name = dto.name
        if dto.datedelivered is not None:
            invoice.datedelivered = dto.datedelivered
        if dto.duedate is not None:
            invoice.duedate = dto.duedate
        if dto.description is not None:
            invoice.description = dto.description
        if dto.totaldiscountamount is not None:
            invoice.totaldiscountamount = dto.totaldiscountamount
            # Recalculate totals
            invoice.calculate_totals()

        invoice.modifiedby = user
        invoice.save()

        return invoice

    @staticmethod
    @transaction.atomic
    def add_invoice_detail(invoice_id: UUID, dto: CreateInvoiceDetailDto, user: SystemUser) -> InvoiceDetail:
        """Add line item to invoice."""
        invoice = InvoiceService.get_invoice_by_id(invoice_id, user)

        # Can't modify paid or canceled invoices
        if invoice.statecode in [InvoiceStateCode.PAID, InvoiceStateCode.CANCELED]:
            raise ValidationError('Cannot modify paid or canceled invoices')

        # Validate imputation code if provided
        if dto.imputationcodeid:
            from apps.budgets.models import ImputationCode
            if not ImputationCode.objects.filter(imputationcodeid=dto.imputationcodeid).exists():
                raise ValidationError(f'Imputation code {dto.imputationcodeid} not found')

        # Create detail
        detail = InvoiceDetail.objects.create(
            invoiceid=invoice,
            productname=dto.productname,
            productdescription=dto.productdescription,
            quantity=dto.quantity,
            priceperunit=dto.priceperunit,
            manualdiscountamount=dto.manualdiscountamount,
            tax=dto.tax,
            sequencenumber=dto.sequencenumber,
            imputationcodeid_id=dto.imputationcodeid
        )

        # Recalculate invoice totals
        invoice.calculate_totals()
        invoice.modifiedby = user
        invoice.save()

        return detail

    @staticmethod
    @transaction.atomic
    def remove_invoice_detail(invoice_id: UUID, detail_id: UUID, user: SystemUser) -> None:
        """Remove line item from invoice."""
        invoice = InvoiceService.get_invoice_by_id(invoice_id, user)

        # Can't modify paid or canceled invoices
        if invoice.statecode in [InvoiceStateCode.PAID, InvoiceStateCode.CANCELED]:
            raise ValidationError('Cannot modify paid or canceled invoices')

        try:
            detail = InvoiceDetail.objects.get(
                invoicedetailid=detail_id,
                invoiceid=invoice
            )
            detail.delete()
        except InvoiceDetail.DoesNotExist:
            raise NotFound(f"Invoice detail with ID {detail_id} not found")

        # Recalculate invoice totals
        invoice.calculate_totals()
        invoice.modifiedby = user
        invoice.save()

    @staticmethod
    @transaction.atomic
    @audit_action(action='payment', entity='invoice', record_arg='invoice_id')
    def record_payment(invoice_id: UUID, dto: RecordPaymentDto, user: SystemUser) -> Invoice:
        """
        Record a payment on an invoice.

        Args:
            invoice_id: UUID of the invoice
            dto: RecordPaymentDto with payment details
            user: SystemUser recording the payment

        Returns:
            Updated Invoice instance
        """
        invoice = InvoiceService.get_invoice_by_id(invoice_id, user)

        # Can't pay canceled invoices
        if invoice.statecode == InvoiceStateCode.CANCELED:
            raise ValidationError('Cannot record payment on canceled invoice')

        # Validate payment amount
        if dto.payment_amount <= 0:
            raise ValidationError('Payment amount must be greater than zero')

        if dto.payment_amount > invoice.totalamountdue:
            raise ValidationError(
                f'Payment amount ({dto.payment_amount}) exceeds amount due ({invoice.totalamountdue})'
            )

        # Record payment
        invoice.totalpaid += dto.payment_amount
        invoice.totalamountdue = invoice.totalamount - invoice.totalpaid

        # Update status
        if invoice.totalamountdue == 0:
            # Fully paid
            invoice.statecode = InvoiceStateCode.PAID
            invoice.statuscode = InvoiceStatusCode.COMPLETE
            invoice.paidon = dto.payment_date or date.today()
        else:
            # Partially paid
            invoice.statecode = InvoiceStateCode.ACTIVE
            invoice.statuscode = InvoiceStatusCode.PARTIAL

        invoice.modifiedby = user
        invoice.save()

        return invoice

    @staticmethod
    @transaction.atomic
    @audit_action(action='cancel', entity='invoice', record_arg='invoice_id')
    def cancel_invoice(invoice_id: UUID, dto: CancelInvoiceDto, user: SystemUser) -> Invoice:
        """Cancel an invoice."""
        invoice = InvoiceService.get_invoice_by_id(invoice_id, user)

        # Can't cancel already paid invoices
        if invoice.statecode == InvoiceStateCode.PAID:
            raise ValidationError('Cannot cancel paid invoices')

        # Can't cancel invoices with payments
        if invoice.totalpaid > Decimal('0.00'):
            raise ValidationError('Cannot cancel an invoice with payments')

        # Update status
        invoice.statecode = InvoiceStateCode.CANCELED
        invoice.statuscode = InvoiceStatusCode.CANCELED

        if dto.reason:
            invoice.description = (
                f"{invoice.description or ''}\n\nCanceled: {dto.reason}".strip()
            )

        invoice.modifiedby = user
        invoice.save()

        return invoice

    @staticmethod
    def get_invoice_stats(user: SystemUser) -> InvoiceStatsSchema:
        """Get invoice statistics for the user."""
        # Filter by ownership
        from core.permissions import filter_by_ownership
        queryset = filter_by_ownership(Invoice.objects.all(), user)

        # Calculate stats
        stats = queryset.aggregate(
            total_amount=Sum('totalamount'),
            total_paid=Sum('totalpaid'),
            total_due=Sum('totalamountdue')
        )

        return InvoiceStatsSchema(
            total_invoices=queryset.count(),
            total_amount=stats['total_amount'] or Decimal('0.00'),
            total_paid=stats['total_paid'] or Decimal('0.00'),
            total_due=stats['total_due'] or Decimal('0.00'),
            active_count=queryset.filter(statecode=InvoiceStateCode.ACTIVE).count(),
            paid_count=queryset.filter(statecode=InvoiceStateCode.PAID).count(),
            overdue_count=queryset.filter(
                statecode=InvoiceStateCode.ACTIVE,
                duedate__lt=date.today()
            ).count(),
            canceled_count=queryset.filter(statecode=InvoiceStateCode.CANCELED).count()
        )

    @staticmethod
    def get_overdue_invoices(user: SystemUser):
        """Get overdue invoices for the user."""
        from core.permissions import filter_by_ownership

        # Filter by ownership and overdue criteria
        queryset = filter_by_ownership(Invoice.objects.all(), user)

        return queryset.filter(
            statecode=InvoiceStateCode.ACTIVE,
            duedate__lt=date.today()
        ).order_by('duedate')
