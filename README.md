# CRM Backend Foundation

**Microsoft Dynamics 365 CDS-Compatible CRM Backend**

A complete Django 5.0+ backend implementing Microsoft Dynamics 365 Common Data Service architecture with Django Ninja REST APIs. Full sales pipeline from Lead to Invoice with RBAC security.

## Features

- 🔐 **Secure Authentication** - Session-based auth with 30-min timeout
- 👥 **RBAC System** - 5 predefined roles with entity-level permissions
- 💼 **Complete Sales Pipeline** - Lead → Opportunity → Quote → Order → Invoice
- 🚀 **Type-Safe APIs** - Django Ninja with automatic OpenAPI documentation (68+ endpoints)
- 📊 **CDS Data Model** - UUID primary keys, state/status patterns, audit trail
- 🏗️ **Four-Layer Architecture** - Models → Schemas → Services → Routers
- 🔍 **Advanced Filtering** - Query by state, owner, date ranges with pagination
- 💰 **Payment Tracking** - Partial and full payment recording on invoices

## Quick Start

### Automated Setup (Recommended)

Run the automated setup script from the project root:

**Windows (Batch):**
```cmd
setup.bat
```

**Windows (PowerShell):**
```powershell
.\setup.ps1
```

This will create your virtual environment, install dependencies, and create the `.env` configuration file.

### Manual Setup

For detailed setup instructions, troubleshooting, and manual configuration, see **[SETUP.md](SETUP.md)**.

### Quick Commands

```bash
# Navigate to backend directory
cd backend

# Activate virtual environment (Windows)
venv\Scripts\activate

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Access

- **API Documentation**: http://localhost:8000/api/docs
- **Django Admin**: http://localhost:8000/admin

## Project Structure

```
backend/
├── crm/                 # Django project settings
│   ├── settings.py     # Configuration
│   ├── urls.py         # URL routing + API registration
│   └── wsgi.py         # WSGI entry point
├── apps/               # Django applications (10 apps)
│   ├── users/          # User management & authentication
│   ├── leads/          # Lead management + qualification
│   ├── opportunities/  # Opportunity tracking + win/lose
│   ├── accounts/       # B2B companies/organizations
│   ├── contacts/       # B2C individuals
│   ├── quotes/         # Price proposals + line items
│   ├── orders/         # Sales orders + fulfillment
│   ├── invoices/       # Billing + payment tracking
│   ├── products/       # Product catalog (partial)
│   └── activities/     # Email, calls, meetings (partial)
├── core/               # Shared utilities
│   ├── models.py       # AuditMixin base class
│   ├── permissions.py  # RBAC implementation
│   ├── pagination.py   # Pagination utilities
│   ├── middleware.py   # Audit trail middleware
│   └── exceptions.py   # Custom exceptions
└── manage.py           # Django management script
```

## Architecture Principles

### Data Model Fidelity (Dynamics CDS)
- UUID primary keys on all entities
- CDS naming conventions (lowercase, no underscores)
- State + Status dual tracking
- Audit trail on all business records

### Four-Layer Architecture
1. **Models** (`models.py`) - Django ORM entities
2. **Schemas** (`schemas.py`) - Django Ninja DTOs
3. **Services** (`services.py`) - Business logic
4. **Routers** (`routers.py`) - API endpoints

### Security
- Session-based authentication
- 30-minute timeout
- Account lockout after 3 failed attempts
- Entity-level and record-level permissions

## Sales Pipeline Workflow

### Complete Flow: Lead → Invoice

```
Lead (Open)
    ↓ [Qualify]
Opportunity (Open)
    ↓ [Create Quote]
Quote (Draft → Active → Won)
    ↓ [Create Order]
Order (Submitted → Fulfilled)
    ↓ [Create Invoice]
Invoice (Active → Paid)
```

### Step-by-Step Example

#### 1. Create and Qualify a Lead

```bash
# Create lead
POST /api/leads/
{
  "firstname": "John",
  "lastname": "Smith",
  "companyname": "Acme Corp",
  "emailaddress1": "john@acme.com",
  "subject": "Interested in CRM solution"
}

# Qualify lead (creates Account, Contact, Opportunity)
POST /api/leads/{lead_id}/qualify
{
  "create_account": true,
  "create_contact": true,
  "create_opportunity": true
}
```

#### 2. Win the Opportunity

```bash
# Update opportunity
PATCH /api/opportunities/{opp_id}
{
  "estimatedvalue": "50000.00",
  "estimatedclosedate": "2025-12-31"
}

# Win opportunity
POST /api/opportunities/{opp_id}/win
{
  "actualrevenue": "50000.00",
  "closedate": "2025-12-15"
}
```

#### 3. Create and Activate Quote

```bash
# Create quote from opportunity
POST /api/quotes/from-opportunity/{opp_id}

# Add line items
POST /api/quotes/{quote_id}/details
{
  "productname": "CRM Enterprise License",
  "quantity": 100,
  "priceperunit": 500.00,
  "tax": 8000.00
}

# Activate quote
POST /api/quotes/{quote_id}/activate
{
  "effective_from": "2025-12-01",
  "effective_to": "2026-02-28"
}

# Mark quote as won
POST /api/quotes/{quote_id}/close
{
  "statuscode": 3
}
```

#### 4. Create and Fulfill Order

```bash
# Create order from won quote
POST /api/orders/from-quote/{quote_id}

# Submit order
POST /api/orders/{order_id}/submit

# Fulfill order
POST /api/orders/{order_id}/fulfill
{
  "date_fulfilled": "2025-12-20"
}
```

#### 5. Invoice and Payment

```bash
# Create invoice from fulfilled order
POST /api/invoices/from-order/{order_id}

# Record partial payment
POST /api/invoices/{invoice_id}/record-payment
{
  "payment_amount": 25000.00,
  "payment_date": "2025-12-25"
}

# Record final payment
POST /api/invoices/{invoice_id}/record-payment
{
  "payment_amount": 25000.00,
  "payment_date": "2026-01-15"
}
```

## API Endpoints (68+)

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Current user info
- `POST /api/auth/change-password` - Change password

### User Management
- `GET /api/users` - List users
- `POST /api/users` - Create user (Admin only)
- `GET /api/users/{id}` - Get user details
- `PATCH /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Deactivate user
- `POST /api/users/{id}/assign-role` - Assign security role

### Leads
- `GET /api/leads` - List leads
- `POST /api/leads` - Create lead
- `GET /api/leads/{id}` - Get lead
- `PATCH /api/leads/{id}` - Update lead
- `DELETE /api/leads/{id}` - Delete lead
- `POST /api/leads/{id}/qualify` - Qualify lead → Create opportunity

### Opportunities
- `GET /api/opportunities` - List opportunities
- `POST /api/opportunities` - Create opportunity
- `GET /api/opportunities/{id}` - Get opportunity
- `PATCH /api/opportunities/{id}` - Update opportunity
- `DELETE /api/opportunities/{id}` - Delete opportunity
- `POST /api/opportunities/{id}/win` - Mark as won
- `POST /api/opportunities/{id}/lose` - Mark as lost

### Accounts & Contacts
- `GET /api/accounts` - List accounts
- `POST /api/accounts` - Create account
- `GET /api/accounts/{id}` - Get account
- `PATCH /api/accounts/{id}` - Update account
- `GET /api/contacts` - List contacts
- `POST /api/contacts` - Create contact
- `GET /api/contacts/{id}` - Get contact

### Quotes
- `GET /api/quotes` - List quotes
- `POST /api/quotes` - Create quote
- `POST /api/quotes/from-opportunity/{id}` - Create from opportunity
- `GET /api/quotes/{id}` - Get quote
- `PATCH /api/quotes/{id}` - Update quote
- `POST /api/quotes/{id}/activate` - Activate quote
- `POST /api/quotes/{id}/close` - Close quote (won/lost)
- `POST /api/quotes/{id}/details` - Add line item
- `GET /api/quotes/{id}/details` - List line items

### Orders
- `GET /api/orders` - List orders
- `POST /api/orders/from-quote/{id}` - Create from won quote
- `GET /api/orders/{id}` - Get order
- `PATCH /api/orders/{id}` - Update order
- `POST /api/orders/{id}/submit` - Submit order
- `POST /api/orders/{id}/fulfill` - Fulfill order
- `POST /api/orders/{id}/cancel` - Cancel order

### Invoices
- `GET /api/invoices` - List invoices
- `POST /api/invoices/from-order/{id}` - Create from fulfilled order
- `GET /api/invoices/{id}` - Get invoice
- `POST /api/invoices/{id}/record-payment` - Record payment
- `POST /api/invoices/{id}/cancel` - Cancel invoice

## Role-Based Access Control (RBAC)

The system implements 5 predefined security roles with different permission levels:

### System Administrator
- Full access to all entities
- Can create/manage users
- Can modify any record
- Views all records across the organization

### Sales Manager
- Full access to sales entities (Leads, Opportunities, Quotes, Orders, Invoices)
- Can view all sales records (not filtered by ownership)
- Cannot create/manage users
- Can read product catalog

**Example permissions:**
- ✅ Create/update/delete leads and opportunities
- ✅ View all team members' records
- ✅ Activate quotes and fulfill orders
- ❌ Create or manage users

### Salesperson
- Can create and manage own sales records
- Limited delete permissions
- Records filtered by ownership (sees only own records)

**Example permissions:**
- ✅ Create/update own leads and opportunities
- ✅ Qualify leads and win opportunities
- ✅ Create quotes and orders
- ❌ Delete leads or opportunities
- ❌ View other salespeople's records

### Marketing User
- Limited to leads and campaigns
- Can create and update contacts
- Read-only access to accounts

**Example permissions:**
- ✅ Create/update leads
- ✅ Create/update contacts
- ✅ View accounts (read-only)
- ❌ Create opportunities
- ❌ Access quotes or orders

### Read-Only User
- View-only access to all entities
- Cannot create, update, or delete any records

**Example permissions:**
- ✅ View leads, opportunities, quotes, orders, invoices
- ❌ Create any records
- ❌ Update any records
- ❌ Delete any records

### Testing Permissions

```bash
# Login as different roles
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"emailaddress1": "salesperson@crm.com", "password": "password123"}'

# Try to create a lead (should succeed for Salesperson)
curl -X POST http://localhost:8000/api/leads/ \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=xxx" \
  -d '{"firstname": "Test", "lastname": "Lead", "companyname": "Test Co"}'

# Try to create a user (should fail with 403 for Salesperson)
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=xxx" \
  -d '{"emailaddress1": "test@test.com", "fullname": "Test"}'
# Expected: {"detail": "You don't have permission...", "code": "permission_denied", "status": 403}
```

## Testing & Development

### Load Dummy Data

The system includes a comprehensive dummy data generator:

```bash
cd backend
python manage.py load_dummy_data --clear
```

This creates:
- 5 users (1 admin, 1 sales manager, 2 salespeople, 1 marketing user)
- 5 accounts and 8 contacts
- 5 leads (various states)
- 6 opportunities (open and won)
- 4 quotes (draft, active, won)
- 2 orders (submitted, fulfilled)
- 1 invoice (with partial payment)

### Testing with Postman

Import the Postman collection: `CRM-Backend-Collection.json`

The collection includes:
- All 68+ API endpoints
- Pre-configured environment variables
- Auto-saving of IDs (lead_id, opportunity_id, quote_id, etc.)
- Example workflows for complete sales pipeline

### Create Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Django Shell

```bash
python manage.py shell
```

### Check Permissions

```python
from apps.users.models import SystemUser
from core.permissions import has_permission, Permission

user = SystemUser.objects.get(emailaddress1='salesperson@crm.com')
has_permission(user, Permission.LEAD_CREATE)  # True
has_permission(user, Permission.USER_CREATE)  # False
```

## Technology Stack

- **Framework**: Django 5.0.1
- **API**: Django Ninja 1.1.0
- **Database**: PostgreSQL (production), SQLite (dev)
- **Server**: Gunicorn + Uvicorn
- **Testing**: pytest + pytest-django

## Documentation

- **Specification**: `specs/001-crm-backend-foundation/spec.md`
- **Implementation Plan**: `specs/001-crm-backend-foundation/plan.md`
- **Data Model**: `specs/001-crm-backend-foundation/data-model.md`
- **API Contracts**: `specs/001-crm-backend-foundation/contracts/`
- **Quick Start Guide**: `specs/001-crm-backend-foundation/quickstart.md`

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
