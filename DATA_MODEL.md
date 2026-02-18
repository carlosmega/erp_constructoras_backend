# Modelo de Datos - CRM Frontend

> **Documentación completa del modelo de datos basado en Microsoft Dynamics 365 Sales (CDS)**
>
> Este documento describe todas las entidades, relaciones y estructuras de datos que el backend debe implementar.

---

## 📋 Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Guía para Implementación Django + Ninja](#guía-para-implementación-django--ninja)
3. [Entidades Principales](#entidades-principales)
4. [Entidades de Catálogo](#entidades-de-catálogo)
5. [Entidades de Actividades](#entidades-de-actividades)
6. [Entidades Avanzadas](#entidades-avanzadas)
7. [Entidades de Seguridad](#entidades-de-seguridad)
8. [Relaciones entre Entidades](#relaciones-entre-entidades)
9. [Enumeraciones (Enums)](#enumeraciones-enums)
10. [Flujos de Negocio](#flujos-de-negocio)
11. [API Contracts](#api-contracts)
12. [Campos de Auditoría](#campos-de-auditoría)
13. [Validaciones y Reglas de Negocio](#validaciones-y-reglas-de-negocio)
14. [Recomendaciones de Base de Datos](#recomendaciones-de-base-de-datos)

---

## 🎯 Resumen Ejecutivo

Este construido siguiendo el modelo de datos de **Microsoft Dynamics 365 Sales**, utilizando el estándar CDS (Common Data Service). El sistema maneja:

- **Pipeline de Ventas**: Lead → Opportunity → Quote → Order → Invoice
- **Gestión de Clientes**: Account (B2B) y Contact (B2C/personas)
- **Catálogo de Productos**: Products con Price Lists
- **Actividades**: Email, Phone Call, Task, Appointment
- **Seguridad**: RBAC con 5 roles, Audit Logging, Record Ownership

### Características Clave

- **Relaciones Polimórficas**: `customerid` puede ser Account o Contact
- **Estados y Status**: Todos los registros usan `statecode` + `statuscode`
- **Ownership**: Todos los registros tienen `ownerid` (usuario asignado)
- **Campos Computados**: Muchos totales se calculan automáticamente
- **Audit Trail**: Todas las operaciones CRUD se registran

---

## 🐍 Guía para Implementación Django + Ninja

### Arquitectura Backend Recomendada

```
backend/
├── crm/                          # Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── leads/
│   │   ├── models.py            # Lead, LeadStateCode (choices)
│   │   ├── schemas.py           # Ninja schemas (DTOs)
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
    ├── permissions.py           # RBAC
    ├── pagination.py            # DRF pagination
    └── exceptions.py            # Custom exceptions
```

### Stack Recomendado

- **Django 5.0+** - ORM y estructura base
- **Django Ninja** - API moderna y tipada (alternativa a DRF)
- **PostgreSQL** - Base de datos principal (soporte UUID, JSONB)
- **django-filter** - Filtrado avanzado
- **django-extensions** - Utilidades de desarrollo
- **python-decouple** - Configuración de entorno
- **gunicorn** + **uvicorn** - Servidor ASGI/WSGI
- **Celery** (opcional) - Tareas asíncronas (envío de emails, generación de PDFs)

### Patrón de Implementación por Entidad

Para cada entidad CDS, seguir este patrón:

#### 1. **models.py** - Django Model

```python
from django.db import models
import uuid

class Lead(models.Model):
    """CDS Lead entity - Cliente Potencial"""

    # Primary Key (UUID en vez de auto-increment)
    leadid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # State & Status (usar IntegerChoices)
    class StateCode(models.IntegerChoices):
        OPEN = 0, 'Open'
        QUALIFIED = 1, 'Qualified'
        DISQUALIFIED = 2, 'Disqualified'

    class StatusCode(models.IntegerChoices):
        NEW = 1, 'New'
        CONTACTED = 2, 'Contacted'
        QUALIFIED = 3, 'Qualified'
        DISQUALIFIED = 4, 'Disqualified'

    statecode = models.IntegerField(
        choices=StateCode.choices,
        default=StateCode.OPEN,
        db_index=True  # Índice para filtrado rápido
    )
    statuscode = models.IntegerField(
        choices=StatusCode.choices,
        default=StatusCode.NEW
    )

    # Basic Information
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    companyname = models.CharField(max_length=200, null=True, blank=True)

    # Relaciones (ForeignKey con UUID)
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,  # No permitir eliminar usuario con leads asignados
        related_name='leads',
        db_column='ownerid'
    )

    # Audit Fields (auto_now para modifiedon)
    createdon = models.DateTimeField(auto_now_add=True)
    modifiedon = models.DateTimeField(auto_now=True)
    createdby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='leads_created'
    )
    modifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='leads_modified'
    )

    class Meta:
        db_table = 'lead'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode', 'createdon']),
            models.Index(fields=['ownerid', 'statecode']),
        ]

    def __str__(self):
        return f"{self.firstname} {self.lastname}"
```

#### 2. **schemas.py** - Ninja Schemas (DTOs)

```python
from ninja import Schema, ModelSchema
from pydantic import Field, validator
from datetime import datetime
from typing import Optional
import uuid

# Response Schema (full entity)
class LeadSchema(ModelSchema):
    """Lead response schema - matches TypeScript Lead interface"""

    leadid: uuid.UUID
    statecode: int
    statuscode: int
    firstname: str
    lastname: str
    fullname: Optional[str] = None  # Computed field
    companyname: Optional[str] = None
    emailaddress1: Optional[str] = None

    createdon: datetime
    modifiedon: datetime

    class Config:
        model = Lead
        model_fields = '__all__'

    @staticmethod
    def resolve_fullname(obj):
        """Computed field: firstname + lastname"""
        return f"{obj.firstname} {obj.lastname}"

# Create DTO
class CreateLeadDto(Schema):
    """DTO for creating Lead - matches TypeScript CreateLeadDto"""

    firstname: str = Field(..., min_length=1, max_length=100)
    lastname: str = Field(..., min_length=1, max_length=100)
    companyname: Optional[str] = Field(None, max_length=200)
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None
    leadsourcecode: int = Field(..., ge=1, le=10)  # Enum validation
    ownerid: uuid.UUID

    @validator('emailaddress1')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email address')
        return v

# Update DTO
class UpdateLeadDto(Schema):
    """DTO for updating Lead - all fields optional"""

    firstname: Optional[str] = Field(None, min_length=1)
    lastname: Optional[str] = Field(None, min_length=1)
    companyname: Optional[str] = None
    emailaddress1: Optional[str] = None
    # ... otros campos

# Qualify DTO
class QualifyLeadDto(Schema):
    """DTO for lead qualification - matches TypeScript QualifyLeadDto"""

    createAccount: bool
    existingAccountId: Optional[uuid.UUID] = None
    createContact: bool
    existingContactId: Optional[uuid.UUID] = None
    opportunityName: str
    estimatedValue: float = Field(..., gt=0)
    estimatedCloseDate: datetime
    description: Optional[str] = None

class QualifyLeadResponse(Schema):
    """Response after qualifying lead"""

    leadId: uuid.UUID
    accountId: Optional[uuid.UUID] = None
    contactId: uuid.UUID
    opportunityId: uuid.UUID
    account: Optional[dict] = None  # AccountSchema
    contact: dict  # ContactSchema
    opportunity: dict  # OpportunitySchema
```

#### 3. **routers.py** - API Endpoints

```python
from ninja import Router
from ninja.pagination import paginate
from typing import List
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import Lead
from .schemas import LeadSchema, CreateLeadDto, UpdateLeadDto, QualifyLeadDto, QualifyLeadResponse
from .services import LeadService
from core.permissions import require_permission
from core.pagination import CustomPagination

router = Router(tags=["Leads"])

@router.get("/", response=List[LeadSchema])
@paginate(CustomPagination)
@require_permission('leads.view_lead')
def list_leads(request, statecode: int = None, ownerid: str = None):
    """
    GET /api/leads
    Lista todos los leads con filtros opcionales
    """
    queryset = Lead.objects.select_related('ownerid', 'createdby')

    if statecode is not None:
        queryset = queryset.filter(statecode=statecode)

    if ownerid:
        queryset = queryset.filter(ownerid=ownerid)

    return queryset

@router.get("/{leadid}", response=LeadSchema)
@require_permission('leads.view_lead')
def get_lead(request, leadid: uuid.UUID):
    """
    GET /api/leads/{id}
    Obtiene un lead por ID
    """
    return get_object_or_404(Lead, leadid=leadid)

@router.post("/", response=LeadSchema)
@require_permission('leads.add_lead')
def create_lead(request, payload: CreateLeadDto):
    """
    POST /api/leads
    Crea un nuevo lead
    """
    lead = Lead.objects.create(
        **payload.dict(),
        createdby=request.user,
        modifiedby=request.user
    )
    return lead

@router.patch("/{leadid}", response=LeadSchema)
@require_permission('leads.change_lead')
def update_lead(request, leadid: uuid.UUID, payload: UpdateLeadDto):
    """
    PATCH /api/leads/{id}
    Actualiza un lead existente
    """
    lead = get_object_or_404(Lead, leadid=leadid)

    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(lead, attr, value)

    lead.modifiedby = request.user
    lead.save()

    return lead

@router.delete("/{leadid}")
@require_permission('leads.delete_lead')
def delete_lead(request, leadid: uuid.UUID):
    """
    DELETE /api/leads/{id}
    Elimina un lead
    """
    lead = get_object_or_404(Lead, leadid=leadid)
    lead.delete()
    return {"success": True}

@router.post("/{leadid}/qualify", response=QualifyLeadResponse)
@require_permission('leads.qualify_lead')
@transaction.atomic
def qualify_lead(request, leadid: uuid.UUID, payload: QualifyLeadDto):
    """
    POST /api/leads/{id}/qualify
    Califica un lead (convierte a Account/Contact/Opportunity)

    CRITICAL: Este es un flujo complejo que debe ser atómico (transacción)
    """
    lead = get_object_or_404(Lead, leadid=leadid)

    # Validar estado
    if lead.statecode != Lead.StateCode.OPEN:
        raise ValueError("Lead must be Open to qualify")

    # Usar servicio de negocio
    service = LeadService()
    result = service.qualify_lead(lead, payload, request.user)

    return result
```

#### 4. **services.py** - Business Logic

```python
from django.db import transaction
from apps.accounts.models import Account
from apps.contacts.models import Contact
from apps.opportunities.models import Opportunity
from .models import Lead

class LeadService:
    """Lógica de negocio para Leads"""

    @transaction.atomic
    def qualify_lead(self, lead: Lead, dto: QualifyLeadDto, user):
        """
        Califica un lead (implementa los 3 escenarios: B2B nuevo, B2B existente, B2C)

        Returns:
            QualifyLeadResponse con las entidades creadas
        """
        # 1. Determinar si es B2B o B2C
        is_b2b = bool(lead.companyname)

        # 2. Crear/Vincular Account (solo B2B)
        account = None
        if is_b2b:
            if dto.createAccount:
                account = Account.objects.create(
                    name=lead.companyname,
                    emailaddress1=lead.emailaddress1,
                    telephone1=lead.telephone1,
                    address1_line1=lead.address1_line1,
                    address1_city=lead.address1_city,
                    ownerid=lead.ownerid,
                    createdby=user,
                    modifiedby=user
                )
            elif dto.existingAccountId:
                account = Account.objects.get(accountid=dto.existingAccountId)

        # 3. Crear/Vincular Contact
        if dto.createContact:
            contact = Contact.objects.create(
                firstname=lead.firstname,
                lastname=lead.lastname,
                emailaddress1=lead.emailaddress1,
                telephone1=lead.telephone1,
                jobtitle=lead.jobtitle,
                parentcustomerid=account,  # None en B2C
                ownerid=lead.ownerid,
                createdby=user,
                modifiedby=user
            )
        else:
            contact = Contact.objects.get(contactid=dto.existingContactId)

        # 4. Crear Opportunity
        opportunity = Opportunity.objects.create(
            name=dto.opportunityName,
            originatingleadid=lead,  # Vínculo al Lead original
            customerid=account.accountid if is_b2b else contact.contactid,
            customeridtype='account' if is_b2b else 'contact',
            salesstage=0,  # Qualify
            closeprobability=25,
            estimatedvalue=dto.estimatedValue,
            estimatedclosedate=dto.estimatedCloseDate,
            description=dto.description,
            ownerid=lead.ownerid,
            createdby=user,
            modifiedby=user
        )

        # 5. Actualizar Lead a Qualified
        lead.statecode = Lead.StateCode.QUALIFIED
        lead.statuscode = Lead.StatusCode.QUALIFIED
        lead.modifiedby = user
        lead.save()

        # 6. Retornar resultado
        return {
            'leadId': lead.leadid,
            'accountId': account.accountid if account else None,
            'contactId': contact.contactid,
            'opportunityId': opportunity.opportunityid,
            'account': account,
            'contact': contact,
            'opportunity': opportunity
        }
```

### Configuración Django Ninja

```python
# crm/urls.py
from ninja import NinjaAPI
from apps.leads.routers import router as leads_router
from apps.opportunities.routers import router as opportunities_router
# ... otros routers

api = NinjaAPI(
    title="CRM Sales API",
    version="1.0.0",
    description="API basada en Microsoft Dynamics 365 Sales (CDS)"
)

# Registrar routers
api.add_router("/leads", leads_router)
api.add_router("/opportunities", opportunities_router)
api.add_router("/accounts", accounts_router)
api.add_router("/contacts", contacts_router)
api.add_router("/quotes", quotes_router)
api.add_router("/orders", orders_router)
api.add_router("/invoices", invoices_router)
api.add_router("/products", products_router)
api.add_router("/activities", activities_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

### Paginación Compatible con Frontend

```python
# core/pagination.py
from ninja.pagination import PaginationBase
from ninja import Schema
from typing import List, Any

class CustomPagination(PaginationBase):
    """Paginación compatible con Django REST Framework format"""

    class Input(Schema):
        page: int = 1
        page_size: int = 50

    class Output(Schema):
        count: int
        next: str = None
        previous: str = None
        results: List[Any]

    def paginate_queryset(self, queryset, pagination: Input, **params):
        offset = (pagination.page - 1) * pagination.page_size
        count = queryset.count()

        return {
            'count': count,
            'next': f"?page={pagination.page + 1}" if offset + pagination.page_size < count else None,
            'previous': f"?page={pagination.page - 1}" if pagination.page > 1 else None,
            'results': queryset[offset:offset + pagination.page_size]
        }
```

### Manejo de Errores

```python
# core/exceptions.py
from ninja.errors import HttpError

class ApiErrorCode:
    """Match frontend ApiErrorCode enum"""
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    LEAD_ALREADY_QUALIFIED = "LEAD_ALREADY_QUALIFIED"

class BusinessLogicError(HttpError):
    """Custom exception for business logic errors"""
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(status_code, message)
        self.code = code

# Uso en routers:
if lead.statecode != Lead.StateCode.OPEN:
    raise BusinessLogicError(
        code=ApiErrorCode.LEAD_ALREADY_QUALIFIED,
        message="Lead must be Open to qualify",
        status_code=400
    )
```

### RBAC (Role-Based Access Control)

```python
# core/permissions.py
from functools import wraps
from django.http import JsonResponse

def require_permission(permission: str):
    """Decorator para verificar permisos basados en rol de usuario"""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'UNAUTHORIZED',
                        'message': 'Authentication required'
                    }
                }, status=401)

            if not request.user.has_perm(permission):
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'FORBIDDEN',
                        'message': 'Insufficient permissions'
                    }
                }, status=403)

            return func(request, *args, **kwargs)
        return wrapper
    return decorator
```

### Audit Logging Middleware

```python
# core/middleware.py
from apps.audit.models import AuditLog

class AuditLogMiddleware:
    """Middleware para registrar todas las operaciones CRUD"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Registrar solo mutaciones (POST, PATCH, DELETE)
        if request.method in ['POST', 'PATCH', 'PUT', 'DELETE']:
            self.log_action(request, response)

        return response

    def log_action(self, request, response):
        """Crear registro de auditoría"""
        if request.user.is_authenticated:
            AuditLog.objects.create(
                action=self.get_action(request.method),
                entity=self.get_entity_from_path(request.path),
                recordid=self.get_record_id(request.path),
                userid=request.user.systemuserid,
                username=request.user.fullname,
                userrole=request.user.role,
                ipaddress=self.get_client_ip(request),
                useragent=request.META.get('HTTP_USER_AGENT', ''),
            )
```

### Testing Recomendado

```python
# apps/leads/tests.py
from django.test import TestCase
from apps.leads.models import Lead
from apps.leads.services import LeadService

class LeadQualificationTestCase(TestCase):
    """Test de calificación de leads (3 escenarios)"""

    def setUp(self):
        self.user = SystemUser.objects.create(...)
        self.service = LeadService()

    def test_qualify_lead_b2b_new_account(self):
        """Escenario 1: B2B - Crear nuevo Account"""
        lead = Lead.objects.create(
            firstname="John",
            lastname="Doe",
            companyname="Acme Corp",  # B2B
            ownerid=self.user
        )

        dto = QualifyLeadDto(
            createAccount=True,
            createContact=True,
            opportunityName="Acme Corp - Sales Opportunity",
            estimatedValue=50000,
            estimatedCloseDate="2024-12-31"
        )

        result = self.service.qualify_lead(lead, dto, self.user)

        self.assertIsNotNone(result['accountId'])
        self.assertIsNotNone(result['contactId'])
        self.assertIsNotNone(result['opportunityId'])
        self.assertEqual(lead.statecode, Lead.StateCode.QUALIFIED)

    def test_qualify_lead_b2c(self):
        """Escenario 3: B2C - Sin Account"""
        lead = Lead.objects.create(
            firstname="Mary",
            lastname="Smith",
            companyname=None,  # B2C
            ownerid=self.user
        )

        dto = QualifyLeadDto(
            createAccount=False,
            createContact=True,
            opportunityName="Mary Smith - Sales Opportunity",
            estimatedValue=5000,
            estimatedCloseDate="2024-11-30"
        )

        result = self.service.qualify_lead(lead, dto, self.user)

        self.assertIsNone(result['accountId'])  # No Account en B2C
        self.assertIsNotNone(result['contactId'])
        self.assertIsNotNone(result['opportunityId'])
```

---

## 📦 Entidades Principales

### 1. Lead (Cliente Potencial)

**Propósito**: Primer contacto con un posible cliente.

**Tabla**: `lead`

**Campos Principales**:

```typescript
interface Lead {
  // Primary Key
  leadid: string                        // GUID

  // State & Status
  statecode: LeadStateCode              // 0=Open, 1=Qualified, 2=Disqualified
  statuscode: LeadStatusCode            // New, Contacted, Qualified, Disqualified

  // Basic Information
  firstname: string                     // REQUIRED
  lastname: string                      // REQUIRED
  fullname?: string                     // COMPUTED: firstname + lastname
  jobtitle?: string
  companyname?: string                  // Null en B2C

  // Contact Information
  emailaddress1?: string
  telephone1?: string
  mobilephone?: string
  websiteurl?: string

  // Address
  address1_line1?: string
  address1_line2?: string
  address1_city?: string
  address1_stateorprovince?: string
  address1_postalcode?: string
  address1_country?: string

  // Lead Qualification
  leadsourcecode: LeadSourceCode        // REQUIRED: Advertisement, Web, etc.
  leadqualitycode?: LeadQualityCode     // Hot, Warm, Cold
  description?: string

  // Estimated Value
  estimatedvalue?: number
  estimatedclosedate?: string           // ISO 8601

  // Business Process Flow - Qualify Stage
  budgetamount?: number
  budgetstatus?: BudgetStatusCode       // No Budget, May Buy, Can Buy, Will Buy
  timeframe?: string
  needanalysis?: string
  decisionmaker?: string                // Contact ID

  // Relationships
  ownerid: string                       // REQUIRED: User ID
  originatingcampaignid?: string

  // Audit Fields
  createdon: string                     // ISO 8601 datetime
  modifiedon: string                    // ISO 8601 datetime
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateLeadDto`: firstname, lastname, leadsourcecode, ownerid
- `UpdateLeadDto`: campos actualizables
- `QualifyLeadDto`: para conversión a Opportunity
- `QualifyLeadResponse`: entidades creadas (Account, Contact, Opportunity)

**Flujo**:
1. Lead creado → `statecode: 0` (Open)
2. Lead calificado → `statecode: 1` (Qualified) + genera Account/Contact/Opportunity
3. Lead descalificado → `statecode: 2` (Disqualified)

---

### 2. Opportunity (Oportunidad de Venta)

**Propósito**: Posible venta en proceso.

**Tabla**: `opportunity`

**Campos Principales**:

```typescript
interface Opportunity {
  // Primary Key
  opportunityid: string                 // GUID

  // State & Status
  statecode: OpportunityStateCode       // 0=Open, 1=Won, 2=Lost
  statuscode: OpportunityStatusCode     // In_Progress, On_Hold, Won, Lost, Canceled

  // Basic Information
  name: string                          // REQUIRED
  description?: string

  // Customer (POLIMÓRFICO)
  customerid: string                    // REQUIRED: Account ID o Contact ID
  customeridtype: CustomerType          // REQUIRED: 'account' o 'contact'

  // Sales Information
  salesstage: SalesStageCode            // Qualify, Develop, Propose, Close
  closeprobability: number              // 0-100 (auto-calculado según salesstage)
  estimatedvalue: number                // REQUIRED
  estimatedclosedate: string            // REQUIRED: ISO 8601
  actualvalue?: number
  actualclosedate?: string              // ISO 8601

  // Lead Origin
  originatingleadid?: string            // Lead que generó esta Opportunity

  // Relationships
  ownerid: string                       // REQUIRED: User ID
  campaignid?: string

  // Close Information
  closestatus?: string                  // Won/Lost reason

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateOpportunityDto`: name, customerid, customeridtype, salesstage, estimatedvalue, estimatedclosedate, ownerid
- `UpdateOpportunityDto`: campos actualizables
- `CloseOpportunityDto`: para cerrar (Win/Loss)

**Probabilidades por Sales Stage**:
- Qualify: 25%
- Develop: 50%
- Propose: 75%
- Close: 100% (Won) / 0% (Lost)

---

### 3. Account (Cuenta/Empresa)

**Propósito**: Empresa u organización cliente (B2B).

**Tabla**: `account`

**Campos Principales**:

```typescript
interface Account {
  // Primary Key
  accountid: string                     // GUID

  // State & Status
  statecode: AccountStateCode           // 0=Active, 1=Inactive
  statuscode?: number

  // Basic Information
  name: string                          // REQUIRED
  accountnumber?: string
  description?: string

  // Contact Information
  emailaddress1?: string
  telephone1?: string
  telephone2?: string
  fax?: string
  websiteurl?: string

  // Address (Primary)
  address1_line1?: string
  address1_line2?: string
  address1_line3?: string
  address1_city?: string
  address1_stateorprovince?: string
  address1_postalcode?: string
  address1_country?: string

  // Address (Secondary)
  address2_line1?: string
  address2_line2?: string
  address2_line3?: string
  address2_city?: string
  address2_stateorprovince?: string
  address2_postalcode?: string
  address2_country?: string

  // Business Information
  industrycode?: IndustryCode
  accountcategorycode?: AccountCategoryCode
  revenue?: number
  numberofemployees?: number
  ownershipcode?: number

  // Hierarchy
  parentaccountid?: string              // Para cuentas corporativas

  // Relationships
  ownerid: string                       // REQUIRED
  primarycontactid?: string

  // Credit Information
  creditonhold?: boolean
  creditlimit?: number

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateAccountDto`: name, ownerid
- `UpdateAccountDto`: campos actualizables

**Relaciones**:
- 1 Account → N Contacts
- 1 Account → N Opportunities

---

### 4. Contact (Contacto/Persona)

**Propósito**: Persona individual (tomador de decisiones).

**Tabla**: `contact`

**Campos Principales**:

```typescript
interface Contact {
  // Primary Key
  contactid: string                     // GUID

  // State & Status
  statecode: ContactStateCode           // 0=Active, 1=Inactive
  statuscode?: number

  // Basic Information
  firstname: string                     // REQUIRED
  lastname: string                      // REQUIRED
  fullname?: string                     // COMPUTED: firstname + lastname
  middlename?: string
  salutation?: string                   // Mr., Mrs., Dr.
  jobtitle?: string
  department?: string

  // Contact Information
  emailaddress1?: string
  emailaddress2?: string
  telephone1?: string
  telephone2?: string
  mobilephone?: string
  fax?: string

  // Address
  address1_line1?: string
  address1_line2?: string
  address1_line3?: string
  address1_city?: string
  address1_stateorprovince?: string
  address1_postalcode?: string
  address1_country?: string

  // Relationships
  parentcustomerid?: string             // Account ID (null en B2C)
  ownerid: string                       // REQUIRED

  // Additional Information
  birthdate?: string                    // ISO 8601 date
  gendercode?: number                   // 1=Male, 2=Female
  familystatuscode?: number
  spousesname?: string
  preferredcontactmethodcode?: number
  donotbulkemail?: boolean
  donotphone?: boolean
  donotemail?: boolean

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateContactDto`: firstname, lastname, ownerid
- `UpdateContactDto`: campos actualizables

**Relaciones**:
- Pertenece a Account (B2B) vía `parentcustomerid`
- Vinculado a Opportunities vía `customerid` (B2C)

---

### 5. Quote (Cotización)

**Propósito**: Propuesta formal de productos/servicios con precios.

**Tabla**: `quote`

**Campos Principales**:

```typescript
interface Quote {
  // Primary Key
  quoteid: string                       // GUID

  // State & Status
  statecode: QuoteStateCode             // 0=Draft, 1=Active, 2=Won, 3=Closed
  statuscode: QuoteStatusCode

  // Basic Information
  name: string                          // REQUIRED
  quotenumber?: string                  // Auto-generado
  description?: string

  // Customer (heredado de Opportunity)
  customerid: string                    // REQUIRED
  customeridtype: 'account' | 'contact' // REQUIRED

  // Relationships
  opportunityid: string                 // REQUIRED
  ownerid: string                       // REQUIRED

  // Pricing (COMPUTED)
  totalamount: number                   // Suma de Quote Lines
  totallineitemamount?: number
  totaldiscountamount?: number
  totalamountlessfreight?: number
  freightamount?: number
  discountamount?: number
  discountpercentage?: number

  // Tax
  totaltax?: number

  // Dates
  effectivefrom: string                 // REQUIRED: ISO 8601 date
  effectiveto: string                   // REQUIRED: ISO 8601 date
  requestdeliveryby?: string            // ISO 8601 date
  closedon?: string                     // ISO 8601 datetime

  // Shipping
  shipto_name?: string
  shipto_line1?: string
  shipto_line2?: string
  shipto_city?: string
  shipto_stateorprovince?: string
  shipto_postalcode?: string
  shipto_country?: string

  // Billing
  billto_name?: string
  billto_line1?: string
  billto_line2?: string
  billto_city?: string
  billto_stateorprovince?: string
  billto_postalcode?: string
  billto_country?: string

  // Payment Terms
  paymenttermscode?: number
  freighttermscode?: number

  // Close Information
  closingnotes?: string

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateQuoteDto`: name, opportunityid, customerid, customeridtype, effectivefrom, effectiveto, ownerid
- `UpdateQuoteDto`: campos actualizables (solo en Draft)
- `ActivateQuoteDto`: cambiar a Active
- `CloseQuoteDto`: cerrar (Won/Lost)

**Flujo**:
1. Draft (0) → editable
2. Active (1) → enviada al cliente (no editable)
3. Won (2) → aceptada → genera Order
4. Closed (3) → perdida o cancelada

**⚠️ IMPORTANTE**: Quote debe tener al menos 1 Quote Line (producto)

---

### 6. QuoteDetail (Quote Line Item)

**Propósito**: Línea de producto/servicio en una Quote.

**Tabla**: `quotedetail`

**Campos Principales**:

```typescript
interface QuoteDetail {
  // Primary Key
  quotedetailid: string                 // GUID

  // Relationships
  quoteid: string                       // REQUIRED: Quote padre
  productid?: string                    // Producto del catálogo (null si write-in)
  uomid?: string                        // Unit of Measure

  // Line Information
  lineitemnumber?: number
  productdescription?: string
  isproductoverridden?: boolean         // true = write-in product

  // Pricing
  quantity: number                      // REQUIRED
  priceperunit: number                  // REQUIRED
  baseamount?: number                   // quantity * priceperunit

  // Discounts
  manualdiscountamount?: number
  volumediscountamount?: number

  // Tax
  tax?: number

  // Extended Amount (COMPUTED)
  extendedamount: number                // Total de la línea

  // Audit Fields
  createdon: string
  modifiedon: string
}
```

**Cálculo**:
```
baseamount = quantity * priceperunit
extendedamount = baseamount - manualdiscountamount - volumediscountamount + tax
```

**DTOs**:
- `CreateQuoteDetailDto`: quoteid, quantity, priceperunit
- `UpdateQuoteDetailDto`: campos actualizables

---

### 7. Order (Sales Order / Pedido)

**Propósito**: Orden de compra confirmada (post-venta ganada).

**Tabla**: `salesorder`

**Campos Principales**:

```typescript
interface Order {
  // Primary Key
  salesorderid: string                  // GUID

  // State & Status
  statecode: OrderStateCode             // 0=Active, 1=Submitted, 2=Canceled, 3=Fulfilled, 4=Invoiced
  statuscode?: OrderStatusCode

  // Basic Information
  name: string                          // REQUIRED
  ordernumber?: string                  // Auto-generado
  description?: string

  // Customer (heredado de Quote)
  customerid: string                    // REQUIRED
  customeridtype: 'account' | 'contact' // REQUIRED

  // Relationships
  quoteid?: string                      // Quote origen
  opportunityid?: string
  ownerid: string                       // REQUIRED

  // Pricing (COMPUTED)
  totalamount: number
  totalamountlessfreight?: number
  freightamount?: number
  discountamount?: number
  discountpercentage?: number

  // Tax
  totaltax?: number

  // Dates
  datefulfilled?: string                // ISO 8601 date
  requestdeliveryby?: string            // ISO 8601 date
  submitdate?: string                   // ISO 8601 date

  // Shipping
  shipto_name?: string
  shipto_line1?: string
  shipto_line2?: string
  shipto_city?: string
  shipto_stateorprovince?: string
  shipto_postalcode?: string
  shipto_country?: string
  shippingmethodcode?: ShippingMethodCode

  // Billing
  billto_name?: string
  billto_line1?: string
  billto_line2?: string
  billto_city?: string
  billto_stateorprovince?: string
  billto_postalcode?: string
  billto_country?: string

  // Payment Terms
  paymenttermscode?: PaymentTermsCode
  freighttermscode?: FreightTermsCode

  // Priority
  prioritycode?: PriorityCode

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateOrderDto`: name, customerid, customeridtype, ownerid
- `UpdateOrderDto`: campos actualizables
- `FulfillOrderDto`: marcar como cumplida

**Flujo**:
1. Active (0) → orden creada
2. Submitted (1) → enviada a cumplimiento
3. Fulfilled (3) → cumplida → puede generar Invoice
4. Invoiced (4) → facturada
5. Canceled (2) → cancelada

**Generación**: Automáticamente desde Quote Won (copia Quote Lines → Order Lines)

---

### 8. OrderDetail (Order Line Item)

**Propósito**: Línea de producto/servicio en un Order.

**Tabla**: `salesorderdetail`

**Estructura**: Idéntica a `QuoteDetail` pero con `salesorderid` como FK.

---

### 9. Invoice (Factura)

**Propósito**: Factura generada desde un Order.

**Tabla**: `invoice`

**Campos Principales**:

```typescript
interface Invoice {
  // Primary Key
  invoiceid: string                     // GUID

  // State & Status
  statecode: InvoiceStateCode           // 0=Active, 2=Paid, 3=Canceled
  statuscode?: number

  // Basic Information
  name: string                          // REQUIRED
  invoicenumber?: string                // Auto-generado
  description?: string

  // Customer (heredado de Order)
  customerid: string                    // REQUIRED
  customeridtype: 'account' | 'contact' // REQUIRED

  // Relationships
  salesorderid?: string                 // Order origen
  opportunityid?: string
  ownerid: string                       // REQUIRED

  // Pricing (COMPUTED)
  totalamount: number
  totalamountlessfreight?: number
  freightamount?: number
  discountamount?: number
  discountpercentage?: number

  // Tax
  totaltax?: number

  // Dates
  datedelivered?: string                // ISO 8601 date
  duedate: string                       // REQUIRED: ISO 8601 date

  // Payment
  totalpaid?: number
  totalbalance?: number                 // totalamount - totalpaid

  // Billing
  billto_name?: string
  billto_line1?: string
  billto_line2?: string
  billto_city?: string
  billto_stateorprovince?: string
  billto_postalcode?: string
  billto_country?: string

  // Shipping (informativo)
  shipto_name?: string
  shipto_line1?: string
  shipto_line2?: string
  shipto_city?: string
  shipto_stateorprovince?: string
  shipto_postalcode?: string
  shipto_country?: string

  // Payment Terms
  paymenttermscode?: number

  // Priority
  prioritycode?: number

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateInvoiceDto`: name, customerid, customeridtype, duedate, ownerid
- `UpdateInvoiceDto`: campos actualizables
- `MarkInvoicePaidDto`: marcar como pagada

**Flujo**:
1. Active (0) → factura activa (pendiente de pago)
2. Paid (2) → factura pagada
3. Canceled (3) → factura cancelada

**Generación**: Automáticamente desde Order Fulfilled (copia Order Lines → Invoice Lines)

---

### 10. InvoiceDetail (Invoice Line Item)

**Propósito**: Línea de producto/servicio en una Invoice.

**Tabla**: `invoicedetail`

**Estructura**: Idéntica a `QuoteDetail` pero con `invoiceid` como FK.

---

## 🛒 Entidades de Catálogo

### 11. Product (Producto/Servicio)

**Propósito**: Producto o servicio en el catálogo vendible.

**Tabla**: `product`

**Campos Principales**:

```typescript
interface Product {
  // Primary Key
  productid: string                     // GUID

  // State & Status
  statecode: number                     // 0=Active, 1=Inactive
  statuscode?: number

  // Basic Information
  name: string                          // REQUIRED
  productnumber?: string                // SKU
  description?: string

  // Product Type
  productstructure?: number             // 1=Product, 2=Product Family, 3=Bundle
  producttypecode?: number              // 1=Sales Inventory, 2=Misc Charges

  // Pricing (default)
  price?: number
  standardcost?: number

  // Inventory
  currentcost?: number
  stockvolume?: number
  stockweight?: number
  quantityonhand?: number
  quantityallocated?: number

  // Unit of Measure
  defaultuomid?: string
  defaultuomscheduleid?: string

  // Vendor
  vendorid?: string
  vendorpartnumber?: string
  vendorname?: string

  // Dimensions
  size?: string
  color?: string
  style?: string

  // Supplier
  suppliername?: string

  // Hierarchy
  parentproductid?: string              // Para bundles/familias

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**DTOs**:
- `CreateProductDto`: name
- `UpdateProductDto`: campos actualizables

---

### 12. PriceList (Lista de Precios)

**Propósito**: Define precios especiales para productos.

**Tabla**: `pricelevel`

**Campos Principales**:

```typescript
interface PriceList {
  // Primary Key
  pricelevelid: string                  // GUID

  // Basic Information
  name: string                          // REQUIRED
  description?: string

  // Dates
  begindate?: string                    // ISO 8601 date
  enddate?: string                      // ISO 8601 date

  // Status
  statecode: number                     // 0=Active, 1=Inactive

  // Audit Fields
  createdon: string
  modifiedon: string
}
```

---

### 13. PriceListItem (Precio de Producto)

**Propósito**: Precio específico de un producto en una lista de precios.

**Tabla**: `productpricelevel`

**Campos Principales**:

```typescript
interface PriceListItem {
  // Primary Key
  productpricelevelid: string           // GUID

  // Relationships
  pricelevelid: string                  // REQUIRED: Price List
  productid: string                     // REQUIRED: Product
  uomid?: string                        // Unit of Measure

  // Pricing
  amount: number                        // REQUIRED: Precio

  // Audit Fields
  createdon: string
  modifiedon: string
}
```

---

## 📅 Entidades de Actividades

### 14. Activity (Base)

**Propósito**: Base para todas las actividades.

**Tabla**: `activitypointer` (tabla base)

**Campos Principales**:

```typescript
interface Activity {
  // Primary Key
  activityid: string                    // GUID

  // Activity Type
  activitytypecode: ActivityTypeCode    // Email, Phone_Call, Task, Appointment

  // State & Status
  statecode: ActivityStateCode          // 0=Open, 1=Completed, 2=Canceled, 3=Scheduled
  statuscode?: number

  // Basic Information
  subject: string                       // REQUIRED
  description?: string

  // Regarding (POLIMÓRFICO)
  regardingobjectid?: string            // Lead/Opportunity/Account/Contact ID
  regardingobjectidtype?: string        // 'lead', 'opportunity', 'account', 'contact'

  // Scheduling
  scheduledstart?: string               // ISO 8601 datetime
  scheduledend?: string                 // ISO 8601 datetime
  actualdurationminutes?: number

  // Completion
  actualstart?: string                  // ISO 8601 datetime
  actualend?: string                    // ISO 8601 datetime

  // Priority
  prioritycode?: number                 // 0=Low, 1=Normal, 2=High

  // Ownership
  ownerid: string                       // REQUIRED

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}
```

**Tipos Específicos**:
- **Email**: campos adicionales (to, from, body)
- **PhoneCall**: campos adicionales (phonenumber, direction)
- **Task**: campos adicionales (percentcomplete)
- **Appointment**: campos adicionales (location, attendees)

---

### 15. Email

**Propósito**: Email relacionado a un registro.

**Tabla**: `email`

**Campos Adicionales**:

```typescript
interface Email extends Activity {
  // Email Specific
  to?: string
  from?: string
  cc?: string
  bcc?: string
  body?: string
  directioncode?: boolean               // true=outgoing, false=incoming
}
```

---

### 16. PhoneCall

**Propósito**: Llamada telefónica registrada.

**Tabla**: `phonecall`

**Campos Adicionales**:

```typescript
interface PhoneCall extends Activity {
  // Phone Call Specific
  phonenumber?: string
  directioncode?: boolean               // true=outgoing, false=incoming
}
```

---

### 17. Task

**Propósito**: Tarea por completar.

**Tabla**: `task`

**Campos Adicionales**:

```typescript
interface Task extends Activity {
  // Task Specific
  percentcomplete?: number              // 0-100
}
```

---

### 18. Appointment

**Propósito**: Reunión o cita agendada.

**Tabla**: `appointment`

**Campos Adicionales**:

```typescript
interface Appointment extends Activity {
  // Appointment Specific
  location?: string
  requiredattendees?: string            // JSON array de Contact IDs
  optionalattendees?: string            // JSON array de Contact IDs
}
```

---

## 🚀 Entidades Avanzadas

### 19. QuoteTemplate (Plantilla de Cotización)

**Propósito**: Plantillas reutilizables para crear cotizaciones rápidamente.

**Tabla**: `quotetemplate`

**Campos Principales**:

```typescript
interface QuoteTemplate {
  // Primary Key
  quotetemplateid: string               // GUID

  // Basic Information
  name: string                          // REQUIRED
  description?: string

  // Category
  category: QuoteTemplateCategory       // Standard, Custom, Industry, Service, Product, Bundle

  // Template Data (JSON)
  templatedata: QuoteTemplateData       // Estructura de Quote pre-configurada

  // Sharing & Usage
  isshared: boolean                     // true = disponible para todos los usuarios
  usagecount: number                    // Cuántas veces se ha usado

  // Owner
  ownerid: string                       // REQUIRED

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}

interface QuoteTemplateData {
  // Quote defaults
  effectivedays?: number                // Días de validez desde creación
  paymenttermscode?: number
  freighttermscode?: number
  discountpercentage?: number

  // Pre-configured Quote Lines
  lines: QuoteTemplateLineData[]
}

interface QuoteTemplateLineData {
  productid?: string
  productdescription?: string
  quantity: number
  priceperunit?: number                 // null = usar precio de catálogo
  manualdiscountamount?: number
}

enum QuoteTemplateCategory {
  Standard = 'standard',
  Custom = 'custom',
  Industry = 'industry',
  Service = 'service',
  Product = 'product',
  Bundle = 'bundle',
}
```

**DTOs**:
- `CreateQuoteTemplateDto`: name, category, templatedata, ownerid
- `UpdateQuoteTemplateDto`: campos actualizables
- `UseQuoteTemplateDto`: opportunityid (para crear Quote desde template)

**Flujo de uso**:
```typescript
// 1. Crear template
POST /api/quote-templates
{
  "name": "Standard SaaS Quote",
  "category": "service",
  "templatedata": {
    "effectivedays": 30,
    "paymenttermscode": 1,  // Net 30
    "lines": [
      {"productid": "prod-123", "quantity": 1},
      {"productid": "prod-456", "quantity": 12}
    ]
  }
}

// 2. Usar template para crear Quote
POST /api/quotes/from-template
{
  "templateid": "template-abc",
  "opportunityid": "opp-123"
}
// → Crea Quote con líneas pre-configuradas
```

---

### 20. QuoteVersion (Control de Versiones de Cotización)

**Propósito**: Historial de cambios de cotizaciones (audit trail completo).

**Tabla**: `quoteversion`

**Campos Principales**:

```typescript
interface QuoteVersion {
  // Primary Key
  quoteversionid: string                // GUID

  // Relationship
  quoteid: string                       // REQUIRED: Quote padre

  // Version Info
  versionnumber: number                 // 1, 2, 3, ... (incremental)
  versiondata: QuoteVersionData         // Snapshot completo del Quote en esta versión

  // Change Tracking
  changetype: QuoteVersionChangeType    // Create, Update, Activate, Close, etc.
  changedfields?: string[]              // Array de nombres de campos modificados
  changedsummary?: string               // Resumen legible de cambios

  // Context
  createdby: string                     // REQUIRED: Usuario que creó esta versión
  createdon: string                     // REQUIRED: Timestamp

  // Metadata
  comment?: string                      // Comentario opcional del usuario
}

interface QuoteVersionData {
  quote: Quote                          // Snapshot del Quote
  quoteLines: QuoteDetail[]             // Snapshot de todas las líneas
}

enum QuoteVersionChangeType {
  Create = 'create',                    // Versión inicial
  Update = 'update',                    // Cambios en datos
  AddLine = 'add-line',                 // Nueva línea agregada
  UpdateLine = 'update-line',           // Línea modificada
  DeleteLine = 'delete-line',           // Línea eliminada
  Activate = 'activate',                // Quote activado
  Close = 'close',                      // Quote cerrado
  Win = 'win',                          // Quote ganado
  Lose = 'lose',                        // Quote perdido
}
```

**DTOs**:
- `CreateQuoteVersionDto`: quoteid, changetype, comment (auto-creado en cambios)
- `QuoteVersionSummary`: versión simplificada para listar historial

**Uso**:
```typescript
// GET /api/quotes/{id}/versions
// Retorna todas las versiones de un Quote

// GET /api/quotes/{id}/versions/{versionNumber}
// Obtiene snapshot de una versión específica

// POST /api/quotes/{id}/revert-to-version
// Revierte Quote a una versión anterior (solo Draft)
```

**⚠️ IMPORTANTE**:
- Se crea automáticamente una versión en cada cambio significativo
- Versiones inmutables (no se pueden editar/eliminar)
- Útil para compliance, auditorías, disputas con clientes

---

### 21. ReturnRequest (Solicitud de Devolución - RMA)

**Propósito**: Gestión de devoluciones de productos (Return Material Authorization).

**Tabla**: `returnrequest`

**Campos Principales**:

```typescript
interface ReturnRequest {
  // Primary Key
  returnrequestid: string               // GUID

  // State & Status
  statecode: ReturnRequestStateCode     // Pending, Approved, Completed, Rejected
  statuscode: ReturnRequestStatusCode

  // Basic Information
  name: string                          // REQUIRED
  requestnumber?: string                // Auto-generado (RMA-00001)
  description?: string

  // Relationship
  salesorderid: string                  // REQUIRED: Order original
  invoiceid?: string                    // Invoice relacionado

  // Customer
  customerid: string                    // REQUIRED
  customeridtype: 'account' | 'contact' // REQUIRED

  // Return Details
  returntype: ReturnType                // Full, Partial, Exchange, Store credit
  returnreason: ReturnReasonCode        // Defective, Wrong item, Damaged, etc.
  returnreasondetails?: string          // Descripción detallada

  // Financial
  totalreturnvalue: number              // Valor total de devolución
  restockingfee?: number                // Cargo por reposición (%)
  refundamount: number                  // Monto a reembolsar
  shippingrefund?: number               // Reembolso de envío

  // Shipping (Return)
  returntrackingnumber?: string
  returnshippingcarrier?: string

  // Dates
  requestdate: string                   // REQUIRED: Fecha de solicitud
  approveddate?: string
  completeddate?: string

  // Approved By
  approvedby?: string                   // User ID
  rejectedby?: string                   // User ID
  rejectionreason?: string

  // Owner
  ownerid: string                       // REQUIRED

  // Audit Fields
  createdon: string
  modifiedon: string
  createdby?: string
  modifiedby?: string
}

enum ReturnRequestStateCode {
  Pending = 0,                          // Pendiente de aprobación
  Approved = 1,                         // Aprobado, en proceso
  Completed = 2,                        // Completado (refund procesado)
  Rejected = 3,                         // Rechazado
}

enum ReturnType {
  FullRefund = 'full-refund',
  PartialRefund = 'partial-refund',
  Exchange = 'exchange',
  StoreCredit = 'store-credit',
}

enum ReturnReasonCode {
  Defective = 1,                        // Producto defectuoso
  WrongItem = 2,                        // Artículo incorrecto
  Damaged = 3,                          // Dañado en envío
  NotAsDescribed = 4,                   // No coincide con descripción
  ChangedMind = 5,                      // Cliente cambió de opinión
  LateDelivery = 6,                     // Entrega tardía
  QualityIssue = 7,                     // Problema de calidad
  Other = 99,                           // Otro motivo
}
```

**DTOs**:
- `CreateReturnRequestDto`: salesorderid, returntype, returnreason, items
- `ApproveReturnRequestDto`: refundamount, restockingfee, approvedby
- `CompleteReturnRequestDto`: completeddate
- `RejectReturnRequestDto`: rejectionreason, rejectedby

**Flujo**:
```
1. Pending (0) → Cliente crea solicitud de devolución
2. Approved (1) → Manager aprueba, genera RMA number
3. Completed (2) → Producto recibido, refund procesado
   O
   Rejected (3) → Solicitud rechazada
```

**Reglas de Negocio**:
- Solo se pueden devolver Orders con `statecode = Fulfilled` o `Invoiced`
- `restockingfee` es opcional (típicamente 10-20%)
- `refundamount` = `totalreturnvalue - restockingfee - shippingcost`
- Si `returntype = Exchange`, se debe crear nuevo Order
- Manager o Admin debe aprobar antes de procesar

---

## 🔐 Entidades de Seguridad

### 22. SystemUser (Usuario)

**Propósito**: Usuario del sistema CRM.

**Tabla**: `systemuser`

**Campos Principales**:

```typescript
interface SystemUser {
  // Primary Key
  systemuserid: string                  // GUID

  // Personal Information
  firstname: string                     // REQUIRED
  lastname: string                      // REQUIRED
  fullname: string                      // COMPUTED: firstname + lastname

  // Contact Information
  internalemailaddress: string          // REQUIRED: login username
  mobilephone?: string

  // Authentication
  password: string                      // Hashed (bcrypt)

  // Role & Permissions
  role: UserRole                        // REQUIRED

  // Status
  isdisabled: boolean

  // Organization
  businessunitid?: string

  // Metadata
  domainname?: string
  azureactivedirectoryobjectid?: string

  // Audit Fields
  createdon: Date
  modifiedon: Date
  statecode: number                     // 0=Active, 1=Inactive
  statuscode: number
}
```

**Roles Disponibles**:

```typescript
enum UserRole {
  SystemAdministrator = 'system-administrator',
  SalesManager = 'sales-manager',
  SalesRepresentative = 'sales-representative',
  CustomerServiceRep = 'customer-service-rep',
  MarketingProfessional = 'marketing-professional',
}
```

**DTOs**:
- `CreateSystemUserDto`: firstname, lastname, internalemailaddress, password, role
- `UpdateSystemUserDto`: campos actualizables
- `SystemUserSummary`: versión sin password (safe para cliente)

---

### 23. AuditLog (Registro de Auditoría)

**Propósito**: Rastrea todas las operaciones CRUD en el CRM.

**Tabla**: `audit`

**Campos Principales**:

```typescript
interface AuditLog {
  // Primary Key
  auditid: string                       // GUID

  // Action Info
  action: AuditAction                   // Create, Update, Delete, etc.
  entity: PermissionEntity              // Lead, Opportunity, etc.
  recordid: string                      // ID del registro afectado
  recordname?: string                   // Nombre del registro

  // User Info
  userid: string                        // Quién realizó la acción
  username: string                      // Nombre completo (desnormalizado)
  userrole: string                      // Rol al momento de la acción

  // Change Details
  changes?: AuditFieldChange[]          // Campos que cambiaron
  oldvalues?: Record<string, any>       // Snapshot antes
  newvalues?: Record<string, any>       // Snapshot después

  // Context
  ipaddress?: string
  useragent?: string
  sessionid?: string

  // Metadata
  timestamp: Date                       // REQUIRED
  message?: string
}
```

**AuditFieldChange**:

```typescript
interface AuditFieldChange {
  fieldName: string
  oldValue: string | number | boolean | null
  newValue: string | number | boolean | null
}
```

**Acciones de Auditoría**:

```typescript
enum AuditAction {
  Create = 'create',
  Update = 'update',
  Delete = 'delete',
  Read = 'read',
  Share = 'share',
  Assign = 'assign',
  Activate = 'activate',
  Deactivate = 'deactivate',
  Qualify = 'qualify',
  Close = 'close',
  Win = 'win',
  Lose = 'lose',
  Cancel = 'cancel',
}
```

---

## 🔗 Relaciones entre Entidades

### Diagrama de Relaciones

```
Lead (1) ──qualify──> Opportunity (1)
                          │
                          ├──> Account (0..1) [B2B]
                          ├──> Contact (1)
                          │
Opportunity (1) ──> Quote (N)
                      │
Quote (1) ──win──> Order (1)
                      │
Order (1) ──fulfill──> Invoice (1)
```

### Relaciones Detalladas

#### Lead → Opportunity (1:1)
- **FK**: `Opportunity.originatingleadid` → `Lead.leadid`
- **Flujo**: Lead calificado genera 1 Opportunity

#### Lead → Account (0..1)
- **Generación**: Lead calificado puede crear Account (B2B)
- **No hay FK directo**

#### Lead → Contact (1)
- **Generación**: Lead calificado genera/vincula Contact
- **No hay FK directo**

#### Opportunity → Account (N:1) [B2B]
- **FK Polimórfico**: `Opportunity.customerid` + `Opportunity.customeridtype = 'account'`
- **Relación**: N Opportunities → 1 Account

#### Opportunity → Contact (N:1) [B2C o contacto secundario]
- **FK Polimórfico**: `Opportunity.customerid` + `Opportunity.customeridtype = 'contact'`
- **Relación**: N Opportunities → 1 Contact

#### Account → Contact (1:N)
- **FK**: `Contact.parentcustomerid` → `Account.accountid`
- **Relación**: 1 Account → N Contacts

#### Opportunity → Quote (1:N)
- **FK**: `Quote.opportunityid` → `Opportunity.opportunityid`
- **Relación**: 1 Opportunity → N Quotes

#### Quote → QuoteDetail (1:N)
- **FK**: `QuoteDetail.quoteid` → `Quote.quoteid`
- **Relación**: 1 Quote → N Quote Lines
- **⚠️ Requerido**: Al menos 1 línea

#### Quote → Order (1:1)
- **FK**: `Order.quoteid` → `Quote.quoteid`
- **Flujo**: Quote Won genera 1 Order

#### Order → OrderDetail (1:N)
- **FK**: `OrderDetail.salesorderid` → `Order.salesorderid`
- **Relación**: 1 Order → N Order Lines

#### Order → Invoice (1:1)
- **FK**: `Invoice.salesorderid` → `Order.salesorderid`
- **Flujo**: Order Fulfilled genera 1 Invoice

#### Invoice → InvoiceDetail (1:N)
- **FK**: `InvoiceDetail.invoiceid` → `Invoice.invoiceid`
- **Relación**: 1 Invoice → N Invoice Lines

#### Product → QuoteDetail/OrderDetail/InvoiceDetail (1:N)
- **FK**: `*Detail.productid` → `Product.productid`
- **Relación**: 1 Product → N Lines

#### Activity → [Lead/Opportunity/Account/Contact] (N:1)
- **FK Polimórfico**: `Activity.regardingobjectid` + `Activity.regardingobjectidtype`
- **Relación**: N Activities → 1 Record

#### SystemUser → [All Records] (1:N)
- **FK**: `*.ownerid` → `SystemUser.systemuserid`
- **Relación**: 1 User → N Records

---

## 📊 Enumeraciones (Enums)

### Estados y Status

#### LeadStateCode
```typescript
enum LeadStateCode {
  Open = 0,
  Qualified = 1,
  Disqualified = 2,
}
```

#### LeadStatusCode
```typescript
enum LeadStatusCode {
  New = 1,
  Contacted = 2,
  Qualified = 3,
  Disqualified = 4,
}
```

#### LeadSourceCode
```typescript
enum LeadSourceCode {
  Advertisement = 1,
  Employee_Referral = 2,
  External_Referral = 3,
  Partner = 4,
  Public_Relations = 5,
  Seminar = 6,
  Trade_Show = 7,
  Web = 8,
  Word_of_Mouth = 9,
  Other = 10,
}
```

#### LeadQualityCode
```typescript
enum LeadQualityCode {
  Hot = 1,
  Warm = 2,
  Cold = 3,
}
```

#### BudgetStatusCode
```typescript
enum BudgetStatusCode {
  No_Committed_Budget = 0,
  May_Buy = 1,
  Can_Buy = 2,
  Will_Buy = 3,
}
```

---

#### OpportunityStateCode
```typescript
enum OpportunityStateCode {
  Open = 0,
  Won = 1,
  Lost = 2,
}
```

#### OpportunityStatusCode
```typescript
enum OpportunityStatusCode {
  In_Progress = 1,
  On_Hold = 2,
  Won = 3,
  Canceled = 4,
  Out_Sold = 5,
  Lost = 6,
}
```

#### SalesStageCode
```typescript
enum SalesStageCode {
  Qualify = 0,
  Develop = 1,
  Propose = 2,
  Close = 3,
}
```

**Probabilidades**:
- Qualify: 25%
- Develop: 50%
- Propose: 75%
- Close: 100% (Won) / 0% (Lost)

---

#### QuoteStateCode
```typescript
enum QuoteStateCode {
  Draft = 0,
  Active = 1,
  Won = 2,
  Closed = 3,
}
```

#### QuoteStatusCode
```typescript
enum QuoteStatusCode {
  Open = 1,
  In_Progress = 2,
  Closed = 3,
  Lost = 4,
  Canceled = 5,
  Revised = 6,
}
```

---

#### OrderStateCode
```typescript
enum OrderStateCode {
  Active = 0,
  Submitted = 1,
  Canceled = 2,
  Fulfilled = 3,
  Invoiced = 4,
}
```

#### OrderStatusCode
```typescript
enum OrderStatusCode {
  New = 1,
  Pending = 2,
  In_Progress = 3,
  No_Money = 4,
  Complete = 100000,
  Partial = 100001,
  Invoiced = 100002,
  Canceled = 100003,
}
```

---

#### InvoiceStateCode
```typescript
enum InvoiceStateCode {
  Active = 0,
  Closed = 1,
  Paid = 2,
  Canceled = 3,
}
```

---

#### AccountStateCode
```typescript
enum AccountStateCode {
  Active = 0,
  Inactive = 1,
}
```

#### AccountCategoryCode
```typescript
enum AccountCategoryCode {
  Preferred_Customer = 1,
  Standard = 2,
}
```

#### IndustryCode
```typescript
enum IndustryCode {
  Accounting = 1,
  Agriculture = 2,
  Broadcasting = 3,
  Consulting = 4,
  Education = 5,
  Financial_Services = 6,
  Government = 7,
  Healthcare = 8,
  Hospitality = 9,
  Insurance = 10,
  Legal_Services = 11,
  Manufacturing = 12,
  Real_Estate = 13,
  Retail = 14,
  Technology = 15,
  Telecommunications = 16,
  Transportation = 17,
  Other = 18,
}
```

---

#### ContactStateCode
```typescript
enum ContactStateCode {
  Active = 0,
  Inactive = 1,
}
```

---

#### ActivityStateCode
```typescript
enum ActivityStateCode {
  Open = 0,
  Completed = 1,
  Canceled = 2,
  Scheduled = 3,
}
```

#### ActivityTypeCode
```typescript
enum ActivityTypeCode {
  Email = 'email',
  Phone_Call = 'phonecall',
  Task = 'task',
  Appointment = 'appointment',
  Meeting = 'meeting',
}
```

---

### Términos de Pago y Envío

#### PaymentTermsCode
```typescript
enum PaymentTermsCode {
  Net_30 = 1,
  Two_Percent_10_Net_30 = 2,
  Net_45 = 3,
  Net_60 = 4,
}
```

#### FreightTermsCode
```typescript
enum FreightTermsCode {
  FOB = 1,      // Free on Board
  No_Charge = 2,
}
```

#### ShippingMethodCode
```typescript
enum ShippingMethodCode {
  Airborne = 1,
  DHL = 2,
  FedEx = 3,
  UPS = 4,
  Postal_Mail = 5,
  Full_Load = 6,
  Will_Call = 7,
}
```

#### PriorityCode
```typescript
enum PriorityCode {
  Low = 0,
  Normal = 1,
  High = 2,
  Urgent = 3,
}
```

---

### Seguridad

#### Permission
```typescript
enum Permission {
  Create = 'create',
  Read = 'read',
  Update = 'update',
  Delete = 'delete',
  Share = 'share',
  Export = 'export',
}
```

#### PermissionEntity
```typescript
enum PermissionEntity {
  Lead = 'lead',
  Opportunity = 'opportunity',
  Account = 'account',
  Contact = 'contact',
  Quote = 'quote',
  QuoteDetail = 'quote-detail',
  Order = 'order',
  OrderDetail = 'order-detail',
  Invoice = 'invoice',
  InvoiceDetail = 'invoice-detail',
  Product = 'product',
  Activity = 'activity',
  SystemUser = 'system-user',
  AuditLog = 'audit-log',
}
```

#### AccessLevel
```typescript
enum AccessLevel {
  None = 'none',           // Sin acceso
  User = 'user',           // Solo registros propios
  Team = 'team',           // Registros del equipo
  BusinessUnit = 'bu',     // Registros de la unidad de negocio
  Organization = 'org',    // Todos los registros
}
```

---

## 🔄 Flujos de Negocio

### 1. Flujo Completo de Ventas (Lead-to-Cash)

```
┌──────────┐
│  Lead    │ (Lead creado - primer contacto)
│ Open (0) │
└────┬─────┘
     │ qualify()
     ▼
┌──────────────┐
│ Opportunity  │ (Opportunity creada)
│   Open (0)   │ + Account (B2B) + Contact
└──────┬───────┘
       │ create quote
       ▼
┌──────────┐
│  Quote   │ (Quote Draft)
│ Draft (0)│ + Quote Lines (productos)
└────┬─────┘
     │ activate()
┌────┴─────┐
│  Quote   │ (Quote Active - enviada al cliente)
│ Active(1)│
└────┬─────┘
     │ win()
     ▼
┌──────────┐
│  Order   │ (Order creado automáticamente)
│ Active(0)│ + Order Lines (copiadas de Quote)
└────┬─────┘
     │ fulfill()
┌────┴─────┐
│  Order   │ (Order cumplido)
│Fulfilled │
│    (3)   │
└────┬─────┘
     │ create invoice
     ▼
┌──────────┐
│ Invoice  │ (Invoice creado automáticamente)
│ Active(0)│ + Invoice Lines (copiadas de Order)
└────┬─────┘
     │ mark as paid
┌────┴─────┐
│ Invoice  │ (Invoice pagado - fin del ciclo)
│  Paid(2) │
└──────────┘
```

---

### 2. Flujo de Calificación de Lead (DETALLADO)

**Endpoint**: `POST /api/leads/{id}/qualify`

**Input DTO**:
```typescript
interface QualifyLeadDto {
  createAccount: boolean          // ¿Crear nuevo Account?
  existingAccountId?: string      // O vincular Account existente
  createContact: boolean          // ¿Crear nuevo Contact?
  existingContactId?: string      // O vincular Contact existente
  opportunityName: string         // REQUIRED
  estimatedValue: number          // REQUIRED
  estimatedCloseDate: string      // REQUIRED: ISO 8601
  description?: string
}
```

#### Escenario A: Lead B2B (Nuevo Cliente Empresarial)

**Estado Inicial**:
```typescript
Lead {
  leadid: "lead-001",
  firstname: "John",
  lastname: "Smith",
  companyname: "Tech Innovations Inc",  // ← Indica B2B
  emailaddress1: "john.smith@techinnovations.com",
  telephone1: "+1-555-1234",
  leadsourcecode: LeadSourceCode.Web,
  statecode: LeadStateCode.Open         // 0
}
```

**Proceso Backend**:
```typescript
async function qualifyLead(leadId: string, dto: QualifyLeadDto) {
  // 1. Validar Lead
  const lead = await leadService.getById(leadId)
  if (lead.statecode !== LeadStateCode.Open) {
    throw new Error('LEAD_ALREADY_QUALIFIED')
  }

  // 2. Determinar si es B2B o B2C
  const isB2B = !!lead.companyname

  // 3. Crear/Vincular Account (solo si B2B)
  let accountId: string | undefined
  if (isB2B && dto.createAccount) {
    const account = await accountService.create({
      name: lead.companyname!,
      emailaddress1: lead.emailaddress1,
      telephone1: lead.telephone1,
      address1_line1: lead.address1_line1,
      address1_city: lead.address1_city,
      address1_stateorprovince: lead.address1_stateorprovince,
      address1_postalcode: lead.address1_postalcode,
      address1_country: lead.address1_country,
      ownerid: lead.ownerid
    })
    accountId = account.accountid
  } else if (dto.existingAccountId) {
    accountId = dto.existingAccountId
  }

  // 4. Crear/Vincular Contact
  let contactId: string
  if (dto.createContact) {
    const contact = await contactService.create({
      firstname: lead.firstname,
      lastname: lead.lastname,
      emailaddress1: lead.emailaddress1,
      telephone1: lead.telephone1,
      mobilephone: lead.mobilephone,
      jobtitle: lead.jobtitle,
      address1_line1: lead.address1_line1,
      address1_city: lead.address1_city,
      address1_stateorprovince: lead.address1_stateorprovince,
      address1_postalcode: lead.address1_postalcode,
      address1_country: lead.address1_country,
      parentcustomerid: accountId,      // Vincula a Account (B2B) o null (B2C)
      ownerid: lead.ownerid
    })
    contactId = contact.contactid
  } else {
    contactId = dto.existingContactId!
  }

  // 5. Crear Opportunity
  const opportunity = await opportunityService.create({
    name: dto.opportunityName,
    originatingleadid: lead.leadid,     // 🔗 VÍNCULO CLAVE
    customerid: isB2B ? accountId! : contactId,
    customeridtype: isB2B ? CustomerType.Account : CustomerType.Contact,
    salesstage: SalesStageCode.Qualify,
    closeprobability: 25,               // Auto-calculado
    estimatedvalue: dto.estimatedValue,
    estimatedclosedate: dto.estimatedCloseDate,
    description: dto.description,
    ownerid: lead.ownerid
  })

  // 6. Actualizar Lead a Qualified
  await leadService.update(lead.leadid, {
    statecode: LeadStateCode.Qualified, // 0 → 1
    statuscode: LeadStatusCode.Qualified
  })

  // 7. Registrar Audit Log
  await auditLogService.logAction(
    AuditAction.Qualify,
    PermissionEntity.Lead,
    lead.leadid,
    lead.fullname,
    session.user.id,
    session.user.name,
    session.user.role,
    `Qualified lead "${lead.fullname}" - created Opportunity "${opportunity.name}"`
  )

  // 8. Retornar entidades creadas
  return {
    leadId: lead.leadid,
    accountId: accountId,
    contactId: contactId,
    opportunityId: opportunity.opportunityid,
    account: accountId ? await accountService.getById(accountId) : undefined,
    contact: await contactService.getById(contactId),
    opportunity: opportunity
  }
}
```

**Resultado**:

```typescript
// Account creado
Account {
  accountid: "acc-001",
  name: "Tech Innovations Inc",
  emailaddress1: "john.smith@techinnovations.com",
  statecode: AccountStateCode.Active
}

// Contact creado
Contact {
  contactid: "con-001",
  firstname: "John",
  lastname: "Smith",
  fullname: "John Smith",
  parentcustomerid: "acc-001",        // ← Vinculado a Account
  statecode: ContactStateCode.Active
}

// Opportunity creada
Opportunity {
  opportunityid: "opp-001",
  name: "Tech Innovations Inc - Sales Opportunity",
  originatingleadid: "lead-001",      // 🔗 Lead origen
  customerid: "acc-001",              // ← Account
  customeridtype: CustomerType.Account,
  salesstage: SalesStageCode.Qualify,
  closeprobability: 25,
  statecode: OpportunityStateCode.Open
}

// Lead actualizado
Lead {
  leadid: "lead-001",
  statecode: LeadStateCode.Qualified, // ← CAMBIÓ de 0 a 1
  // ... resto sin cambios
}
```

#### Escenario B: Lead B2C (Cliente Individual)

**Estado Inicial**:
```typescript
Lead {
  leadid: "lead-002",
  firstname: "Mary",
  lastname: "Johnson",
  companyname: null,                  // ← Sin empresa = B2C
  emailaddress1: "mary.johnson@email.com",
  statecode: LeadStateCode.Open
}
```

**Resultado**: Solo Contact + Opportunity (sin Account)

```typescript
// Contact creado
Contact {
  contactid: "con-002",
  firstname: "Mary",
  lastname: "Johnson",
  parentcustomerid: null,             // ← Sin Account (B2C)
  statecode: ContactStateCode.Active
}

// Opportunity creada
Opportunity {
  opportunityid: "opp-002",
  name: "Mary Johnson - Sales Opportunity",
  originatingleadid: "lead-002",
  customerid: "con-002",              // ← Contact directo
  customeridtype: CustomerType.Contact,
  statecode: OpportunityStateCode.Open
}
```

**⚠️ IMPORTANTE**:
- El Lead NO se elimina, solo cambia a `statecode: Qualified (1)`
- Se mantiene como registro histórico
- Vínculo `Opportunity.originatingleadid` permite rastrear el origen

---

### 3. Business Process Flow (BPF) - Lead Qualification

El frontend implementa un **Business Process Flow** visual que guía al usuario:

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌───────────┐ ── ┌───────────┐ ── ┌───────────┐ ── ┌─────────┐│
│  │ ✓ Qualify │    │ ● Develop │    │ ○ Propose │    │ ○ Close ││
│  └───────────┘    └───────────┘    └───────────┘    └─────────┘│
│   Completed        Active           Pending          Pending    │
└─────────────────────────────────────────────────────────────────┘
```

**Qualify Stage - Campos requeridos**:
- ☑ Budget Amount (`budgetamount`)
- ☑ Budget Status (`budgetstatus`)
- ☑ Purchase Timeframe (`timeframe`)
- ☐ Need Analysis (`needanalysis`)
- ☐ Decision Maker (`decisionmaker`)

El backend debe persistir estos campos en el modelo `Lead`.

---

### 4. Flujo de Quote → Order (Win Quote)

**Endpoint**: `POST /api/quotes/{id}/win`

**Validaciones**:
```typescript
// 1. Quote debe estar Active
if (quote.statecode !== QuoteStateCode.Active) {
  throw new Error('QUOTE_NOT_ACTIVE')
}

// 2. Quote debe tener al menos 1 línea
const lines = await quoteDetailService.getByQuoteId(quoteId)
if (lines.length === 0) {
  throw new Error('QUOTE_HAS_NO_LINES')
}
```

**Proceso**:
```typescript
async function winQuote(quoteId: string) {
  // 1. Obtener Quote y Lines
  const quote = await quoteService.getById(quoteId)
  const quoteLines = await quoteDetailService.getByQuoteId(quoteId)

  // 2. Crear Order (copiar datos de Quote)
  const order = await orderService.create({
    name: quote.name,
    quoteid: quote.quoteid,
    opportunityid: quote.opportunityid,
    customerid: quote.customerid,
    customeridtype: quote.customeridtype,
    totalamount: quote.totalamount,
    freightamount: quote.freightamount,
    discountamount: quote.discountamount,
    totaltax: quote.totaltax,
    shipto_name: quote.shipto_name,
    shipto_line1: quote.shipto_line1,
    shipto_city: quote.shipto_city,
    // ... copiar todos los campos relevantes
    ownerid: quote.ownerid
  })

  // 3. Copiar Quote Lines → Order Lines
  for (const quoteLine of quoteLines) {
    await orderDetailService.create({
      salesorderid: order.salesorderid,
      productid: quoteLine.productid,
      productdescription: quoteLine.productdescription,
      quantity: quoteLine.quantity,
      priceperunit: quoteLine.priceperunit,
      manualdiscountamount: quoteLine.manualdiscountamount,
      tax: quoteLine.tax,
      extendedamount: quoteLine.extendedamount
    })
  }

  // 4. Actualizar Quote a Won
  await quoteService.update(quoteId, {
    statecode: QuoteStateCode.Won,    // 1 → 2
    statuscode: QuoteStatusCode.Won,
    closedon: new Date().toISOString()
  })

  // 5. Audit Log
  await auditLogService.logAction(
    AuditAction.Win,
    PermissionEntity.Quote,
    quote.quoteid,
    quote.name,
    session.user.id,
    session.user.name,
    session.user.role,
    `Quote "${quote.name}" won - Order ${order.ordernumber} created`
  )

  return order
}
```

---

### 5. Flujo de Order → Invoice (Fulfill Order)

**Endpoint**: `POST /api/orders/{id}/fulfill`

**Proceso**:
```typescript
async function fulfillOrder(orderId: string, dto: FulfillOrderDto) {
  // 1. Validar Order
  const order = await orderService.getById(orderId)
  if (order.statecode === OrderStateCode.Fulfilled) {
    throw new Error('ORDER_ALREADY_FULFILLED')
  }

  // 2. Actualizar Order a Fulfilled
  await orderService.update(orderId, {
    statecode: OrderStateCode.Fulfilled,  // → 3
    datefulfilled: dto.datefulfilled || new Date().toISOString()
  })

  // 3. Crear Invoice (copiar datos de Order)
  const invoice = await invoiceService.create({
    name: order.name,
    salesorderid: order.salesorderid,
    opportunityid: order.opportunityid,
    customerid: order.customerid,
    customeridtype: order.customeridtype,
    totalamount: order.totalamount,
    duedate: calculateDueDate(order.paymenttermscode),
    // ... copiar campos relevantes
    ownerid: order.ownerid
  })

  // 4. Copiar Order Lines → Invoice Lines
  const orderLines = await orderDetailService.getByOrderId(orderId)
  for (const orderLine of orderLines) {
    await invoiceDetailService.create({
      invoiceid: invoice.invoiceid,
      productid: orderLine.productid,
      productdescription: orderLine.productdescription,
      quantity: orderLine.quantity,
      priceperunit: orderLine.priceperunit,
      extendedamount: orderLine.extendedamount
    })
  }

  // 5. Actualizar Order a Invoiced
  await orderService.update(orderId, {
    statecode: OrderStateCode.Invoiced   // → 4
  })

  // 6. Audit Log
  await auditLogService.logAction(
    AuditAction.Fulfill,
    PermissionEntity.Order,
    order.salesorderid,
    order.name,
    session.user.id,
    session.user.name,
    session.user.role,
    `Order fulfilled - Invoice ${invoice.invoicenumber} created`
  )

  return invoice
}
```

---

### 6. Relaciones y Queries Importantes

#### Obtener Opportunity desde Lead
```typescript
// API: GET /api/opportunities?originatingleadid={leadId}
async function getOpportunityFromLead(leadId: string) {
  return await opportunityService.getAll({
    filter: { originatingleadid: leadId }
  })
}
```

#### Obtener Lead desde Opportunity
```typescript
// API: GET /api/leads/{id}
async function getLeadFromOpportunity(opportunityId: string) {
  const opportunity = await opportunityService.getById(opportunityId)
  if (opportunity?.originatingleadid) {
    return await leadService.getById(opportunity.originatingleadid)
  }
  return null
}
```

#### Obtener Order desde Quote
```typescript
// API: GET /api/orders?quoteid={quoteId}
async function getOrderFromQuote(quoteId: string) {
  return await orderService.getAll({
    filter: { quoteid: quoteId }
  })
}
```

#### Obtener Invoice desde Order
```typescript
// API: GET /api/invoices?salesorderid={orderId}
async function getInvoiceFromOrder(orderId: string) {
  return await invoiceService.getAll({
    filter: { salesorderid: orderId }
  })
}
```

---

### 7. Transiciones de Estado Válidas

#### Lead
```
Open (0) → Qualified (1)    ✓ qualify()
Open (0) → Disqualified (2) ✓ disqualify()
Qualified (1) → Open (0)    ✗ NO PERMITIDO
```

#### Opportunity
```
Open (0) → Won (1)          ✓ close(Win)
Open (0) → Lost (2)         ✓ close(Loss)
Won (1) → Open (0)          ✗ NO PERMITIDO
Lost (2) → Open (0)         ✓ reopen() (opcional)
```

#### Quote
```
Draft (0) → Active (1)      ✓ activate()
Active (1) → Won (2)        ✓ win()
Active (1) → Closed (3)     ✓ close(Lost)
Draft (0) → Won (2)         ✗ NO PERMITIDO (debe activarse primero)
Won (2) → Draft (0)         ✗ NO PERMITIDO
```

#### Order
```
Active (0) → Submitted (1)  ✓ submit()
Submitted (1) → Fulfilled (3) ✓ fulfill()
Fulfilled (3) → Invoiced (4)  ✓ (auto al crear Invoice)
Active (0) → Canceled (2)   ✓ cancel()
Fulfilled (3) → Canceled (2) ✗ NO PERMITIDO
```

#### Invoice
```
Active (0) → Paid (2)       ✓ markAsPaid()
Active (0) → Canceled (3)   ✓ cancel()
Paid (2) → Active (0)       ✗ NO PERMITIDO
```

---

## 📡 API Contracts

### Respuestas Estándar

#### ApiSuccessResponse
```typescript
{
  success: true,
  data: T,
  message?: string
}
```

#### ApiErrorResponse
```typescript
{
  success: false,
  error: {
    code: string,
    message: string,
    details?: Record<string, string[]>
  }
}
```

### Códigos de Error

```typescript
enum ApiErrorCode {
  // Authentication & Authorization
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  INVALID_TOKEN = 'INVALID_TOKEN',
  TOKEN_EXPIRED = 'TOKEN_EXPIRED',

  // Validation
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  INVALID_INPUT = 'INVALID_INPUT',
  REQUIRED_FIELD_MISSING = 'REQUIRED_FIELD_MISSING',

  // Resource
  NOT_FOUND = 'NOT_FOUND',
  ALREADY_EXISTS = 'ALREADY_EXISTS',
  CONFLICT = 'CONFLICT',

  // Business Logic
  INVALID_STATE_TRANSITION = 'INVALID_STATE_TRANSITION',
  LEAD_ALREADY_QUALIFIED = 'LEAD_ALREADY_QUALIFIED',
  OPPORTUNITY_ALREADY_CLOSED = 'OPPORTUNITY_ALREADY_CLOSED',
  QUOTE_NOT_ACTIVE = 'QUOTE_NOT_ACTIVE',
  INSUFFICIENT_PERMISSIONS = 'INSUFFICIENT_PERMISSIONS',

  // Server
  INTERNAL_SERVER_ERROR = 'INTERNAL_SERVER_ERROR',
  SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE',

  // Network
  NETWORK_ERROR = 'NETWORK_ERROR',
  TIMEOUT = 'TIMEOUT'
}
```

### Paginación

```typescript
interface PaginatedResponse<T> {
  items: T[]
  totalCount: number
  page: number
  pageSize: number
  totalPages: number
  hasNextPage: boolean
  hasPreviousPage: boolean
}
```

---

## 🕒 Campos de Auditoría

Todos los registros incluyen estos campos automáticos:

```typescript
{
  createdon: string      // ISO 8601 datetime - Fecha de creación
  modifiedon: string     // ISO 8601 datetime - Fecha de última modificación
  createdby?: string     // User ID que creó el registro
  modifiedby?: string    // User ID que modificó el registro
}
```

**⚠️ IMPORTANTE**: El backend debe gestionar estos campos automáticamente:
- `createdon` y `createdby` → al crear
- `modifiedon` y `modifiedby` → al actualizar

---

## 🔐 Sistema de Permisos (RBAC)

### Matriz de Permisos por Rol

| Rol                      | Leads | Opportunities | Quotes | Orders | Invoices | Products | Access Level |
|--------------------------|-------|---------------|--------|--------|----------|----------|--------------|
| System Administrator     | CRUDE | CRUDE         | CRUDE  | CRUDE  | CRUDE    | CRUDE    | Organization |
| Sales Manager            | CRUDE | CRUDE         | CRUDE  | CRUDE  | CRUDE    | RE       | Team         |
| Sales Representative     | CRUDE | CRUDE         | CRUDE  | CRU E  | CRU E    | R        | User         |
| Customer Service Rep     | R     | R             | R      | RU     | R        | R        | User         |
| Marketing Professional   | CRUE  | R             | -      | -      | -        | R        | Team         |

**Leyenda**:
- C = Create
- R = Read
- U = Update
- D = Delete
- E = Export

### Record Ownership

- Todos los registros tienen `ownerid`
- **User Level**: Solo ve sus propios registros
- **Team Level**: Ve registros de su equipo
- **Organization Level**: Ve todos los registros

---

## 📝 Notas Importantes

### 1. Relaciones Polimórficas

**Opportunity, Quote, Order, Invoice** usan `customerid` polimórfico:

```typescript
{
  customerid: string,           // GUID
  customeridtype: 'account' | 'contact'
}
```

**Activity** usa `regardingobjectid` polimórfico:

```typescript
{
  regardingobjectid: string,    // GUID
  regardingobjectidtype: 'lead' | 'opportunity' | 'account' | 'contact'
}
```

### 2. Campos Computados

No deben guardarse en BD, se calculan dinámicamente:

- `fullname` = `firstname` + `lastname`
- `totalamount` = suma de líneas de detalle
- `closeprobability` = basado en `salesstage`
- `extendedamount` = `quantity` * `priceperunit` - descuentos + impuestos

### 3. Generación Automática

Estos campos se generan automáticamente:

- `*number` (quotenumber, ordernumber, invoicenumber)
- `*id` (GUIDs)
- `createdon`, `modifiedon`

### 4. Validaciones de Estado

- Lead calificado: `statecode` debe ser Open (0)
- Quote activado: debe tener al menos 1 línea
- Quote ganado: `statecode` debe ser Active (1)
- Order cumplido: `statecode` debe ser Submitted (1)

### 5. Formatos de Fecha

- **Dates**: ISO 8601 date (`YYYY-MM-DD`)
- **Datetimes**: ISO 8601 datetime (`YYYY-MM-DDTHH:mm:ss.sssZ`)

---

## 🚀 Endpoints de API Requeridos

### Authentication
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/session` - Get session

### Leads
- `GET /api/leads` - List (con filtros y paginación)
- `GET /api/leads/{id}` - Get by ID
- `POST /api/leads` - Create
- `PUT /api/leads/{id}` - Update
- `DELETE /api/leads/{id}` - Delete
- `POST /api/leads/{id}/qualify` - Qualify

### Opportunities
- `GET /api/opportunities` - List
- `GET /api/opportunities/{id}` - Get by ID
- `POST /api/opportunities` - Create
- `PUT /api/opportunities/{id}` - Update
- `DELETE /api/opportunities/{id}` - Delete
- `POST /api/opportunities/{id}/close` - Close (Win/Loss)

### Accounts
- `GET /api/accounts` - List
- `GET /api/accounts/{id}` - Get by ID
- `POST /api/accounts` - Create
- `PUT /api/accounts/{id}` - Update
- `DELETE /api/accounts/{id}` - Delete

### Contacts
- `GET /api/contacts` - List
- `GET /api/contacts/{id}` - Get by ID
- `POST /api/contacts` - Create
- `PUT /api/contacts/{id}` - Update
- `DELETE /api/contacts/{id}` - Delete

### Quotes
- `GET /api/quotes` - List
- `GET /api/quotes/{id}` - Get by ID
- `POST /api/quotes` - Create
- `PUT /api/quotes/{id}` - Update
- `DELETE /api/quotes/{id}` - Delete
- `POST /api/quotes/{id}/activate` - Activate
- `POST /api/quotes/{id}/win` - Win (genera Order)
- `POST /api/quotes/{id}/close` - Close (Lost)
- `GET /api/quotes/{id}/pdf` - Generate PDF

### Quote Details
- `GET /api/quotes/{id}/lines` - List lines
- `POST /api/quotes/{id}/lines` - Add line
- `PUT /api/quotes/{id}/lines/{lineId}` - Update line
- `DELETE /api/quotes/{id}/lines/{lineId}` - Delete line

### Orders
- `GET /api/orders` - List
- `GET /api/orders/{id}` - Get by ID
- `POST /api/orders` - Create
- `PUT /api/orders/{id}` - Update
- `DELETE /api/orders/{id}` - Delete
- `POST /api/orders/{id}/fulfill` - Fulfill (genera Invoice)
- `GET /api/orders/{id}/pdf` - Generate PDF

### Invoices
- `GET /api/invoices` - List
- `GET /api/invoices/{id}` - Get by ID
- `POST /api/invoices` - Create
- `PUT /api/invoices/{id}` - Update
- `DELETE /api/invoices/{id}` - Delete
- `POST /api/invoices/{id}/mark-paid` - Mark as paid
- `GET /api/invoices/{id}/pdf` - Generate PDF

### Products
- `GET /api/products` - List
- `GET /api/products/{id}` - Get by ID
- `POST /api/products` - Create
- `PUT /api/products/{id}` - Update
- `DELETE /api/products/{id}` - Delete

### Activities
- `GET /api/activities` - List
- `GET /api/activities/{id}` - Get by ID
- `POST /api/activities` - Create
- `PUT /api/activities/{id}` - Update
- `DELETE /api/activities/{id}` - Delete
- `POST /api/activities/{id}/complete` - Complete

### Users
- `GET /api/users` - List
- `GET /api/users/{id}` - Get by ID
- `POST /api/users` - Create
- `PUT /api/users/{id}` - Update
- `DELETE /api/users/{id}` - Delete

### Audit Logs
- `GET /api/audit-logs` - List (con filtros)
- `GET /api/audit-logs/{id}` - Get by ID
- `GET /api/audit-logs/entity/{entity}/{recordId}` - Get by record

---

## ✅ Validaciones y Reglas de Negocio

### Validaciones Críticas por Entidad

#### Lead
- **firstname**: REQUIRED, min_length=1, max_length=100
- **lastname**: REQUIRED, min_length=1, max_length=100
- **leadsourcecode**: REQUIRED, valor entre 1-10
- **emailaddress1**: Formato email válido (opcional)
- **companyname**: Requerido para B2B, max_length=200

**Reglas de Calificación**:
- Solo Leads en `statecode = Open (0)` pueden calificarse
- Si `companyname` existe → B2B (crear/vincular Account)
- Si `companyname` es null → B2C (NO crear Account)
- Lead calificado cambia a `statecode = Qualified (1)`, NO Inactive

#### Opportunity
- **name**: REQUIRED, min_length=1
- **customerid**: REQUIRED (UUID válido)
- **customeridtype**: REQUIRED ('account' | 'contact')
- **estimatedvalue**: REQUIRED, > 0
- **estimatedclosedate**: REQUIRED, >= fecha actual
- **closeprobability**: AUTO-CALCULADO según salesstage (NO permitir override manual)

**Validación Customer Polimórfico**:
```python
if opportunity.customeridtype == 'account':
    assert Account.objects.filter(accountid=opportunity.customerid).exists()
elif opportunity.customeridtype == 'contact':
    assert Contact.objects.filter(contactid=opportunity.customerid).exists()
```

#### Quote
- **effectiveto**: DEBE ser > effectivefrom
- **Activación**: Requiere al menos 1 QuoteDetail
- **Win**: Quote DEBE estar en Active (statecode=1)
- **totalamount**: COMPUTED = SUM(QuoteDetail.extendedamount) + freightamount

#### Order
- **Fulfillment**: Solo Orders en `statecode = Submitted (1)` pueden cumplirse
- **Invoice generation**: Al cumplir, crear Invoice automáticamente

#### Invoice
- **totalbalance**: COMPUTED = totalamount - totalpaid
- **Si totalbalance <= 0**: Auto-cambiar a `statecode = Paid (2)`

---

### Matriz de Transiciones de Estados Válidas

| Entidad | Desde → Hasta | Condición | Acción |
|---------|---------------|-----------|--------|
| Lead | Open → Qualified | Crear Account/Contact/Opportunity | ✅ Permitido |
| Lead | Open → Disqualified | Establecer motivo | ✅ Permitido |
| Lead | Qualified → Open | - | ❌ NO PERMITIDO |
| Opportunity | Open → Won | Requiere Quote Active + actualvalue > 0 | ✅ Permitido |
| Opportunity | Open → Lost | Requiere closestatus (motivo) | ✅ Permitido |
| Quote | Draft → Active | Requiere ≥1 QuoteDetail | ✅ Permitido |
| Quote | Active → Won | Crea Order, cierra Opportunity | ✅ Permitido |
| Quote | Draft → Won | - | ❌ NO PERMITIDO |
| Order | Submitted → Fulfilled | Crea Invoice | ✅ Permitido |
| Invoice | Active → Paid | totalbalance = 0 | ✅ Permitido |

---

## 🗄️ Recomendaciones de Base de Datos

### Índices Críticos (PostgreSQL)

```sql
-- Lead
CREATE INDEX idx_lead_statecode_createdon ON lead(statecode, createdon DESC);
CREATE INDEX idx_lead_ownerid_statecode ON lead(ownerid, statecode);
CREATE INDEX idx_lead_fulltext ON lead USING gin(to_tsvector('english', firstname || ' ' || lastname || ' ' || COALESCE(companyname, '')));

-- Opportunity
CREATE INDEX idx_opportunity_statecode_closedate ON opportunity(statecode, estimatedclosedate DESC);
CREATE INDEX idx_opportunity_ownerid ON opportunity(ownerid, statecode);
CREATE INDEX idx_opportunity_customerid ON opportunity(customerid);
CREATE INDEX idx_opportunity_originatingleadid ON opportunity(originatingleadid);

-- Quote
CREATE INDEX idx_quote_statecode_createdon ON quote(statecode, createdon DESC);
CREATE INDEX idx_quote_opportunityid ON quote(opportunityid);
CREATE INDEX idx_quote_effectiveto ON quote(effectiveto) WHERE statecode IN (0, 1);

-- Order
CREATE INDEX idx_order_statecode_createdon ON salesorder(statecode, createdon DESC);
CREATE INDEX idx_order_quoteid ON salesorder(quoteid);

-- Invoice
CREATE INDEX idx_invoice_statecode_duedate ON invoice(statecode, duedate);
CREATE INDEX idx_invoice_salesorderid ON invoice(salesorderid);
CREATE INDEX idx_invoice_balance ON invoice(totalbalance) WHERE totalbalance > 0;

-- Activity
CREATE INDEX idx_activity_regardingobjectid ON activitypointer(regardingobjectid);
CREATE INDEX idx_activity_ownerid_statecode ON activitypointer(ownerid, statecode);

-- AuditLog
CREATE INDEX idx_audit_entity_recordid ON audit(entity, recordid);
CREATE INDEX idx_audit_timestamp ON audit(timestamp DESC);
```

### Constraints de Integridad

```sql
-- Estados válidos
ALTER TABLE lead ADD CONSTRAINT chk_lead_statecode CHECK (statecode IN (0, 1, 2));
ALTER TABLE opportunity ADD CONSTRAINT chk_opp_statecode CHECK (statecode IN (0, 1, 2));

-- Customer polimórfico
ALTER TABLE opportunity ADD CONSTRAINT chk_opp_customertype
    CHECK (customeridtype IN ('account', 'contact'));

-- Fechas
ALTER TABLE quote ADD CONSTRAINT chk_quote_dates CHECK (effectiveto > effectivefrom);

-- Valores positivos
ALTER TABLE opportunity ADD CONSTRAINT chk_opp_value CHECK (estimatedvalue > 0);
ALTER TABLE quotedetail ADD CONSTRAINT chk_detail_qty CHECK (quantity > 0);
```

### Triggers para Auto-Generación

```sql
-- Auto-generar quotenumber
CREATE SEQUENCE quote_number_seq START 1;

CREATE OR REPLACE FUNCTION generate_quote_number()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.quotenumber IS NULL THEN
        NEW.quotenumber = 'QUO-' || LPAD(nextval('quote_number_seq')::TEXT, 6, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_quote_number BEFORE INSERT ON quote
    FOR EACH ROW EXECUTE FUNCTION generate_quote_number();
```

---

## 📚 Referencias

- **Modelo Base**: Microsoft Dynamics 365 Sales (Common Data Service)
- **Ubicación Código Frontend**: `src/core/contracts/`
- **Tecnologías Backend**: Django 5.0+ con Django Ninja, PostgreSQL 15+
- **Documentación Adicional**:
  - `BPF_VISUAL_GUIDE.md` - Business Process Flows
  - `SECURITY_INTEGRATION.md` - Sistema de seguridad
  - `PERMISSION_MATRIX.md` - Matriz de permisos detallada
  - `CLAUDE.md` - Guía arquitectónica del proyecto

---

**Última Actualización**: 2025-11-27
**Versión**: 2.0 (Django + Ninja Implementation Guide)
**Autor**: Sistema de análisis de repositorio + Guía de implementación Django
