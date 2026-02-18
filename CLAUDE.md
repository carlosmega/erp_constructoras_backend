# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a CRM backend built with **Django 5.0+ and Django Ninja**, following the **Microsoft Dynamics 365 Sales (Common Data Service)** data model. The system implements a complete sales pipeline with activities, product catalog, and RBAC security.

## Technology Stack

- **Django 5.0+** - ORM and base structure
- **Django Ninja** - Modern typed API (alternative to DRF)
- **PostgreSQL** - Primary database (UUID, JSONB support required)
- **django-filter** - Advanced filtering
- **django-extensions** - Development utilities
- **python-decouple** - Environment configuration
- **gunicorn** + **uvicorn** - ASGI/WSGI server
- **Celery** (optional) - Async tasks (email sending, PDF generation)

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
│   └── audit/
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

### Security Model (RBAC)

System implements 5 predefined roles:
1. **System Administrator**: Full access
2. **Sales Manager**: Manage sales team, view all opportunities
3. **Salesperson**: Manage own leads/opportunities
4. **Marketing User**: Manage campaigns and leads
5. **Read-Only User**: View-only access

Permissions are entity-level (Create, Read, Update, Delete) with record-level ownership filters.

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

## Development Notes

- Entity names use CDS naming: lowercase, no underscores (e.g., `leadid`, `emailaddress1`)
- Follow the pattern in DATA_MODEL.md for field types and constraints
- State transitions should be validated in services layer
- All list endpoints must support filtering by `statecode`, `ownerid`, date ranges
- Use `select_related()`/`prefetch_related()` to avoid N+1 queries
- Return proper HTTP status codes (200, 201, 400, 404, 403)

## Reference Documentation

Full data model specification with all fields, enums, validations, and API contracts is in [DATA_MODEL.md](DATA_MODEL.md).
