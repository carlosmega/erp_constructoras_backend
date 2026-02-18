<!--
Sync Impact Report:
Version: 0.0.0 → 1.0.0 (INITIAL CONSTITUTION)
Rationale: Initial constitution establishment for CRM Backend based on Dynamics CDS model

Added Principles:
  - I. Data Model Fidelity (Dynamics CDS)
  - II. Four-Layer Architecture (NON-NEGOTIABLE)
  - III. Service-Encapsulated Logic (NON-NEGOTIABLE)
  - IV. Audit Trail Integrity
  - V. API Consistency & Typing
  - VI. Database Optimization
  - VII. RBAC Security Model

Added Sections:
  - Technical Constraints
  - Quality Standards

Templates Requiring Review:
  ✅ plan-template.md - Constitution Check section exists, aligns with principles
  ✅ spec-template.md - Requirements structure supports data model entities
  ✅ tasks-template.md - 4-layer implementation pattern can be applied

Follow-up Actions:
  - None - all placeholders filled
  - Constitution ready for use in feature planning
-->

# CRM Backend (Dynamics CDS) Constitution

## Core Principles

### I. Data Model Fidelity (Dynamics CDS)

All entities MUST strictly adhere to Microsoft Dynamics 365 Common Data Service patterns:

- **UUID Primary Keys**: Every entity uses `entityid = models.UUIDField(primary_key=True, default=uuid.uuid4)` - no auto-increment integers
- **State + Status Pattern**: Dual state tracking with `statecode` (high-level) and `statuscode` (detailed) using IntegerChoices
- **CDS Naming Convention**: Lowercase field names, no underscores (e.g., `emailaddress1`, `leadid`, `createdon`)
- **Polymorphic References**: Customer fields can reference Account OR Contact via GenericForeignKey or discriminator pattern
- **Ownership Pattern**: All business entities have `ownerid` foreign key to SystemUser

**Rationale**: Maintains compatibility with Dynamics 365 data model, enables future integration, ensures consistent entity structure across the system.

### II. Four-Layer Architecture (NON-NEGOTIABLE)

Every entity MUST implement exactly four layers in this order:

1. **models.py**: Django ORM model with UUID pk, state/status enums, foreign keys, audit fields, Meta class with indexes
2. **schemas.py**: Django Ninja DTOs - EntitySchema (full response), CreateEntityDto, UpdateEntityDto, operation-specific DTOs
3. **services.py**: Business logic - state transitions, computed fields, cross-entity operations, validation rules, audit logging
4. **routers.py**: API endpoints - standard CRUD (list, get, create, update, delete) + custom actions

**Rationale**: Separation of concerns - database layer, data transfer, business logic, and API interface remain decoupled. This pattern is consistent across ALL entities, making the codebase predictable and maintainable.

### III. Service-Encapsulated Logic (NON-NEGOTIABLE)

Business logic MUST reside exclusively in the service layer:

- State transitions (e.g., Lead qualification, Quote acceptance) implemented in services
- Cross-entity operations (e.g., Lead → Opportunity conversion) in services
- Validation rules beyond field-level constraints in services
- Computed field calculations (e.g., `totalamount`, `fullname`) in services
- Routers MUST be thin - they call services, handle HTTP concerns only
- Models MUST be data structures - no business logic beyond simple properties

**Violations**: Business logic in models, routers, or schemas.

**Rationale**: Single source of truth for business rules. Services can be tested independently, reused across endpoints, and modified without touching data or API layers.

### IV. Audit Trail Integrity

All business entities MUST maintain complete audit trails:

- `createdon = models.DateTimeField(auto_now_add=True)` - creation timestamp
- `modifiedon = models.DateTimeField(auto_now=True)` - last modification timestamp
- `createdby = models.ForeignKey('users.SystemUser', ...)` - creator user
- `modifiedby = models.ForeignKey('users.SystemUser', ...)` - last modifier user
- Services MUST populate audit fields on create/update operations
- Audit fields are read-only via API (not in CreateDto/UpdateDto)

**Rationale**: Regulatory compliance, debugging, user accountability, change tracking for critical business data.

### V. API Consistency & Typing

All API endpoints MUST follow standardized patterns:

- **Standard CRUD**: `GET /api/{entities}` (list), `GET /api/{entities}/{id}` (get), `POST /api/{entities}` (create), `PATCH /api/{entities}/{id}` (update), `DELETE /api/{entities}/{id}` (delete)
- **Custom Actions**: `POST /api/{entities}/{id}/{action}` (e.g., `/api/leads/{id}/qualify`)
- **Typed Schemas**: Django Ninja schemas with full type annotations, validation rules
- **Filtering**: All list endpoints support filtering by `statecode`, `ownerid`, date ranges via django-filter
- **Pagination**: All list endpoints return paginated results
- **HTTP Status Codes**: Proper codes - 200 (OK), 201 (Created), 400 (Bad Request), 404 (Not Found), 403 (Forbidden)

**Rationale**: Predictable API surface, auto-generated documentation, type safety, consistent client experience.

### VI. Database Optimization

Database access MUST be optimized for production workloads:

- **Indexes**: All foreign keys indexed, composite indexes for common queries (e.g., `[ownerid, statecode]`)
- **Query Optimization**: Use `select_related()` for foreign keys, `prefetch_related()` for reverse relations to avoid N+1 queries
- **Field Mapping**: Use `db_column` to match CDS naming exactly (lowercase, no underscores)
- **PostgreSQL Features**: Leverage UUID, JSONB, advanced indexing via `django.contrib.postgres`
- **Migration Reviews**: Database migrations must be reviewed for performance impact before merge

**Rationale**: CRM systems handle large datasets with complex relationships. Poor query patterns cause performance degradation at scale.

### VII. RBAC Security Model

Security MUST be enforced at entity and record levels:

- **Predefined Roles**: System Administrator, Sales Manager, Salesperson, Marketing User, Read-Only User
- **Entity-Level Permissions**: CRUD permissions defined per role per entity in `core/permissions.py`
- **Record-Level Ownership**: Users can only access records they own unless role grants broader access
- **Permission Checks**: All endpoints verify permissions before data access
- **Ownership Assignment**: All creates assign `ownerid` to current authenticated user

**Rationale**: Multi-tenant CRM requires granular access control. Sales data is sensitive and must respect organizational hierarchies.

## Technical Constraints

These technology choices are foundational and MUST be followed:

- **Framework**: Django 5.0+ with Django Ninja for API layer
- **Database**: PostgreSQL (production) - SQLite allowed for local dev only
- **Python Version**: 3.11+ required for modern type hints
- **Type Safety**: Full type annotations required in schemas, services, routers
- **Environment Config**: python-decouple for all configuration (no hardcoded secrets)
- **Server**: gunicorn + uvicorn for ASGI/WSGI serving in production

**Async Tasks** (optional): Celery for email sending, PDF generation, heavy processing - NOT required for MVP.

**Rationale**: These choices provide UUID support, modern async capabilities, type safety, and production-grade performance. Changing these would require architecture redesign.

## Quality Standards

All code MUST meet these quality gates before merge:

### Code Organization

- Follow project structure: `apps/{entity}/` with models, schemas, services, routers
- Shared utilities in `core/` (permissions, pagination, exceptions)
- One entity per app module

### Testing Requirements

- **Unit Tests**: Service layer logic must have unit test coverage
- **Integration Tests**: State transitions and cross-entity operations require integration tests
- **Contract Tests**: API endpoints must have contract tests validating request/response schemas
- Tests are OPTIONAL for MVP unless explicitly requested in feature spec

### Code Review

- All changes require review by at least one team member
- Reviewers MUST verify:
  - 4-layer architecture compliance
  - Service layer contains business logic (not in models/routers)
  - Audit fields present and populated
  - Proper indexes on new models
  - No N+1 query patterns
  - RBAC permissions implemented

### Documentation

- Each entity must document state transitions in service layer comments
- API endpoints auto-document via Django Ninja schemas
- Complex business rules require inline comments explaining "why"
- README updates required when adding new entity types

## Governance

This constitution supersedes all other development practices and guides.

### Amendment Procedure

1. Proposed changes must be documented with rationale
2. Impact analysis on existing features required
3. Team consensus required for principle changes
4. Version bump following semantic versioning:
   - **MAJOR**: Breaking changes to principles, incompatible governance shifts
   - **MINOR**: New principles added, expanded guidance sections
   - **PATCH**: Clarifications, wording improvements, non-semantic fixes

### Compliance

- All pull requests MUST verify compliance with active constitution version
- Constitution Check in plan.md template gates feature planning
- Non-compliance must be explicitly justified in Complexity Tracking table
- Complexity introduced without constitutional justification will be rejected

### Version Control

- Constitution version tracked in this file header
- Changes logged in Sync Impact Report (HTML comment at file top)
- Ratification and amendment dates maintained in ISO format YYYY-MM-DD

**Version**: 1.0.0 | **Ratified**: 2025-11-27 | **Last Amended**: 2025-11-27
