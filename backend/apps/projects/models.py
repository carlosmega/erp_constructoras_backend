"""
Construction Project entity models.
Implements project management for construction projects including
zones, suppliers, and team members.
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from core.models import AuditMixin


# SAT RFC (Mexican fiscal ID).
# - Persona moral (empresa): 3 letras + 6 dígitos fecha + 3 alfanum homoclave = 12 chars
# - Persona física: 4 letras + 6 dígitos fecha + 3 alfanum homoclave = 13 chars
RFC_VALIDATOR = RegexValidator(
    regex=r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$',
    message='RFC must match SAT format (12-13 chars: letters + YYMMDD + 3 alphanum).',
)


# ============================================================================
# Enum Definitions
# ============================================================================

class ProjectStateCode(models.IntegerChoices):
    DRAFT = 0, 'Draft'
    ACTIVE = 1, 'Active'
    ON_HOLD = 2, 'On Hold'
    COMPLETED = 3, 'Completed'
    CANCELED = 4, 'Canceled'


class ProjectTypeCode(models.IntegerChoices):
    PUBLIC = 0, 'Public'
    PRIVATE = 1, 'Private'


class BiddingTypeCode(models.IntegerChoices):
    OPEN_BID = 0, 'Open Bid'
    INVITED_BID = 1, 'Invited Bid'
    DIRECT_AWARD = 2, 'Direct Award'


class PeriodTypeCode(models.IntegerChoices):
    WEEKLY = 0, 'Weekly'
    FORTNIGHTLY = 1, 'Fortnightly'


class EmailProtocolCode(models.IntegerChoices):
    IMAP = 0, 'IMAP'
    GRAPH_API = 1, 'Graph API'


class ProjectRoleCode(models.TextChoices):
    PROJECT_MANAGER = 'ProjectManager', 'Project Manager'
    ADMIN_ASSISTANT = 'AdminAssistant', 'Admin Assistant'
    PRODUCTION_MANAGER = 'ProductionManager', 'Production Manager'
    SITE_ENGINEER = 'SiteEngineer', 'Site Engineer'
    SAFETY_OFFICER = 'SafetyOfficer', 'Safety Officer'
    QUALITY_INSPECTOR = 'QualityInspector', 'Quality Inspector'
    CLIENT_CONTACT = 'ClientContact', 'Client Contact'
    OTHER = 'Other', 'Other'


class ZoneStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    INACTIVE = 1, 'Inactive'


class SupplierStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    INACTIVE = 1, 'Inactive'


# ============================================================================
# ConstructionProject Model
# ============================================================================

class ConstructionProject(AuditMixin):
    """Construction project entity."""

    # Primary Key
    projectid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='projectid'
    )

    # Project Information
    projectnumber = models.CharField(
        max_length=20,
        db_column='projectnumber',
        unique=True
    )

    name = models.CharField(
        max_length=300,
        db_column='name'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    # State Management
    statecode = models.IntegerField(
        choices=ProjectStateCode.choices,
        default=ProjectStateCode.DRAFT,
        db_column='statecode'
    )

    # Customer Reference
    accountid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.PROTECT,
        db_column='accountid',
        related_name='projects'
    )

    # Opportunity Reference (optional)
    opportunityid = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        db_column='opportunityid',
        blank=True,
        null=True,
        related_name='projects'
    )

    # Key Dates
    presentationdate = models.DateField(
        db_column='presentationdate',
        blank=True,
        null=True
    )

    awarddate = models.DateField(
        db_column='awarddate',
        blank=True,
        null=True
    )

    startdate = models.DateField(
        db_column='startdate',
        blank=True,
        null=True
    )

    contractenddate = models.DateField(
        db_column='contractenddate',
        blank=True,
        null=True
    )

    expectedenddate = models.DateField(
        db_column='expectedenddate',
        blank=True,
        null=True
    )

    durationmonths = models.IntegerField(
        db_column='durationmonths',
        validators=[MinValueValidator(1)]
    )

    # Project Classification
    projecttype = models.IntegerField(
        choices=ProjectTypeCode.choices,
        db_column='projecttype'
    )

    biddingtype = models.IntegerField(
        choices=BiddingTypeCode.choices,
        db_column='biddingtype'
    )

    # Contract Amounts
    contractamount_notax = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='contractamount_notax',
        validators=[MinValueValidator(0)]
    )

    contractamount_withtax = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='contractamount_withtax',
        validators=[MinValueValidator(0)]
    )

    # Advance Payment
    advancepayment_notax = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='advancepayment_notax',
        blank=True,
        null=True
    )

    advancepayment_withtax = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='advancepayment_withtax',
        blank=True,
        null=True
    )

    # Exchange Rate
    exchangerate_mxn_usd = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        db_column='exchangerate_mxn_usd',
        blank=True,
        null=True
    )

    # Advance Bond (flattened)
    advancebond_amount = models.DecimalField(
        max_digits=19, decimal_places=2, db_column='advancebond_amount', blank=True, null=True
    )
    advancebond_policycost = models.DecimalField(
        max_digits=19, decimal_places=2, db_column='advancebond_policycost', blank=True, null=True
    )
    advancebond_validitystartdate = models.DateField(
        db_column='advancebond_validitystartdate', blank=True, null=True
    )
    advancebond_validityenddate = models.DateField(
        db_column='advancebond_validityenddate', blank=True, null=True
    )

    # Completion Bond (flattened)
    completionbond_amount = models.DecimalField(
        max_digits=19, decimal_places=2, db_column='completionbond_amount', blank=True, null=True
    )
    completionbond_policycost = models.DecimalField(
        max_digits=19, decimal_places=2, db_column='completionbond_policycost', blank=True, null=True
    )
    completionbond_validitystartdate = models.DateField(
        db_column='completionbond_validitystartdate', blank=True, null=True
    )
    completionbond_validityenddate = models.DateField(
        db_column='completionbond_validityenddate', blank=True, null=True
    )

    # Defects Bond (flattened)
    defectsbond_amount = models.DecimalField(
        max_digits=19, decimal_places=2, db_column='defectsbond_amount', blank=True, null=True
    )
    defectsbond_policycost = models.DecimalField(
        max_digits=19, decimal_places=2, db_column='defectsbond_policycost', blank=True, null=True
    )
    defectsbond_validitystartdate = models.DateField(
        db_column='defectsbond_validitystartdate', blank=True, null=True
    )
    defectsbond_validityenddate = models.DateField(
        db_column='defectsbond_validityenddate', blank=True, null=True
    )

    # Email Configuration
    projectemail = models.EmailField(
        max_length=200,
        db_column='projectemail',
        blank=True,
        null=True
    )

    emailconfigured = models.BooleanField(
        default=False,
        db_column='emailconfigured'
    )

    emailprotocol = models.IntegerField(
        choices=EmailProtocolCode.choices,
        db_column='emailprotocol',
        blank=True,
        null=True
    )

    # Period Configuration
    periodtype = models.IntegerField(
        choices=PeriodTypeCode.choices,
        default=PeriodTypeCode.WEEKLY,
        db_column='periodtype'
    )

    # Alert Thresholds
    alertthreshold_warning = models.DecimalField(
        max_digits=5, decimal_places=2, db_column='alertthreshold_warning', blank=True, null=True
    )
    alertthreshold_critical = models.DecimalField(
        max_digits=5, decimal_places=2, db_column='alertthreshold_critical', blank=True, null=True
    )
    alertthreshold_exceeded = models.DecimalField(
        max_digits=5, decimal_places=2, db_column='alertthreshold_exceeded', blank=True, null=True
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_projects'
    )

    class Meta:
        db_table = 'constructionproject'
        verbose_name = 'Construction Project'
        verbose_name_plural = 'Construction Projects'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['projectnumber']),
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['accountid']),
            models.Index(fields=['startdate']),
        ]

    def __str__(self):
        return f"{self.projectnumber} - {self.name}"

    @property
    def is_active(self):
        return self.statecode == ProjectStateCode.ACTIVE

    @property
    def state_name(self):
        return ProjectStateCode(self.statecode).label

    @property
    def project_type_name(self):
        return ProjectTypeCode(self.projecttype).label

    @property
    def bidding_type_name(self):
        return BiddingTypeCode(self.biddingtype).label

    @property
    def period_type_name(self):
        return PeriodTypeCode(self.periodtype).label


# ============================================================================
# ProjectTeamMember Model
# ============================================================================

class ProjectTeamMember(AuditMixin):
    """Team member assigned to a construction project."""

    teammemberid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='teammemberid'
    )

    projectid = models.ForeignKey(
        ConstructionProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='teammembers'
    )

    systemuserid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='systemuserid',
        related_name='team_memberships'
    )

    role = models.CharField(
        max_length=50,
        choices=ProjectRoleCode.choices,
        db_column='role'
    )

    class Meta:
        db_table = 'projectteammember'
        verbose_name = 'Project Team Member'
        verbose_name_plural = 'Project Team Members'
        ordering = ['systemuserid__fullname']
        constraints = [
            models.UniqueConstraint(
                fields=['projectid', 'systemuserid'],
                name='unique_team_member_per_project'
            ),
        ]

    def __str__(self):
        return f"{self.systemuserid.fullname} ({self.get_role_display()})"


# ============================================================================
# ProjectZone Model
# ============================================================================

class ProjectZone(AuditMixin):
    """Zone/area within a construction project."""

    zoneid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='zoneid'
    )

    projectid = models.ForeignKey(
        ConstructionProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='zones'
    )

    name = models.CharField(
        max_length=200,
        db_column='name'
    )

    prefix = models.CharField(
        max_length=3,
        db_column='prefix'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    statecode = models.IntegerField(
        choices=ZoneStateCode.choices,
        default=ZoneStateCode.ACTIVE,
        db_column='statecode'
    )

    sortorder = models.IntegerField(
        default=0,
        db_column='sortorder'
    )

    class Meta:
        db_table = 'projectzone'
        verbose_name = 'Project Zone'
        verbose_name_plural = 'Project Zones'
        ordering = ['sortorder', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['projectid', 'prefix'],
                name='unique_zone_prefix_per_project'
            ),
        ]

    def __str__(self):
        return f"[{self.prefix}] {self.name}"


# ============================================================================
# ProjectSupplier Model
# ============================================================================

class ProjectSupplier(AuditMixin):
    """Supplier linked to a construction project."""

    projectsupplierid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='projectsupplierid'
    )

    projectid = models.ForeignKey(
        ConstructionProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='suppliers'
    )

    accountid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.PROTECT,
        db_column='accountid',
        related_name='project_suppliers'
    )

    suppliernumber = models.IntegerField(
        db_column='suppliernumber'
    )

    rfc = models.CharField(
        max_length=13,
        db_column='rfc',
        validators=[RFC_VALIDATOR],
    )

    businessname = models.CharField(
        max_length=300,
        db_column='businessname'
    )

    statecode = models.IntegerField(
        choices=SupplierStateCode.choices,
        default=SupplierStateCode.ACTIVE,
        db_column='statecode'
    )

    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'projectsupplier'
        verbose_name = 'Project Supplier'
        verbose_name_plural = 'Project Suppliers'
        ordering = ['suppliernumber']
        constraints = [
            models.UniqueConstraint(
                fields=['projectid', 'rfc'],
                name='unique_supplier_rfc_per_project'
            ),
        ]

    def __str__(self):
        return f"#{self.suppliernumber} - {self.businessname}"
