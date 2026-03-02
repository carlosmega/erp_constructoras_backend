# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a CRM + Operations backend built with **Django 5.0+ and Django Ninja**, following the **Microsoft Dynamics 365 Sales (Common Data Service)** data model. The system implements a complete sales pipeline with activities, product catalog, RBAC security, and an **Operations module** for managing expenses and income of civil construction and mining companies.

## Technology Stack

- **Django 5.0+** - ORM and base structure
- **Django Ninja** - Modern typed API (alternative to DRF)
- **PostgreSQL** - Primary database (UUID, JSONB support required)
- **django-filter** - Advanced filtering
- **django-extensions** - Development utilities
- **python-decouple** - Environment configuration
- **gunicorn** + **uvicorn** - ASGI/WSGI server
- **Celery** (optional) - Async tasks (email sending, PDF generation)
- **Factory Boy** - Test data generation (pytest factories)
- **python-dateutil** - Date utilities (period generation with `relativedelta`)

## Project Structure

```
backend/
├── crm/                          # Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── leads/
│   │   ├── models.py            # Lead entity, StateCode/StatusCode choices
│   │   ├── schemas.py           # Django Ninja schemas (DTOs)
│   │   ├── routers.py           # API endpoints
│   │   ├── services.py          # Business logic
│   │   └── migrations/
│   ├── opportunities/
│   ├── accounts/
│   ├── contacts/
│   ├── quotes/
│   ├── orders/
│   ├── invoices/
│   ├── products/
│   ├── activities/
│   ├── users/
│   ├── audit/
│   ├── projects/            # Construction project management (Operations)
│   │   ├── models.py        # ConstructionProject, Zone, Supplier, TeamMember
│   │   ├── schemas.py       # DTOs with nested bonds, resolved FKs
│   │   ├── services.py      # CRUD + auto project numbering (PRY-YYYY-NNN)
│   │   ├── routers.py       # /projects, /zones, /suppliers, /team-members
│   │   └── tests/           # factories.py, test_models.py, test_services.py
│   ├── budgets/             # Budget & cost structure (Operations)
│   │   ├── models.py        # CostCategory, ImputationCode, ImputationPeriod
│   │   ├── schemas.py       # DTOs for categories, codes, periods
│   │   ├── services.py      # Seed defaults, auto code gen, period init
│   │   ├── routers.py       # /categories, /codes, /periods
│   │   └── tests/           # factories.py, test_models.py, test_services.py
│   └── expenses/            # Expense management (Operations)
│       ├── models.py        # ProjectExpense, ExpenseLine, Attachment, Estimate
│       ├── schemas.py       # DTOs + classify/verify/summary schemas
│       ├── services.py      # 7 services (expense, classification, verification...)
│       ├── routers.py       # /expenses, /expense-lines, /attachments, /estimates
│       └── tests/           # factories.py, test_models.py, test_services.py
└── core/
    ├── permissions.py           # RBAC implementation
    ├── pagination.py            # Pagination utilities
    └── exceptions.py            # Custom exceptions
```

## Core Architecture Concepts

### Sales Pipeline Flow

The system implements this linear sales pipeline:

**Lead → Opportunity → Quote → Order → Invoice**

- **Lead**: Potential customer (qualification required)
- **Opportunity**: Qualified lead with estimated value and close date
- **Quote**: Formal price proposal with line items
- **Order**: Accepted quote (becomes binding contract)
- **Invoice**: Billing document from fulfilled order

### Data Model Patterns

#### 1. UUID Primary Keys
All entities use UUIDs instead of auto-increment integers:
```python
entityid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```

#### 2. State + Status Pattern
Every entity has dual state tracking:
- **`statecode`**: High-level state (Open/Won/Lost, Active/Inactive)
- **`statuscode`**: Detailed status within each state

Example for Lead:
- `statecode`: 0=Open, 1=Qualified, 2=Disqualified
- `statuscode`: 1=New, 2=Contacted, 3=Qualified, 4=Disqualified

#### 3. Polymorphic Customer Reference
The `customerid` field can reference either:
- **Account** (B2B companies)
- **Contact** (B2C individuals)

Implementation uses `GenericForeignKey` or separate `accountid`/`contactid` fields with a `customertype` discriminator.

#### 4. Ownership Pattern
All business entities have:
```python
ownerid = models.ForeignKey('users.SystemUser', ...)  # Assigned user
```

#### 5. Audit Trail
Standard audit fields on all entities:
```python
createdon = models.DateTimeField(auto_now_add=True)
modifiedon = models.DateTimeField(auto_now=True)
createdby = models.ForeignKey('users.SystemUser', ...)
modifiedby = models.ForeignKey('users.SystemUser', ...)
```

### Key Entities

#### Core Sales Entities
- **Lead**: Potential customer with qualification workflow
- **Opportunity**: Qualified sales opportunity with pipeline stages
- **Quote**: Product/service proposals with line items
- **Order**: Confirmed orders from accepted quotes
- **Invoice**: Billing documents

#### Customer Entities
- **Account**: B2B companies/organizations
- **Contact**: B2C individuals (can belong to an Account)

#### Catalog Entities
- **Product**: Items/services for sale
- **PriceListItem**: Product pricing in different price lists

#### Activity Entities
All inherit from base Activity entity:
- **Email**: Email communications
- **PhoneCall**: Phone call logs
- **Task**: To-do items
- **Appointment**: Calendar meetings

These link to any entity via `regardingobjectid` (polymorphic).

#### Operations Module Entities
- **ConstructionProject**: Main project entity with flattened bond fields, account/owner relations, project numbering (PRY-YYYY-NNN)
- **ProjectTeamMember**: Team members with role enum (ProjectManager, SiteEngineer, SafetyOfficer, etc.)
- **ProjectZone**: Geographic zones with unique prefix per project (e.g., TAM, MTY)
- **ProjectSupplier**: Suppliers with RFC validation and auto-numbering
- **CostCategory**: Direct (P1-P10) and indirect (C1-C8) cost categories with seed defaults
- **ImputationCode**: Budget line items with auto-generated codes (e.g., TAM-P4-17 for direct, C1-5 for indirect)
- **ImputationPeriod**: Weekly or fortnightly periods with Spanish month labels (ENE, FEB, MAR...)
- **ProjectExpense**: Multi-document expenses (invoice, payroll, provision) with classification and verification workflows
- **ExpenseLine**: Line items per expense with automatic total recalculation
- **ExpenseAttachment**: File attachment metadata for expenses
- **ClassificationLog**: Audit trail for expense classification changes
- **ClientEstimate**: Client billing estimates with computed IVA totals and auto-numbering

### Security Model (RBAC)

System implements 5 predefined roles:
1. **System Administrator**: Full access
2. **Sales Manager**: Manage sales team, view all opportunities
3. **Salesperson**: Manage own leads/opportunities
4. **Marketing User**: Manage campaigns and leads
5. **Read-Only User**: View-only access

Permissions are entity-level (Create, Read, Update, Delete) with record-level ownership filters.

Operations module permissions: `PROJECT_*`, `BUDGET_*`, `EXPENSE_*` (+ CLASSIFY, VERIFY), `ESTIMATE_*`.
- **System Administrator / Sales Manager**: Full access to all operations entities
- **Salesperson**: Create/read/update own projects, budgets, expenses, estimates (no delete). Can classify but not verify expenses.
- **Read-Only User**: View-only access to all operations entities

## Implementation Pattern

For each entity, implement this 4-layer structure:

### 1. models.py
- Django model with UUID primary key
- StateCode/StatusCode as IntegerChoices
- Foreign keys to related entities
- Audit fields (created/modified by/on)
- Meta class with db_table, ordering, indexes

### 2. schemas.py (Django Ninja DTOs)
- **EntitySchema**: Full response (ModelSchema)
- **CreateEntityDto**: Creation payload with validation
- **UpdateEntityDto**: Update payload (all fields optional)
- **Special DTOs**: Operation-specific (e.g., QualifyLeadDto)

### 3. services.py
Business logic layer handling:
- State transitions
- Computed fields calculation
- Cross-entity operations (e.g., Lead qualification creates Opportunity)
- Validation rules
- Audit logging

### 4. routers.py (API Endpoints)
Django Ninja routers with standard CRUD:
- `GET /api/entities` - List with filtering/pagination
- `GET /api/entities/{id}` - Get single
- `POST /api/entities` - Create
- `PATCH /api/entities/{id}` - Update
- `DELETE /api/entities/{id}` - Delete
- Custom actions (e.g., `POST /api/leads/{id}/qualify`)

## Database Considerations

- Use PostgreSQL for production (UUID, JSONB support)
- Index all foreign keys and state fields
- Composite indexes for common query patterns (e.g., `[ownerid, statecode]`)
- Use `db_column` to match CDS naming (lowercase, no underscores)
- Enable `django.contrib.postgres` for advanced features

## Business Logic Examples

### Lead Qualification
When qualifying a lead:
1. Create Opportunity with lead data
2. Optionally create Account and/or Contact
3. Link Opportunity to customer
4. Set Lead statecode=1 (Qualified)
5. Set Lead statuscode=3 (Qualified)
6. Log audit trail

### Quote to Order Conversion
When accepting a quote:
1. Create Order with same line items
2. Copy pricing, discounts, totals
3. Set Quote statecode=2 (Won)
4. Link Order to Quote via `quoteid`
5. Trigger fulfillment workflow

### Computed Fields
Many totals are calculated, not stored:
- `totalamount` = SUM(line items subtotal) + tax - discount
- `fullname` = firstname + " " + lastname
- `estimatedvalue` on Opportunity rolls up quote values

## Operations Module Architecture

The Operations module manages construction project finances across 3 Django apps:

### Data Flow
```
ConstructionProject
  ├── ProjectZone (geographic zones like TAM, MTY)
  ├── ProjectSupplier (vendors with RFC)
  ├── ProjectTeamMember (roles: PM, Engineer, etc.)
  ├── CostCategory (P1-P10 direct, C1-C8 indirect)
  │   └── ImputationCode (budget lines: TAM-P4-17)
  ├── ImputationPeriod (weekly/fortnightly with Spanish labels)
  ├── ProjectExpense (invoice, payroll, provision)
  │   ├── ExpenseLine (line items)
  │   ├── ExpenseAttachment (file metadata)
  │   └── ClassificationLog (audit trail)
  └── ClientEstimate (billing to client)
```

### Key Business Logic
- **Auto-numbering**: Projects (PRY-YYYY-NNN), suppliers, estimates, imputation codes
- **Seed defaults**: `CostCategoryService.seed_default_categories()` creates 18 standard categories
- **Period generation**: `PeriodService.initialize_periods()` creates weekly/fortnightly periods from project dates with Spanish labels
- **Classification workflow**: Expenses can be classified/unclassified with full audit logging in ClassificationLog
- **Verification**: Independent verification status tracking per expense
- **Provision conversion**: Provisions can be converted to real expenses via `ProvisionService`
- **Auto-recalculation**: Adding/removing expense lines auto-recalculates expense totals

### Testing Pattern
- **Factory Boy** factories for all models (e.g., `ConstructionProjectFactory`, `ActiveProjectFactory`)
- Tests use `@pytest.mark.unit` and `@pytest.mark.workflow` markers
- All test files follow: `tests/factories.py`, `tests/test_models.py`, `tests/test_services.py`
- Run operations tests: `python -m pytest apps/projects/tests/ apps/budgets/tests/ apps/expenses/tests/ -v`

## Development Notes

- Entity names use CDS naming: lowercase, no underscores (e.g., `leadid`, `emailaddress1`)
- Follow the pattern in DATA_MODEL.md for field types and constraints
- State transitions should be validated in services layer
- All list endpoints must support filtering by `statecode`, `ownerid`, date ranges
- Use `select_related()`/`prefetch_related()` to avoid N+1 queries
- Return proper HTTP status codes (200, 201, 400, 404, 403)
- Operations module schemas accept nested bond objects (`ProjectBondDto`) but store them as flat fields in the model
- Direct imputation codes require a zone; indirect codes must NOT have a zone

## Reference Documentation

Full data model specification with all fields, enums, validations, and API contracts is in [DATA_MODEL.md](DATA_MODEL.md).
