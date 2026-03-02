# CRM Backend Foundation

**Microsoft Dynamics 365 CDS-Compatible CRM Backend**

A complete Django 5.0+ backend implementing Microsoft Dynamics 365 Common Data Service architecture with Django Ninja REST APIs. Full sales pipeline from Lead to Invoice with RBAC security, plus an **Operations module** for managing expenses and income of civil construction and mining companies.

## Features

### CRM Module
- 🔐 **Secure Authentication** - Session-based auth with 30-min timeout
- 👥 **RBAC System** - 5 predefined roles with entity-level permissions
- 💼 **Complete Sales Pipeline** - Lead → Opportunity → Quote → Order → Invoice
- 🚀 **Type-Safe APIs** - Django Ninja with automatic OpenAPI documentation (100+ endpoints)
- 📊 **CDS Data Model** - UUID primary keys, state/status patterns, audit trail
- 🏗️ **Four-Layer Architecture** - Models → Schemas → Services → Routers
- 🔍 **Advanced Filtering** - Query by state, owner, date ranges with pagination
- 💰 **Payment Tracking** - Partial and full payment recording on invoices

### Operations Module
- 🏗️ **Construction Project Management** - Full project lifecycle (Draft → Active → Completed)
- 📊 **Budget & Cost Structure** - Direct/indirect cost categories with imputation codes
- 💸 **Expense Management** - Multi-document expenses (invoices, payroll, provisions)
- 🏷️ **Expense Classification** - Assign imputation codes with full audit trail
- ✅ **Verification Workflow** - Independent expense verification tracking
- 📅 **Period Management** - Weekly/fortnightly periods with Spanish labels
- 📋 **Client Estimates** - Billing estimates with computed IVA totals
- 🔢 **Auto-numbering** - Projects (PRY-YYYY-NNN), suppliers, estimates, imputation codes

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
├── apps/               # Django applications (13 apps)
│   ├── users/          # User management & authentication
│   ├── leads/          # Lead management + qualification
│   ├── opportunities/  # Opportunity tracking + win/lose
│   ├── accounts/       # B2B companies/organizations
│   ├── contacts/       # B2C individuals
│   ├── quotes/         # Price proposals + line items
│   ├── orders/         # Sales orders + fulfillment
│   ├── invoices/       # Billing + payment tracking
│   ├── products/       # Product catalog (partial)
│   ├── activities/     # Email, calls, meetings (partial)
│   ├── projects/       # Construction project management (Operations)
│   ├── budgets/        # Budget & cost structure (Operations)
│   └── expenses/       # Expense management & classification (Operations)
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

## API Endpoints (100+)

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

### Operations Module - Projects
- `GET /api/projects` - List projects (with state/search/owner filters)
- `POST /api/projects` - Create project (auto-generates PRY-YYYY-NNN)
- `GET /api/projects/{id}` - Get project details
- `PATCH /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Soft delete (set to Canceled)
- `GET /api/projects/search/?q=` - Search by name/number/account
- `GET /api/projects/{id}/zones/` - List project zones
- `POST /api/projects/{id}/zones/` - Create zone
- `PATCH /api/zones/{id}` - Update zone
- `DELETE /api/zones/{id}` - Delete zone
- `GET /api/projects/{id}/suppliers/` - List project suppliers
- `POST /api/projects/{id}/suppliers/` - Add supplier (auto-numbering, RFC validation)
- `DELETE /api/suppliers/{id}` - Remove supplier
- `GET /api/projects/{id}/team-members/` - List team members
- `POST /api/projects/{id}/team-members/` - Add team member
- `PATCH /api/team-members/{id}` - Update team member
- `DELETE /api/team-members/{id}` - Remove team member

### Operations Module - Budgets
- `GET /api/categories/projects/{id}/categories/` - List cost categories
- `POST /api/categories/projects/{id}/categories/` - Create category or seed defaults (18 standard categories)
- `GET /api/codes/projects/{id}/codes/` - List imputation codes (filter by costtype, categoryid)
- `POST /api/codes/projects/{id}/codes/` - Create imputation code (auto-generates code string)
- `GET /api/codes/codes/{id}/` - Get imputation code
- `PATCH /api/codes/codes/{id}/` - Update imputation code
- `GET /api/periods/projects/{id}/periods/` - List periods
- `POST /api/periods/projects/{id}/periods/init/` - Initialize periods from project dates
- `POST /api/periods/projects/{id}/periods/extend/` - Extend periods by N months
- `PATCH /api/periods/periods/{id}/close/` - Close period
- `PATCH /api/periods/periods/{id}/reopen/` - Reopen period

### Operations Module - Expenses
- `GET /api/expenses/projects/{id}/expenses/` - List expenses (filter by period, type, status)
- `POST /api/expenses/projects/{id}/expenses/` - Create expense
- `GET /api/expenses/expenses/{id}/` - Get expense
- `PATCH /api/expenses/expenses/{id}/` - Update expense
- `PATCH /api/expenses/expenses/{id}/cancel/` - Cancel expense
- `POST /api/expenses/expenses/{id}/classify/` - Classify expense with imputation code
- `POST /api/expenses/expenses/bulk-classify/` - Bulk classify multiple expenses
- `POST /api/expenses/expenses/{id}/unclassify/` - Remove classification
- `PATCH /api/expenses/expenses/{id}/verify/` - Update verification status
- `POST /api/expenses/expenses/{id}/convert-provision/` - Convert provision to real expense
- `GET /api/expenses/projects/{id}/expenses/unclassified/` - List unclassified expenses
- `GET /api/expenses/projects/{id}/expenses/summary/` - Aggregate expense summary
- `GET /api/expense-lines/expenses/{id}/lines/` - List expense lines
- `POST /api/expense-lines/expenses/{id}/lines/` - Add line (auto-recalculates totals)
- `PATCH /api/expense-lines/expense-lines/{id}/` - Update line
- `DELETE /api/expense-lines/expense-lines/{id}/` - Delete line
- `GET /api/attachments/expenses/{id}/attachments/` - List attachments
- `POST /api/attachments/expenses/{id}/attachments/` - Add attachment
- `DELETE /api/attachments/attachments/{id}/` - Delete attachment
- `GET /api/expenses/expenses/{id}/logs/` - Classification audit logs
- `GET /api/estimates/projects/{id}/estimates/` - List client estimates
- `POST /api/estimates/projects/{id}/estimates/` - Create estimate (auto-numbering, computed IVA)
- `PATCH /api/estimates/estimates/{id}/` - Update estimate
- `DELETE /api/estimates/estimates/{id}/` - Cancel estimate

## Role-Based Access Control (RBAC)

The system implements 5 predefined security roles with different permission levels:

### System Administrator
- Full access to all entities (CRM + Operations)
- Can create/manage users
- Can modify any record
- Views all records across the organization

### Sales Manager
- Full access to sales entities (Leads, Opportunities, Quotes, Orders, Invoices)
- Full access to Operations module (projects, budgets, expenses, estimates)
- Can view all sales records (not filtered by ownership)
- Cannot create/manage users

**Example permissions:**
- ✅ Create/update/delete leads and opportunities
- ✅ View all team members' records
- ✅ Activate quotes and fulfill orders
- ✅ Full operations management (classify + verify expenses)
- ❌ Create or manage users

### Salesperson
- Can create and manage own sales records
- Can manage own operations projects, budgets, and expenses
- Limited delete permissions
- Records filtered by ownership (sees only own records)

**Example permissions:**
- ✅ Create/update own leads and opportunities
- ✅ Qualify leads and win opportunities
- ✅ Create quotes and orders
- ✅ Create/update own projects, budgets, expenses, estimates
- ✅ Classify expenses
- ❌ Delete leads, opportunities, projects, or expenses
- ❌ Verify expenses
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
- View-only access to all entities (CRM + Operations)
- Cannot create, update, or delete any records

**Example permissions:**
- ✅ View leads, opportunities, quotes, orders, invoices
- ✅ View projects, budgets, expenses, estimates (read-only)
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

### Run Tests

```bash
cd backend

# Run all tests
python -m pytest -v --no-cov

# Run CRM tests only
python -m pytest apps/leads/tests/ apps/opportunities/tests/ apps/accounts/tests/ -v --no-cov

# Run Operations module tests only (190 tests)
python -m pytest apps/projects/tests/ apps/budgets/tests/ apps/expenses/tests/ -v --no-cov

# Run by marker
python -m pytest -m unit -v --no-cov        # Unit tests only
python -m pytest -m workflow -v --no-cov     # Workflow tests only
```

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
- All 100+ API endpoints
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

## Operations Module Workflow

### Complete Flow: Project Setup → Expense Tracking

```
1. Create Project (PRY-2026-001)
   ├── Add Zones (TAM, MTY, CDMX)
   ├── Add Team Members (PM, Engineers)
   └── Add Suppliers (with RFC validation)

2. Setup Budget Structure
   ├── Seed Default Categories (18 standard: P1-P10 direct, C1-C8 indirect)
   ├── Create Imputation Codes (TAM-P4-1, C1-5, etc.)
   └── Initialize Periods (fortnightly with Spanish labels)

3. Track Expenses
   ├── Create Expenses (invoice, payroll, provision)
   ├── Add Lines (auto-recalculates totals)
   ├── Classify → Assign imputation code (audit logged)
   ├── Verify → Mark as verified/discrepant
   └── Convert Provisions → Real expenses

4. Client Estimates
   └── Create Estimates (auto-numbering, computed IVA)
```

### Example: Create and Classify an Expense

```bash
# 1. Create a project
POST /api/projects/
{
  "name": "Highway Bridge Project",
  "accountid": "uuid-of-account",
  "projecttype": 0,
  "biddingtype": 0,
  "startdate": "2026-01-01",
  "contractenddate": "2026-12-31"
}
# Returns: { "projectid": "...", "projectnumber": "PRY-2026-001", ... }

# 2. Seed default cost categories
POST /api/categories/projects/{project_id}/categories/
# Returns: 18 categories (P1-P10 direct + C1-C8 indirect)

# 3. Create an imputation code
POST /api/codes/projects/{project_id}/codes/
{
  "categoryid": "uuid-of-category-P4",
  "zoneid": "uuid-of-zone-TAM",
  "costtype": 0,
  "name": "Concrete Materials",
  "totalbudget": "500000.00"
}
# Returns: { "code": "TAM-P4-1", ... }

# 4. Create an expense
POST /api/expenses/projects/{project_id}/expenses/
{
  "documenttype": 0,
  "suppliername": "Cemex SA",
  "invoicenumber": "FAC-2026-001",
  "subtotal": "100000.00",
  "tax": "16000.00",
  "total": "116000.00",
  "periodid": "uuid-of-period"
}

# 5. Classify the expense
POST /api/expenses/expenses/{expense_id}/classify/
{
  "imputationcodeid": "uuid-of-code",
  "notes": "Concrete for bridge foundation"
}
```

## Technology Stack

- **Framework**: Django 5.0.1
- **API**: Django Ninja 1.1.0
- **Database**: PostgreSQL (production), SQLite (dev)
- **Server**: Gunicorn + Uvicorn
- **Testing**: pytest + pytest-django + Factory Boy
- **Date Utils**: python-dateutil (period generation)

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
