"""Unit tests for Invoice Inbox services."""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.invoiceinbox.models import (
    IncomingInvoice,
    IncomingInvoiceStateCode,
    InboxSyncLog,
)
from apps.invoiceinbox.services import (
    IncomingInvoiceService,
    InboxMatchingService,
)
from apps.invoiceinbox.tests.factories import (
    IncomingInvoiceFactory,
    ClassifiedInvoiceFactory,
    InboxSyncLogFactory,
)
from apps.expenses.models import ProjectExpense, ExpenseStateCode
from apps.expenses.tests.factories import ProjectExpenseFactory, InvoiceExpenseFactory
from apps.projects.tests.factories import ConstructionProjectFactory
from apps.budgets.tests.factories import ImputationCodeFactory, ImputationPeriodFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, NotFound


# =============================================================================
# IncomingInvoiceService — classify_invoice
# =============================================================================

@pytest.mark.unit
class TestClassifyInvoice:
    """Tests for IncomingInvoiceService.classify_invoice."""

    def test_classify_invoice(self, db):
        """Draft -> Classified with imputation code (project already assigned)."""
        user = SalespersonFactory()
        project = ConstructionProjectFactory()
        imp_code = ImputationCodeFactory(
            categoryid__projectid=project,
        )
        invoice = IncomingInvoiceFactory(
            projectid=project,
            createdby=user,
            modifiedby=user,
        )

        result = IncomingInvoiceService.classify_invoice(
            incoming_id=invoice.incominginvoiceid,
            imputation_code_id=imp_code.imputationcodeid,
            user=user,
            notes='Test classification',
        )

        assert result.statecode == IncomingInvoiceStateCode.CLASSIFIED
        assert result.projectid_id == project.projectid
        assert result.imputationcodeid_id == imp_code.imputationcodeid
        assert result.classificationnotes == 'Test classification'

    def test_classify_wrong_project_imputation_code(self, db):
        """Cannot classify with imputation code from a different project."""
        user = SalespersonFactory()
        project = ConstructionProjectFactory()
        other_project = ConstructionProjectFactory()
        imp_code = ImputationCodeFactory(
            categoryid__projectid=other_project,
        )
        invoice = IncomingInvoiceFactory(
            projectid=project,
            createdby=user,
            modifiedby=user,
        )

        with pytest.raises(NotFound, match='Imputation code'):
            IncomingInvoiceService.classify_invoice(
                incoming_id=invoice.incominginvoiceid,
                imputation_code_id=imp_code.imputationcodeid,
                user=user,
            )


# =============================================================================
# IncomingInvoiceService — reject_invoice
# =============================================================================

@pytest.mark.unit
class TestRejectInvoice:
    """Tests for IncomingInvoiceService.reject_invoice."""

    def test_reject_invoice(self, db):
        """Draft -> Rejected."""
        user = SalespersonFactory()
        invoice = IncomingInvoiceFactory(createdby=user, modifiedby=user)

        result = IncomingInvoiceService.reject_invoice(
            incoming_id=invoice.incominginvoiceid,
            notes='Not a valid invoice for this project',
            user=user,
        )

        assert result.statecode == IncomingInvoiceStateCode.REJECTED
        assert result.rejectionnotes == 'Not a valid invoice for this project'

    def test_reject_linked_raises_error(self, db):
        """Cannot reject a linked invoice."""
        user = SalespersonFactory()
        project = ConstructionProjectFactory()
        expense = ProjectExpenseFactory(
            projectid=project,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        invoice = IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.LINKED,
            projectid=project,
            linkedexpenseid=expense,
            createdby=user,
            modifiedby=user,
        )

        with pytest.raises(ValidationError, match='Cannot reject a linked invoice'):
            IncomingInvoiceService.reject_invoice(
                incoming_id=invoice.incominginvoiceid,
                notes='Should fail',
                user=user,
            )


# =============================================================================
# IncomingInvoiceService — link_to_expense
# =============================================================================

@pytest.mark.unit
class TestLinkToExpense:
    """Tests for IncomingInvoiceService.link_to_expense."""

    def test_link_creates_expense(self, db):
        """Link a classified invoice to create a new ProjectExpense."""
        user = SalespersonFactory()
        project = ConstructionProjectFactory(ownerid=user, createdby=user, modifiedby=user)
        period = ImputationPeriodFactory(projectid=project)
        invoice = IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.CLASSIFIED,
            projectid=project,
            emisorrfc='XAXX010101000',
            emisornombre='Proveedor SA de CV',
            uuid='LINK-TEST-UUID-0001',
            folio='F-001',
            fecha='2026-01-15T10:30:00',
            subtotal=Decimal('10000.00'),
            totalimpuestostrasladados=Decimal('1600.00'),
            total=Decimal('11600.00'),
            createdby=user,
            modifiedby=user,
        )

        result = IncomingInvoiceService.link_to_expense(
            incoming_id=invoice.incominginvoiceid,
            period_id=period.periodid,
            user=user,
        )

        assert result.statecode == IncomingInvoiceStateCode.LINKED
        assert result.linkedexpenseid is not None
        assert result.matchtype == 'manual'

        # Verify the created expense
        expense = result.linkedexpenseid
        assert expense.supplierrfc == 'XAXX010101000'
        assert expense.suppliername == 'Proveedor SA de CV'
        assert expense.invoiceuuid == 'LINK-TEST-UUID-0001'
        assert expense.subtotal == Decimal('10000.00')
        assert expense.netamount == Decimal('11600.00')


# =============================================================================
# IncomingInvoiceService — unlink_invoice
# =============================================================================

@pytest.mark.unit
class TestUnlinkInvoice:
    """Tests for IncomingInvoiceService.unlink_invoice."""

    def test_unlink_invoice(self, db):
        """Linked -> Classified, clears linkedexpenseid."""
        user = SalespersonFactory()
        project = ConstructionProjectFactory(ownerid=user, createdby=user, modifiedby=user)
        expense = ProjectExpenseFactory(
            projectid=project,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        invoice = IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.LINKED,
            projectid=project,
            linkedexpenseid=expense,
            matchtype='manual',
            createdby=user,
            modifiedby=user,
        )

        result = IncomingInvoiceService.unlink_invoice(
            incoming_id=invoice.incominginvoiceid,
            user=user,
        )

        assert result.statecode == IncomingInvoiceStateCode.CLASSIFIED
        assert result.linkedexpenseid is None
        assert result.matchtype is None


# =============================================================================
# IncomingInvoiceService — get_inbox_summary
# =============================================================================

@pytest.mark.unit
class TestInboxSummary:
    """Tests for IncomingInvoiceService.get_inbox_summary."""

    def test_inbox_summary(self, db):
        """Verify count aggregation across all states."""
        user = SalespersonFactory()
        project = ConstructionProjectFactory()

        # Create invoices in different states
        IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.DRAFT,
            projectid=project,
            createdby=user,
            modifiedby=user,
        )
        IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.DRAFT,
            projectid=project,
            createdby=user,
            modifiedby=user,
        )
        IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.CLASSIFIED,
            projectid=project,
            createdby=user,
            modifiedby=user,
        )
        expense = ProjectExpenseFactory(
            projectid=project,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.LINKED,
            projectid=project,
            linkedexpenseid=expense,
            createdby=user,
            modifiedby=user,
        )
        IncomingInvoiceFactory(
            statecode=IncomingInvoiceStateCode.REJECTED,
            projectid=project,
            createdby=user,
            modifiedby=user,
        )

        summary = IncomingInvoiceService.get_inbox_summary(project_id=project.projectid)

        assert summary['draftcount'] == 2
        assert summary['classifiedcount'] == 1
        assert summary['linkedcount'] == 1
        assert summary['rejectedcount'] == 1
        assert summary['totalcount'] == 5

    def test_inbox_summary_with_sync_log(self, db):
        """Verify lastsyncdate is populated when sync log exists."""
        project = ConstructionProjectFactory()
        InboxSyncLogFactory(projectid=project)

        summary = IncomingInvoiceService.get_inbox_summary(project_id=project.projectid)
        assert summary['lastsyncdate'] is not None

    def test_inbox_summary_empty(self, db):
        """Summary returns zeros when no invoices exist."""
        project = ConstructionProjectFactory()
        summary = IncomingInvoiceService.get_inbox_summary(project_id=project.projectid)
        assert summary['draftcount'] == 0
        assert summary['classifiedcount'] == 0
        assert summary['linkedcount'] == 0
        assert summary['rejectedcount'] == 0
        assert summary['totalcount'] == 0
        assert summary['lastsyncdate'] is None

    def test_inbox_summary_global(self, db):
        """Global summary counts across all projects."""
        user = SalespersonFactory()
        project1 = ConstructionProjectFactory()
        project2 = ConstructionProjectFactory()

        IncomingInvoiceFactory(projectid=project1, createdby=user, modifiedby=user)
        IncomingInvoiceFactory(projectid=project2, createdby=user, modifiedby=user)

        summary = IncomingInvoiceService.get_inbox_summary()
        assert summary['totalcount'] == 2


# =============================================================================
# InboxMatchingService
# =============================================================================

@pytest.mark.unit
class TestInboxMatchingService:
    """Tests for InboxMatchingService.find_matches."""

    def test_matching_uuid_exact(self, db):
        """Find match by exact UUID with 100% confidence."""
        user = SalespersonFactory()
        test_uuid = 'MATCH-UUID-1111-2222-3333'

        # Create an existing expense with matching UUID
        expense = InvoiceExpenseFactory(
            invoiceuuid=test_uuid,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        # Create incoming invoice with same UUID
        invoice = IncomingInvoiceFactory(
            uuid=test_uuid,
            createdby=user,
            modifiedby=user,
        )

        matches = InboxMatchingService.find_matches(invoice)

        assert len(matches) >= 1
        assert matches[0]['matchtype'] == 'uuid_exact'
        assert matches[0]['confidence'] == 100
        assert matches[0]['expenseid'] == expense.expenseid

    def test_matching_rfc_amount(self, db):
        """Find match by RFC + amount within 1% tolerance."""
        user = SalespersonFactory()
        rfc = 'RFC_MATCH_TEST'

        # Create an existing expense with matching RFC and amount
        expense = InvoiceExpenseFactory(
            supplierrfc=rfc,
            netamount=Decimal('11600.00'),
            invoiceuuid='DIFFERENT-UUID-NO-MATCH',
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        # Create incoming invoice with same RFC and similar amount (no UUID match)
        invoice = IncomingInvoiceFactory(
            uuid='INCOMING-UUID-NO-MATCH',
            emisorrfc=rfc,
            total=Decimal('11600.00'),
            folio=None,  # No folio to skip rfc_folio match
            createdby=user,
            modifiedby=user,
        )

        matches = InboxMatchingService.find_matches(invoice)

        assert len(matches) >= 1
        assert matches[0]['matchtype'] == 'rfc_amount'
        assert matches[0]['confidence'] == 60
        assert matches[0]['expenseid'] == expense.expenseid

    def test_matching_rfc_folio(self, db):
        """Find match by RFC + folio with 80% confidence."""
        user = SalespersonFactory()
        rfc = 'RFC_FOLIO_TEST'
        folio = 'F-99999'

        expense = InvoiceExpenseFactory(
            supplierrfc=rfc,
            invoicefolio=folio,
            invoiceuuid='NO-UUID-MATCH',
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        invoice = IncomingInvoiceFactory(
            uuid='DIFFERENT-UUID',
            emisorrfc=rfc,
            folio=folio,
            createdby=user,
            modifiedby=user,
        )

        matches = InboxMatchingService.find_matches(invoice)

        assert len(matches) >= 1
        assert matches[0]['matchtype'] == 'rfc_folio'
        assert matches[0]['confidence'] == 80
        assert matches[0]['expenseid'] == expense.expenseid

    def test_matching_no_results(self, db):
        """No matches when no expenses match."""
        user = SalespersonFactory()
        invoice = IncomingInvoiceFactory(
            uuid='UNIQUE-NO-MATCH-UUID',
            emisorrfc='NOMATCH000000',
            total=Decimal('99999.99'),
            createdby=user,
            modifiedby=user,
        )

        matches = InboxMatchingService.find_matches(invoice)
        assert len(matches) == 0

    def test_matching_excludes_canceled_expenses(self, db):
        """Canceled expenses should not be returned as matches."""
        user = SalespersonFactory()
        test_uuid = 'CANCELED-TEST-UUID'

        InvoiceExpenseFactory(
            invoiceuuid=test_uuid,
            statecode=ExpenseStateCode.CANCELED,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        invoice = IncomingInvoiceFactory(
            uuid=test_uuid,
            createdby=user,
            modifiedby=user,
        )

        matches = InboxMatchingService.find_matches(invoice)
        assert len(matches) == 0
