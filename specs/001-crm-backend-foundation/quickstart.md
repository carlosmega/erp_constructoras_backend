# Quick Start Guide: CRM Backend Foundation

**Feature**: 001-crm-backend-foundation
**Date**: 2025-11-27
**Audience**: Developers setting up the CRM backend for development or deployment

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.11+** (Python 3.12 recommended)
- **PostgreSQL 14+** (16 recommended for best UUID performance)
- **Git** (for version control)
- **pip** (Python package manager, comes with Python)
- **virtualenv** or **venv** (for Python virtual environments)

### Optional but Recommended

- **pgAdmin** or **psql** (PostgreSQL client for database management)
- **Postman** or **HTTPie** (API testing)
- **VS Code** or **PyCharm** (IDE with Python support)

---

## Quick Setup (5 Minutes)

For experienced developers who want to get running immediately:

```bash
# 1. Clone and navigate
git clone <repository-url>
cd CRM_Claude_Backend

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 5. Create database
createdb crm_backend  # Or use pgAdmin

# 6. Run migrations
python manage.py migrate

# 7. Seed security roles
# (Automatically done via migration 0002_seed_roles)

# 8. Create superuser
python manage.py createsuperuser

# 9. Run development server
python manage.py runserver

# 10. Access API documentation
# Open browser: http://localhost:8000/api/docs
```

---

## Detailed Setup Instructions

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd CRM_Claude_Backend
```

### Step 2: Create Virtual Environment

**macOS/Linux:**
```bash
python3.11 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` prefix in your terminal prompt.

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- Django 5.0+
- Django Ninja (REST API framework)
- psycopg (PostgreSQL adapter)
- python-decouple (environment configuration)
- pytest and testing tools

### Step 4: Configure Environment

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your settings:

```ini
# Database Configuration
DB_NAME=crm_backend
DB_USER=your_postgres_user
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

# Django Settings
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Session Configuration
SESSION_COOKIE_AGE=1800  # 30 minutes

# Security Settings (Development)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

**Generate a Secret Key** (if needed):
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 5: Create PostgreSQL Database

**Option A: Using psql (CLI)**
```bash
psql -U postgres
CREATE DATABASE crm_backend;
\q
```

**Option B: Using pgAdmin (GUI)**
1. Open pgAdmin
2. Right-click Databases → Create → Database
3. Name: `crm_backend`
4. Owner: Your PostgreSQL user
5. Save

### Step 6: Run Database Migrations

```bash
# Apply all migrations
python manage.py migrate

# Verify migrations applied
python manage.py showmigrations
```

This creates:
- `systemuser` table with UUID primary keys
- `securityrole` table
- Audit trail fields on all entities
- 5 predefined security roles (seeded automatically)

### Step 7: Create Initial Superuser

```bash
python manage.py createsuperuser
```

You'll be prompted for:
- **Email address**: Your email (used for login)
- **Full name**: Your display name
- **Password**: Strong password (min 8 chars)

The superuser is automatically assigned the "System Administrator" role.

### Step 8: Run Development Server

```bash
python manage.py runserver
```

Server starts at: `http://localhost:8000`

You should see:
```
System check identified no issues (0 silenced).
November 27, 2025 - 12:00:00
Django version 5.0.1, using settings 'crm.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

---

## Verify Installation

### 1. Access API Documentation

Open browser: **http://localhost:8000/api/docs**

You should see interactive Swagger UI with:
- **Users** endpoints (list, create, get, update, delete, assign-role)
- **Authentication** endpoints (login, logout, me, change-password)

### 2. Test Authentication (CLI)

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"emailaddress1": "your@email.com", "password": "yourpassword"}' \
  -c cookies.txt

# Response:
# {
#   "message": "Login successful",
#   "user": {
#     "systemuserid": "...",
#     "emailaddress1": "your@email.com",
#     "fullname": "Your Name",
#     "role_name": "System Administrator"
#   }
# }
```

**Get Current User:**
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -b cookies.txt

# Response: User info
```

**List Users:**
```bash
curl -X GET http://localhost:8000/api/users \
  -b cookies.txt

# Response: Paginated list of users
```

### 3. Access Django Admin Panel

Open browser: **http://localhost:8000/admin**

Login with your superuser credentials.

You can manage:
- System Users
- Security Roles
- View audit trails

---

## Project Structure Overview

```
backend/
├── crm/                      # Django project settings
│   ├── settings.py          # Configuration (uses .env)
│   ├── urls.py              # Root URL routing
│   └── wsgi.py / asgi.py    # Server entry points
│
├── apps/
│   └── users/               # User management app
│       ├── models.py        # SystemUser, SecurityRole
│       ├── schemas.py       # Django Ninja DTOs
│       ├── services.py      # Business logic
│       ├── routers.py       # API endpoints
│       └── migrations/      # Database migrations
│
├── core/                    # Shared utilities
│   ├── permissions.py       # RBAC implementation
│   ├── pagination.py        # Pagination helpers
│   ├── middleware.py        # Audit trail middleware
│   └── models.py            # AuditMixin base class
│
├── tests/                   # Integration & contract tests
│   ├── contract/
│   └── integration/
│
├── manage.py                # Django management command
├── requirements.txt         # Python dependencies
├── pytest.ini               # Test configuration
└── .env                     # Environment variables (not in git)
```

---

## Common Development Tasks

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov=core

# Run specific test file
pytest apps/users/tests/test_services.py

# Run with verbose output
pytest -v
```

### Database Management

**Create new migration:**
```bash
python manage.py makemigrations apps.users
```

**Apply migrations:**
```bash
python manage.py migrate
```

**Reset database** (⚠️ destroys all data):
```bash
python manage.py flush
```

**Open database shell:**
```bash
python manage.py dbshell
```

### Django Shell (REPL)

```bash
python manage.py shell
```

Example usage:
```python
from apps.users.models import SystemUser, SecurityRole

# Get all users
users = SystemUser.objects.all()

# Get specific role
admin_role = SecurityRole.objects.get(name='System Administrator')

# Create user programmatically
user = SystemUser.objects.create_user(
    emailaddress1='test@example.com',
    fullname='Test User',
    password='TestPassword123',
    securityroleid=admin_role
)
```

### View SQL Queries

```bash
# Enable query logging in settings.py (development only)
python manage.py runserver --settings=crm.settings_debug
```

Or use Django Debug Toolbar:
```bash
pip install django-debug-toolbar
# Add to INSTALLED_APPS and middleware
```

---

## API Usage Examples

### Authentication Flow

**1. Login**
```bash
POST /api/auth/login
{
  "emailaddress1": "user@example.com",
  "password": "SecurePassword123"
}

Response 200:
{
  "message": "Login successful",
  "user": {
    "systemuserid": "550e8400-e29b-41d4-a716-446655440000",
    "emailaddress1": "user@example.com",
    "fullname": "John Doe",
    "role_name": "Salesperson"
  }
}
```

**2. Create User (Admin Only)**
```bash
POST /api/users
{
  "emailaddress1": "newuser@example.com",
  "fullname": "Jane Smith",
  "password": "SecurePassword456",
  "securityroleid": "660e8400-e29b-41d4-a716-446655440001"
}

Response 201:
{
  "systemuserid": "770e8400-e29b-41d4-a716-446655440002",
  "emailaddress1": "newuser@example.com",
  "fullname": "Jane Smith",
  "isdisabled": false,
  "role_name": "Salesperson",
  "createdon": "2025-11-27T12:00:00Z",
  ...
}
```

**3. List Users with Filtering**
```bash
GET /api/users?role=Salesperson&isdisabled=false&page=1&page_size=50

Response 200:
{
  "count": 25,
  "next": "http://localhost:8000/api/users?page=2",
  "previous": null,
  "results": [...]
}
```

**4. Update User**
```bash
PATCH /api/users/770e8400-e29b-41d4-a716-446655440002
{
  "fullname": "Jane Smith-Johnson"
}

Response 200: {updated user object}
```

**5. Assign Role**
```bash
POST /api/users/770e8400-e29b-41d4-a716-446655440002/assign-role
{
  "securityroleid": "880e8400-e29b-41d4-a716-446655440003"
}

Response 200: {user with new role}
```

---

## Troubleshooting

### Database Connection Errors

**Error**: `django.db.utils.OperationalError: could not connect to server`

**Solutions**:
1. Verify PostgreSQL is running: `pg_ctl status`
2. Check `.env` credentials match PostgreSQL settings
3. Ensure database exists: `psql -l`
4. Verify PostgreSQL accepts connections on configured port

### Migration Errors

**Error**: `django.db.migrations.exceptions.InconsistentMigrationHistory`

**Solutions**:
1. Delete database and recreate: `dropdb crm_backend && createdb crm_backend`
2. Run migrations again: `python manage.py migrate`

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'django'`

**Solutions**:
1. Ensure virtual environment is activated: `source venv/bin/activate`
2. Reinstall dependencies: `pip install -r requirements.txt`

### Session/Authentication Issues

**Error**: `CSRF Failed: CSRF token missing or incorrect`

**Solutions**:
1. Ensure CSRF middleware is enabled in settings
2. Include CSRF token in requests (auto-handled in Swagger UI)
3. For API clients, use session-based auth with cookies

---

## Production Deployment Notes

**⚠️ For production, modify `.env`:**

```ini
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Enable HTTPS
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Use strong secret key
SECRET_KEY=<generate-new-strong-key>

# PostgreSQL (production instance)
DB_HOST=your-production-db.rds.amazonaws.com
DB_NAME=crm_production
DB_USER=crm_user
DB_PASSWORD=<strong-password>
```

**Production Server:**
```bash
# Collect static files
python manage.py collectstatic

# Run with gunicorn + uvicorn
gunicorn crm.asgi:application -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --access-logfile - \
  --error-logfile -
```

---

## Next Steps

1. **Implement remaining CRM entities** (Lead, Account, Contact, Opportunity)
2. **Add comprehensive tests** for authentication and RBAC
3. **Configure CI/CD pipeline** for automated testing and deployment
4. **Set up monitoring and logging** for production

## Support

For issues or questions:
- Check [data-model.md](data-model.md) for entity details
- Review [contracts/](contracts/) for API specifications
- Consult [research.md](research.md) for architectural decisions
