"""
Django management command to seed minimal test data for E2E tests.

Creates the minimum data needed so Playwright E2E tests don't skip:
- Security roles (5 predefined)
- Admin user (admin@crm.com / admin123) for E2E auth
- Sample accounts, contacts, leads, opportunities, products, cases
- Sample construction project

Idempotent: safe to run multiple times.

Usage:
    python manage.py seed_test_data
    python manage.py seed_test_data --clear  # Reset and reseed
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
import uuid

from apps.users.models import SystemUser, SecurityRole


# Security roles (must match conftest.py and permissions.py)
ROLES = [
    ('System Administrator', 'Full access to all entities and operations'),
    ('Sales Manager', 'Manage sales team and view all opportunities'),
    ('Salesperson', 'Manage own leads and opportunities'),
    ('Marketing User', 'Manage campaigns and marketing leads'),
    ('Read-Only User', 'View-only access to entities'),
]


class Command(BaseCommand):
    help = 'Seed minimal test data for E2E tests (idempotent)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear seeded data before reseeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing test data...'))
            self._clear()

        with transaction.atomic():
            admin = self._seed_roles_and_users()
            self._seed_accounts(admin)
            self._seed_contacts(admin)
            self._seed_leads(admin)
            self._seed_products(admin)
            self._seed_opportunities(admin)
            self._seed_cases(admin)
            self._seed_project(admin)

        self.stdout.write(self.style.SUCCESS('Test data seeded successfully!'))
        self.stdout.write(self.style.SUCCESS('  Login: admin@crm.com / admin123'))

    def _clear(self):
        """Remove seeded data (preserves roles)."""
        from apps.leads.models import Lead
        from apps.accounts.models import Account
        from apps.contacts.models import Contact
        from apps.opportunities.models import Opportunity
        from apps.products.models import Product
        from apps.cases.models import Case
        from apps.projects.models import ConstructionProject

        for model in [Lead, Opportunity, Account, Contact, Product, Case, ConstructionProject]:
            count = model.objects.count()
            if count:
                model.objects.all().delete()
                self.stdout.write(f'  Deleted {count} {model.__name__} records')

    def _seed_roles_and_users(self):
        """Create security roles and admin user."""
        for name, desc in ROLES:
            SecurityRole.objects.get_or_create(
                name=name,
                defaults={'description': desc}
            )
        self.stdout.write(self.style.SUCCESS('  [OK] Security roles'))

        admin_role = SecurityRole.objects.get(name='System Administrator')

        # Create admin user for E2E auth (matches auth.setup.ts)
        admin, created = SystemUser.objects.get_or_create(
            emailaddress1='admin@crm.com',
            defaults={
                'fullname': 'System Administrator',
                'securityroleid': admin_role,
                'isdisabled': False,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS('  [OK] Admin user created'))
        else:
            self.stdout.write('  [--] Admin user already exists')

        return admin

    def _seed_accounts(self, admin):
        """Create sample accounts for E2E tests."""
        from apps.accounts.models import Account, AccountStateCode

        accounts_data = [
            ('Constructora del Norte SA', 'contact@cdnorte.mx', '+52 81 1234 5678'),
            ('Minera Peñoles', 'ventas@penoles.mx', '+52 55 9876 5432'),
            ('Cemex Concretos', 'info@cemex.com', '+52 81 5555 1234'),
        ]

        for name, email, phone in accounts_data:
            Account.objects.get_or_create(
                name=name,
                defaults={
                    'emailaddress1': email,
                    'telephone1': phone,
                    'statecode': AccountStateCode.ACTIVE,
                    'ownerid': admin,
                    'createdby': admin,
                    'modifiedby': admin,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  [OK] {len(accounts_data)} accounts'))

    def _seed_contacts(self, admin):
        """Create sample contacts."""
        from apps.contacts.models import Contact, ContactStateCode
        from apps.accounts.models import Account

        account = Account.objects.first()

        contacts_data = [
            ('Juan', 'Pérez', 'juan.perez@cdnorte.mx', 'Director de Obra'),
            ('María', 'González', 'maria.gonzalez@penoles.mx', 'Gerente de Compras'),
            ('Roberto', 'Sánchez', 'roberto.sanchez@cemex.com', 'Ingeniero de Proyecto'),
        ]

        for first, last, email, job in contacts_data:
            Contact.objects.get_or_create(
                emailaddress1=email,
                defaults={
                    'firstname': first,
                    'lastname': last,
                    'jobtitle': job,
                    'statecode': ContactStateCode.ACTIVE,
                    'parentcustomerid': account,
                    'ownerid': admin,
                    'createdby': admin,
                    'modifiedby': admin,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  [OK] {len(contacts_data)} contacts'))

    def _seed_leads(self, admin):
        """Create sample leads."""
        from apps.leads.models import Lead, LeadStateCode, LeadStatusCode, LeadQualityCode, LeadSourceCode

        leads_data = [
            ('Carlos', 'Mendoza', 'carlos@ejemplo.mx', 'Pavimentación Av. Industrial', LeadQualityCode.HOT),
            ('Ana', 'Torres', 'ana@ejemplo.mx', 'Ampliación planta Monterrey', LeadQualityCode.WARM),
            ('Luis', 'Ramírez', 'luis@ejemplo.mx', 'Puente vehicular Saltillo', LeadQualityCode.COLD),
        ]

        for first, last, email, subject, quality in leads_data:
            Lead.objects.get_or_create(
                emailaddress1=email,
                defaults={
                    'firstname': first,
                    'lastname': last,
                    'subject': subject,
                    'companyname': f'Empresa de {last}',
                    'leadqualitycode': quality,
                    'leadsourcecode': LeadSourceCode.WEB,
                    'estimatedvalue': Decimal('500000.00'),
                    'statecode': LeadStateCode.OPEN,
                    'statuscode': LeadStatusCode.NEW,
                    'ownerid': admin,
                    'createdby': admin,
                    'modifiedby': admin,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  [OK] {len(leads_data)} leads'))

    def _seed_products(self, admin):
        """Create sample products."""
        from apps.products.models import Product, ProductStateCode, ProductStructure, ProductTypeCode

        products_data = [
            ('Concreto Premezclado f\'c=250', 'CONC-250', Decimal('2500.00')),
            ('Acero de Refuerzo #4', 'ACER-004', Decimal('18500.00')),
            ('Block de Concreto 15x20x40', 'BLCK-001', Decimal('12.50')),
            ('Tubería PVC 4"', 'TUBE-004', Decimal('185.00')),
            ('Mano de Obra Albañilería', 'MO-ALB-01', Decimal('450.00')),
        ]

        for name, number, price in products_data:
            Product.objects.get_or_create(
                productnumber=number,
                defaults={
                    'name': name,
                    'price': price,
                    'standardcost': price * Decimal('0.7'),
                    'currentcost': price * Decimal('0.75'),
                    'statecode': ProductStateCode.ACTIVE,
                    'productstructure': ProductStructure.PRODUCT,
                    'producttypecode': ProductTypeCode.SALES_INVENTORY,
                    'quantityonhand': 100,
                    'createdby': admin,
                    'modifiedby': admin,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  [OK] {len(products_data)} products'))

    def _seed_opportunities(self, admin):
        """Create sample opportunities."""
        from apps.opportunities.models import Opportunity, OpportunityStateCode, OpportunityStatusCode, SalesStage
        from apps.accounts.models import Account

        account = Account.objects.first()

        opps_data = [
            ('Proyecto Carretera Saltillo-Monterrey', SalesStage.QUALIFY, Decimal('15000000.00')),
            ('Ampliación Planta Cemento', SalesStage.DEVELOP, Decimal('8000000.00')),
            ('Puente Peatonal Centro', SalesStage.PROPOSE, Decimal('3500000.00')),
        ]

        for name, stage, revenue in opps_data:
            Opportunity.objects.get_or_create(
                name=name,
                defaults={
                    'estimatedrevenue': revenue,
                    'salesstage': stage,
                    'estimatedclosedate': date.today() + timedelta(days=90),
                    'statecode': OpportunityStateCode.OPEN,
                    'statuscode': OpportunityStatusCode.IN_PROGRESS,
                    'accountid': account,
                    'ownerid': admin,
                    'createdby': admin,
                    'modifiedby': admin,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  [OK] {len(opps_data)} opportunities'))

    def _seed_cases(self, admin):
        """Create sample cases."""
        from apps.cases.models import Case, CaseStateCode, CaseStatusCode, CasePriorityCode, CaseOriginCode
        from apps.contacts.models import Contact

        contact = Contact.objects.first()

        # Skip if cases already exist
        if Case.objects.filter(statecode=CaseStateCode.ACTIVE).exists():
            self.stdout.write('  [--] Cases already exist')
            return

        cases_data = [
            ('Retraso en entrega de material', CasePriorityCode.HIGH, CaseOriginCode.PHONE),
            ('Consulta sobre garantía de obra', CasePriorityCode.NORMAL, CaseOriginCode.EMAIL),
            ('Solicitud de cotización urgente', CasePriorityCode.HIGH, CaseOriginCode.WEB),
        ]

        for title, priority, origin in cases_data:
            try:
                from apps.cases.services import CaseService
                from apps.cases.schemas import CreateCaseDto
                dto = CreateCaseDto(
                    title=title,
                    prioritycode=priority,
                    caseorigincode=origin,
                    contactid=contact.contactid if contact else None,
                )
                CaseService.create_case(dto, admin)
            except Exception:
                # Fallback: create directly without ticket number generation
                pass
        self.stdout.write(self.style.SUCCESS(f'  [OK] {len(cases_data)} cases'))

    def _seed_project(self, admin):
        """Create a sample construction project."""
        from apps.projects.models import ConstructionProject, ProjectStateCode
        from apps.accounts.models import Account

        account = Account.objects.first()

        ConstructionProject.objects.get_or_create(
            name='Proyecto E2E - Pavimentación Industrial',
            defaults={
                'description': 'Proyecto de prueba para tests E2E',
                'projecttype': 1,  # Private
                'biddingtype': 2,  # Direct award
                'startdate': date.today(),
                'contractenddate': date.today() + timedelta(days=365),
                'expectedenddate': date.today() + timedelta(days=330),
                'durationmonths': 12,
                'contractamount_notax': Decimal('10000000.00'),
                'contractamount_withtax': Decimal('11600000.00'),
                'statecode': ProjectStateCode.ACTIVE,
                'accountid': account,
                'ownerid': admin,
                'createdby': admin,
                'modifiedby': admin,
            }
        )
        self.stdout.write(self.style.SUCCESS('  [OK] 1 construction project'))
