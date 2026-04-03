"""Machinery management models for equipment tracking, insurance, and operational status."""

import uuid
from decimal import Decimal
from django.db import models
from core.models import AuditMixin


# ============================================================================
# Enums
# ============================================================================

class OwnershipTypeCode(models.IntegerChoices):
    PROPIO = 0, 'Propio'
    RENTADO_DE_TERCERO = 1, 'Rentado de Tercero'


class OperationalStatusCode(models.IntegerChoices):
    DISPONIBLE = 0, 'Disponible'
    ASIGNADO_A_PROYECTO = 1, 'Asignado a Proyecto'
    RENTADO_A_CLIENTE = 2, 'Rentado a Cliente'
    EN_MANTENIMIENTO = 3, 'En Mantenimiento'
    FUERA_DE_SERVICIO = 4, 'Fuera de Servicio'


class EquipmentStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    INACTIVE = 1, 'Inactive'


class InsuranceTypeCode(models.IntegerChoices):
    DANO_FISICO = 0, 'Daño Físico'
    RESPONSABILIDAD_CIVIL = 1, 'Responsabilidad Civil'
    TRANSPORTE = 2, 'Transporte'
    TODO_RIESGO = 3, 'Todo Riesgo'


class InsuranceStateCode(models.IntegerChoices):
    VIGENTE = 0, 'Vigente'
    VENCIDA = 1, 'Vencida'
    CANCELADA = 2, 'Cancelada'


class BillingModalityCode(models.IntegerChoices):
    DAYS = 0, 'Por Días'
    HOURS = 1, 'Por Horas'


class ContractStatusCode(models.IntegerChoices):
    ACTIVE = 0, 'Activo'
    COMPLETED = 1, 'Completado'
    CANCELLED = 2, 'Cancelado'


class EstimationStatusCode(models.IntegerChoices):
    DRAFT = 0, 'Borrador'
    REVIEWED = 1, 'Revisado'
    APPROVED = 2, 'Aprobado'
    INVOICED = 3, 'Facturado'


class ImputabilityCode(models.IntegerChoices):
    IMPUTABLE = 0, 'Imputable a Cliente'
    NOT_IMPUTABLE = 1, 'No Imputable a Cliente'


# ============================================================================
# Models
# ============================================================================

class EquipmentCategory(AuditMixin):
    """Category for grouping equipment types."""

    categoryid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='categoryid'
    )

    name = models.CharField(
        max_length=100,
        db_column='name'
    )

    code = models.CharField(
        max_length=10,
        unique=True,
        db_column='code'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    estimatedfuelconsumption = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        db_column='estimatedfuelconsumption',
        blank=True,
        null=True
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_equipment_categories',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'equipmentcategory'
        ordering = ['name']
        indexes = [
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class EquipmentBrand(AuditMixin):
    """Catalog of equipment brands/manufacturers."""

    brandid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='brandid'
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        db_column='name'
    )

    code = models.CharField(
        max_length=10,
        unique=True,
        db_column='code'
    )

    country = models.CharField(
        max_length=100,
        db_column='country',
        blank=True,
        null=True
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_equipment_brands',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'equipmentbrand'
        ordering = ['name']
        indexes = [
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return self.name


class EquipmentModel(AuditMixin):
    """Catalog of equipment models belonging to a brand."""

    modelid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='modelid'
    )

    brandid = models.ForeignKey(
        EquipmentBrand,
        on_delete=models.PROTECT,
        db_column='brandid',
        related_name='models'
    )

    name = models.CharField(
        max_length=100,
        db_column='name'
    )

    categoryid = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.SET_NULL,
        db_column='categoryid',
        related_name='models',
        blank=True,
        null=True
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_equipment_models',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'equipmentmodel'
        ordering = ['brandid', 'name']
        indexes = [
            models.Index(fields=['brandid', 'statecode']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['brandid', 'name'],
                name='unique_model_per_brand',
            ),
        ]

    def __str__(self):
        return f"{self.brandid.name} {self.name}"


class Equipment(AuditMixin):
    """Individual piece of equipment or machinery."""

    equipmentid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='equipmentid'
    )

    equipmentnumber = models.CharField(
        max_length=20,
        unique=True,
        db_column='equipmentnumber'
    )

    categoryid = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        db_column='categoryid',
        related_name='equipment'
    )

    ownershiptype = models.IntegerField(
        choices=OwnershipTypeCode.choices,
        db_column='ownershiptype'
    )

    brandid = models.ForeignKey(
        EquipmentBrand,
        on_delete=models.PROTECT,
        db_column='brandid',
        related_name='equipment',
        blank=True,
        null=True
    )

    modelid = models.ForeignKey(
        EquipmentModel,
        on_delete=models.PROTECT,
        db_column='modelid',
        related_name='equipment',
        blank=True,
        null=True
    )

    # Denormalized text from brandid/modelid for display/search convenience
    brand = models.CharField(
        max_length=100,
        db_column='brand',
        help_text='Denormalized from brandid for display'
    )

    model = models.CharField(
        max_length=100,
        db_column='model',
        help_text='Denormalized from modelid for display'
    )

    year = models.IntegerField(
        db_column='year'
    )

    serialnumber = models.CharField(
        max_length=100,
        db_column='serialnumber'
    )

    engineserialnumber = models.CharField(
        max_length=100,
        db_column='engineserialnumber',
        blank=True,
        null=True
    )

    capacity = models.CharField(
        max_length=50,
        db_column='capacity',
        blank=True,
        null=True
    )

    currenthourmeter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column='currenthourmeter'
    )

    operationalstatus = models.IntegerField(
        choices=OperationalStatusCode.choices,
        default=OperationalStatusCode.DISPONIBLE,
        db_column='operationalstatus'
    )

    currentprojectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.SET_NULL,
        db_column='currentprojectid',
        related_name='equipment',
        blank=True,
        null=True
    )

    acquisitioncost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='acquisitioncost',
        blank=True,
        null=True
    )

    purchasedate = models.DateField(
        db_column='purchasedate',
        blank=True,
        null=True
    )

    estimatedusefullifehours = models.IntegerField(
        db_column='estimatedusefullifehours',
        blank=True,
        null=True
    )

    salvagevalue = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='salvagevalue',
        blank=True,
        null=True
    )

    supplierid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        db_column='supplierid',
        related_name='supplied_equipment',
        blank=True,
        null=True
    )

    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_equipment',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'equipment'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['categoryid', 'statecode']),
            models.Index(fields=['operationalstatus']),
            models.Index(fields=['ownershiptype']),
            models.Index(fields=['brandid']),
        ]

    def __str__(self):
        return f"{self.equipmentnumber} - {self.brand} {self.model}"


class EquipmentInsurance(AuditMixin):
    """Insurance policy for a piece of equipment."""

    insuranceid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='insuranceid'
    )

    equipmentid = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        db_column='equipmentid',
        related_name='insurances'
    )

    insurancetype = models.IntegerField(
        choices=InsuranceTypeCode.choices,
        db_column='insurancetype'
    )

    insurancecompany = models.CharField(
        max_length=200,
        db_column='insurancecompany'
    )

    policynumber = models.CharField(
        max_length=50,
        db_column='policynumber'
    )

    startdate = models.DateField(
        db_column='startdate'
    )

    expirydate = models.DateField(
        db_column='expirydate'
    )

    annualpremium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column='annualpremium'
    )

    monthlypremium = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column='monthlypremium'
    )

    insuredamount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='insuredamount'
    )

    statecode = models.IntegerField(
        choices=InsuranceStateCode.choices,
        default=InsuranceStateCode.VIGENTE,
        db_column='statecode'
    )

    class Meta:
        db_table = 'equipmentinsurance'
        ordering = ['-startdate']
        indexes = [
            models.Index(fields=['equipmentid', 'statecode']),
        ]

    def __str__(self):
        return f"{self.policynumber} - {self.get_insurancetype_display()} ({self.equipmentid})"


class JustificationReason(AuditMixin):
    """Catalog of reasons for low hours (maps to Excel Auxiliar-HC)."""

    reasonid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='reasonid'
    )

    name = models.CharField(
        max_length=200,
        unique=True,
        db_column='name'
    )

    imputabilityvalue = models.IntegerField(
        db_column='imputabilityvalue',
        help_text='0=not imputable, 1=imputable'
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_justification_reasons',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'justificationreason'
        ordering = ['name']
        indexes = [
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return self.name


class RentalContract(AuditMixin):
    """Rental contract linking equipment to lessor, client, and project."""

    contractid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='contractid'
    )

    equipmentid = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        db_column='equipmentid',
        related_name='rentalcontracts'
    )

    lessorname = models.CharField(
        max_length=300,
        db_column='lessorname',
        help_text='Arrendador name'
    )

    economicnumber = models.CharField(
        max_length=50,
        db_column='economicnumber',
        help_text='No. Económico'
    )

    projectname = models.CharField(
        max_length=300,
        db_column='projectname',
        help_text='Obra name'
    )

    clientname = models.CharField(
        max_length=300,
        db_column='clientname',
        help_text='Client company name'
    )

    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.SET_NULL,
        db_column='projectid',
        related_name='rentalcontracts',
        blank=True,
        null=True
    )

    billingmodality = models.IntegerField(
        choices=BillingModalityCode.choices,
        db_column='billingmodality'
    )

    monthlyrate = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='monthlyrate'
    )

    basemeasurement = models.IntegerField(
        db_column='basemeasurement',
        help_text='Base: 30 for days, 200 for hours'
    )

    taxrate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0800'),
        db_column='taxrate'
    )

    arrivalfreightstatus = models.CharField(
        max_length=50,
        db_column='arrivalfreightstatus',
        blank=True,
        null=True
    )

    departurefreightstatus = models.CharField(
        max_length=50,
        db_column='departurefreightstatus',
        blank=True,
        null=True
    )

    startdate = models.DateField(
        db_column='startdate'
    )

    enddate = models.DateField(
        db_column='enddate',
        blank=True,
        null=True
    )

    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    statuscode = models.IntegerField(
        choices=ContractStatusCode.choices,
        default=ContractStatusCode.ACTIVE,
        db_column='statuscode'
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_rental_contracts',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'rentalcontract'
        ordering = ['-startdate']
        indexes = [
            models.Index(fields=['equipmentid', 'statecode']),
            models.Index(fields=['statuscode']),
        ]

    @property
    def unitprice(self):
        """Returns monthlyrate / basemeasurement, or 0 on division by zero."""
        if not self.basemeasurement:
            return Decimal('0')
        return (self.monthlyrate / self.basemeasurement).quantize(Decimal('0.01'))

    def __str__(self):
        return f"Contract {self.contractid} - {self.equipmentid}"


class DailyEquipmentLog(AuditMixin):
    """Daily operation log entry (maps to Excel BD-Conciliación rows)."""

    logid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='logid'
    )

    contractid = models.ForeignKey(
        RentalContract,
        on_delete=models.PROTECT,
        db_column='contractid',
        related_name='dailylogs'
    )

    equipmentid = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        db_column='equipmentid',
        related_name='dailylogs'
    )

    estimationnumber = models.IntegerField(
        db_column='estimationnumber',
        help_text='No. Estimación'
    )

    logdate = models.DateField(
        db_column='logdate'
    )

    sequencenumber = models.IntegerField(
        db_column='sequencenumber',
        help_text='Folio correlativo'
    )

    hourmeterstart = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column='hourmeterstart'
    )

    hourmeterend = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column='hourmeterend'
    )

    justificationreasonid = models.ForeignKey(
        JustificationReason,
        on_delete=models.SET_NULL,
        db_column='justificationreasonid',
        related_name='dailylogs',
        blank=True,
        null=True
    )

    authorizedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        db_column='authorizedby',
        related_name='authorized_logs',
        blank=True,
        null=True
    )

    comments = models.TextField(
        db_column='comments',
        blank=True,
        null=True
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_daily_logs',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'dailyequipmentlog'
        ordering = ['logdate', 'sequencenumber']
        indexes = [
            models.Index(fields=['contractid', 'estimationnumber']),
            models.Index(fields=['equipmentid', 'logdate']),
            models.Index(fields=['statecode']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['contractid', 'logdate'],
                name='unique_log_per_contract_per_day',
            ),
        ]

    @property
    def workedhours(self):
        """Hours worked = hourmeterend - hourmeterstart."""
        return self.hourmeterend - self.hourmeterstart

    @property
    def dayofweek(self):
        """Day of week as ISO integer (1=Mon, 7=Sun)."""
        return self.logdate.isoweekday()

    @property
    def indicator(self):
        """APPROVED if workedhours > 4, else REQUIRES_JUSTIFICATION."""
        if self.workedhours > 4:
            return 'APPROVED'
        return 'REQUIRES_JUSTIFICATION'

    @property
    def isimputable(self):
        """Imputable if any score >= 1: hours>4, reason.imputabilityvalue==1, or authorizedby set."""
        if self.workedhours > 4:
            return ImputabilityCode.IMPUTABLE
        if self.justificationreasonid and self.justificationreasonid.imputabilityvalue == 1:
            return ImputabilityCode.IMPUTABLE
        if self.authorizedby:
            return ImputabilityCode.IMPUTABLE
        return ImputabilityCode.NOT_IMPUTABLE

    def __str__(self):
        return f"Log {self.logdate} - {self.equipmentid}"


class BillingEstimation(AuditMixin):
    """Aggregated billing estimation (pre-invoice)."""

    estimationid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='estimationid'
    )

    contractid = models.ForeignKey(
        RentalContract,
        on_delete=models.PROTECT,
        db_column='contractid',
        related_name='estimations'
    )

    estimationnumber = models.IntegerField(
        db_column='estimationnumber'
    )

    periodstart = models.DateField(
        db_column='periodstart'
    )

    periodend = models.DateField(
        db_column='periodend'
    )

    totalhours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column='totalhours'
    )

    imputablehours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column='imputablehours'
    )

    nonimputablehours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        db_column='nonimputablehours'
    )

    totaldays = models.IntegerField(
        default=0,
        db_column='totaldays'
    )

    imputabledays = models.IntegerField(
        default=0,
        db_column='imputabledays'
    )

    nonimputabledays = models.IntegerField(
        default=0,
        db_column='nonimputabledays'
    )

    sundaycount = models.IntegerField(
        default=0,
        db_column='sundaycount'
    )

    measurement = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        db_column='measurement',
        help_text='Imputable days or hours'
    )

    unitprice = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='unitprice'
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='amount',
        help_text='measurement x unitprice'
    )

    advancepercentage = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        db_column='advancepercentage'
    )

    accumulatedmeasurement = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='accumulatedmeasurement'
    )

    accumulatedamount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='accumulatedamount'
    )

    taxamount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='taxamount'
    )

    totalamount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='totalamount'
    )

    conceptdescription = models.TextField(
        db_column='conceptdescription',
        blank=True,
        null=True
    )

    observations = models.TextField(
        db_column='observations',
        blank=True,
        null=True
    )

    statuscode = models.IntegerField(
        choices=EstimationStatusCode.choices,
        default=EstimationStatusCode.DRAFT,
        db_column='statuscode'
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_billing_estimations',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'billingestimation'
        ordering = ['contractid', 'estimationnumber']
        indexes = [
            models.Index(fields=['contractid', 'estimationnumber']),
            models.Index(fields=['statuscode']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['contractid', 'estimationnumber'],
                name='unique_estimation_per_contract',
            ),
        ]

    def __str__(self):
        return f"Estimation #{self.estimationnumber} - Contract {self.contractid}"


class EstimationDeduction(AuditMixin):
    """Deductions on estimations (maintenance costs etc.)."""

    deductionid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='deductionid'
    )

    estimationid = models.ForeignKey(
        BillingEstimation,
        on_delete=models.CASCADE,
        db_column='estimationid',
        related_name='deductions'
    )

    concept = models.CharField(
        max_length=500,
        db_column='concept'
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        db_column='amount',
        help_text='Negative value for deductions'
    )

    statecode = models.IntegerField(
        choices=EquipmentStateCode.choices,
        default=EquipmentStateCode.ACTIVE,
        db_column='statecode'
    )

    class Meta:
        db_table = 'estimationdeduction'
        ordering = ['estimationid', 'concept']
        indexes = [
            models.Index(fields=['estimationid']),
        ]

    def __str__(self):
        return f"{self.concept} ({self.amount})"
