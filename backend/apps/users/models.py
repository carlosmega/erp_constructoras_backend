"""
User management models for CRM Backend Foundation.

Implements SystemUser and SecurityRole entities following Dynamics CDS patterns.

Phase 3 Implementation (User Story 1)
Tasks T024-T029: SecurityRole and SystemUser models
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from core.models import AuditMixin
import uuid


class SecurityRole(models.Model):
    """
    Predefined security roles for RBAC.

    CDS Entity: securityrole
    Primary Key: securityroleid (UUID)
    """
    securityroleid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='securityroleid'
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        db_column='name'
    )
    description = models.TextField(
        null=True,
        blank=True,
        db_column='description'
    )

    class Meta:
        db_table = 'securityrole'
        ordering = ['name']
        verbose_name = 'Security Role'
        verbose_name_plural = 'Security Roles'

    def __str__(self):
        return self.name


class SystemUserManager(BaseUserManager):
    """
    Custom manager for SystemUser model.

    Provides create_user() and create_superuser() methods for Django auth.
    """

    def create_user(self, emailaddress1, fullname, password=None, **extra_fields):
        """
        Create and save a SystemUser with the given email, full name, and password.
        """
        if not emailaddress1:
            raise ValueError('Email address is required')
        if not fullname:
            raise ValueError('Full name is required')

        email = self.normalize_email(emailaddress1)
        user = self.model(
            emailaddress1=email,
            fullname=fullname,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, emailaddress1, fullname, password=None, **extra_fields):
        """
        Create and save a superuser with System Administrator role.
        """
        # Get or create System Administrator role
        try:
            admin_role = SecurityRole.objects.get(name='System Administrator')
        except SecurityRole.DoesNotExist:
            # If roles haven't been seeded yet, create the admin role
            admin_role = SecurityRole.objects.create(
                name='System Administrator',
                description='Full access to all entities and operations'
            )

        extra_fields.setdefault('securityroleid', admin_role)
        extra_fields.setdefault('isdisabled', False)

        return self.create_user(emailaddress1, fullname, password, **extra_fields)


class SystemUser(AbstractBaseUser, AuditMixin):
    """
    User account for CRM system access.

    CDS Entity: systemuser
    Primary Key: systemuserid (UUID)
    Username Field: emailaddress1

    Extends AbstractBaseUser for Django authentication and AuditMixin for audit trail.
    """
    systemuserid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='systemuserid'
    )
    emailaddress1 = models.EmailField(
        max_length=100,
        unique=True,
        db_column='emailaddress1'
    )
    fullname = models.CharField(
        max_length=200,
        db_column='fullname'
    )
    # password field inherited from AbstractBaseUser
    isdisabled = models.BooleanField(
        default=False,
        db_column='isdisabled'
    )
    failedloginattempts = models.IntegerField(
        default=0,
        db_column='failedloginattempts'
    )
    lastlogindate = models.DateTimeField(
        null=True,
        blank=True,
        db_column='lastlogindate'
    )
    securityroleid = models.ForeignKey(
        SecurityRole,
        on_delete=models.PROTECT,  # Cannot delete role if users assigned
        db_column='securityroleid'
    )

    objects = SystemUserManager()

    USERNAME_FIELD = 'emailaddress1'
    REQUIRED_FIELDS = ['fullname']

    class Meta:
        db_table = 'systemuser'
        ordering = ['fullname']
        indexes = [
            models.Index(fields=['isdisabled', 'securityroleid']),
        ]
        verbose_name = 'System User'
        verbose_name_plural = 'System Users'

    def __str__(self):
        return f"{self.fullname} ({self.emailaddress1})"

    @property
    def is_active(self):
        """
        Django auth compatibility property.
        Returns True if user is not disabled.
        """
        return not self.isdisabled

    @property
    def is_locked(self):
        """
        Check if account is locked due to failed login attempts.
        Account is locked after 3 or more failed attempts.
        """
        return self.failedloginattempts >= 3

    @property
    def role_name(self):
        """
        Convenience property to get the role name.
        """
        return self.securityroleid.name if self.securityroleid else None

    @property
    def is_staff(self):
        """
        Django admin compatibility.
        Allow System Administrators to access admin panel.
        """
        return self.securityroleid and self.securityroleid.name == 'System Administrator'

    @property
    def is_superuser(self):
        """
        Django admin compatibility.
        System Administrators are superusers.
        """
        return self.securityroleid and self.securityroleid.name == 'System Administrator'

    def has_perm(self, perm, obj=None):
        """
        Django permission check.
        System Administrators have all permissions.
        """
        return self.is_superuser

    def has_module_perms(self, app_label):
        """
        Django permission check for app access.
        System Administrators have access to all apps.
        """
        return self.is_superuser
