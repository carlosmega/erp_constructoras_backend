"""Expense management business logic service layer."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from django.db import models, transaction
from django.db.models import Sum, Count, Q, QuerySet, Max
from django.utils import timezone

from apps.expenses.models import (
    ProjectExpense,
    ExpenseLine,
    ExpenseAttachment,
    ClassificationLog,
    ClientEstimate,
    ClassificationStatusCode,
    ClassificationActionCode,
    ExpenseStateCode,
    DocumentTypeCode,
    ProvisionStatusCode,
    EstimateStateCode,
)
from apps.expenses.schemas import (
    CreateProjectExpenseDto,
    UpdateProjectExpenseDto,
    CreateExpenseLineDto,
    UpdateExpenseLineDto,
    CreateExpenseAttachmentDto,
    ClassifyExpenseDto,
    BulkClassifyDto,
    VerifyExpenseDto,
    CreateClientEstimateDto,
    UpdateClientEstimateDto,
)
from core.exceptions import ValidationError, NotFound


# =============================================================================
# ExpenseService
# =============================================================================

class ExpenseService:
    """Service for ProjectExpense entity business logic."""

    @staticmethod
    def list_expenses(
        project_id: UUID,
        user,
        period_id: Optional[UUID] = None,
        documenttype: Optional[int] = None,
        classificationstatus: Optional[int] = None,
        statecode: Optional[int] = None,
    ) -> QuerySet[ProjectExpense]:
        """List expenses for a project with optional filtering."""
        queryset = ProjectExpense.objects.filter(projectid=project_id)

        if period_id is not None:
            queryset = queryset.filter(periodid=period_id)
        if documenttype is not None:
            queryset = queryset.filter(documenttype=documenttype)
        if classificationstatus is not None:
            queryset = queryset.filter(classificationstatus=classificationstatus)
        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)

        return queryset.select_related(
            'ownerid', 'periodid', 'imputationcodeid'
        )

    @staticmethod
    @transaction.atomic
    def create_expense(dto: CreateProjectExpenseDto, user) -> ProjectExpense:
        """Create a new project expense with optional lines."""
        expense = ProjectExpense(
            projectid_id=dto.projectid,
            periodid_id=dto.periodid,
            documenttype=dto.documenttype,
            imputationcodeid_id=dto.imputationcodeid,
            supplierrfc=dto.supplierrfc,
            suppliername=dto.suppliername,
            invoiceuuid=dto.invoiceuuid,
            invoicefolio=dto.invoicefolio,
            invoicedate=dto.invoicedate,
            expensesource=dto.expensesource,
            payrolltype=dto.payrolltype,
            workername=dto.workername,
            provisionstatus=dto.provisionstatus,
            paymentmethod=dto.paymentmethod,
            paymentstatus=dto.paymentstatus,
            currency=dto.currency,
            exchangerate=dto.exchangerate,
            subtotal=dto.subtotal,
            taxamount=dto.taxamount,
            retentionamount=dto.retentionamount,
            discountamount=dto.discountamount,
            netamount=dto.netamount,
            notes=dto.notes,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        if dto.imputationcodeid:
            expense.classificationstatus = ClassificationStatusCode.CLASSIFIED

        expense.save()

        if dto.lines:
            for idx, line_dto in enumerate(dto.lines, start=1):
                subtotal = line_dto.quantity * line_dto.unitprice
                netamount = subtotal + line_dto.taxamount - line_dto.retentionamount - line_dto.discountamount
                ExpenseLine.objects.create(
                    expenseid=expense,
                    linenumber=idx,
                    description=line_dto.description,
                    quantity=line_dto.quantity,
                    unitprice=line_dto.unitprice,
                    subtotal=subtotal,
                    taxamount=line_dto.taxamount,
                    retentionamount=line_dto.retentionamount,
                    discountamount=line_dto.discountamount,
                    netamount=netamount,
                )
            ExpenseLineService._recalculate_expense_totals(expense)

        return expense

    @staticmethod
    def get_expense_by_id(expense_id: UUID, user) -> ProjectExpense:
        """Get expense by ID with related data."""
        try:
            return ProjectExpense.objects.select_related(
                'ownerid', 'periodid', 'imputationcodeid', 'verifiedby',
                'projectid', 'provisionconvertedfromid'
            ).get(expenseid=expense_id)
        except ProjectExpense.DoesNotExist:
            raise NotFound(f"Expense with ID {expense_id} not found")

    @staticmethod
    @transaction.atomic
    def update_expense(expense_id: UUID, dto: UpdateProjectExpenseDto, user) -> ProjectExpense:
        """Update an existing project expense."""
        expense = ExpenseService.get_expense_by_id(expense_id, user)

        update_fields = [
            'periodid', 'documenttype', 'supplierrfc', 'suppliername',
            'invoiceuuid', 'invoicefolio', 'invoicedate', 'expensesource',
            'payrolltype', 'workername', 'paymentmethod', 'paymentstatus',
            'currency', 'exchangerate', 'subtotal', 'taxamount',
            'retentionamount', 'discountamount', 'netamount', 'notes',
        ]

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                if field == 'periodid':
                    expense.periodid_id = value
                else:
                    setattr(expense, field, value)

        expense.modifiedby = user
        expense.save()

        if dto.lines is not None:
            expense.lines.all().delete()
            for idx, line_dto in enumerate(dto.lines, start=1):
                subtotal = line_dto.quantity * line_dto.unitprice
                netamount = subtotal + line_dto.taxamount - line_dto.retentionamount - line_dto.discountamount
                ExpenseLine.objects.create(
                    expenseid=expense,
                    linenumber=idx,
                    description=line_dto.description,
                    quantity=line_dto.quantity,
                    unitprice=line_dto.unitprice,
                    subtotal=subtotal,
                    taxamount=line_dto.taxamount,
                    retentionamount=line_dto.retentionamount,
                    discountamount=line_dto.discountamount,
                    netamount=netamount,
                )
            ExpenseLineService._recalculate_expense_totals(expense)

        return expense

    @staticmethod
    def cancel_expense(expense_id: UUID, user) -> ProjectExpense:
        """Cancel a project expense."""
        expense = ExpenseService.get_expense_by_id(expense_id, user)
        expense.statecode = ExpenseStateCode.CANCELED
        expense.modifiedby = user
        expense.save()
        return expense

    @staticmethod
    def get_unclassified_expenses(project_id: UUID, user) -> QuerySet[ProjectExpense]:
        """Get expenses that are pending classification."""
        return ProjectExpense.objects.filter(
            projectid=project_id,
            classificationstatus=ClassificationStatusCode.PENDING,
            statecode=ExpenseStateCode.ACTIVE,
        ).select_related('ownerid', 'periodid', 'imputationcodeid')

    @staticmethod
    def get_expense_summary(project_id: UUID, user) -> dict:
        """Get aggregate expense summary for a project."""
        base_qs = ProjectExpense.objects.filter(
            projectid=project_id,
            statecode=ExpenseStateCode.ACTIVE,
        )

        totals = base_qs.aggregate(
            total_count=Count('expenseid'),
            total_amount=Sum('netamount'),
        )

        classified_count = base_qs.filter(
            classificationstatus=ClassificationStatusCode.CLASSIFIED
        ).count()
        unclassified_count = base_qs.filter(
            classificationstatus=ClassificationStatusCode.PENDING
        ).count()

        # Verification status counts
        verified_count = base_qs.filter(verificationstatus=1).count()
        pending_verification_count = base_qs.filter(verificationstatus=0).count()
        discrepancy_count = base_qs.filter(verificationstatus=2).count()

        # By document type as dict keyed by document type code
        by_doc_type_qs = base_qs.values('documenttype').annotate(
            count=Count('expenseid'),
            amount=Sum('netamount'),
        ).order_by('documenttype')

        by_document_type = {}
        for row in by_doc_type_qs:
            doc_type = row['documenttype']
            by_document_type[doc_type] = {
                'count': row['count'],
                'amount': float(row['amount'] or 0),
            }

        return {
            'totalExpenses': totals['total_count'] or 0,
            'totalAmount': totals['total_amount'] or Decimal('0.00'),
            'classifiedCount': classified_count,
            'unclassifiedCount': unclassified_count,
            'verifiedCount': verified_count,
            'pendingVerificationCount': pending_verification_count,
            'discrepancyCount': discrepancy_count,
            'byDocumentType': by_document_type,
        }


# =============================================================================
# ClassificationService
# =============================================================================

class ClassificationService:
    """Service for expense classification business logic."""

    @staticmethod
    @transaction.atomic
    def classify_expense(expense_id: UUID, imputation_code_id: UUID, notes: Optional[str], user) -> ProjectExpense:
        """Classify an expense with an imputation code."""
        expense = ExpenseService.get_expense_by_id(expense_id, user)

        from apps.budgets.models import ImputationCode
        try:
            new_code = ImputationCode.objects.get(imputationcodeid=imputation_code_id)
        except ImputationCode.DoesNotExist:
            raise NotFound(f"Imputation code with ID {imputation_code_id} not found")

        # Determine action
        if expense.imputationcodeid is None:
            action = ClassificationActionCode.ASSIGNED
        else:
            action = ClassificationActionCode.CHANGED

        # Create classification log
        ClassificationLog.objects.create(
            expenseid=expense,
            previousimputationcodeid=expense.imputationcodeid,
            previousimputationcode=expense.imputationcodeid.code if expense.imputationcodeid else None,
            newimputationcodeid=new_code,
            newimputationcode=new_code.code,
            action=action,
            classifiedby=user,
            classifiedbyname=user.fullname,
            notes=notes,
        )

        # Update expense
        expense.imputationcodeid = new_code
        expense.classificationstatus = ClassificationStatusCode.CLASSIFIED
        expense.modifiedby = user
        expense.save()

        # Update imputation code totalspent
        total = ProjectExpense.objects.filter(
            imputationcodeid=new_code,
            statecode=ExpenseStateCode.ACTIVE,
        ).aggregate(total=Sum('netamount'))['total'] or Decimal('0.00')
        new_code.totalspent = total
        new_code.save()

        return expense

    @staticmethod
    @transaction.atomic
    def bulk_classify(expense_ids: list[UUID], imputation_code_id: UUID, notes: Optional[str], user) -> list[ProjectExpense]:
        """Classify multiple expenses with the same imputation code."""
        results = []
        for expense_id in expense_ids:
            expense = ClassificationService.classify_expense(
                expense_id, imputation_code_id, notes, user
            )
            results.append(expense)
        return results

    @staticmethod
    @transaction.atomic
    def unclassify_expense(expense_id: UUID, notes: Optional[str], user) -> ProjectExpense:
        """Remove classification from an expense."""
        expense = ExpenseService.get_expense_by_id(expense_id, user)

        if expense.imputationcodeid is None:
            raise ValidationError("Expense is not classified")

        old_code = expense.imputationcodeid

        # Create classification log
        ClassificationLog.objects.create(
            expenseid=expense,
            previousimputationcodeid=old_code,
            previousimputationcode=old_code.code,
            newimputationcodeid=None,
            newimputationcode=None,
            action=ClassificationActionCode.REMOVED,
            classifiedby=user,
            classifiedbyname=user.fullname,
            notes=notes,
        )

        # Update expense
        expense.imputationcodeid = None
        expense.classificationstatus = ClassificationStatusCode.PENDING
        expense.modifiedby = user
        expense.save()

        # Update old imputation code totalspent
        total = ProjectExpense.objects.filter(
            imputationcodeid=old_code,
            statecode=ExpenseStateCode.ACTIVE,
        ).aggregate(total=Sum('netamount'))['total'] or Decimal('0.00')
        old_code.totalspent = total
        old_code.save()

        return expense

    @staticmethod
    def get_classification_logs(expense_id: UUID) -> QuerySet[ClassificationLog]:
        """Get classification logs for an expense."""
        return ClassificationLog.objects.filter(
            expenseid=expense_id
        ).select_related(
            'classifiedby', 'previousimputationcodeid', 'newimputationcodeid'
        ).order_by('-createdon')


# =============================================================================
# VerificationService
# =============================================================================

class VerificationService:
    """Service for expense verification business logic."""

    @staticmethod
    def update_verification(expense_id: UUID, status: int, notes: Optional[str], user) -> ProjectExpense:
        """Update verification status on an expense."""
        expense = ExpenseService.get_expense_by_id(expense_id, user)
        expense.verificationstatus = status
        expense.verificationnotes = notes
        expense.verifiedby = user
        expense.verifiedon = timezone.now()
        expense.modifiedby = user
        expense.save()
        return expense


# =============================================================================
# ExpenseLineService
# =============================================================================

class ExpenseLineService:
    """Service for ExpenseLine entity business logic."""

    @staticmethod
    def list_lines(expense_id: UUID) -> QuerySet[ExpenseLine]:
        """Get all lines for an expense."""
        return ExpenseLine.objects.filter(expenseid=expense_id).order_by('linenumber')

    @staticmethod
    @transaction.atomic
    def add_line(expense_id: UUID, dto: CreateExpenseLineDto, user) -> ExpenseLine:
        """Add a line to an expense and recalculate totals."""
        expense = ExpenseService.get_expense_by_id(expense_id, user)

        # Auto-assign line number
        max_line = ExpenseLine.objects.filter(
            expenseid=expense
        ).aggregate(max_line=Max('linenumber'))['max_line'] or 0

        subtotal = dto.quantity * dto.unitprice
        netamount = subtotal + dto.taxamount - dto.retentionamount - dto.discountamount

        line = ExpenseLine.objects.create(
            expenseid=expense,
            linenumber=max_line + 1,
            description=dto.description,
            quantity=dto.quantity,
            unitprice=dto.unitprice,
            subtotal=subtotal,
            taxamount=dto.taxamount,
            retentionamount=dto.retentionamount,
            discountamount=dto.discountamount,
            netamount=netamount,
        )

        ExpenseLineService._recalculate_expense_totals(expense)
        return line

    @staticmethod
    @transaction.atomic
    def update_line(line_id: UUID, dto: UpdateExpenseLineDto, user) -> ExpenseLine:
        """Update an expense line and recalculate totals."""
        try:
            line = ExpenseLine.objects.select_related('expenseid').get(expenselineid=line_id)
        except ExpenseLine.DoesNotExist:
            raise NotFound(f"Expense line with ID {line_id} not found")

        update_fields = ['description', 'quantity', 'unitprice', 'taxamount', 'retentionamount', 'discountamount']
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(line, field, value)

        # Recalculate line subtotal and netamount
        line.subtotal = line.quantity * line.unitprice
        line.netamount = line.subtotal + line.taxamount - line.retentionamount - line.discountamount
        line.save()

        ExpenseLineService._recalculate_expense_totals(line.expenseid)
        return line

    @staticmethod
    @transaction.atomic
    def remove_line(line_id: UUID, user) -> None:
        """Remove an expense line and recalculate totals."""
        try:
            line = ExpenseLine.objects.select_related('expenseid').get(expenselineid=line_id)
        except ExpenseLine.DoesNotExist:
            raise NotFound(f"Expense line with ID {line_id} not found")

        expense = line.expenseid
        line.delete()
        ExpenseLineService._recalculate_expense_totals(expense)

    @staticmethod
    def _recalculate_expense_totals(expense: ProjectExpense) -> None:
        """Sum all lines and update the parent expense totals."""
        totals = ExpenseLine.objects.filter(
            expenseid=expense
        ).aggregate(
            total_subtotal=Sum('subtotal'),
            total_tax=Sum('taxamount'),
            total_retention=Sum('retentionamount'),
            total_discount=Sum('discountamount'),
            total_net=Sum('netamount'),
        )

        expense.subtotal = totals['total_subtotal'] or Decimal('0.00')
        expense.taxamount = totals['total_tax'] or Decimal('0.00')
        expense.retentionamount = totals['total_retention'] or Decimal('0.00')
        expense.discountamount = totals['total_discount'] or Decimal('0.00')
        expense.netamount = totals['total_net'] or Decimal('0.00')
        expense.save()


# =============================================================================
# AttachmentService
# =============================================================================

class AttachmentService:
    """Service for ExpenseAttachment entity business logic."""

    @staticmethod
    def list_attachments(expense_id: UUID) -> QuerySet[ExpenseAttachment]:
        """Get all attachments for an expense."""
        return ExpenseAttachment.objects.filter(expenseid=expense_id)

    @staticmethod
    def add_attachment(dto: CreateExpenseAttachmentDto, user) -> ExpenseAttachment:
        """Create attachment metadata."""
        # Validate expense exists
        try:
            ProjectExpense.objects.get(expenseid=dto.expenseid)
        except ProjectExpense.DoesNotExist:
            raise NotFound(f"Expense with ID {dto.expenseid} not found")

        return ExpenseAttachment.objects.create(
            expenseid_id=dto.expenseid,
            filename=dto.filename,
            suggestedfilename=dto.suggestedfilename,
            filetype=dto.filetype,
            filesize=dto.filesize,
            mimetype=dto.mimetype,
            storageurl=dto.storageurl,
        )

    @staticmethod
    def remove_attachment(attachment_id: UUID, user) -> None:
        """Delete an attachment."""
        try:
            attachment = ExpenseAttachment.objects.get(attachmentid=attachment_id)
        except ExpenseAttachment.DoesNotExist:
            raise NotFound(f"Attachment with ID {attachment_id} not found")
        attachment.delete()


# =============================================================================
# ProvisionService
# =============================================================================

class ProvisionService:
    """Service for provision conversion business logic."""

    @staticmethod
    @transaction.atomic
    def convert_provision(provision_id: UUID, real_expense_dto: CreateProjectExpenseDto, user) -> ProjectExpense:
        """Convert a provision to a real expense."""
        provision = ExpenseService.get_expense_by_id(provision_id, user)

        if provision.documenttype != DocumentTypeCode.PROVISION:
            raise ValidationError("Expense is not a provision")

        if provision.provisionstatus != ProvisionStatusCode.ACTIVE:
            raise ValidationError("Provision is not active")

        # Mark provision as converted
        provision.provisionstatus = ProvisionStatusCode.CONVERTED
        provision.modifiedby = user
        provision.save()

        # Create real expense from dto
        new_expense = ExpenseService.create_expense(real_expense_dto, user)
        new_expense.provisionconvertedfromid = provision
        new_expense.save()

        return new_expense


# =============================================================================
# EstimateService
# =============================================================================

class EstimateService:
    """Service for ClientEstimate entity business logic."""

    @staticmethod
    def list_estimates(project_id: UUID, user) -> QuerySet[ClientEstimate]:
        """Get all estimates for a project."""
        return ClientEstimate.objects.filter(
            projectid=project_id
        ).select_related('periodid')

    @staticmethod
    def get_estimate_by_id(estimate_id: UUID, user) -> ClientEstimate:
        """Get a single estimate by ID."""
        try:
            return ClientEstimate.objects.select_related(
                'periodid', 'createdby', 'modifiedby'
            ).get(estimateid=estimate_id)
        except ClientEstimate.DoesNotExist:
            raise NotFound(f"Estimate with ID {estimate_id} not found")

    @staticmethod
    @transaction.atomic
    def create_estimate(dto: CreateClientEstimateDto, user) -> ClientEstimate:
        """Create a new client estimate with auto-numbering and computed fields."""
        # Auto-assign estimate number
        max_num = ClientEstimate.objects.filter(
            projectid=dto.projectid
        ).aggregate(max_num=Max('estimatenumber'))['max_num'] or 0

        estimate = ClientEstimate(
            projectid_id=dto.projectid,
            periodid_id=dto.periodid,
            estimatenumber=max_num + 1,
            invoicenumber=dto.invoicenumber,
            invoicedate=dto.invoicedate,
            estimationperiod=dto.estimationperiod,
            estimatetype=dto.estimatetype,
            estimatedamount=dto.estimatedamount,
            advanceamortization=dto.advanceamortization,
            otherdeductions=dto.otherdeductions,
            materialdeductions=dto.materialdeductions,
            guaranteefund=dto.guaranteefund,
            taxretained=dto.taxretained,
            paymentstatus=dto.paymentstatus,
            paymentdate=dto.paymentdate,
            amountpaid=dto.amountpaid,
            createdby=user,
            modifiedby=user,
        )

        EstimateService._calculate_estimate_totals(estimate)
        estimate.save()
        return estimate

    @staticmethod
    @transaction.atomic
    def update_estimate(estimate_id: UUID, dto: UpdateClientEstimateDto, user) -> ClientEstimate:
        """Update a client estimate and recalculate computed fields."""
        try:
            estimate = ClientEstimate.objects.get(estimateid=estimate_id)
        except ClientEstimate.DoesNotExist:
            raise NotFound(f"Estimate with ID {estimate_id} not found")

        update_fields = [
            'periodid', 'invoicenumber', 'invoicedate', 'estimationperiod',
            'estimatetype', 'estimatedamount', 'advanceamortization',
            'otherdeductions', 'materialdeductions', 'guaranteefund',
            'taxretained', 'paymentstatus', 'paymentdate', 'amountpaid',
        ]

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                if field == 'periodid':
                    estimate.periodid_id = value
                else:
                    setattr(estimate, field, value)

        estimate.modifiedby = user
        EstimateService._calculate_estimate_totals(estimate)
        estimate.save()
        return estimate

    @staticmethod
    def delete_estimate(estimate_id: UUID, user) -> ClientEstimate:
        """Cancel a client estimate."""
        try:
            estimate = ClientEstimate.objects.get(estimateid=estimate_id)
        except ClientEstimate.DoesNotExist:
            raise NotFound(f"Estimate with ID {estimate_id} not found")

        estimate.statecode = EstimateStateCode.CANCELED
        estimate.modifiedby = user
        estimate.save()
        return estimate

    @staticmethod
    def _calculate_estimate_totals(estimate: ClientEstimate) -> None:
        """Calculate computed financial fields on an estimate."""
        estimate.totaldeductions = (
            estimate.advanceamortization
            + estimate.otherdeductions
            + estimate.materialdeductions
            + estimate.guaranteefund
        )
        estimate.amountnotax = estimate.estimatedamount - estimate.totaldeductions
        estimate.taxamount = estimate.amountnotax * Decimal('0.16')
        estimate.totalinvoiced = estimate.amountnotax + estimate.taxamount - estimate.taxretained
        estimate.collectableamount = estimate.totalinvoiced
