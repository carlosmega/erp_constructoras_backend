"""
Account entity model.
Implements Microsoft Dynamics 365 CDS Account entity (B2B companies).
Phase 7 Implementation
"""

import uuid
from django.db import models
from core.models import AuditMixin


class CustomerTypeCode(models.IntegerChoices):
    """Customer type code following CDS pattern."""
    CUSTOMER = 1, 'Customer'
    SUPPLIER = 2, 'Supplier'
    BOTH = 3, 'Both'


class AccountStateCode(models.IntegerChoices):
    """Account state code."""
    ACTIVE = 0, 'Active'
    INACTIVE = 1, 'Inactive'


class AccountStatusCode(models.IntegerChoices):
    """Account status code."""
    ACTIVE = 1, 'Active'
    INACTIVE = 2, 'Inactive'


class Account(AuditMixin):
    """Account entity (B2B company/organization)."""

    # Primary Key
    accountid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='accountid'
    )

    # Account Information
    name = models.CharField(
        max_length=160,
        db_column='name'
    )

    accountnumber = models.CharField(
        max_length=20,
        db_column='accountnumber',
        blank=True,
        null=True,
        unique=True
    )

    # Contact Information
    emailaddress1 = models.EmailField(
        max_length=100,
        db_column='emailaddress1',
        blank=True,
        null=True
    )

    telephone1 = models.CharField(
        max_length=50,
        db_column='telephone1',
        blank=True,
        null=True,
        verbose_name='Main Phone'
    )

    telephone2 = models.CharField(
        max_length=50,
        db_column='telephone2',
        blank=True,
        null=True,
        verbose_name='Other Phone'
    )

    fax = models.CharField(
        max_length=50,
        db_column='fax',
        blank=True,
        null=True,
        verbose_name='Fax'
    )

    websiteurl = models.URLField(
        max_length=200,
        db_column='websiteurl',
        blank=True,
        null=True,
        verbose_name='Website'
    )

    # Address Information
    address1_line1 = models.CharField(
        max_length=250,
        db_column='address1_line1',
        blank=True,
        null=True,
        verbose_name='Street 1'
    )

    address1_line2 = models.CharField(
        max_length=250,
        db_column='address1_line2',
        blank=True,
        null=True,
        verbose_name='Street 2'
    )

    address1_city = models.CharField(
        max_length=80,
        db_column='address1_city',
        blank=True,
        null=True,
        verbose_name='City'
    )

    address1_stateorprovince = models.CharField(
        max_length=50,
        db_column='address1_stateorprovince',
        blank=True,
        null=True,
        verbose_name='State/Province'
    )

    address1_postalcode = models.CharField(
        max_length=20,
        db_column='address1_postalcode',
        blank=True,
        null=True,
        verbose_name='ZIP/Postal Code'
    )

    address1_country = models.CharField(
        max_length=80,
        db_column='address1_country',
        blank=True,
        null=True,
        verbose_name='Country/Region'
    )

    # Business Information
    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    revenue = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='revenue',
        blank=True,
        null=True,
        verbose_name='Annual Revenue'
    )

    numberofemployees = models.IntegerField(
        db_column='numberofemployees',
        blank=True,
        null=True,
        verbose_name='Number of Employees'
    )

    customertypecode = models.IntegerField(
        choices=CustomerTypeCode.choices,
        default=CustomerTypeCode.CUSTOMER,
        db_column='customertypecode'
    )

    industrycode = models.IntegerField(
        db_column='industrycode',
        blank=True,
        null=True,
        verbose_name='Industry'
    )

    accountcategorycode = models.IntegerField(
        db_column='accountcategorycode',
        blank=True,
        null=True,
        verbose_name='Category'
    )

    # Hierarchy
    parentaccountid = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        db_column='parentaccountid',
        blank=True,
        null=True,
        related_name='child_accounts',
        verbose_name='Parent Account'
    )

    # Relationships
    primarycontactid = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        db_column='primarycontactid',
        blank=True,
        null=True,
        related_name='primary_account',
        verbose_name='Primary Contact'
    )

    # Credit Information
    creditonhold = models.BooleanField(
        db_column='creditonhold',
        default=False,
        verbose_name='Credit On Hold'
    )

    creditlimit = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='creditlimit',
        blank=True,
        null=True,
        verbose_name='Credit Limit'
    )

    # State Management
    statecode = models.IntegerField(
        choices=AccountStateCode.choices,
        default=AccountStateCode.ACTIVE,
        db_column='statecode'
    )

    statuscode = models.IntegerField(
        choices=AccountStatusCode.choices,
        default=AccountStatusCode.ACTIVE,
        db_column='statuscode'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_accounts'
    )

    class Meta:
        db_table = 'account'
        verbose_name = 'Account'
        verbose_name_plural = 'Accounts'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['accountnumber']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.statecode == AccountStateCode.ACTIVE

    @property
    def state_name(self):
        return AccountStateCode(self.statecode).label

    @property
    def status_name(self):
        return AccountStatusCode(self.statuscode).label
