"""Factory Boy factories for Invoice Inbox models."""

import factory
from decimal import Decimal
from factory.django import DjangoModelFactory

from apps.invoiceinbox.models import (
    IncomingInvoice,
    IncomingInvoiceStateCode,
    InboxSyncLog,
    SyncStatusCode,
    SyncTriggerCode,
)
from apps.users.tests.factories import SalespersonFactory
from apps.projects.tests.factories import ConstructionProjectFactory


class IncomingInvoiceFactory(DjangoModelFactory):
    """Base factory for creating IncomingInvoice instances."""

    class Meta:
        model = IncomingInvoice

    projectid = factory.SubFactory(ConstructionProjectFactory)
    imputationcodeid = None
    statecode = IncomingInvoiceStateCode.DRAFT

    # Email source metadata
    emailmessageid = factory.Sequence(lambda n: f'<msg-{n}@mail.example.com>')
    emailsubject = factory.Faker('sentence')
    emailfrom = factory.Faker('email')
    emailreceivedon = factory.Faker('date_time_this_year')
    graphmessageid = factory.Sequence(lambda n: f'graph-msg-{n}')

    # CFDI parsed data
    cfdiversion = '4.0'
    uuid = factory.Faker('uuid4')
    serie = 'A'
    folio = factory.Sequence(lambda n: f'{n + 1:05d}')
    fecha = factory.Faker('date_time_this_year')
    fechatimbrado = factory.Faker('date_time_this_year')

    # Emisor (supplier)
    emisorrfc = factory.Sequence(lambda n: f'XAXX{n:06d}000')
    emisornombre = factory.Faker('company')
    emisorregimenfiscal = '601'

    # Receptor (company)
    receptorrfc = 'XEXX010101000'
    receptornombre = 'ConstruPro SA de CV'
    receptorusocfdi = 'G03'

    # Amounts
    moneda = 'MXN'
    tipocambio = Decimal('1.0000')
    subtotal = Decimal('10000.00')
    descuento = Decimal('0.00')
    totalimpuestostrasladados = Decimal('1600.00')
    totalimpuestosretenidos = Decimal('0.00')
    total = Decimal('11600.00')

    # Payment info
    formapago = '03'
    metodopago = 'PUE'

    # Conceptos
    conceptosjson = factory.LazyFunction(lambda: [
        {
            'claveprodserv': '80101500',
            'cantidad': '1',
            'claveunidad': 'E48',
            'unidad': 'Servicio',
            'descripcion': 'Servicio de consultoria',
            'valorunitario': '10000.00',
            'importe': '10000.00',
        }
    ])

    # File references
    xmlfile = None
    xmlfilename = None
    xmlfilesize = 0
    pdffile = None
    pdffilename = None
    pdffilesize = 0

    # Links
    linkedexpenseid = None
    suggestedexpenseid = None
    matchtype = None
    matchconfidence = 0

    # Processing metadata
    parseerrors = None
    rejectionnotes = None
    classificationnotes = None

    # Audit
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


class ClassifiedInvoiceFactory(IncomingInvoiceFactory):
    """Factory for classified incoming invoices."""
    statecode = IncomingInvoiceStateCode.CLASSIFIED


class RejectedInvoiceFactory(IncomingInvoiceFactory):
    """Factory for rejected incoming invoices."""
    statecode = IncomingInvoiceStateCode.REJECTED
    rejectionnotes = 'Duplicate invoice'


class InboxSyncLogFactory(DjangoModelFactory):
    """Factory for creating InboxSyncLog instances."""

    class Meta:
        model = InboxSyncLog

    projectid = factory.SubFactory(ConstructionProjectFactory)
    syncstatus = SyncStatusCode.SUCCESS
    triggeredby = SyncTriggerCode.MANUAL
    triggeredbyuserid = factory.SubFactory(SalespersonFactory)

    totalemailsfetched = factory.Faker('random_int', min=1, max=50)
    newxmlattachments = factory.Faker('random_int', min=0, max=20)
    newpdfattachments = factory.Faker('random_int', min=0, max=20)
    duplicatesskipped = factory.Faker('random_int', min=0, max=10)
    errorscount = 0
    errorsdetail = factory.LazyFunction(list)

    completedon = factory.Faker('date_time_this_year')
