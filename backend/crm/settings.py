"""
Django settings for CRM Backend Foundation project.

Generated for feature: 001-crm-backend-foundation
Following Microsoft Dynamics 365 CDS architecture patterns.
"""

import os
from pathlib import Path
from decouple import config, Csv
import dj_database_url

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-CHANGE-THIS-IN-PRODUCTION')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

# Dev-only auto-login (DevAutoLoginMiddleware). Defaults to False so production
# fails CLOSED even if DEBUG is accidentally left True. Enable explicitly in local
# dev via DEV_AUTOLOGIN=true in .env.
DEV_AUTOLOGIN = config('DEV_AUTOLOGIN', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',  # PostgreSQL-specific features

    # Third-party apps
    'corsheaders',  # CORS headers for frontend integration
    'ninja',  # Django Ninja REST framework
    'django_filters',  # Advanced filtering

    # Project apps
    'apps.users',  # User management and authentication (will be added in Phase 2)
    'apps.leads',  # Lead management (Phase 5)
    'apps.opportunities',  # Opportunity management (Phase 6)
    'apps.accounts',  # Account management (Phase 7)
    'apps.contacts',  # Contact management (Phase 7)
    'apps.quotes',  # Quote management (Phase 8)
    'apps.orders',  # Order management (Phase 9)
    'apps.invoices',  # Invoice management (Phase 10)
    'apps.products',  # Product catalog (Phase 11)
    'apps.activities',  # Activity management (Phase 12)
    'apps.cases',  # Case management (Phase 13)
    'apps.notifications',  # Notification system
    'apps.graph',  # Microsoft Graph integration (Office 365 email sync)
    'apps.projects',  # Construction project management (Operations module)
    'apps.budgets',  # Budget & cost structure (Operations module)
    'apps.expenses',  # Expense management & classification (Operations module)
    'apps.invoiceinbox',  # Invoice email inbox (Operations module)
    'apps.proyeccion',  # Budget estimation / proyección (Operations module)
    'apps.corporate',  # Corporate headquarters budget & allocation (Operations module)
    'apps.machinery',  # Machinery & equipment management (Operations module)
    'apps.hrpayroll',  # HR & Payroll module (employees, payroll, attendance)
    'apps.audit',  # Audit trail (cross-entity change tracking)
    'apps.agents',  # AI-powered agents (scoring, classification, alerts, forecasting)
    'core',  # Shared utilities
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS - Must be before CommonMiddleware
    'core.middleware.ApiTrailingSlashMiddleware',  # Rewrite mutation URLs for trailing slash
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.DevAutoLoginMiddleware',  # Auto-login admin in DEBUG mode
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.AuditMiddleware',  # Custom audit trail middleware (will be added in Phase 2)
]

ROOT_URLCONF = 'crm.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'crm.wsgi.application'

# ============================================================================
# Database
# ============================================================================
# Priority order:
#   1. DATABASE_URL (Railway/Heroku-style — auto-injected by Railway Postgres plugin)
#   2. Individual DB_* env vars (local dev with PostgreSQL)
#   3. SQLite fallback (local dev without Postgres installed)
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=config('DB_SSL_REQUIRE', default=False, cast=bool),
        )
    }
    DATABASES['default']['ATOMIC_REQUESTS'] = True
elif config('DB_NAME', default=''):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'ATOMIC_REQUESTS': True,
            'CONN_MAX_AGE': 600,
        }
    }
else:
    # SQLite fallback for local dev without Postgres
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'ATOMIC_REQUESTS': True,
            'OPTIONS': {
                'timeout': 30,
                'check_same_thread': False,
            }
        }
    }

    # Enable WAL mode for SQLite — allows concurrent reads during writes
    from django.db.backends.signals import connection_created

    def _enable_wal_mode(sender, connection, **kwargs):
        if connection.vendor == 'sqlite':
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA busy_timeout=30000;')

    connection_created.connect(_enable_wal_mode)

# Custom User Model (Dynamics CDS SystemUser)
AUTH_USER_MODEL = 'users.SystemUser'  # Will be configured in Phase 3

# Authentication Backends
# Custom backend that properly loads securityroleid relationship
AUTHENTICATION_BACKENDS = [
    'apps.users.backends.SystemUserBackend',  # Custom backend for SystemUser
]

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,  # NIST guidelines
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Session Configuration
# 30-minute timeout as per specification (FR-004)
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=1800, cast=int)  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True  # Reset timeout on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)  # HTTPS only in production

# ============================================================================
# Cache (Redis) + Sessions backend
# ============================================================================
REDIS_URL = config('REDIS_URL', default='')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,  # Fail open on Redis outage
            },
            'KEY_PREFIX': 'crm',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
    SESSION_CACHE_ALIAS = 'default'
    DJANGO_REDIS_IGNORE_EXCEPTIONS = True
else:
    # In-memory cache for local dev when Redis is not running
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'crm-default',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'  # All timestamps in UTC per design doc
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Whitenoise — use manifest storage only in production (requires collectstatic).
# In dev/test, the manifest doesn't exist so we fall back to plain StaticFilesStorage.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
            if not DEBUG
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

# Media files (user uploads)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security Settings
# Production values should be set via environment variables
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)

# Trust the X-Forwarded-Proto header from Railway's edge proxy (HTTPS termination)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ============================================================================
# CORS Configuration for Frontend Integration (Next.js, React, etc.)
# ============================================================================

# Allowed origins for CORS (development defaults to localhost:3000)
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001',
    cast=Csv()
)

# Allow cookies/sessions in cross-origin requests
CORS_ALLOW_CREDENTIALS = True

# Allowed headers
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Allowed HTTP methods
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# CSRF trusted origins (must match CORS origins)
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=Csv()
)

# Exempt Django Ninja API routes from CSRF (API uses session auth instead)
CSRF_EXEMPT_URLS = ['/api/']

# Cookie settings for cross-origin requests.
# When frontend and backend are on different sites (e.g. sibling subdomains under
# *.up.railway.app, which is on the Public Suffix List), the browser treats fetch
# requests as cross-site and refuses to attach SameSite=Lax cookies — Django then
# sees an anonymous user and returns 403. Set CROSS_SITE_COOKIES=True in that case;
# the browser also requires Secure=True when SameSite=None.
_CROSS_SITE_COOKIES = config('CROSS_SITE_COOKIES', default=False, cast=bool)

SESSION_COOKIE_SAMESITE = 'None' if _CROSS_SITE_COOKIES else 'Lax'
CSRF_COOKIE_SAMESITE = 'None' if _CROSS_SITE_COOKIES else 'Lax'

if _CROSS_SITE_COOKIES:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

CSRF_COOKIE_HTTPONLY = False  # Must be False so JavaScript can read it

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'crm_backend.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': True,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# ============================================================================
# Email Configuration
# ============================================================================

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='CRM Sales <noreply@example.com>')
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=30, cast=int)

# ============================================================================
# Microsoft Graph Integration (Office 365 Email Sync)
# ============================================================================

MICROSOFT_CLIENT_ID = config('MICROSOFT_CLIENT_ID', default='')
MICROSOFT_CLIENT_SECRET = config('MICROSOFT_CLIENT_SECRET', default='')
MICROSOFT_TENANT_ID = config('MICROSOFT_TENANT_ID', default='')
MICROSOFT_REDIRECT_URI = config('MICROSOFT_REDIRECT_URI', default='http://localhost:8000/api/graph/callback')
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')
