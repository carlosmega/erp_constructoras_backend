# Data Model: CRM Backend Foundation

**Feature**: 001-crm-backend-foundation
**Date**: 2025-11-27
**Status**: Design Complete

## Overview

This document defines the data entities for the CRM backend foundation, following Microsoft Dynamics 365 Common Data Service patterns. All entities use UUID primary keys, CDS naming conventions, and the four-layer architecture pattern.

---

## Base Classes

### AuditMixin (Abstract Base Class)

**Purpose**: Provides audit trail fields for all business entities

**Location**: `core/models.py`

**Fields**:

| Field Name | Type | Constraints | CDS Column | Description |
|------------|------|-------------|------------|-------------|
| createdon | DateTimeField | NOT NULL, auto_now_add | `createdon` | Timestamp when record was created |
| modifiedon | DateTimeField | NOT NULL, auto_now | `modifiedon` | Timestamp when record was last modified |
| createdby | ForeignKey(SystemUser) | NULL allowed, SET_NULL on delete | `createdby` | User who created the record |
| modifiedby | ForeignKey(SystemUser) | NULL allowed, SET_NULL on delete | `modifiedby` | User who last modified the record |

**Indexes**:
- No explicit indexes (used as mixin)

**Notes**:
- Abstract model (not a database table)
- `createdby` and `modifiedby` allow NULL for system-generated records or initial bootstrap
- Uses related_name pattern `%(class)s_created` and `%(class)s_modified` to avoid conflicts

**Django Implementation**:
```python
# core/models.py
from django.db import models
import uuid

class AuditMixin(models.Model):
    """Abstract base class for audit trail fields"""
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )
    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )
    createdby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        db_column='createdby'
    )
    modifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_modified',
        db_column='modifiedby'
    )

    class Meta:
        abstract = True
```

---

## Core Entities

### SecurityRole

**Purpose**: Defines predefined user roles with permission levels

**Location**: `apps/users/models.py`

**Primary Key**: `securityroleid` (UUID)

**Fields**:

| Field Name | Type | Constraints | CDS Column | Description |
|------------|------|-------------|------------|-------------|
| securityroleid | UUIDField | PRIMARY KEY, default=uuid4 | `securityroleid` | Unique identifier for the role |
| name | CharField(100) | NOT NULL, unique | `name` | Role display name (e.g., "System Administrator") |
| description | TextField | NULL allowed | `description` | Description of role purpose and permissions |

**Indexes**:
- Primary key (automatic)
- Unique index on `name`

**Predefined Roles** (seeded via migration):
1. `System Administrator` - Full access to all entities and operations
2. `Sales Manager` - Manage team records, view all opportunities
3. `Salesperson` - Manage own records only
4. `Marketing User` - Manage campaigns and leads
5. `Read-Only User` - View-only access

**State/Status**: Not applicable (roles are static configuration)

**Relationships**:
- One-to-Many with SystemUser (one role can be assigned to many users)

**Validation Rules**:
- Role names cannot be modified after creation (enforced in service layer)
- Only 5 predefined roles exist (no custom roles in MVP)

**Django Implementation**:
```python
class SecurityRole(models.Model):
    """Predefined security roles for RBAC"""
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
```

**Data Migration** (seed roles):
```python
# apps/users/migrations/0002_seed_roles.py
from django.db import migrations
import uuid

def seed_roles(apps, schema_editor):
    SecurityRole = apps.get_model('users', 'SecurityRole')
    roles = [
        {
            'securityroleid': uuid.uuid4(),
            'name': 'System Administrator',
            'description': 'Full access to all entities and operations'
        },
        {
            'securityroleid': uuid.uuid4(),
            'name': 'Sales Manager',
            'description': 'Manage team records and view all opportunities'
        },
        {
            'securityroleid': uuid.uuid4(),
            'name': 'Salesperson',
            'description': 'Manage own records only'
        },
        {
            'securityroleid': uuid.uuid4(),
            'name': 'Marketing User',
            'description': 'Manage campaigns and leads, read-only on opportunities'
        },
        {
            'securityroleid': uuid.uuid4(),
            'name': 'Read-Only User',
            'description': 'View-only access to all entities'
        },
    ]
    SecurityRole.objects.bulk_create([SecurityRole(**role) for role in roles])

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed_roles, reverse_code=migrations.RunPython.noop),
    ]
```

---

### SystemUser

**Purpose**: User accounts for CRM system access with authentication and role assignment

**Location**: `apps/users/models.py`

**Primary Key**: `systemuserid` (UUID)

**Extends**: Django's AbstractBaseUser, AuditMixin

**Fields**:

| Field Name | Type | Constraints | CDS Column | Description |
|------------|------|-------------|------------|-------------|
| systemuserid | UUIDField | PRIMARY KEY, default=uuid4 | `systemuserid` | Unique identifier for the user |
| emailaddress1 | EmailField(100) | NOT NULL, unique | `emailaddress1` | Email address (used for login) |
| fullname | CharField(200) | NOT NULL | `fullname` | User's full display name |
| password | CharField(128) | NOT NULL (hashed) | `password` | Hashed password (Django handles hashing) |
| isdisabled | BooleanField | NOT NULL, default=False | `isdisabled` | Whether account is active (False=active, True=disabled) |
| failedloginattempts | IntegerField | NOT NULL, default=0 | `failedloginattempts` | Count of consecutive failed login attempts |
| lastlogindate | DateTimeField | NULL allowed | `lastlogindate` | Timestamp of last successful login |
| securityroleid | ForeignKey(SecurityRole) | NOT NULL | `securityroleid` | Assigned security role |
| createdon | DateTimeField | (from AuditMixin) | `createdon` | Creation timestamp |
| modifiedon | DateTimeField | (from AuditMixin) | `modifiedon` | Last modification timestamp |
| createdby | ForeignKey(SystemUser) | (from AuditMixin) | `createdby` | Creator user |
| modifiedby | ForeignKey(SystemUser) | (from AuditMixin) | `modifiedby` | Last modifier user |

**Indexes**:
- Primary key on `systemuserid` (automatic)
- Unique index on `emailaddress1`
- Index on `securityroleid` (foreign key)
- Composite index on `[isdisabled, securityroleid]` for user list queries

**State/Status**:
- Uses `isdisabled` boolean instead of statecode/statuscode (simpler for users)
- False = Active user
- True = Disabled user (soft delete)

**Relationships**:
- Many-to-One with SecurityRole (many users can have same role)
- Self-referential FK for `createdby` and `modifiedby` (audit trail)
- One-to-Many with all business entities via `ownerid` (future)

**Validation Rules**:
- Email must be valid format and unique
- Password must meet complexity requirements (enforced via AUTH_PASSWORD_VALIDATORS)
- `failedloginattempts` resets to 0 on successful login
- Account locked if `failedloginattempts >= 3` (checked in service layer)
- `fullname` must not be empty

**Computed Properties**:
- `is_active`: Returns NOT isdisabled (for Django auth compatibility)
- `is_locked`: Returns failedloginattempts >= 3

**Django Implementation**:
```python
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
import uuid

class SystemUserManager(BaseUserManager):
    """Custom manager for SystemUser"""
    def create_user(self, emailaddress1, fullname, password=None, **extra_fields):
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
        # Get or create System Administrator role
        admin_role = SecurityRole.objects.get(name='System Administrator')
        extra_fields.setdefault('securityroleid', admin_role)
        extra_fields.setdefault('isdisabled', False)
        return self.create_user(emailaddress1, fullname, password, **extra_fields)

class SystemUser(AbstractBaseUser, AuditMixin):
    """User account for CRM system access"""
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
    password = models.CharField(
        max_length=128,
        db_column='password'
    )
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
        """Django auth compatibility"""
        return not self.isdisabled

    @property
    def is_locked(self):
        """Check if account is locked due to failed login attempts"""
        return self.failedloginattempts >= 3

    @property
    def role_name(self):
        """Convenience property for role name"""
        return self.securityroleid.name if self.securityroleid else None
```

---

## Database Schema Diagram

```
┌─────────────────────────────────┐
│       SecurityRole              │
├─────────────────────────────────┤
│ PK securityroleid (UUID)        │
│    name (VARCHAR, UNIQUE)       │
│    description (TEXT)           │
└─────────────────────────────────┘
                │
                │ 1:N
                │
┌─────────────────────────────────┐
│       SystemUser                │
├─────────────────────────────────┤
│ PK systemuserid (UUID)          │
│ UK emailaddress1 (VARCHAR)      │
│    fullname (VARCHAR)           │
│    password (VARCHAR)           │
│    isdisabled (BOOLEAN)         │
│    failedloginattempts (INT)    │
│    lastlogindate (TIMESTAMP)    │
│ FK securityroleid → SecurityRole│
│    createdon (TIMESTAMP)        │
│    modifiedon (TIMESTAMP)       │
│ FK createdby → SystemUser       │
│ FK modifiedby → SystemUser      │
└─────────────────────────────────┘
```

---

## Query Optimization Strategies

### Common Queries and Optimizations

1. **List active users by role**
   ```python
   # Optimized with composite index [isdisabled, securityroleid]
   SystemUser.objects.filter(
       isdisabled=False,
       securityroleid__name='Salesperson'
   ).select_related('securityroleid', 'createdby', 'modifiedby')
   ```

2. **Get user with full audit trail**
   ```python
   # Use select_related to prevent N+1 queries
   SystemUser.objects.select_related(
       'securityroleid',
       'createdby',
       'modifiedby'
   ).get(systemuserid=user_id)
   ```

3. **Count users by role**
   ```python
   # Uses index on securityroleid
   SecurityRole.objects.annotate(
       user_count=Count('systemuser')
   )
   ```

### Index Coverage

| Query Pattern | Indexes Used |
|---------------|--------------|
| Login (email lookup) | Unique index on `emailaddress1` |
| List active users | Composite index `[isdisabled, securityroleid]` |
| List users by role | FK index on `securityroleid` |
| Audit trail queries | FK indexes on `createdby`, `modifiedby` |

---

## Migration Order

1. **0001_initial.py**: Create SecurityRole and SystemUser tables
2. **0002_seed_roles.py**: Insert 5 predefined security roles
3. **0003_create_superuser.py**: Create initial admin user (development only)

---

## Next Steps

- API contracts defined in `contracts/` directory
- Service layer implementation in `apps/users/services.py`
- Router implementation in `apps/users/routers.py`
- Schemas (DTOs) in `apps/users/schemas.py`
