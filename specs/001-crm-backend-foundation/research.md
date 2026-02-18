# Research: CRM Backend Foundation

**Feature**: 001-crm-backend-foundation
**Date**: 2025-11-27
**Status**: Complete

## Overview

This document consolidates research findings for implementing the CRM backend foundation using Django 5.0+, Django Ninja, and PostgreSQL. All decisions align with the project constitution and Microsoft Dynamics 365 CDS patterns.

---

## 1. Django 5.0+ Authentication Patterns

### Decision: Extend Django's Built-in Authentication

**Chosen Approach**: Extend `django.contrib.auth` with custom user model

**Rationale**:
- Django's auth system is battle-tested for security (password hashing, session management, CSRF protection)
- Custom user model allows UUID primary keys and CDS field naming
- Leverages existing Django session framework for 30-minute timeout requirement
- Integrates seamlessly with Django admin for initial user management
- Django Ninja has built-in support for Django auth decorators

**Implementation Strategy**:
```python
# apps/users/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

class SystemUser(AbstractBaseUser):
    systemuserid = models.UUIDField(primary_key=True, default=uuid.uuid4)
    emailaddress1 = models.EmailField(unique=True, db_column='emailaddress1')
    fullname = models.CharField(max_length=200, db_column='fullname')
    # ... additional fields

    USERNAME_FIELD = 'emailaddress1'
```

**Alternatives Considered**:
- **JWT tokens**: Rejected - Adds complexity, harder to invalidate sessions, stateless nature conflicts with session timeout requirement
- **OAuth2**: Rejected for MVP - Third-party dependency, overkill for internal CRM users
- **Custom from scratch**: Rejected - Security risks, reinventing the wheel

**Security Features Included**:
- PBKDF2 password hashing (Django default, NIST-approved)
- Session-based authentication with CSRF protection
- Configurable session timeout via `SESSION_COOKIE_AGE = 1800` (30 minutes)
- Account lockout via custom authentication backend (tracking failed attempts)
- Secure password validation rules via `AUTH_PASSWORD_VALIDATORS`

**References**:
- Django 5.0 Authentication: https://docs.djangoproject.com/en/5.0/topics/auth/
- Custom User Models: https://docs.djangoproject.com/en/5.0/topics/auth/customizing/

---

## 2. Django Ninja Best Practices

### Decision: Schema-First API Design with Django Ninja

**Chosen Approach**: Use Django Ninja for type-safe REST API with automatic OpenAPI docs

**Rationale**:
- Type-safe schemas with Python 3.11 type hints (constitution requirement)
- Automatic OpenAPI/Swagger documentation generation
- Faster than Django REST Framework (async support, less overhead)
- Clean separation between models (ORM) and schemas (DTOs)
- Built-in validation using Pydantic
- Native support for Django auth and permissions

**Implementation Pattern**:

```python
# apps/users/schemas.py
from ninja import Schema, ModelSchema
from typing import Optional
import uuid

class UserSchema(ModelSchema):
    """Full user representation (read)"""
    class Config:
        model = SystemUser
        model_fields = ['systemuserid', 'emailaddress1', 'fullname', 'isdisabled', 'createdon']

class CreateUserDto(Schema):
    """User creation payload (write)"""
    emailaddress1: str
    fullname: str
    password: str
    securityroleid: uuid.UUID

class UpdateUserDto(Schema):
    """User update payload (partial write)"""
    fullname: Optional[str] = None
    isdisabled: Optional[bool] = None
```

**Router Pattern**:
```python
# apps/users/routers.py
from ninja import Router
from apps.users.services import UserService

router = Router(tags=["Users"])

@router.get("/", response=List[UserSchema])
def list_users(request, role: Optional[str] = None):
    return UserService.list_users(request.user, role_filter=role)

@router.post("/", response=UserSchema)
def create_user(request, payload: CreateUserDto):
    return UserService.create_user(request.user, payload)
```

**Error Handling**:
- Use Django Ninja's built-in exception handling
- Custom exception classes in `core/exceptions.py`
- Consistent error response format with HTTP status codes

**Alternatives Considered**:
- **Django REST Framework**: Rejected - Slower, more boilerplate, less type-safe
- **FastAPI**: Rejected - Would require replacing Django entirely, loses Django ORM and admin
- **Plain Django views**: Rejected - No automatic API docs, manual serialization, more code

**References**:
- Django Ninja Docs: https://django-ninja.rest-framework.com/
- Schema Patterns: https://django-ninja.rest-framework.com/guides/response/

---

## 3. PostgreSQL UUID and CDS Naming

### Decision: UUID Primary Keys with `db_column` Mapping

**Chosen Approach**: Use PostgreSQL native UUID type with Django `db_column` for CDS naming

**Rationale**:
- PostgreSQL has native UUID type with optimized storage (16 bytes vs 36-byte strings)
- UUIDs prevent ID enumeration attacks (security benefit)
- Enables distributed record generation without ID conflicts
- CDS compatibility requires lowercase field names without underscores
- Django's `db_column` allows Python-friendly code while maintaining CDS database naming

**Implementation**:
```python
class SystemUser(AbstractBaseUser):
    systemuserid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='systemuserid'  # CDS naming
    )
    emailaddress1 = models.EmailField(
        unique=True,
        db_column='emailaddress1'  # CDS naming (no email_address)
    )
```

**Index Strategy**:
- PostgreSQL automatically indexes primary keys (UUIDs)
- Foreign key UUID fields need explicit indexes: `db_index=True`
- Composite indexes for common queries: `indexes = [models.Index(fields=['isdisabled', 'securityroleid'])]`
- Use `select_related()` aggressively to prevent N+1 queries with UUIDs

**Performance Considerations**:
- UUID indexes are larger than integer indexes (16 bytes vs 4-8 bytes)
- Use UUIDv4 (random) for security; UUIDv7 (time-ordered) if insert performance critical
- PostgreSQL handles UUID indexes efficiently with btree
- At CRM scale (millions of records), UUID overhead is negligible vs security benefits

**Database Migration**:
```python
# Enable PostgreSQL UUID extension
operations = [
    migrations.RunSQL("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"),
    # ... model creation
]
```

**Alternatives Considered**:
- **Auto-increment integers**: Rejected - CDS incompatible, security risk (ID enumeration)
- **UUID as CHAR(36)**: Rejected - Wastes space, slower queries
- **Custom ID generation**: Rejected - Complexity, UUIDs are standard

**References**:
- PostgreSQL UUID: https://www.postgresql.org/docs/current/datatype-uuid.html
- Django UUID Fields: https://docs.djangoproject.com/en/5.0/ref/models/fields/#uuidfield

---

## 4. RBAC Implementation Patterns

### Decision: Code-Defined Permissions with Database Storage

**Chosen Approach**: Hybrid - roles in database, permission logic in code

**Rationale**:
- 5 predefined roles are **fixed** per constitution (not user-configurable)
- Permission rules are business logic (belong in code, not data)
- Database stores role assignments (which user has which role)
- Code defines what each role can do (maintainable, version-controlled)
- Supports both entity-level and record-level permissions

**Permission Architecture**:

```python
# core/permissions.py
from enum import Enum
from typing import Set

class SecurityRoleEnum(str, Enum):
    SYSTEM_ADMINISTRATOR = "System Administrator"
    SALES_MANAGER = "Sales Manager"
    SALESPERSON = "Salesperson"
    MARKETING_USER = "Marketing User"
    READ_ONLY_USER = "Read-Only User"

class Permission(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"

# Permission matrix (code-defined)
ROLE_PERMISSIONS = {
    SecurityRoleEnum.SYSTEM_ADMINISTRATOR: {
        'SystemUser': {Permission.CREATE, Permission.READ, Permission.UPDATE, Permission.DELETE},
        # ... all entities
    },
    SecurityRoleEnum.SALESPERSON: {
        'Lead': {Permission.CREATE, Permission.READ, Permission.UPDATE},  # Own records only
        'Account': {Permission.READ},  # Read-only
    },
    # ... other roles
}

def has_permission(user, entity: str, permission: Permission, record=None) -> bool:
    """Check if user has permission on entity (and optionally specific record)"""
    # 1. Check entity-level permission
    # 2. Check record-level permission (ownership)
    # 3. Return True/False
```

**Django Ninja Integration**:
```python
# Decorator for permission checks
from functools import wraps

def requires_permission(entity: str, permission: Permission):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, entity, permission):
                raise PermissionDenied("Insufficient permissions")
            return func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage in router
@router.post("/", response=UserSchema)
@requires_permission("SystemUser", Permission.CREATE)
def create_user(request, payload: CreateUserDto):
    return UserService.create_user(request.user, payload)
```

**Record-Level Filtering**:
```python
def filter_by_permissions(queryset, user, entity: str):
    """Filter queryset to records user can access"""
    role = user.securityrole.name

    if role == SecurityRoleEnum.SYSTEM_ADMINISTRATOR:
        return queryset  # Access all
    elif role == SecurityRoleEnum.SALES_MANAGER:
        # Access own + team records
        return queryset.filter(Q(ownerid=user) | Q(ownerid__manager=user))
    elif role == SecurityRoleEnum.SALESPERSON:
        # Access own records only
        return queryset.filter(ownerid=user)
    # ... other roles
```

**Alternatives Considered**:
- **Database-driven permissions**: Rejected - Complex UI needed, over-engineering for 5 fixed roles
- **Django's `django.contrib.auth.permissions`**: Rejected - Entity-level only, no record-level ownership
- **Middleware-only**: Rejected - Harder to test, less granular control

**References**:
- Django Permissions: https://docs.djangoproject.com/en/5.0/topics/auth/default/#permissions-and-authorization

---

## 5. Audit Trail Implementation

### Decision: Middleware + Service Layer Approach

**Chosen Approach**: Middleware captures request context, services populate audit fields

**Rationale**:
- Middleware has access to HTTP request (authenticated user)
- Services perform database operations (best place to populate audit fields)
- Thread-local storage passes user context from middleware to services
- Handles edge cases (system-generated changes, admin actions)

**Implementation**:

```python
# core/middleware.py
import threading

_thread_locals = threading.local()

def get_current_user():
    """Get current authenticated user from thread-local storage"""
    return getattr(_thread_locals, 'user', None)

class AuditMiddleware:
    """Middleware to capture current user for audit trail"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = request.user if request.user.is_authenticated else None
        response = self.get_response(request)
        _thread_locals.user = None
        return response
```

```python
# core/models.py
class AuditMixin(models.Model):
    """Base mixin for audit trail fields"""
    createdon = models.DateTimeField(auto_now_add=True, db_column='createdon')
    modifiedon = models.DateTimeField(auto_now=True, db_column='modifiedon')
    createdby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='%(class)s_created',
        db_column='createdby'
    )
    modifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='%(class)s_modified',
        db_column='modifiedby'
    )

    class Meta:
        abstract = True
```

```python
# apps/users/services.py
from core.middleware import get_current_user

class UserService:
    @staticmethod
    def create_user(payload: CreateUserDto) -> SystemUser:
        current_user = get_current_user()
        user = SystemUser(
            emailaddress1=payload.emailaddress1,
            fullname=payload.fullname,
            createdby=current_user,  # Auto-populated
            modifiedby=current_user  # Auto-populated
        )
        user.set_password(payload.password)
        user.save()
        return user
```

**Edge Cases Handled**:
- **Initial superuser creation**: `createdby=None` allowed via `null=True`
- **System-generated changes**: Use a system user account or `None`
- **Admin panel operations**: Middleware captures admin user automatically
- **Management commands**: Either set thread-local manually or use `None`

**Alternatives Considered**:
- **Django signals (pre_save/post_save)**: Rejected - Harder to access request context, signal overhead
- **Model save() override**: Rejected - Violates "no business logic in models" principle
- **Manual in every service**: Rejected - Error-prone, boilerplate, easy to forget

**References**:
- Django Middleware: https://docs.djangoproject.com/en/5.0/topics/http/middleware/
- Thread-local storage: https://docs.python.org/3/library/threading.html#thread-local-data

---

## 6. Testing Strategy

### Decision: Three-Layer Testing (Unit, Integration, Contract)

**Framework**: pytest with pytest-django

**Test Organization**:

1. **Unit Tests** (`apps/users/tests/`)
   - Test service logic in isolation
   - Mock database calls
   - Fast execution (<1 second total)

2. **Integration Tests** (`tests/integration/`)
   - Test full flows (auth → RBAC → audit trail)
   - Use test database
   - Verify middleware + service + model integration

3. **Contract Tests** (`tests/contract/`)
   - Test API schemas and endpoints
   - Verify request/response formats
   - Validate OpenAPI compliance

**Example Test Structure**:
```python
# apps/users/tests/test_services.py (Unit)
def test_create_user_populates_audit_fields():
    payload = CreateUserDto(emailaddress1="test@example.com", ...)
    user = UserService.create_user(payload)
    assert user.createdby is not None
    assert user.createdon is not None

# tests/integration/test_authentication_flow.py (Integration)
def test_login_creates_session(client):
    response = client.post('/api/auth/login', {'email': 'user@example.com', 'password': 'pass'})
    assert response.status_code == 200
    assert 'sessionid' in response.cookies

# tests/contract/test_users_api.py (Contract)
def test_create_user_response_schema(client):
    response = client.post('/api/users', {...})
    data = response.json()
    assert 'systemuserid' in data
    assert 'emailaddress1' in data
    assert 'createdon' in data
```

**Rationale**:
- Constitution requires testing but marks as optional for MVP
- Three layers provide good coverage without over-testing
- pytest-django integrates well with Django ORM
- Fast unit tests enable TDD workflow

---

## 7. Dependencies and Versions

### Final Dependency List

```
# requirements.txt
Django==5.0.1
django-ninja==1.1.0
psycopg[binary]==3.1.18        # PostgreSQL adapter
python-decouple==3.8           # Environment config
django-filter==23.5            # Advanced filtering
gunicorn==21.2.0               # WSGI server
uvicorn[standard]==0.27.0      # ASGI server
pytest==8.0.0
pytest-django==4.7.0
pytest-cov==4.1.0
```

**Rationale**:
- Pinned versions for reproducibility
- Django 5.0+ required per constitution
- psycopg 3.x for modern PostgreSQL features
- gunicorn + uvicorn for production serving
- pytest ecosystem for testing

---

## Research Completion Summary

All research areas resolved. Key decisions documented with rationales. Implementation can proceed to Phase 1 (Design) with confidence.

**Next Phase**: Generate data-model.md, API contracts, and quickstart.md based on these findings.
