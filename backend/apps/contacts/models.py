"""
Contact entity model.
Implements Microsoft Dynamics 365 CDS Contact entity (B2C individuals).
Phase 7 Implementation
"""

import uuid
from django.db import models
from core.models import AuditMixin


class ContactStateCode(models.IntegerChoices):
    """Contact state code."""
    ACTIVE = 0, 'Active'
    INACTIVE = 1, 'Inactive'


class ContactStatusCode(models.IntegerChoices):
    """Contact status code."""
    ACTIVE = 1, 'Active'
    INACTIVE = 2, 'Inactive'


class Contact(AuditMixin):
    """Contact entity (B2C individual/person)."""

    # Primary Key
    contactid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='contactid'
    )

    # Personal Information
    firstname = models.CharField(
        max_length=50,
        db_column='firstname',
        blank=True,
        null=True
    )

    lastname = models.CharField(
        max_length=50,
        db_column='lastname'
    )

    fullname = models.CharField(
        max_length=160,
        db_column='fullname',
        blank=True
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
        verbose_name='Business Phone'
    )

    mobilephone = models.CharField(
        max_length=50,
        db_column='mobilephone',
        blank=True,
        null=True
    )

    # Business Information
    jobtitle = models.CharField(
        max_length=100,
        db_column='jobtitle',
        blank=True,
        null=True
    )

    # Parent Account (company this contact works for)
    parentcustomerid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        db_column='parentcustomerid',
        blank=True,
        null=True,
        related_name='contacts',
        verbose_name='Company Name'
    )

    # Address Information
    address1_line1 = models.CharField(
        max_length=250,
        db_column='address1_line1',
        blank=True,
        null=True,
        verbose_name='Street 1'
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

    # Additional Information
    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    # State Management
    statecode = models.IntegerField(
        choices=ContactStateCode.choices,
        default=ContactStateCode.ACTIVE,
        db_column='statecode'
    )

    statuscode = models.IntegerField(
        choices=ContactStatusCode.choices,
        default=ContactStatusCode.ACTIVE,
        db_column='statuscode'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_contacts'
    )

    class Meta:
        db_table = 'contact'
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['lastname', 'firstname']),
            models.Index(fields=['fullname']),
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['emailaddress1']),
            models.Index(fields=['parentcustomerid']),
        ]

    def __str__(self):
        return self.fullname or f"{self.firstname or ''} {self.lastname}".strip()

    def save(self, *args, **kwargs):
        """Override save to auto-compute fullname."""
        # Always recompute fullname based on firstname and lastname
        parts = []
        if self.firstname:
            parts.append(self.firstname)
        if self.lastname:
            parts.append(self.lastname)
        self.fullname = ' '.join(parts) if parts else ''

        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.statecode == ContactStateCode.ACTIVE

    @property
    def state_name(self):
        return ContactStateCode(self.statecode).label

    @property
    def status_name(self):
        return ContactStatusCode(self.statuscode).label

    @property
    def company_name(self):
        """Get parent account name."""
        return self.parentcustomerid.name if self.parentcustomerid else None
