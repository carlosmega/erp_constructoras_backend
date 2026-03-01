"""Unit tests for Expense Management models."""

import pytest
from decimal import Decimal
from datetime import date

from apps.expenses.models import (
    ProjectExpense,
    ExpenseLine,
    ExpenseAttachment,
    ClassificationLog,
    ClientEstimate,
    DocumentTypeCode,
    ClassificationStatusCode,
    PaymentStatusCode,
    CurrencyCode,
    ExpensePaymentMethodCode,
    PayrollTypeCode,
    ProvisionStatusCode,
    VerificationStatusCode,
    ExpenseStateCode,
    ClassificationActionCode,
    AttachmentTypeCode,
    EstimateTypeCode,
    EstimateStateCode,
)
from apps.expenses.tests.factories import (
    ProjectExpenseFactory,
    InvoiceExpenseFactory,
    PayrollExpenseFactory,
    ProvisionExpenseFactory,
    ExpenseLineFactory,
    ExpenseAttachmentFactory,
    ClassificationLogFactory,
    ClientEstimateFactory,
)
from apps.users.tests.factories import SalespersonFactory


# =============================================================================
# Enum Tests
# =============================================================================

@pytest.mark.unit
class TestExpenseEnums:
    """Tests for expense enum definitions."""

    def test_document_type_code_values(self):
        assert DocumentTypeCode.INVOICE.value == 0
        assert DocumentTypeCode.CREDIT_NOTE.value == 1
        assert DocumentTypeCode.NO_INVOICE_EXPENSE.value == 2
        assert DocumentTypeCode.PAYROLL.value == 3
        assert DocumentTypeCode.PROVISION.value == 4

    def test_classification_status_code_values(self):
        assert ClassificationStatusCode.PENDING.value == 1
        assert ClassificationStatusCode.CLASSIFIED.value == 2
        assert ClassificationStatusCode.PARTIAL.value == 3

    def test_payment_status_code_values(self):
        assert PaymentStatusCode.PENDING.value == 0
        assert PaymentStatusCode.PAID.value == 1
        assert PaymentStatusCode.PARTIALLY_PAID.value == 2
        assert PaymentStatusCode.OVERDUE.value == 3

    def test_currency_code_values(self):
        assert CurrencyCode.MXN.value == 0
        assert CurrencyCode.USD.value == 1

    def test_expense_payment_method_code_values(self):
        assert ExpensePaymentMethodCode.CREDIT_CARD.value == 0
        assert ExpensePaymentMethodCode.BANK_TRANSFER.value == 1
        assert ExpensePaymentMethodCode.CASH.value == 2
        assert ExpensePaymentMethodCode.CHECK.value == 3
        assert ExpensePaymentMethodCode.DEBIT_CARD.value == 4
        assert ExpensePaymentMethodCode.OTHER.value == 99

    def test_payroll_type_code_values(self):
        assert PayrollTypeCode.WEEKLY.value == 0
        assert PayrollTypeCode.BIWEEKLY.value == 1

    def test_provision_status_code_values(self):
        assert ProvisionStatusCode.ACTIVE.value == 0
        assert ProvisionStatusCode.CONVERTED.value == 1
        assert ProvisionStatusCode.CANCELED.value == 2

    def test_verification_status_code_values(self):
        assert VerificationStatusCode.PENDING.value == 0
        assert VerificationStatusCode.VERIFIED.value == 1
        assert VerificationStatusCode.DISCREPANCY.value == 2

    def test_expense_state_code_values(self):
        assert ExpenseStateCode.ACTIVE.value == 0
        assert ExpenseStateCode.CANCELED.value == 1

    def test_classification_action_code_values(self):
        assert ClassificationActionCode.ASSIGNED.value == 0
        assert ClassificationActionCode.CHANGED.value == 1
        assert ClassificationActionCode.REMOVED.value == 2

    def test_attachment_type_code_values(self):
        assert AttachmentTypeCode.PDF.value == 0
        assert AttachmentTypeCode.XML.value == 1
        assert AttachmentTypeCode.IMAGE.value == 2
        assert AttachmentTypeCode.OTHER.value == 99

    def test_estimate_type_code_values(self):
        assert EstimateTypeCode.ESTIMATE.value == 0
        assert EstimateTypeCode.OTHER.value == 1

    def test_estimate_state_code_values(self):
        assert EstimateStateCode.ACTIVE.value == 0
        assert EstimateStateCode.PAID.value == 1
        assert EstimateStateCode.CANCELED.value == 2


# =============================================================================
# ProjectExpense Model Tests
# =============================================================================

@pytest.mark.unit
class TestProjectExpenseModel:
    """Tests for ProjectExpense model creation."""

    def test_create_expense_factory(self, db):
        """Test factory creates valid expense."""
        expense = ProjectExpenseFactory()
        assert expense.expenseid is not None
        assert expense.projectid is not None
        assert expense.periodid is not None
        assert expense.ownerid is not None
        assert expense.statecode == ExpenseStateCode.ACTIVE

    def test_create_invoice_expense(self, db):
        """Test InvoiceExpenseFactory creates valid invoice expense."""
        expense = InvoiceExpenseFactory()
        assert expense.documenttype == DocumentTypeCode.INVOICE
        assert expense.invoiceuuid is not None

    def test_create_payroll_expense(self, db):
        """Test PayrollExpenseFactory creates valid payroll expense."""
        expense = PayrollExpenseFactory()
        assert expense.documenttype == DocumentTypeCode.PAYROLL
        assert expense.payrolltype == PayrollTypeCode.WEEKLY
        assert expense.workername is not None

    def test_create_provision_expense(self, db):
        """Test ProvisionExpenseFactory creates valid provision expense."""
        expense = ProvisionExpenseFactory()
        assert expense.documenttype == DocumentTypeCode.PROVISION
        assert expense.provisionstatus == ProvisionStatusCode.ACTIVE

    def test_expense_str_representation(self, db):
        """Test __str__ method."""
        expense = ProjectExpenseFactory(documenttype=DocumentTypeCode.INVOICE)
        assert 'Invoice' in str(expense)

    def test_expense_default_values(self, db):
        """Test default values on expense creation."""
        expense = ProjectExpenseFactory()
        assert expense.classificationstatus == ClassificationStatusCode.PENDING
        assert expense.paymentstatus == PaymentStatusCode.PENDING
        assert expense.currency == CurrencyCode.MXN
        assert expense.exchangerate == Decimal('1.0000')
        assert expense.verificationstatus == VerificationStatusCode.PENDING


# =============================================================================
# ExpenseLine Model Tests
# =============================================================================

@pytest.mark.unit
class TestExpenseLineModel:
    """Tests for ExpenseLine model."""

    def test_create_expense_line(self, db):
        """Test creating an expense line."""
        line = ExpenseLineFactory()
        assert line.expenselineid is not None
        assert line.linenumber >= 1
        assert line.quantity == Decimal('10.0000')
        assert line.unitprice == Decimal('100.0000')

    def test_expense_line_str(self, db):
        """Test __str__ method."""
        line = ExpenseLineFactory(linenumber=1, description='Test material')
        assert 'Line 1' in str(line)
        assert 'Test material' in str(line)


# =============================================================================
# ExpenseAttachment Model Tests
# =============================================================================

@pytest.mark.unit
class TestExpenseAttachmentModel:
    """Tests for ExpenseAttachment model."""

    def test_create_attachment(self, db):
        """Test creating an attachment."""
        attachment = ExpenseAttachmentFactory()
        assert attachment.attachmentid is not None
        assert attachment.filename is not None
        assert attachment.filetype == AttachmentTypeCode.PDF
        assert attachment.mimetype == 'application/pdf'

    def test_attachment_str(self, db):
        """Test __str__ method."""
        attachment = ExpenseAttachmentFactory(filename='invoice.pdf')
        assert str(attachment) == 'invoice.pdf'


# =============================================================================
# ClassificationLog Model Tests
# =============================================================================

@pytest.mark.unit
class TestClassificationLogModel:
    """Tests for ClassificationLog model."""

    def test_create_classification_log(self, db):
        """Test creating a classification log entry."""
        log = ClassificationLogFactory()
        assert log.classificationlogid is not None
        assert log.action == ClassificationActionCode.ASSIGNED
        assert log.classifiedbyname is not None

    def test_classification_log_str(self, db):
        """Test __str__ method."""
        log = ClassificationLogFactory()
        assert 'Assigned' in str(log)


# =============================================================================
# ClientEstimate Model Tests
# =============================================================================

@pytest.mark.unit
class TestClientEstimateModel:
    """Tests for ClientEstimate model."""

    def test_create_estimate(self, db):
        """Test creating a client estimate."""
        estimate = ClientEstimateFactory()
        assert estimate.estimateid is not None
        assert estimate.estimatenumber >= 1
        assert estimate.estimatedamount == Decimal('100000.00')
        assert estimate.statecode == EstimateStateCode.ACTIVE

    def test_estimate_str(self, db):
        """Test __str__ method."""
        estimate = ClientEstimateFactory(estimatenumber=5)
        assert '#5' in str(estimate)


# =============================================================================
# Cascade Delete Tests
# =============================================================================

@pytest.mark.unit
class TestCascadeDelete:
    """Tests for cascade deletion behavior."""

    def test_delete_expense_cascades_to_lines(self, db):
        """Deleting expense cascades to lines."""
        expense = ProjectExpenseFactory()
        ExpenseLineFactory(expenseid=expense, linenumber=1)
        ExpenseLineFactory(expenseid=expense, linenumber=2)

        assert ExpenseLine.objects.filter(expenseid=expense).count() == 2

        expense_pk = expense.expenseid
        expense.delete()
        assert ExpenseLine.objects.filter(expenseid_id=expense_pk).count() == 0

    def test_delete_expense_cascades_to_attachments(self, db):
        """Deleting expense cascades to attachments."""
        expense = ProjectExpenseFactory()
        ExpenseAttachmentFactory(expenseid=expense)

        assert ExpenseAttachment.objects.filter(expenseid=expense).count() == 1

        expense_pk = expense.expenseid
        expense.delete()
        assert ExpenseAttachment.objects.filter(expenseid_id=expense_pk).count() == 0

    def test_delete_expense_cascades_to_logs(self, db):
        """Deleting expense cascades to classification logs."""
        expense = ProjectExpenseFactory()
        ClassificationLogFactory(expenseid=expense)

        assert ClassificationLog.objects.filter(expenseid=expense).count() == 1

        expense_pk = expense.expenseid
        expense.delete()
        assert ClassificationLog.objects.filter(expenseid_id=expense_pk).count() == 0
