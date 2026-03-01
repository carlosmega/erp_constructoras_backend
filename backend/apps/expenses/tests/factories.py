"""Factory Boy factories for Expense Management models."""

import factory
from decimal import Decimal
from datetime import date
from factory.django import DjangoModelFactory

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
from apps.users.tests.factories import SalespersonFactory
from apps.projects.tests.factories import ConstructionProjectFactory
from apps.budgets.tests.factories import ImputationPeriodFactory, ImputationCodeFactory


class ProjectExpenseFactory(DjangoModelFactory):
    """Base factory for creating ProjectExpense instances."""

    class Meta:
        model = ProjectExpense

    projectid = factory.SubFactory(ConstructionProjectFactory)
    periodid = factory.SubFactory(ImputationPeriodFactory)
    imputationcodeid = None
    classificationstatus = ClassificationStatusCode.PENDING
    documenttype = DocumentTypeCode.INVOICE
    supplierrfc = factory.Sequence(lambda n: f'RFC{n:010d}')
    suppliername = factory.Faker('company')
    invoiceuuid = None
    invoicefolio = factory.Sequence(lambda n: f'F-{n:06d}')
    invoicedate = factory.LazyFunction(date.today)
    expensesource = None
    payrolltype = None
    workername = None
    provisionstatus = None
    provisionconvertedfromid = None
    paymentmethod = ExpensePaymentMethodCode.BANK_TRANSFER
    paymentstatus = PaymentStatusCode.PENDING
    currency = CurrencyCode.MXN
    exchangerate = Decimal('1.0000')
    subtotal = Decimal('1000.00')
    taxamount = Decimal('160.00')
    retentionamount = Decimal('0.00')
    discountamount = Decimal('0.00')
    netamount = Decimal('1160.00')
    verificationstatus = VerificationStatusCode.PENDING
    verificationnotes = None
    verifiedby = None
    verifiedon = None
    statecode = ExpenseStateCode.ACTIVE
    notes = None
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class InvoiceExpenseFactory(ProjectExpenseFactory):
    """Factory for invoice-type expenses."""
    documenttype = DocumentTypeCode.INVOICE
    invoiceuuid = factory.Faker('uuid4')
    paymentmethod = ExpensePaymentMethodCode.BANK_TRANSFER


class PayrollExpenseFactory(ProjectExpenseFactory):
    """Factory for payroll-type expenses."""
    documenttype = DocumentTypeCode.PAYROLL
    payrolltype = PayrollTypeCode.WEEKLY
    workername = factory.Faker('name')
    supplierrfc = None
    suppliername = None
    invoiceuuid = None
    invoicefolio = None
    invoicedate = None


class ProvisionExpenseFactory(ProjectExpenseFactory):
    """Factory for provision-type expenses."""
    documenttype = DocumentTypeCode.PROVISION
    provisionstatus = ProvisionStatusCode.ACTIVE
    supplierrfc = None
    suppliername = None
    invoiceuuid = None
    invoicefolio = None


class ExpenseLineFactory(DjangoModelFactory):
    """Factory for creating ExpenseLine instances."""

    class Meta:
        model = ExpenseLine

    expenseid = factory.SubFactory(ProjectExpenseFactory)
    linenumber = factory.Sequence(lambda n: n + 1)
    description = factory.Faker('sentence')
    quantity = Decimal('10.0000')
    unitprice = Decimal('100.0000')
    subtotal = Decimal('1000.00')
    taxamount = Decimal('160.00')
    retentionamount = Decimal('0.00')
    discountamount = Decimal('0.00')
    netamount = Decimal('1160.00')


class ExpenseAttachmentFactory(DjangoModelFactory):
    """Factory for creating ExpenseAttachment instances."""

    class Meta:
        model = ExpenseAttachment

    expenseid = factory.SubFactory(ProjectExpenseFactory)
    filename = factory.Faker('file_name', extension='pdf')
    suggestedfilename = factory.LazyAttribute(lambda obj: f"expense_{obj.filename}")
    filetype = AttachmentTypeCode.PDF
    filesize = factory.Faker('random_int', min=1024, max=5242880)
    mimetype = 'application/pdf'
    storageurl = factory.Faker('url')


class ClassificationLogFactory(DjangoModelFactory):
    """Factory for creating ClassificationLog instances."""

    class Meta:
        model = ClassificationLog

    expenseid = factory.SubFactory(ProjectExpenseFactory)
    previousimputationcodeid = None
    previousimputationcode = None
    newimputationcodeid = factory.SubFactory(ImputationCodeFactory)
    newimputationcode = factory.LazyAttribute(
        lambda obj: obj.newimputationcodeid.code if obj.newimputationcodeid else None
    )
    action = ClassificationActionCode.ASSIGNED
    classifiedby = factory.SubFactory(SalespersonFactory)
    classifiedbyname = factory.LazyAttribute(lambda obj: obj.classifiedby.fullname)
    notes = None


class ClientEstimateFactory(DjangoModelFactory):
    """Factory for creating ClientEstimate instances."""

    class Meta:
        model = ClientEstimate

    projectid = factory.SubFactory(ConstructionProjectFactory)
    periodid = factory.SubFactory(ImputationPeriodFactory)
    estimatenumber = factory.Sequence(lambda n: n + 1)
    invoicenumber = factory.Sequence(lambda n: f'EST-{n:04d}')
    invoicedate = factory.LazyFunction(date.today)
    estimationperiod = None
    estimatetype = EstimateTypeCode.ESTIMATE
    estimatedamount = Decimal('100000.00')
    advanceamortization = Decimal('5000.00')
    otherdeductions = Decimal('2000.00')
    materialdeductions = Decimal('3000.00')
    guaranteefund = Decimal('5000.00')
    totaldeductions = Decimal('15000.00')
    amountnotax = Decimal('85000.00')
    taxamount = Decimal('13600.00')
    taxretained = Decimal('0.00')
    totalinvoiced = Decimal('98600.00')
    collectableamount = Decimal('98600.00')
    paymentstatus = PaymentStatusCode.PENDING
    paymentdate = None
    amountpaid = Decimal('0.00')
    statecode = EstimateStateCode.ACTIVE
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')
