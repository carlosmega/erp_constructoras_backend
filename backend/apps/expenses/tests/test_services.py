"""Unit tests for Expense Management services."""

import pytest
from decimal import Decimal
from uuid import uuid4

from apps.expenses.models import (
    ProjectExpense,
    ExpenseLine,
    ClassificationLog,
    ClientEstimate,
    ClassificationStatusCode,
    ClassificationActionCode,
    DocumentTypeCode,
    ExpenseStateCode,
    ProvisionStatusCode,
    VerificationStatusCode,
    EstimateStateCode,
    PaymentStatusCode,
)
from apps.expenses.services import (
    ExpenseService,
    ClassificationService,
    VerificationService,
    ExpenseLineService,
    AttachmentService,
    ProvisionService,
    EstimateService,
)
from apps.expenses.schemas import (
    CreateProjectExpenseDto,
    UpdateProjectExpenseDto,
    CreateExpenseLineDto,
    UpdateExpenseLineDto,
    CreateExpenseAttachmentDto,
    CreateClientEstimateDto,
    UpdateClientEstimateDto,
)
from apps.expenses.tests.factories import (
    ProjectExpenseFactory,
    ProvisionExpenseFactory,
    ExpenseLineFactory,
    ExpenseAttachmentFactory,
    ClientEstimateFactory,
)
from apps.projects.tests.factories import ConstructionProjectFactory
from apps.budgets.tests.factories import ImputationPeriodFactory, ImputationCodeFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, NotFound


# =============================================================================
# TestExpenseService
# =============================================================================

@pytest.mark.unit
class TestExpenseService:
    """Tests for ExpenseService."""

    def test_create_expense_minimal(self, db, salesperson):
        """Test creating an expense with minimal data."""
        project = ConstructionProjectFactory(ownerid=salesperson)
        period = ImputationPeriodFactory()

        dto = CreateProjectExpenseDto(
            projectid=project.projectid,
            periodid=period.periodid,
            documenttype=DocumentTypeCode.INVOICE,
        )
        expense = ExpenseService.create_expense(dto, salesperson)

        assert expense.expenseid is not None
        assert expense.projectid == project
        assert expense.documenttype == DocumentTypeCode.INVOICE
        assert expense.statecode == ExpenseStateCode.ACTIVE
        assert expense.classificationstatus == ClassificationStatusCode.PENDING

    def test_create_expense_with_lines(self, db, salesperson):
        """Test creating an expense with lines recalculates totals."""
        project = ConstructionProjectFactory(ownerid=salesperson)
        period = ImputationPeriodFactory()

        lines = [
            CreateExpenseLineDto(
                description='Material A',
                quantity=Decimal('10'),
                unitprice=Decimal('100'),
                taxamount=Decimal('160'),
            ),
            CreateExpenseLineDto(
                description='Material B',
                quantity=Decimal('5'),
                unitprice=Decimal('200'),
                taxamount=Decimal('160'),
            ),
        ]

        dto = CreateProjectExpenseDto(
            projectid=project.projectid,
            periodid=period.periodid,
            documenttype=DocumentTypeCode.INVOICE,
            lines=lines,
        )
        expense = ExpenseService.create_expense(dto, salesperson)

        assert expense.lines.count() == 2
        # Line 1: subtotal=1000, net=1000+160=1160
        # Line 2: subtotal=1000, net=1000+160=1160
        assert expense.subtotal == Decimal('2000.00')
        assert expense.taxamount == Decimal('320.00')
        assert expense.netamount == Decimal('2320.00')

    def test_cancel_expense(self, db, salesperson):
        """Test canceling an expense."""
        expense = ProjectExpenseFactory(ownerid=salesperson)

        canceled = ExpenseService.cancel_expense(expense.expenseid, salesperson)

        assert canceled.statecode == ExpenseStateCode.CANCELED

    def test_list_expenses_with_filters(self, db, salesperson):
        """Test listing expenses with filters."""
        project = ConstructionProjectFactory(ownerid=salesperson)
        period = ImputationPeriodFactory()

        ProjectExpenseFactory(
            projectid=project, periodid=period, ownerid=salesperson,
            documenttype=DocumentTypeCode.INVOICE,
        )
        ProjectExpenseFactory(
            projectid=project, periodid=period, ownerid=salesperson,
            documenttype=DocumentTypeCode.PAYROLL,
        )

        all_expenses = ExpenseService.list_expenses(project.projectid, salesperson)
        assert all_expenses.count() == 2

        invoices = ExpenseService.list_expenses(
            project.projectid, salesperson,
            documenttype=DocumentTypeCode.INVOICE,
        )
        assert invoices.count() == 1

    def test_get_expense_by_id_not_found(self, db, salesperson):
        """Test getting non-existent expense raises NotFound."""
        with pytest.raises(NotFound):
            ExpenseService.get_expense_by_id(uuid4(), salesperson)

    def test_get_expense_summary(self, db, salesperson):
        """Test aggregate expense summary."""
        project = ConstructionProjectFactory(ownerid=salesperson)
        period = ImputationPeriodFactory()

        ProjectExpenseFactory(
            projectid=project, periodid=period, ownerid=salesperson,
            netamount=Decimal('1000.00'),
            classificationstatus=ClassificationStatusCode.PENDING,
        )
        ProjectExpenseFactory(
            projectid=project, periodid=period, ownerid=salesperson,
            netamount=Decimal('2000.00'),
            classificationstatus=ClassificationStatusCode.CLASSIFIED,
        )

        summary = ExpenseService.get_expense_summary(project.projectid, salesperson)

        assert summary['totalExpenses'] == 2
        assert summary['totalAmount'] == Decimal('3000.00')
        assert summary['classifiedCount'] == 1
        assert summary['unclassifiedCount'] == 1


# =============================================================================
# TestClassificationService
# =============================================================================

@pytest.mark.unit
class TestClassificationService:
    """Tests for ClassificationService."""

    def test_classify_expense_assigned(self, db, salesperson):
        """Test classifying an unclassified expense creates 'Assigned' log."""
        expense = ProjectExpenseFactory(ownerid=salesperson)
        code = ImputationCodeFactory()

        result = ClassificationService.classify_expense(
            expense.expenseid, code.imputationcodeid, 'First classification', salesperson
        )

        assert result.classificationstatus == ClassificationStatusCode.CLASSIFIED
        assert result.imputationcodeid == code

        logs = ClassificationLog.objects.filter(expenseid=expense)
        assert logs.count() == 1
        assert logs.first().action == ClassificationActionCode.ASSIGNED

    def test_classify_expense_changed(self, db, salesperson):
        """Test re-classifying an expense creates 'Changed' log."""
        code1 = ImputationCodeFactory()
        code2 = ImputationCodeFactory()
        expense = ProjectExpenseFactory(
            ownerid=salesperson,
            imputationcodeid=code1,
            classificationstatus=ClassificationStatusCode.CLASSIFIED,
        )

        result = ClassificationService.classify_expense(
            expense.expenseid, code2.imputationcodeid, 'Re-classification', salesperson
        )

        assert result.imputationcodeid == code2

        logs = ClassificationLog.objects.filter(expenseid=expense)
        assert logs.count() == 1
        assert logs.first().action == ClassificationActionCode.CHANGED

    def test_bulk_classify(self, db, salesperson):
        """Test bulk classifying multiple expenses."""
        project = ConstructionProjectFactory(ownerid=salesperson)
        period = ImputationPeriodFactory()
        code = ImputationCodeFactory()

        exp1 = ProjectExpenseFactory(projectid=project, periodid=period, ownerid=salesperson)
        exp2 = ProjectExpenseFactory(projectid=project, periodid=period, ownerid=salesperson)

        results = ClassificationService.bulk_classify(
            [exp1.expenseid, exp2.expenseid],
            code.imputationcodeid,
            'Bulk assign',
            salesperson,
        )

        assert len(results) == 2
        for result in results:
            assert result.classificationstatus == ClassificationStatusCode.CLASSIFIED
            assert result.imputationcodeid == code

    def test_unclassify_expense(self, db, salesperson):
        """Test removing classification from an expense."""
        code = ImputationCodeFactory()
        expense = ProjectExpenseFactory(
            ownerid=salesperson,
            imputationcodeid=code,
            classificationstatus=ClassificationStatusCode.CLASSIFIED,
        )

        result = ClassificationService.unclassify_expense(
            expense.expenseid, 'Removing classification', salesperson
        )

        assert result.imputationcodeid is None
        assert result.classificationstatus == ClassificationStatusCode.PENDING

        logs = ClassificationLog.objects.filter(expenseid=expense)
        assert logs.count() == 1
        assert logs.first().action == ClassificationActionCode.REMOVED

    def test_unclassify_already_unclassified_fails(self, db, salesperson):
        """Test unclassifying an already unclassified expense raises ValidationError."""
        expense = ProjectExpenseFactory(ownerid=salesperson)

        with pytest.raises(ValidationError, match='not classified'):
            ClassificationService.unclassify_expense(expense.expenseid, None, salesperson)

    def test_get_classification_logs(self, db, salesperson):
        """Test getting classification log history."""
        code = ImputationCodeFactory()
        expense = ProjectExpenseFactory(ownerid=salesperson)

        ClassificationService.classify_expense(
            expense.expenseid, code.imputationcodeid, 'Note 1', salesperson
        )

        logs = ClassificationService.get_classification_logs(expense.expenseid)
        assert logs.count() == 1
        assert logs.first().classifiedbyname == salesperson.fullname


# =============================================================================
# TestVerificationService
# =============================================================================

@pytest.mark.unit
class TestVerificationService:
    """Tests for VerificationService."""

    def test_update_verification_status(self, db, salesperson):
        """Test updating verification status."""
        expense = ProjectExpenseFactory(ownerid=salesperson)

        result = VerificationService.update_verification(
            expense.expenseid,
            VerificationStatusCode.VERIFIED,
            'All amounts verified',
            salesperson,
        )

        assert result.verificationstatus == VerificationStatusCode.VERIFIED
        assert result.verificationnotes == 'All amounts verified'
        assert result.verifiedby == salesperson
        assert result.verifiedon is not None

    def test_update_verification_discrepancy(self, db, salesperson):
        """Test marking a discrepancy."""
        expense = ProjectExpenseFactory(ownerid=salesperson)

        result = VerificationService.update_verification(
            expense.expenseid,
            VerificationStatusCode.DISCREPANCY,
            'Tax amount mismatch',
            salesperson,
        )

        assert result.verificationstatus == VerificationStatusCode.DISCREPANCY


# =============================================================================
# TestExpenseLineService
# =============================================================================

@pytest.mark.unit
class TestExpenseLineService:
    """Tests for ExpenseLineService."""

    def test_add_line_recalculates_totals(self, db, salesperson):
        """Test adding a line recalculates expense totals."""
        expense = ProjectExpenseFactory(
            ownerid=salesperson,
            subtotal=Decimal('0'), taxamount=Decimal('0'),
            retentionamount=Decimal('0'), discountamount=Decimal('0'),
            netamount=Decimal('0'),
        )

        dto = CreateExpenseLineDto(
            description='Concrete',
            quantity=Decimal('10'),
            unitprice=Decimal('500'),
            taxamount=Decimal('800'),
        )
        line = ExpenseLineService.add_line(expense.expenseid, dto, salesperson)

        assert line.linenumber == 1
        assert line.subtotal == Decimal('5000.00')
        assert line.netamount == Decimal('5800.00')

        expense.refresh_from_db()
        assert expense.subtotal == Decimal('5000.00')
        assert expense.taxamount == Decimal('800.00')
        assert expense.netamount == Decimal('5800.00')

    def test_update_line_recalculates_totals(self, db, salesperson):
        """Test updating a line recalculates expense totals."""
        expense = ProjectExpenseFactory(
            ownerid=salesperson,
            subtotal=Decimal('0'), taxamount=Decimal('0'),
            retentionamount=Decimal('0'), discountamount=Decimal('0'),
            netamount=Decimal('0'),
        )
        line = ExpenseLineFactory(
            expenseid=expense,
            linenumber=1,
            quantity=Decimal('10'),
            unitprice=Decimal('100'),
            subtotal=Decimal('1000'),
            taxamount=Decimal('160'),
            netamount=Decimal('1160'),
        )

        # First, recalculate initial state
        ExpenseLineService._recalculate_expense_totals(expense)
        expense.refresh_from_db()
        assert expense.netamount == Decimal('1160.00')

        dto = UpdateExpenseLineDto(quantity=Decimal('20'))
        updated_line = ExpenseLineService.update_line(line.expenselineid, dto, salesperson)

        assert updated_line.subtotal == Decimal('2000.00')
        assert updated_line.netamount == Decimal('2160.00')

        expense.refresh_from_db()
        assert expense.subtotal == Decimal('2000.00')
        assert expense.netamount == Decimal('2160.00')

    def test_remove_line_recalculates_totals(self, db, salesperson):
        """Test removing a line recalculates expense totals."""
        expense = ProjectExpenseFactory(
            ownerid=salesperson,
            subtotal=Decimal('0'), taxamount=Decimal('0'),
            retentionamount=Decimal('0'), discountamount=Decimal('0'),
            netamount=Decimal('0'),
        )
        line1 = ExpenseLineFactory(
            expenseid=expense, linenumber=1,
            quantity=Decimal('10'), unitprice=Decimal('100'),
            subtotal=Decimal('1000'), taxamount=Decimal('160'),
            netamount=Decimal('1160'),
        )
        line2 = ExpenseLineFactory(
            expenseid=expense, linenumber=2,
            quantity=Decimal('5'), unitprice=Decimal('200'),
            subtotal=Decimal('1000'), taxamount=Decimal('160'),
            netamount=Decimal('1160'),
        )

        ExpenseLineService._recalculate_expense_totals(expense)
        expense.refresh_from_db()
        assert expense.netamount == Decimal('2320.00')

        ExpenseLineService.remove_line(line1.expenselineid, salesperson)

        expense.refresh_from_db()
        assert expense.subtotal == Decimal('1000.00')
        assert expense.netamount == Decimal('1160.00')

    def test_remove_line_not_found(self, db, salesperson):
        """Test removing non-existent line raises NotFound."""
        with pytest.raises(NotFound):
            ExpenseLineService.remove_line(uuid4(), salesperson)


# =============================================================================
# TestProvisionService
# =============================================================================

@pytest.mark.unit
class TestProvisionService:
    """Tests for ProvisionService."""

    def test_convert_provision_to_real_expense(self, db, salesperson):
        """Test converting a provision to a real expense."""
        provision = ProvisionExpenseFactory(ownerid=salesperson)
        project = provision.projectid
        period = provision.periodid

        real_dto = CreateProjectExpenseDto(
            projectid=project.projectid,
            periodid=period.periodid,
            documenttype=DocumentTypeCode.INVOICE,
            subtotal=Decimal('5000.00'),
            taxamount=Decimal('800.00'),
            netamount=Decimal('5800.00'),
        )

        new_expense = ProvisionService.convert_provision(
            provision.expenseid, real_dto, salesperson
        )

        # Verify new expense
        assert new_expense.expenseid is not None
        assert new_expense.documenttype == DocumentTypeCode.INVOICE
        assert new_expense.provisionconvertedfromid == provision

        # Verify provision was marked as converted
        provision.refresh_from_db()
        assert provision.provisionstatus == ProvisionStatusCode.CONVERTED

    def test_convert_non_provision_fails(self, db, salesperson):
        """Test converting a non-provision expense fails."""
        expense = ProjectExpenseFactory(
            ownerid=salesperson,
            documenttype=DocumentTypeCode.INVOICE,
        )
        period = expense.periodid
        project = expense.projectid

        dto = CreateProjectExpenseDto(
            projectid=project.projectid,
            periodid=period.periodid,
            documenttype=DocumentTypeCode.INVOICE,
        )

        with pytest.raises(ValidationError, match='not a provision'):
            ProvisionService.convert_provision(expense.expenseid, dto, salesperson)

    def test_convert_non_active_provision_fails(self, db, salesperson):
        """Test converting a non-active provision fails."""
        provision = ProvisionExpenseFactory(
            ownerid=salesperson,
            provisionstatus=ProvisionStatusCode.CONVERTED,
        )
        period = provision.periodid
        project = provision.projectid

        dto = CreateProjectExpenseDto(
            projectid=project.projectid,
            periodid=period.periodid,
            documenttype=DocumentTypeCode.INVOICE,
        )

        with pytest.raises(ValidationError, match='not active'):
            ProvisionService.convert_provision(provision.expenseid, dto, salesperson)


# =============================================================================
# TestEstimateService
# =============================================================================

@pytest.mark.unit
class TestEstimateService:
    """Tests for EstimateService."""

    def test_create_estimate_auto_numbering(self, db, salesperson):
        """Test estimate auto-numbering within a project."""
        project = ConstructionProjectFactory(ownerid=salesperson)

        dto1 = CreateClientEstimateDto(
            projectid=project.projectid,
            estimatedamount=Decimal('100000.00'),
        )
        est1 = EstimateService.create_estimate(dto1, salesperson)
        assert est1.estimatenumber == 1

        dto2 = CreateClientEstimateDto(
            projectid=project.projectid,
            estimatedamount=Decimal('200000.00'),
        )
        est2 = EstimateService.create_estimate(dto2, salesperson)
        assert est2.estimatenumber == 2

    def test_create_estimate_computed_totals(self, db, salesperson):
        """Test estimate computed fields are calculated correctly."""
        project = ConstructionProjectFactory(ownerid=salesperson)

        dto = CreateClientEstimateDto(
            projectid=project.projectid,
            estimatedamount=Decimal('100000.00'),
            advanceamortization=Decimal('5000.00'),
            otherdeductions=Decimal('2000.00'),
            materialdeductions=Decimal('3000.00'),
            guaranteefund=Decimal('5000.00'),
            taxretained=Decimal('0.00'),
        )
        estimate = EstimateService.create_estimate(dto, salesperson)

        # totaldeductions = 5000 + 2000 + 3000 + 5000 = 15000
        assert estimate.totaldeductions == Decimal('15000.00')
        # amountnotax = 100000 - 15000 = 85000
        assert estimate.amountnotax == Decimal('85000.00')
        # taxamount = 85000 * 0.16 = 13600
        assert estimate.taxamount == Decimal('13600.00')
        # totalinvoiced = 85000 + 13600 - 0 = 98600
        assert estimate.totalinvoiced == Decimal('98600.00')
        # collectableamount = totalinvoiced = 98600
        assert estimate.collectableamount == Decimal('98600.00')

    def test_update_estimate_recalculates(self, db, salesperson):
        """Test updating estimate recalculates computed fields."""
        estimate = ClientEstimateFactory()

        dto = UpdateClientEstimateDto(
            estimatedamount=Decimal('200000.00'),
            advanceamortization=Decimal('10000.00'),
        )
        updated = EstimateService.update_estimate(estimate.estimateid, dto, salesperson)

        assert updated.estimatedamount == Decimal('200000.00')
        assert updated.advanceamortization == Decimal('10000.00')
        # Recalculated
        assert updated.totaldeductions == (
            Decimal('10000.00') + updated.otherdeductions
            + updated.materialdeductions + updated.guaranteefund
        )

    def test_delete_estimate_sets_canceled(self, db, salesperson):
        """Test deleting estimate sets statecode to Canceled."""
        estimate = ClientEstimateFactory()

        result = EstimateService.delete_estimate(estimate.estimateid, salesperson)

        assert result.statecode == EstimateStateCode.CANCELED

    def test_list_estimates(self, db, salesperson):
        """Test listing estimates for a project."""
        project = ConstructionProjectFactory(ownerid=salesperson)
        ClientEstimateFactory(projectid=project)
        ClientEstimateFactory(projectid=project)

        estimates = EstimateService.list_estimates(project.projectid, salesperson)
        assert estimates.count() == 2

    def test_get_estimate_not_found(self, db, salesperson):
        """Test getting non-existent estimate raises NotFound."""
        with pytest.raises(NotFound):
            EstimateService.update_estimate(uuid4(), UpdateClientEstimateDto(), salesperson)
