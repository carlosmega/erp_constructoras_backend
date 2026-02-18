# Implementation Plan: CRM Backend Foundation

**Branch**: `001-crm-backend-foundation` | **Date**: 2025-11-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-crm-backend-foundation/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build the foundational backend infrastructure for a CRM system following Microsoft Dynamics 365 Common Data Service architecture. The foundation provides secure user authentication, role-based access control with 5 predefined roles, standardized REST API patterns, and comprehensive audit trail tracking. This enables rapid development of CRM entities (leads, accounts, contacts, opportunities) with consistent security, data integrity, and API behavior.

**Technical Approach**: Django 5.0+ with Django Ninja for type-safe REST APIs, PostgreSQL for production data storage with UUID and JSONB support, four-layer architecture (models → schemas → services → routers) for separation of concerns, and comprehensive RBAC implementation in core utilities.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Django 5.0+, Django Ninja (REST API), django-filter (advanced filtering), python-decouple (env config), gunicorn + uvicorn (ASGI/WSGI)
**Storage**: PostgreSQL (production with UUID/JSONB support), SQLite (local dev only)
**Testing**: pytest with pytest-django, pytest-cov for coverage
**Target Platform**: Linux server (production), cross-platform development (Windows/Mac/Linux)
**Project Type**: Backend web application (REST API only, no frontend)
**Performance Goals**: Handle 100 concurrent users, API response times <2 seconds for 10k records, authentication <3 seconds
**Constraints**: 99.9% uptime for auth services, session timeout 30 minutes, account lockout after 3 failed attempts
**Scale/Scope**: Foundation for multi-entity CRM, support 10k+ user accounts, millions of customer records with proper indexing

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Data Model Fidelity (Dynamics CDS) ✅

**Status**: COMPLIANT

- SystemUser entity will use UUID primary keys (`systemuserid`)
- SecurityRole will follow CDS naming conventions (lowercase, no underscores)
- All entities will include state/status tracking where applicable
- Ownership pattern implemented via `ownerid` foreign key on all business entities
- Audit fields (`createdon`, `modifiedon`, `createdby`, `modifiedby`) on all entities

**Action**: Phase 1 data-model.md will define exact field mappings following CDS patterns.

### Principle II: Four-Layer Architecture (NON-NEGOTIABLE) ✅

**Status**: COMPLIANT

Every entity in this foundation will implement all four layers:

1. **models.py**: Django ORM models for SystemUser, SecurityRole with UUID primary keys, indexes
2. **schemas.py**: Django Ninja schemas for all DTOs (UserSchema, CreateUserDto, UpdateUserDto, etc.)
3. **services.py**: Business logic for authentication, authorization, role assignment, audit trail population
4. **routers.py**: API endpoints following standard CRUD pattern + custom actions (login, logout, assign-role)

**Action**: Project structure will enforce this pattern with apps/users/ and core/ directories.

### Principle III: Service-Encapsulated Logic (NON-NEGOTIABLE) ✅

**Status**: COMPLIANT

All business logic will reside in service layer:

- Authentication logic in `apps/users/services.py` (not in router or model)
- Permission checking in `core/permissions.py` service functions
- Session management and timeout logic in services
- Account lockout logic in authentication service
- Role assignment validation in services
- Models are pure data structures (Django ORM only)
- Routers are thin HTTP handlers that call services

**Action**: Code review checklist will verify no business logic in models or routers.

### Principle IV: Audit Trail Integrity ✅

**Status**: COMPLIANT

- SystemUser entity will track its own creation/modification (bootstrapping scenario handled)
- All future entities will inherit audit fields from base model or mixin
- Services will automatically populate `createdby` and `modifiedby` from request context
- Audit fields are read-only via API (excluded from CreateDto/UpdateDto)
- Migration scripts will handle initial admin user creation edge case

**Action**: Phase 1 will define AuditMixin base class for reuse across all entities.

### Principle V: API Consistency & Typing ✅

**Status**: COMPLIANT

All endpoints follow standardized patterns:

- `GET /api/users` - List users (with filtering by role, active status)
- `GET /api/users/{id}` - Get single user
- `POST /api/users` - Create user (admin only)
- `PATCH /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Deactivate user (soft delete)
- `POST /api/auth/login` - Authenticate user
- `POST /api/auth/logout` - End session
- `POST /api/users/{id}/assign-role` - Custom action for role assignment

Django Ninja provides automatic OpenAPI schema generation and type validation.

**Action**: Phase 1 contracts will define exact request/response schemas.

### Principle VI: Database Optimization ✅

**Status**: COMPLIANT

- All foreign keys will have database indexes
- Composite index on `[active, role]` for user list queries
- `select_related('role', 'createdby', 'modifiedby')` on user queries to prevent N+1
- Field names use `db_column` for CDS naming compliance
- PostgreSQL UUID type for primary keys
- Migration reviews required before production deployment

**Action**: Phase 1 data-model.md will specify all indexes and query optimization strategies.

### Principle VII: RBAC Security Model ✅

**Status**: COMPLIANT

Implementation of exactly 5 predefined roles:

1. **System Administrator** - Full CRUD on all entities, user management
2. **Sales Manager** - CRUD on team's records, read all opportunities
3. **Salesperson** - CRUD on own records only
4. **Marketing User** - Manage campaigns and leads, read-only on opportunities
5. **Read-Only User** - Read access only, no modifications

- Entity-level permissions in `core/permissions.py`
- Record-level filtering based on `ownerid` and role hierarchy
- Permission decorators on all API endpoints
- Automatic `ownerid` assignment on record creation

**Action**: Phase 1 will define permission matrix and implementation strategy.

### Constitution Compliance Summary

**Result**: ✅ ALL 7 PRINCIPLES COMPLIANT

No violations detected. No entries required in Complexity Tracking table.

**Gate Status**: PASSED - Proceeding to Phase 0 Research

## Project Structure

### Documentation (this feature)

```text
specs/001-crm-backend-foundation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - Technology decisions and patterns
├── data-model.md        # Phase 1 output - Entity definitions (SystemUser, SecurityRole)
├── quickstart.md        # Phase 1 output - Setup and usage guide
├── contracts/           # Phase 1 output - API contracts
│   ├── users-api.yaml   # OpenAPI spec for user management endpoints
│   └── auth-api.yaml    # OpenAPI spec for authentication endpoints
└── checklists/
    └── requirements.md  # Quality validation checklist
```

### Source Code (repository root)

Based on CLAUDE.md project structure, this is a backend-only Django application:

```text
backend/
├── crm/                          # Django project settings
│   ├── __init__.py
│   ├── settings.py              # Django configuration, middleware, apps
│   ├── urls.py                  # Root URL configuration
│   ├── wsgi.py                  # WSGI application entry point
│   └── asgi.py                  # ASGI application entry point
│
├── apps/                         # Django apps (one per entity)
│   └── users/                   # User management and authentication
│       ├── __init__.py
│       ├── models.py            # SystemUser, SecurityRole models
│       ├── schemas.py           # Django Ninja DTOs (UserSchema, CreateUserDto, etc.)
│       ├── services.py          # Business logic (auth, role assignment, user mgmt)
│       ├── routers.py           # API endpoints (/api/users, /api/auth)
│       ├── admin.py             # Django admin interface config
│       ├── migrations/          # Database migrations
│       │   └── 0001_initial.py
│       └── tests/               # User-specific tests
│           ├── test_models.py
│           ├── test_services.py
│           └── test_routers.py
│
├── core/                         # Shared utilities
│   ├── __init__.py
│   ├── permissions.py           # RBAC implementation, permission decorators
│   ├── pagination.py            # Pagination utilities for list endpoints
│   ├── exceptions.py            # Custom exception classes
│   ├── middleware.py            # Session management, audit context
│   ├── models.py                # Base models (AuditMixin)
│   └── tests/                   # Core utility tests
│       ├── test_permissions.py
│       └── test_pagination.py
│
├── tests/                        # Integration and contract tests
│   ├── contract/
│   │   ├── test_users_api.py   # Contract tests for user endpoints
│   │   └── test_auth_api.py    # Contract tests for auth endpoints
│   └── integration/
│       ├── test_authentication_flow.py
│       ├── test_rbac_permissions.py
│       └── test_audit_trail.py
│
├── manage.py                     # Django management script
├── requirements.txt              # Python dependencies
├── pytest.ini                    # pytest configuration
├── .env.example                  # Environment variables template
└── README.md                     # Project setup and documentation
```

**Structure Decision**: Backend-only Django application following the structure defined in CLAUDE.md. The `apps/` directory contains domain entities (currently just `users/` for foundation), while `core/` provides shared utilities for permissions, pagination, and common patterns. Each app follows the 4-layer architecture (models → schemas → services → routers). Tests are organized by type (contract, integration) at the project level, with unit tests co-located with their modules.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations detected. This table remains empty.

---

## Phase 0: Research & Technology Decisions

*See [research.md](research.md) for detailed findings*

### Key Research Areas

1. **Django 5.0+ Authentication Patterns**
   - Built-in `django.contrib.auth` vs custom authentication
   - Session management and security best practices
   - Integration with Django Ninja for token/session auth

2. **Django Ninja Best Practices**
   - Schema design patterns for DTOs
   - Authentication and authorization decorators
   - Error handling and validation
   - OpenAPI documentation generation

3. **PostgreSQL UUID and CDS Naming**
   - UUID as primary key performance considerations
   - Field name mapping with `db_column` for CDS compliance
   - Index strategies for UUID foreign keys

4. **RBAC Implementation Patterns**
   - Permission storage (database vs code-defined)
   - Permission checking middleware vs decorators
   - Record-level permission filtering

5. **Audit Trail Implementation**
   - Automatic population of audit fields from request context
   - Middleware vs service layer approach
   - Handling system-generated changes (no user context)

---

## Phase 1: Design Artifacts

### Data Model

*See [data-model.md](data-model.md) for complete entity definitions*

**Entities**:
- SystemUser
- SecurityRole
- AuditMixin (base class for all entities)

### API Contracts

*See [contracts/](contracts/) for OpenAPI specifications*

**Endpoints**:
- User Management: `/api/users` (CRUD operations)
- Authentication: `/api/auth/login`, `/api/auth/logout`
- Role Management: `/api/users/{id}/assign-role`

### Getting Started

*See [quickstart.md](quickstart.md) for setup instructions*

Quick setup:
1. Install Python 3.11+ and PostgreSQL
2. Clone repository and create virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Configure `.env` with database credentials
5. Run migrations: `python manage.py migrate`
6. Create superuser: `python manage.py createsuperuser`
7. Run development server: `python manage.py runserver`
8. Access API docs: `http://localhost:8000/api/docs`

---

## Post-Phase 1 Constitution Re-Check

After completing design phase, re-validate all 7 principles:

- ✅ Principle I (Data Model Fidelity): Confirmed in data-model.md
- ✅ Principle II (Four-Layer Architecture): Enforced in project structure
- ✅ Principle III (Service-Encapsulated Logic): Verified in service definitions
- ✅ Principle IV (Audit Trail): AuditMixin defined and applied
- ✅ Principle V (API Consistency): OpenAPI contracts follow standard patterns
- ✅ Principle VI (Database Optimization): Indexes defined in data-model.md
- ✅ Principle VII (RBAC Security): 5 roles defined with permission matrix

**Final Gate Status**: ✅ PASSED - Ready for Phase 2 (Task Generation)

---

## Next Steps

1. Run `/speckit.tasks` to generate implementation tasks from this plan
2. Tasks will be organized by user story (P1-P4) with clear dependencies
3. Implementation follows: Setup → Foundation → User Stories in priority order
4. Each user story delivers independently testable functionality
