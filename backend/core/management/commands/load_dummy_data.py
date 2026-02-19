"""
Django management command to load dummy data into the CRM.

Mining and Construction Industry — Mexico
Includes: Users, Products, Price Lists, Accounts, Contacts,
          Leads, Opportunities, Quotes, Orders, Invoices.

Usage:
    python manage.py load_dummy_data
    python manage.py load_dummy_data --clear  # Clear existing data first
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta, time, date
from decimal import Decimal
import random

from apps.users.models import SystemUser, SecurityRole
from apps.leads.models import Lead, LeadStateCode, LeadStatusCode, LeadQualityCode, LeadSourceCode
from apps.opportunities.models import Opportunity, OpportunityStateCode, OpportunityStatusCode, SalesStage
from apps.accounts.models import Account, AccountStateCode
from apps.contacts.models import Contact, ContactStateCode
from apps.quotes.models import Quote, QuoteDetail, QuoteStateCode, QuoteStatusCode
from apps.orders.models import SalesOrder, SalesOrderDetail, OrderStateCode, OrderStatusCode
from apps.invoices.models import Invoice, InvoiceDetail, InvoiceStateCode, InvoiceStatusCode
from apps.activities.models import Activity, Email, PhoneCall, Task, Appointment
from apps.cases.models import Case
from apps.quotes.models import QuoteTemplate
from apps.products.models import Product, PriceList, PriceListItem, ProductStructure, ProductTypeCode, ProductStateCode


class Command(BaseCommand):
    help = 'Load dummy data into the CRM database (Mining & Construction - Mexico)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before loading dummy data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to load dummy data (Mining & Construction - Mexico)...'))

        if options['clear']:
            self.stdout.write(self.style.WARNING('WARNING: Clearing existing data...'))
            self.clear_data()

        try:
            with transaction.atomic():
                # First, ensure security roles exist
                self.ensure_security_roles()

                # Get admin user for audit fields (System Administrator role)
                admin_role = SecurityRole.objects.filter(name='System Administrator').first()
                if admin_role:
                    admin = SystemUser.objects.filter(securityroleid=admin_role).first()
                else:
                    admin = None

                if not admin:
                    self.stdout.write(self.style.ERROR('ERROR: No admin user found. Please create one first with: python manage.py createsuperuser'))
                    return

                # Create users
                users = self.create_users(admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(users)} users'))

                # Create products and price lists
                products = self.create_products(admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(products)} products'))

                price_lists = self.create_price_lists(products, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(price_lists)} price lists'))

                # Create accounts
                accounts = self.create_accounts(users, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(accounts)} accounts'))

                # Create contacts
                contacts = self.create_contacts(accounts, users, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(contacts)} contacts'))

                # Create leads
                leads = self.create_leads(users, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(leads)} leads'))

                # Create opportunities
                opportunities = self.create_opportunities(accounts, contacts, leads, users, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(opportunities)} opportunities'))

                # Create quotes
                quotes = self.create_quotes(opportunities, accounts, contacts, users, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(quotes)} quotes'))

                # Create orders
                orders = self.create_orders(quotes, users, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(orders)} orders'))

                # Create invoices
                invoices = self.create_invoices(orders, users, admin)
                self.stdout.write(self.style.SUCCESS(f'Created {len(invoices)} invoices'))

                self.stdout.write(self.style.SUCCESS('\nDummy data loaded successfully!'))
                self.print_summary()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERROR: Error loading data: {str(e)}'))
            raise

    def clear_data(self):
        """Clear existing test data (keeps admin users)."""
        # Delete in order (child first, parent last)
        # Activities and Cases first (they reference Users, Accounts, Contacts, etc.)
        Email.objects.all().delete()
        PhoneCall.objects.all().delete()
        Task.objects.all().delete()
        Appointment.objects.all().delete()
        Activity.objects.all().delete()
        Case.objects.all().delete()
        QuoteTemplate.objects.all().delete()
        PriceListItem.objects.all().delete()
        PriceList.objects.all().delete()
        Product.objects.all().delete()
        InvoiceDetail.objects.all().delete()
        Invoice.objects.all().delete()
        SalesOrderDetail.objects.all().delete()
        SalesOrder.objects.all().delete()
        QuoteDetail.objects.all().delete()
        Quote.objects.all().delete()
        Opportunity.objects.all().delete()
        Lead.objects.all().delete()
        Contact.objects.all().delete()
        Account.objects.all().delete()
        # Keep users with System Administrator role, delete others
        admin_role = SecurityRole.objects.filter(name='System Administrator').first()
        if admin_role:
            SystemUser.objects.exclude(securityroleid=admin_role).delete()
        self.stdout.write(self.style.SUCCESS('Existing data cleared'))

    def ensure_security_roles(self):
        """Create security roles if they don't exist."""
        roles_data = [
            {
                'name': 'System Administrator',
                'description': 'Full access to all entities and operations'
            },
            {
                'name': 'Sales Manager',
                'description': 'Manage sales team and view all opportunities'
            },
            {
                'name': 'Salesperson',
                'description': 'Manage own leads and opportunities'
            },
            {
                'name': 'Marketing User',
                'description': 'Manage campaigns and leads'
            },
            {
                'name': 'Read-Only User',
                'description': 'View-only access to entities'
            },
        ]

        for role_data in roles_data:
            SecurityRole.objects.get_or_create(
                name=role_data['name'],
                defaults={'description': role_data['description']}
            )

    def create_users(self, admin):
        """Create sample users with different roles."""
        users_data = [
            {
                'email': 'manager@crm.com',
                'fullname': 'Roberto Mart\u00ednez',
                'password': 'manager123',
                'role': 'Sales Manager'
            },
            {
                'email': 'vendedor1@crm.com',
                'fullname': 'Ana Garc\u00eda',
                'password': 'vendedor123',
                'role': 'Salesperson'
            },
            {
                'email': 'vendedor2@crm.com',
                'fullname': 'Carlos L\u00f3pez',
                'password': 'vendedor123',
                'role': 'Salesperson'
            },
            {
                'email': 'marketing@crm.com',
                'fullname': 'Laura Hern\u00e1ndez',
                'password': 'marketing123',
                'role': 'Marketing User'
            },
        ]

        users = []
        for user_data in users_data:
            # Check if user already exists
            if not SystemUser.objects.filter(emailaddress1=user_data['email']).exists():
                role = SecurityRole.objects.get(name=user_data['role'])
                user = SystemUser.objects.create_user(
                    emailaddress1=user_data['email'],
                    fullname=user_data['fullname'],
                    password=user_data['password'],
                    securityroleid=role,
                    createdby=admin,
                    modifiedby=admin,
                )
                users.append(user)

        return users

    def create_products(self, admin):
        """Create 120+ mining/construction products organized into families."""
        all_products = []

        # ===================================================================
        # Helper to create a family and its children
        # ===================================================================
        def make_family(name, description):
            family = Product.objects.create(
                name=name,
                description=description,
                productstructure=ProductStructure.PRODUCT_FAMILY,
                producttypecode=ProductTypeCode.SALES_INVENTORY,
                statecode=0,
                statuscode=1,
                createdby=admin,
                modifiedby=admin,
            )
            all_products.append(family)
            return family

        def make_product(family, sku, name, desc, price, vendor,
                         color=None, style=None, size=None,
                         typecode=ProductTypeCode.SALES_INVENTORY,
                         qty_range=(5, 10000)):
            std_cost = (Decimal(str(price)) * Decimal('0.60')).quantize(Decimal('0.0001'))
            cur_cost = (Decimal(str(price)) * Decimal('0.65')).quantize(Decimal('0.0001'))
            qty = Decimal(str(random.randint(qty_range[0], qty_range[1]))) if qty_range[0] > 0 else Decimal('0')
            p = Product.objects.create(
                name=name,
                productnumber=sku,
                description=desc,
                productstructure=ProductStructure.PRODUCT,
                producttypecode=typecode,
                price=Decimal(str(price)),
                standardcost=std_cost,
                currentcost=cur_cost,
                quantityonhand=qty,
                vendorname=vendor,
                color=color,
                style=style,
                size=size,
                parentproductid=family,
                statecode=0,
                statuscode=1,
                createdby=admin,
                modifiedby=admin,
            )
            all_products.append(p)
            return p

        # ===================================================================
        # 1. Tuber\u00edas HDPE y Accesorios (28 products)
        # ===================================================================
        fam_hdpe = make_family(
            'Tuber\u00edas HDPE y Accesorios',
            'Tuber\u00eda de polietileno de alta densidad PE-100 para miner\u00eda, agua y desag\u00fce'
        )

        # Small rolls (100m, PN16)
        hdpe_small = [
            ('HDPE-020', 'Tuber\u00eda HDPE PE-100 PN16 20mm',  '20mm rollo 100m',  185,  '20mm'),
            ('HDPE-025', 'Tuber\u00eda HDPE PE-100 PN16 25mm',  '25mm rollo 100m',  220,  '25mm'),
            ('HDPE-032', 'Tuber\u00eda HDPE PE-100 PN16 32mm',  '32mm rollo 100m',  350,  '32mm'),
            ('HDPE-040', 'Tuber\u00eda HDPE PE-100 PN16 40mm',  '40mm rollo 100m',  480,  '40mm'),
            ('HDPE-050', 'Tuber\u00eda HDPE PE-100 PN16 50mm',  '50mm rollo 100m',  650,  '50mm'),
            ('HDPE-063', 'Tuber\u00eda HDPE PE-100 PN16 63mm',  '63mm rollo 100m',  950,  '63mm'),
        ]
        for sku, name, desc, price, sz in hdpe_small:
            make_product(fam_hdpe, sku, name, desc, price, 'Polimex', color='Negro', style='PE-100 PN16', size=sz)

        # Medium bars (6m, PN16)
        hdpe_med = [
            ('HDPE-075', 'Tuber\u00eda HDPE PE-100 PN16 75mm',  '75mm barra 6m',   1250,  '75mm'),
            ('HDPE-090', 'Tuber\u00eda HDPE PE-100 PN16 90mm',  '90mm barra 6m',   1450,  '90mm'),
            ('HDPE-110', 'Tuber\u00eda HDPE PE-100 PN16 110mm', '110mm barra 6m',  1850,  '110mm'),
            ('HDPE-125', 'Tuber\u00eda HDPE PE-100 PN16 125mm', '125mm barra 6m',  2200,  '125mm'),
            ('HDPE-140', 'Tuber\u00eda HDPE PE-100 PN16 140mm', '140mm barra 6m',  2800,  '140mm'),
        ]
        for sku, name, desc, price, sz in hdpe_med:
            make_product(fam_hdpe, sku, name, desc, price, 'Polimex', color='Negro', style='PE-100 PN16', size=sz)

        # Large bars (12m, PN10)
        hdpe_large = [
            ('HDPE-160', 'Tuber\u00eda HDPE PE-100 PN10 160mm', '160mm barra 12m',  3200,  '160mm'),
            ('HDPE-200', 'Tuber\u00eda HDPE PE-100 PN10 200mm', '200mm barra 12m',  3800,  '200mm'),
            ('HDPE-225', 'Tuber\u00eda HDPE PE-100 PN10 225mm', '225mm barra 12m',  4200,  '225mm'),
            ('HDPE-250', 'Tuber\u00eda HDPE PE-100 PN10 250mm', '250mm barra 12m',  4800,  '250mm'),
            ('HDPE-280', 'Tuber\u00eda HDPE PE-100 PN10 280mm', '280mm barra 12m',  5200,  '280mm'),
        ]
        for sku, name, desc, price, sz in hdpe_large:
            make_product(fam_hdpe, sku, name, desc, price, 'Polimex', color='Negro', style='PE-100 PN10', size=sz)

        # Extra Large bars (12m, PN10)
        hdpe_xl = [
            ('HDPE-315', 'Tuber\u00eda HDPE PE-100 PN10 315mm', '315mm barra 12m',  5800,  '315mm'),
            ('HDPE-355', 'Tuber\u00eda HDPE PE-100 PN10 355mm', '355mm barra 12m',  6500,  '355mm'),
            ('HDPE-400', 'Tuber\u00eda HDPE PE-100 PN10 400mm', '400mm barra 12m',  7200,  '400mm'),
            ('HDPE-450', 'Tuber\u00eda HDPE PE-100 PN10 450mm', '450mm barra 12m',  8000,  '450mm'),
            ('HDPE-500', 'Tuber\u00eda HDPE PE-100 PN10 500mm', '500mm barra 12m',  8800,  '500mm'),
        ]
        for sku, name, desc, price, sz in hdpe_xl:
            make_product(fam_hdpe, sku, name, desc, price, 'Polimex', color='Negro', style='PE-100 PN10', size=sz)

        # XXL (12m, PN10)
        hdpe_xxl = [
            ('HDPE-560',  'Tuber\u00eda HDPE PE-100 PN10 560mm',  '560mm barra 12m',   9800,  '560mm'),
            ('HDPE-630',  'Tuber\u00eda HDPE PE-100 PN10 630mm',  '630mm barra 12m',  12500,  '630mm'),
            ('HDPE-710',  'Tuber\u00eda HDPE PE-100 PN10 710mm',  '710mm barra 12m',  15000,  '710mm'),
            ('HDPE-800',  'Tuber\u00eda HDPE PE-100 PN10 800mm',  '800mm barra 12m',  18500,  '800mm'),
            ('HDPE-900',  'Tuber\u00eda HDPE PE-100 PN10 900mm',  '900mm barra 12m',  22000,  '900mm'),
            ('HDPE-1000', 'Tuber\u00eda HDPE PE-100 PN10 1000mm', '1000mm barra 12m', 28000, '1000mm'),
            ('HDPE-1200', 'Tuber\u00eda HDPE PE-100 PN10 1200mm', '1200mm barra 12m', 38000, '1200mm'),
        ]
        for sku, name, desc, price, sz in hdpe_xxl:
            make_product(fam_hdpe, sku, name, desc, price, 'Polimex', color='Negro', style='PE-100 PN10', size=sz)

        # ===================================================================
        # 2. Cables y Conductores para Minas (12 products)
        # ===================================================================
        fam_cables = make_family(
            'Cables y Conductores para Minas',
            'Cables de potencia, comunicaci\u00f3n y control para operaciones mineras subterr\u00e1neas'
        )

        cables_data = [
            ('CAB-001', 'Cable de Potencia Minero 4/0 AWG 5kV',   'Cable minero flexible 4/0 AWG 5kV, cubierta CPE',          4500, 'Condumex'),
            ('CAB-002', 'Cable de Potencia 2/0 AWG 5kV',          'Cable minero flexible 2/0 AWG 5kV para bombas y motores',   3200, 'Condumex'),
            ('CAB-003', 'Cable 1/0 AWG 600V',                     'Cable uso general 1/0 AWG 600V miner\u00eda subterr\u00e1nea',       1850, 'Viakon'),
            ('CAB-004', 'Cable Tipo Teck 2/0 AWG',                'Cable armado tipo Teck 2/0 AWG para mina subterr\u00e1nea',  2850, 'Viakon'),
            ('CAB-005', 'Cable Tipo Teck 4/0 AWG',                'Cable armado tipo Teck 4/0 AWG para alimentadores',         3800, 'Viakon'),
            ('CAB-006', 'Cable para Jumbo 4/0 AWG',               'Cable reelable para jumbo de perforaci\u00f3n 4/0 AWG',      4200, 'Phelps Dodge'),
            ('CAB-007', 'Cable Flexible Arrastre 2/0 AWG',        'Cable flexible trailing para LHD y cami\u00f3n minero',      3500, 'Phelps Dodge'),
            ('CAB-008', 'Cable Comunicaci\u00f3n 12 pares',            'Cable de comunicaci\u00f3n blindado 12 pares para mina',      850,  'Condumex'),
            ('CAB-009', 'Cable Fibra \u00d3ptica Armado 12 hilos',      'Fibra \u00f3ptica armada 12 hilos para red subterr\u00e1nea',        1200, 'Condumex'),
            ('CAB-010', 'Cable Control Blindado 12x16 AWG',       'Cable de control multiconductor blindado 12x16 AWG',        650,  'Viakon'),
            ('CAB-011', 'Cable Instrumentaci\u00f3n 4 pares',          'Cable de instrumentaci\u00f3n blindado 4 pares 18 AWG',       450,  'Viakon'),
            ('CAB-012', 'Cable Port\u00e1til Extensi\u00f3n 3x10 AWG',      'Cable port\u00e1til para extensiones 3x10 AWG 600V',        250,  'Condumex'),
        ]
        for sku, name, desc, price, vendor in cables_data:
            make_product(fam_cables, sku, name, desc, price, vendor)

        # ===================================================================
        # 3. Equipo de Protecci\u00f3n Personal (12 products)
        # ===================================================================
        fam_epp = make_family(
            'Equipo de Protecci\u00f3n Personal',
            'EPP especializado para miner\u00eda subterr\u00e1nea y a cielo abierto'
        )

        epp_data = [
            ('SEG-001', 'Casco Minero con L\u00e1mpara LED',           'Casco tipo minero con l\u00e1mpara LED integrada recargable',   4500, 'MSA M\u00e9xico'),
            ('SEG-002', 'Autorescatador 60 min',                  'Autorescatador de ox\u00edgeno qu\u00edmico 60 minutos MSHA',      8500, 'Dr\u00e4ger M\u00e9xico'),
            ('SEG-003', 'Arn\u00e9s de Seguridad Minero',              'Arn\u00e9s completo de cuerpo entero para miner\u00eda',           3500, 'MSA M\u00e9xico'),
            ('SEG-004', 'Botas Seguridad Minera',                 'Botas punta de acero, resistentes a \u00e1cido y aceite',      2200, 'Honeywell'),
            ('SEG-005', 'Guantes Nitrilo Industrial',             'Guantes nitrilo reforzado para manejo de materiales',        85,   '3M M\u00e9xico'),
            ('SEG-006', 'Overol Retardante al Fuego',             'Overol tipo Nomex FR para trabajo en mina',                 1800, 'Honeywell'),
            ('SEG-007', 'Respirador P100 Media Cara',             'Respirador media cara con cartuchos P100',                  650,  '3M M\u00e9xico'),
            ('SEG-008', 'Detector Multigas Port\u00e1til',             'Detector 4 gases: O2, CO, H2S, LEL con bomba',             8500, 'Dr\u00e4ger M\u00e9xico'),
            ('SEG-009', 'Lentes de Seguridad Antiempa\u00f1o',         'Lentes seguridad policarbonato antiempa\u00f1o UV400',          185,  '3M M\u00e9xico'),
            ('SEG-010', 'Tapones Auditivos Reutilizables',        'Tapones auditivos NRR 25dB con cord\u00f3n',                   85,   'Honeywell'),
            ('SEG-011', 'Chaleco Reflectante Alta Visibilidad',   'Chaleco reflectante clase 3 alta visibilidad',              350,  'MSA M\u00e9xico'),
            ('SEG-012', 'Kit Primeros Auxilios Minero',           'Kit primeros auxilios industrial 50 personas',              1500, '3M M\u00e9xico'),
        ]
        for sku, name, desc, price, vendor in epp_data:
            make_product(fam_epp, sku, name, desc, price, vendor)

        # ===================================================================
        # 4. Explosivos y Voladura (10 products)
        # ===================================================================
        fam_explosivos = make_family(
            'Explosivos y Accesorios de Voladura',
            'Emulsiones, ANFO, detonadores y accesorios para voladura en miner\u00eda'
        )

        explosivos_data = [
            ('EXP-001', 'Emulsi\u00f3n Encartuchada Tipo 1',          'Emulsi\u00f3n sensibilizada 1-1/4" para barrenaci\u00f3n angosta',  850,   'Dyno Nobel'),
            ('EXP-002', 'Emulsi\u00f3n a Granel por Tonelada',        'Emulsi\u00f3n bombeada a granel por tonelada m\u00e9trica',        4500,  'Orica'),
            ('EXP-003', 'ANFO Ensacado 25kg',                    'Nitrato de amonio + combustible 25kg',                      2800,  'Austin Powder'),
            ('EXP-004', 'Cord\u00f3n Detonante 10g/m',                'Cord\u00f3n detonante PETN 10g/m rollo 500m',                  350,   'Dyno Nobel'),
            ('EXP-005', 'Detonador Electr\u00f3nico Programable',     'Detonador electr\u00f3nico de alta precisi\u00f3n programable',     1200,  'Orica'),
            ('EXP-006', 'Booster Pentolita 150g',                'Booster de pentolita 150g para iniciaci\u00f3n',                450,   'Austin Powder'),
            ('EXP-007', 'Mecha de Seguridad',                    'Mecha de seguridad rollo 100m velocidad controlada',        380,   'Dyno Nobel'),
            ('EXP-008', 'Sistema Voladura Electr\u00f3nica Completo', 'Sistema completo de voladura electr\u00f3nica 200 canales',   28000, 'Orica'),
            ('EXP-009', 'Kit Accesorios de Voladura',             'Kit completo: conectores, l\u00edneas, retardos',               2500,  'Dyno Nobel'),
            ('EXP-010', 'Retardos de Superficie',                'Retardos superficie MS y LP caja 100 piezas',              680,   'Austin Powder'),
        ]
        for sku, name, desc, price, vendor in explosivos_data:
            make_product(fam_explosivos, sku, name, desc, price, vendor)

        # ===================================================================
        # 5. Ventilaci\u00f3n Minera (8 products)
        # ===================================================================
        fam_ventilacion = make_family(
            'Ventilaci\u00f3n Minera',
            'Ventiladores principales, auxiliares, ductos y sensores para miner\u00eda subterr\u00e1nea'
        )

        ventilacion_data = [
            ('VEN-001', 'Ventilador Principal 200HP',          'Ventilador axial principal 200HP para tiro forzado',      850000,  'Howden'),
            ('VEN-002', 'Ventilador Auxiliar 75HP',            'Ventilador auxiliar 75HP para frentes de trabajo',        285000,  'Howden'),
            ('VEN-003', 'Ventilador Auxiliar 30HP',            'Ventilador auxiliar 30HP port\u00e1til',                       95000,   'TLT-Turbo'),
            ('VEN-004', 'Ducto Flexible Ventilaci\u00f3n 1000mm',  'Ducto flexible polietileno 1000mm rollo 25m',            15000,   'TLT-Turbo'),
            ('VEN-005', 'Ducto Flexible Ventilaci\u00f3n 800mm',   'Ducto flexible polietileno 800mm rollo 25m',             12000,   'TLT-Turbo'),
            ('VEN-006', 'Ducto R\u00edgido Ventilaci\u00f3n 1200mm',    'Ducto r\u00edgido met\u00e1lico 1200mm tramo 3m',                22000,   'Howden'),
            ('VEN-007', 'Puerta de Ventilaci\u00f3n',              'Puerta reguladora de ventilaci\u00f3n autom\u00e1tica',             45000,   'Howden'),
            ('VEN-008', 'Sensor de Gases Fijo',                'Sensor fijo multigas estacionario con alarma',            35000,   'TLT-Turbo'),
        ]
        for sku, name, desc, price, vendor in ventilacion_data:
            make_product(fam_ventilacion, sku, name, desc, price, vendor)

        # ===================================================================
        # 6. Equipo de Perforaci\u00f3n (10 products)
        # ===================================================================
        fam_perforacion = make_family(
            'Equipo de Perforaci\u00f3n',
            'Brocas, barras, acoplamientos y accesorios de perforaci\u00f3n para miner\u00eda'
        )

        perforacion_data = [
            ('PER-001', 'Broca Tric\u00f3nica 6-1/2"',             'Broca tric\u00f3nica TCI 6-1/2" para roca dura',              18500, 'Epiroc'),
            ('PER-002', 'Broca Tric\u00f3nica 4-3/4"',             'Broca tric\u00f3nica TCI 4-3/4" para producci\u00f3n',             12500, 'Epiroc'),
            ('PER-003', 'Broca de Botones 45mm',               'Broca de botones balísticos 45mm rosca R32',              2500,  'Sandvik'),
            ('PER-004', 'Barra de Perforaci\u00f3n T38 3.66m',     'Barra de extensi\u00f3n T38 hexagonal 3.66m',                8500,  'Sandvik'),
            ('PER-005', 'Barra de Perforaci\u00f3n T38 1.83m',     'Barra de extensi\u00f3n T38 hexagonal 1.83m',                5200,  'Sandvik'),
            ('PER-006', 'Acoplamiento T38',                    'Acoplamiento hembra-hembra T38 para barras',              3800,  'Epiroc'),
            ('PER-007', 'Barra Integral 1.2m',                 'Barra integral con broca cincel 1.2m para jackleg',       2800,  'Epiroc'),
            ('PER-008', 'Broca Diamante NQ',                   'Broca de diamante calibre NQ para sondeo',               45000, 'Sandvik'),
            ('PER-009', 'Adaptador R32-T38',                   'Adaptador rosca R32 a T38 para perforadora',              4500,  'Epiroc'),
            ('PER-010', 'Aceite de Perforaci\u00f3n Tambi\u00e9n 200L', 'Aceite hidr\u00e1ulico perforaci\u00f3n tambor 200L',              3200,  'Sandvik'),
        ]
        for sku, name, desc, price, vendor in perforacion_data:
            make_product(fam_perforacion, sku, name, desc, price, vendor)

        # ===================================================================
        # 7. Soporte de Roca (10 products)
        # ===================================================================
        fam_soporte = make_family(
            'Soporte de Roca',
            'Pernos, malla, concreto lanzado, marcos y accesorios de fortificaci\u00f3n minera'
        )

        soporte_data = [
            ('SOP-001', 'Split Set 1.5m',                     'Perno split set galvanizado 39mm x 1.5m',                 85,    'DSI Underground'),
            ('SOP-002', 'Split Set 2.4m',                     'Perno split set galvanizado 39mm x 2.4m',                 120,   'DSI Underground'),
            ('SOP-003', 'Perno de Resina 2.4m',               'Perno roscado con resina 22mm x 2.4m',                    165,   'Jennmar'),
            ('SOP-004', 'Malla Electrosoldada 4x4"',          'Malla electrosoldada calibre 4 de 4x4" rollo',            450,   'DSI Underground'),
            ('SOP-005', 'Malla de Cable',                     'Malla de cable de acero alta resistencia 3m x 3m',        850,   'DSI Underground'),
            ('SOP-006', 'Shotcrete por m\u00b3',                    'Concreto lanzado (shotcrete) por metro c\u00fabico',            2800,  'Jennmar'),
            ('SOP-007', 'Fibra de Acero 20kg',                'Fibra de acero para refuerzo de shotcrete 20kg',          4500,  'Jennmar'),
            ('SOP-008', 'Marco Met\u00e1lico TH-29',               'Marco met\u00e1lico TH-29 para soporte de galer\u00eda',           8500,  'DSI Underground'),
            ('SOP-009', 'Resina de Anclaje Cartucho',         'Cartucho resina de anclaje r\u00e1pido 25mm x 300mm',        45,    'Jennmar'),
            ('SOP-010', 'Placa de Acero 150x150mm',           'Placa base acero A36 150x150x6mm para perno',             65,    'DSI Underground'),
        ]
        for sku, name, desc, price, vendor in soporte_data:
            make_product(fam_soporte, sku, name, desc, price, vendor)

        # ===================================================================
        # 8. Bandas Transportadoras (8 products)
        # ===================================================================
        fam_bandas = make_family(
            'Bandas Transportadoras',
            'Bandas, polines, tensores y accesorios para sistemas de transporte de material'
        )

        bandas_data = [
            ('BAN-001', 'Banda EP400/3 1200mm',               'Banda transportadora EP400/3 ply 1200mm ancho',          45000,   'Goodyear'),
            ('BAN-002', 'Banda EP500/4 1400mm',               'Banda transportadora EP500/4 ply 1400mm ancho',          68000,   'Goodyear'),
            ('BAN-003', 'Banda EP315/3 900mm',                'Banda transportadora EP315/3 ply 900mm ancho',           28000,   'Continental'),
            ('BAN-004', 'Polines de Carga 35\u00b0',               'Juego polines carga 3 rodillos 35\u00b0 para 1200mm',        1200,    'Martin Engineering'),
            ('BAN-005', 'Polines de Retorno',                 'Polin retorno liso para banda 1200mm',                    850,     'Martin Engineering'),
            ('BAN-006', 'Tensor Gravitacional',               'Tensor gravitacional contrapeso para banda 1200mm',       15000,   'Continental'),
            ('BAN-007', 'Limpiador Primario de Banda',        'Limpiador primario raspador poliuretano 1200mm',          8500,    'Martin Engineering'),
            ('BAN-008', 'Kit Vulcanizaci\u00f3n en Caliente',      'Kit completo vulcanizaci\u00f3n en caliente para banda',     125000,  'Goodyear'),
        ]
        for sku, name, desc, price, vendor in bandas_data:
            make_product(fam_bandas, sku, name, desc, price, vendor)

        # ===================================================================
        # 9. Bombas y Sistemas de Desag\u00fce (10 products)
        # ===================================================================
        fam_bombas = make_family(
            'Bombas y Sistemas de Desag\u00fce',
            'Bombas sumergibles, centr\u00edfugas, de lodos y accesorios para desag\u00fce minero'
        )

        bombas_data = [
            ('BOM-001', 'Bomba Sumergible 100HP',             'Bomba sumergible 100HP acero inox para mina',             385000,  'Flygt (Xylem)'),
            ('BOM-002', 'Bomba Sumergible 50HP',              'Bomba sumergible 50HP para c\u00e1rcamo de mina',              185000,  'Flygt (Xylem)'),
            ('BOM-003', 'Bomba Sumergible 25HP',              'Bomba sumergible 25HP port\u00e1til para frentes',             95000,   'Flygt (Xylem)'),
            ('BOM-004', 'Bomba Centr\u00edfuga 150HP',             'Bomba centr\u00edfuga horizontal 150HP multietapa',          450000,  'Metso'),
            ('BOM-005', 'Bomba de Lodos 8x6',                 'Bomba de lodos 8x6 alto cromo para pulpa minera',         650000,  'Warman (Weir)'),
            ('BOM-006', 'Impulsor Alto Cromo 8x6',            'Impulsor repuesto alto cromo para bomba 8x6',             45000,   'Warman (Weir)'),
            ('BOM-007', 'Sello Mec\u00e1nico Doble',               'Sello mec\u00e1nico doble para bomba sumergible 100HP',      18500,   'Flygt (Xylem)'),
            ('BOM-008', 'Tuber\u00eda Descarga 6" HDPE',           'Tuber\u00eda de descarga HDPE 6" SDR17 barra 12m',          8500,    'Metso'),
            ('BOM-009', 'V\u00e1lvula Check 8" Wafer',              'V\u00e1lvula check wafer 8" hierro d\u00factil PN16',             12500,   'Metso'),
            ('BOM-010', 'Manguera Flexible 4" Succi\u00f3n',       'Manguera flexible PVC/nitrilo 4" succi\u00f3n tramo 6m',     850,     'Warman (Weir)'),
        ]
        for sku, name, desc, price, vendor in bombas_data:
            make_product(fam_bombas, sku, name, desc, price, vendor)

        # ===================================================================
        # 10. Acero Estructural (10 products)
        # ===================================================================
        fam_acero = make_family(
            'Acero Estructural',
            'Vigas, canales, \u00e1ngulos, placas y perfiles de acero para construcci\u00f3n e infraestructura minera'
        )

        acero_data = [
            ('ACE-001', 'Viga W8x31 por metro',               'Viga IPR W8x31 acero A572 Gr50 por metro lineal',         8500,  'DeAcero'),
            ('ACE-002', 'Viga W10x49 por metro',              'Viga IPR W10x49 acero A572 Gr50 por metro lineal',        12500, 'DeAcero'),
            ('ACE-003', 'Viga W6x20 por metro',               'Viga IPR W6x20 acero A572 Gr50 por metro lineal',         5800,  'Ternium'),
            ('ACE-004', 'Canal CPS 6" por metro',             'Canal estructural CPS 6" acero A36 por metro lineal',     3200,  'AHMSA'),
            ('ACE-005', '\u00c1ngulo L3x3x1/4" por metro',         '\u00c1ngulo estructural L3x3x1/4" A36 por metro lineal',     1850,  'AHMSA'),
            ('ACE-006', 'Placa de Acero 1/2" 4x8 pies',       'Placa acero A36 1/2" espesor 4x8 pies',                  4500,  'Ternium'),
            ('ACE-007', 'Placa de Acero 3/4" 4x8 pies',       'Placa acero A36 3/4" espesor 4x8 pies',                  6800,  'Ternium'),
            ('ACE-008', 'PTR 4x4" Cal.11 por metro',          'Perfil tubular rectangular 4x4" cal.11 por metro',       2200,  'DeAcero'),
            ('ACE-009', 'Solera 3"x3/8" por metro',           'Solera de acero A36 3"x3/8" por metro lineal',            850,   'AHMSA'),
            ('ACE-010', 'Redondo Liso 1" por metro',          'Barra redonda lisa 1" acero 1018 por metro',               950,   'DeAcero'),
        ]
        for sku, name, desc, price, vendor in acero_data:
            make_product(fam_acero, sku, name, desc, price, vendor)

        # ===================================================================
        # 11. Productos Qu\u00edmicos para Procesamiento (8 products)
        # ===================================================================
        fam_quimicos = make_family(
            'Productos Qu\u00edmicos para Procesamiento',
            'Reactivos de flotaci\u00f3n, lixiviaci\u00f3n, cal y productos qu\u00edmicos para planta de beneficio'
        )

        quimicos_data = [
            ('QUI-001', 'Xantato Am\u00edlico de Potasio 25kg',    'Xantato am\u00edlico de potasio saco 25kg colector primario', 4500,  'Cytec (Solvay)'),
            ('QUI-002', 'Espumante MIBC 200L',                'Metil isobutil carbinol (MIBC) tambor 200L',              3200,  'Cytec (Solvay)'),
            ('QUI-003', 'Cal Viva por Tonelada',              'Cal viva (CaO) 90% pureza por tonelada m\u00e9trica',        1800,  'Quimikao'),
            ('QUI-004', '\u00c1cido Sulf\u00farico 98% por Tonelada',    '\u00c1cido sulf\u00farico 98% grado t\u00e9cnico por tonelada',         2500,  'BASF'),
            ('QUI-005', 'Floculante Ani\u00f3nico 25kg',            'Poliacrilamida ani\u00f3nica alto peso molecular 25kg',       8500,  'BASF'),
            ('QUI-006', 'Cianuro de Sodio por Tonelada',      'Cianuro de sodio briquetas 98% por tonelada',             18000, 'Cytec (Solvay)'),
            ('QUI-007', 'Carb\u00f3n Activado Granular 25kg',      'Carb\u00f3n activado granular de coco 6x12 mesh 25kg',       2200,  'BASF'),
            ('QUI-008', 'Sulfato de Cobre 25kg',              'Sulfato de cobre pentahidratado 25kg activador',           450,   'Quimikao'),
        ]
        for sku, name, desc, price, vendor in quimicos_data:
            make_product(fam_quimicos, sku, name, desc, price, vendor)

        # ===================================================================
        # 12. Servicios (7 products, producttypecode=2, qty=0)
        # ===================================================================
        fam_servicios = make_family(
            'Servicios T\u00e9cnicos y Consultor\u00eda',
            'Servicios de instalaci\u00f3n, mantenimiento, capacitaci\u00f3n e ingenier\u00eda para miner\u00eda'
        )

        servicios_data = [
            ('SVC-001', 'Instalaci\u00f3n Tuber\u00eda HDPE por ml',         'Servicio instalaci\u00f3n tuber\u00eda HDPE por metro lineal inc. termofusi\u00f3n',  350),
            ('SVC-002', 'Mantenimiento Bombas Contrato Anual', 'Contrato anual mantenimiento preventivo/correctivo bombas',        125000),
            ('SVC-003', 'Estudio de Ventilaci\u00f3n',              'Estudio completo de ventilaci\u00f3n mina subterr\u00e1nea con modelado CFD',     185000),
            ('SVC-004', 'Capacitaci\u00f3n Seguridad Minera',       'Programa capacitaci\u00f3n seguridad minera 40hrs grupo 25 personas',    45000),
            ('SVC-005', 'Ingenier\u00eda de Soporte de Terreno',    'Servicio ingenier\u00eda geomec\u00e1nica y dise\u00f1o de soporte',                 85000),
            ('SVC-006', 'Termofusi\u00f3n HDPE por Junta',          'Servicio de termofusi\u00f3n a tope HDPE por junta hasta 630mm',         8500),
            ('SVC-007', 'Consultor\u00eda Voladura',                'Consultor\u00eda especializada en dise\u00f1o de voladuras y optimizaci\u00f3n',    65000),
        ]
        for sku, name, desc, price in servicios_data:
            make_product(
                fam_servicios, sku, name, desc, price, 'Servicios Propios',
                typecode=ProductTypeCode.MISC_CHARGES,
                qty_range=(0, 0),
            )

        return all_products

    def create_price_lists(self, products, admin):
        """Create 3 price lists with items for all individual products."""
        today = date.today()
        end_of_year = date(2026, 12, 31)

        # Only individual products (not families)
        individual_products = [p for p in products if p.productstructure == ProductStructure.PRODUCT]

        price_lists_data = [
            {
                'name': 'Lista de Precios Miner\u00eda 2026',
                'description': 'Precios est\u00e1ndar para la industria minera - vigencia 2026',
                'multiplier': Decimal('1.00'),
            },
            {
                'name': 'Precios Volumen - Contratos Anuales',
                'description': 'Precios con descuento del 10% para contratos anuales de suministro',
                'multiplier': Decimal('0.90'),
            },
            {
                'name': 'Precios Construcci\u00f3n e Infraestructura 2026',
                'description': 'Precios con descuento del 5% para sector construcci\u00f3n e infraestructura',
                'multiplier': Decimal('0.95'),
            },
        ]

        price_lists = []
        for pl_data in price_lists_data:
            pl = PriceList.objects.create(
                name=pl_data['name'],
                description=pl_data['description'],
                begindate=today,
                enddate=end_of_year,
                statecode=0,
            )
            price_lists.append(pl)

            # Create price list items for each product
            for product in individual_products:
                if product.price is not None and product.price > 0:
                    amount = (product.price * pl_data['multiplier']).quantize(Decimal('0.0001'))
                    PriceListItem.objects.create(
                        pricelevelid=pl,
                        productid=product,
                        amount=amount,
                    )

        return price_lists

    def create_accounts(self, users, admin):
        """Create 12 Mexican mining/construction B2B accounts."""
        accounts_data = [
            {
                'name': 'Grupo M\u00e9xico',
                'accountnumber': 'ACC-001',
                'email': 'info@grupomexico.com',
                'phone': '55-1035-5000',
                'website': 'https://www.gmexico.com',
                'city': 'Ciudad de M\u00e9xico',
                'state': 'CDMX',
                'revenue': Decimal('150000000000.00'),
                'employees': 85000,
            },
            {
                'name': 'Industrias Pe\u00f1oles',
                'accountnumber': 'ACC-002',
                'email': 'contacto@penoles.com.mx',
                'phone': '871-729-0000',
                'website': 'https://www.penoles.com.mx',
                'city': 'Torre\u00f3n',
                'state': 'Coahuila',
                'revenue': Decimal('95000000000.00'),
                'employees': 40000,
            },
            {
                'name': 'Fresnillo PLC',
                'accountnumber': 'ACC-003',
                'email': 'contacto@fresnilloplc.com',
                'phone': '55-5279-3000',
                'website': 'https://www.fresnilloplc.com',
                'city': 'Ciudad de M\u00e9xico',
                'state': 'CDMX',
                'revenue': Decimal('75000000000.00'),
                'employees': 25000,
            },
            {
                'name': 'Minera Alamos',
                'accountnumber': 'ACC-004',
                'email': 'info@mineraalamos.com',
                'phone': '647-428-0500',
                'website': 'https://www.mineraalamos.com',
                'city': '\u00c1lamos',
                'state': 'Sonora',
                'revenue': Decimal('8000000000.00'),
                'employees': 2500,
            },
            {
                'name': 'First Majestic Silver',
                'accountnumber': 'ACC-005',
                'email': 'info@firstmajestic.com',
                'phone': '618-134-2800',
                'website': 'https://www.firstmajestic.com',
                'city': 'Durango',
                'state': 'Durango',
                'revenue': Decimal('12000000000.00'),
                'employees': 5000,
            },
            {
                'name': 'Torex Gold',
                'accountnumber': 'ACC-006',
                'email': 'contacto@torexgold.com',
                'phone': '747-471-8500',
                'website': 'https://www.torexgold.com',
                'city': 'Guerrero',
                'state': 'Guerrero',
                'revenue': Decimal('15000000000.00'),
                'employees': 4000,
            },
            {
                'name': 'Cemex',
                'accountnumber': 'ACC-007',
                'email': 'info@cemex.com',
                'phone': '81-8888-8888',
                'website': 'https://www.cemex.com',
                'city': 'Monterrey',
                'state': 'Nuevo Le\u00f3n',
                'revenue': Decimal('280000000000.00'),
                'employees': 45000,
            },
            {
                'name': 'Minera Autl\u00e1n',
                'accountnumber': 'ACC-008',
                'email': 'contacto@autlan.com.mx',
                'phone': '444-825-3000',
                'website': 'https://www.autlan.com.mx',
                'city': 'San Luis Potos\u00ed',
                'state': 'San Luis Potos\u00ed',
                'revenue': Decimal('6000000000.00'),
                'employees': 3500,
            },
            {
                'name': 'Constructora ICA',
                'accountnumber': 'ACC-009',
                'email': 'info@ica.com.mx',
                'phone': '55-5272-9991',
                'website': 'https://www.ica.com.mx',
                'city': 'Ciudad de M\u00e9xico',
                'state': 'CDMX',
                'revenue': Decimal('25000000000.00'),
                'employees': 15000,
            },
            {
                'name': 'Grupo Carso Infraestructura',
                'accountnumber': 'ACC-010',
                'email': 'infraestructura@carso.com.mx',
                'phone': '55-5625-5700',
                'website': 'https://www.gcarso.com.mx',
                'city': 'Ciudad de M\u00e9xico',
                'state': 'CDMX',
                'revenue': Decimal('45000000000.00'),
                'employees': 20000,
            },
            {
                'name': 'Mota-Engil M\u00e9xico',
                'accountnumber': 'ACC-011',
                'email': 'contacto@mota-engil.mx',
                'phone': '55-5081-8500',
                'website': 'https://www.mota-engil.mx',
                'city': 'Ciudad de M\u00e9xico',
                'state': 'CDMX',
                'revenue': Decimal('18000000000.00'),
                'employees': 8000,
            },
            {
                'name': 'Endeavour Silver',
                'accountnumber': 'ACC-012',
                'email': 'mexico@edrsilver.com',
                'phone': '473-732-5800',
                'website': 'https://www.edrsilver.com',
                'city': 'Guanajuato',
                'state': 'Guanajuato',
                'revenue': Decimal('10000000000.00'),
                'employees': 3000,
            },
        ]

        accounts = []
        for i, acc_data in enumerate(accounts_data):
            if not Account.objects.filter(name=acc_data['name']).exists():
                owner = random.choice(users) if users else admin
                account = Account.objects.create(
                    name=acc_data['name'],
                    accountnumber=acc_data['accountnumber'],
                    emailaddress1=acc_data['email'],
                    telephone1=acc_data['phone'],
                    websiteurl=acc_data['website'],
                    address1_city=acc_data['city'],
                    address1_stateorprovince=acc_data['state'],
                    address1_country='M\u00e9xico',
                    revenue=acc_data['revenue'],
                    numberofemployees=acc_data['employees'],
                    ownerid=owner,
                    createdby=admin,
                    modifiedby=admin,
                )
                accounts.append(account)

        return accounts

    def create_contacts(self, accounts, users, admin):
        """Create 26 contacts for mining/construction accounts."""
        contacts_data = [
            # Grupo M\u00e9xico (0)
            {'firstname': 'Alejandro', 'lastname': 'Fuentes Ramos', 'email': 'a.fuentes@grupomexico.com', 'phone': '55-1035-5001', 'mobile': '55-2234-5678', 'title': 'Director de Compras', 'account_idx': 0},
            {'firstname': 'Patricia', 'lastname': 'Mendoza Vega', 'email': 'p.mendoza@grupomexico.com', 'phone': '55-1035-5002', 'mobile': '55-3345-6789', 'title': 'Superintendente de Mina', 'account_idx': 0},

            # Industrias Pe\u00f1oles (1)
            {'firstname': 'Fernando', 'lastname': 'Salinas Torres', 'email': 'f.salinas@penoles.com.mx', 'phone': '871-729-0001', 'mobile': '871-1234-5678', 'title': 'Gerente de Seguridad', 'account_idx': 1},
            {'firstname': 'Gabriela', 'lastname': 'Ort\u00edz L\u00f3pez', 'email': 'g.ortiz@penoles.com.mx', 'phone': '871-729-0002', 'mobile': '871-2345-6789', 'title': 'Jefe de Mantenimiento', 'account_idx': 1},

            # Fresnillo PLC (2)
            {'firstname': 'Ricardo', 'lastname': 'Navarro Cruz', 'email': 'r.navarro@fresnilloplc.com', 'phone': '55-5279-3001', 'mobile': '55-4456-7890', 'title': 'Director de Operaciones', 'account_idx': 2},
            {'firstname': 'M\u00f3nica', 'lastname': 'Estrada Ruiz', 'email': 'm.estrada@fresnilloplc.com', 'phone': '55-5279-3002', 'mobile': '55-5567-8901', 'title': 'Gerente de Proyectos', 'account_idx': 2},

            # Minera Alamos (3)
            {'firstname': 'Daniel', 'lastname': 'Herrera Mu\u00f1oz', 'email': 'd.herrera@mineraalamos.com', 'phone': '647-428-0501', 'mobile': '647-1234-5678', 'title': 'Ingeniero de Planta', 'account_idx': 3},
            {'firstname': 'Sandra', 'lastname': 'Zamora D\u00edaz', 'email': 's.zamora@mineraalamos.com', 'phone': '647-428-0502', 'mobile': '647-2345-6789', 'title': 'Gerente de Log\u00edstica', 'account_idx': 3},

            # First Majestic Silver (4)
            {'firstname': 'Jorge', 'lastname': 'Guerrero Pacheco', 'email': 'j.guerrero@firstmajestic.com', 'phone': '618-134-2801', 'mobile': '618-1234-5678', 'title': 'Director T\u00e9cnico', 'account_idx': 4},
            {'firstname': 'Adriana', 'lastname': 'Pe\u00f1a Morales', 'email': 'a.pena@firstmajestic.com', 'phone': '618-134-2802', 'mobile': '618-2345-6789', 'title': 'VP de Operaciones', 'account_idx': 4},

            # Torex Gold (5)
            {'firstname': 'Luis', 'lastname': 'Contreras Silva', 'email': 'l.contreras@torexgold.com', 'phone': '747-471-8501', 'mobile': '747-1234-5678', 'title': 'Superintendente de Mina', 'account_idx': 5},
            {'firstname': 'Ver\u00f3nica', 'lastname': 'Dom\u00ednguez Rojas', 'email': 'v.dominguez@torexgold.com', 'phone': '747-471-8502', 'mobile': '747-2345-6789', 'title': 'Gerente de Compras', 'account_idx': 5},

            # Cemex (6)
            {'firstname': 'Roberto', 'lastname': 'Cant\u00fa Garza', 'email': 'r.cantu@cemex.com', 'phone': '81-8888-8801', 'mobile': '81-1111-2222', 'title': 'Director de Proyectos', 'account_idx': 6},
            {'firstname': 'Diana', 'lastname': 'Leal Villarreal', 'email': 'd.leal@cemex.com', 'phone': '81-8888-8802', 'mobile': '81-2222-3333', 'title': 'Gerente de Planta', 'account_idx': 6},

            # Minera Autl\u00e1n (7)
            {'firstname': 'Hugo', 'lastname': 'Mart\u00ednez Rivas', 'email': 'h.martinez@autlan.com.mx', 'phone': '444-825-3001', 'mobile': '444-1234-5678', 'title': 'Jefe de Mantenimiento', 'account_idx': 7},
            {'firstname': 'Claudia', 'lastname': 'Ram\u00edrez Sol\u00eds', 'email': 'c.ramirez@autlan.com.mx', 'phone': '444-825-3002', 'mobile': '444-2345-6789', 'title': 'Gerente de Seguridad', 'account_idx': 7},

            # Constructora ICA (8)
            {'firstname': 'Miguel', 'lastname': '\u00c1vila Castillo', 'email': 'm.avila@ica.com.mx', 'phone': '55-5272-9992', 'mobile': '55-6678-9012', 'title': 'Director de Operaciones', 'account_idx': 8},
            {'firstname': 'Lilia', 'lastname': 'Barrera N\u00fa\u00f1ez', 'email': 'l.barrera@ica.com.mx', 'phone': '55-5272-9993', 'mobile': '55-7789-0123', 'title': 'Gerente de Compras', 'account_idx': 8},

            # Grupo Carso Infraestructura (9)
            {'firstname': 'Eduardo', 'lastname': 'Soto Medina', 'email': 'e.soto@gcarso.com.mx', 'phone': '55-5625-5701', 'mobile': '55-8890-1234', 'title': 'VP de Operaciones', 'account_idx': 9},
            {'firstname': 'Ana Laura', 'lastname': 'Cordero Ibarra', 'email': 'al.cordero@gcarso.com.mx', 'phone': '55-5625-5702', 'mobile': '55-9901-2345', 'title': 'Gerente de Proyectos', 'account_idx': 9},

            # Mota-Engil M\u00e9xico (10)
            {'firstname': 'Julio', 'lastname': 'Vel\u00e1zquez Landa', 'email': 'j.velazquez@mota-engil.mx', 'phone': '55-5081-8501', 'mobile': '55-1012-3456', 'title': 'Director T\u00e9cnico', 'account_idx': 10},
            {'firstname': 'Mariana', 'lastname': 'Trejo Aguilar', 'email': 'm.trejo@mota-engil.mx', 'phone': '55-5081-8502', 'mobile': '55-1123-4567', 'title': 'Ingeniero de Planta', 'account_idx': 10},

            # Endeavour Silver (11)
            {'firstname': 'Ra\u00fal', 'lastname': 'Espinoza Vargas', 'email': 'r.espinoza@edrsilver.com', 'phone': '473-732-5801', 'mobile': '473-1234-5678', 'title': 'Superintendente de Mina', 'account_idx': 11},
            {'firstname': 'Irene', 'lastname': 'Gallegos Pineda', 'email': 'i.gallegos@edrsilver.com', 'phone': '473-732-5802', 'mobile': '473-2345-6789', 'title': 'Gerente de Log\u00edstica', 'account_idx': 11},

            # Independent contacts (no account)
            {'firstname': 'Sergio', 'lastname': 'Tapia Bernal', 'email': 'sergio.tapia.mining@gmail.com', 'phone': '55-4444-5555', 'mobile': '55-2234-0001', 'title': 'Consultor Independiente de Miner\u00eda', 'account_idx': None},
            {'firstname': 'Carmen', 'lastname': 'Olvera Reyes', 'email': 'carmen.olvera.ing@gmail.com', 'phone': '55-6666-7777', 'mobile': '55-2234-0002', 'title': 'Ingeniera Geomec\u00e1nica Freelance', 'account_idx': None},
        ]

        contacts = []
        for contact_data in contacts_data:
            if not Contact.objects.filter(emailaddress1=contact_data['email']).exists():
                owner = random.choice(users) if users else admin
                parent_account = accounts[contact_data['account_idx']] if contact_data['account_idx'] is not None and contact_data['account_idx'] < len(accounts) else None

                contact = Contact.objects.create(
                    firstname=contact_data['firstname'],
                    lastname=contact_data['lastname'],
                    emailaddress1=contact_data['email'],
                    telephone1=contact_data['phone'],
                    mobilephone=contact_data['mobile'],
                    jobtitle=contact_data['title'],
                    parentcustomerid=parent_account,
                    ownerid=owner,
                    createdby=admin,
                    modifiedby=admin,
                )
                contacts.append(contact)

        return contacts

    def create_leads(self, users, admin):
        """Create 8 leads for mining/construction industry."""
        leads_data = [
            # Open leads (5)
            {
                'firstname': 'Ernesto', 'lastname': 'Quiroga Salazar',
                'email': 'e.quiroga@sanjulian.com.mx', 'phone': '614-432-1100',
                'company': 'Minera San Juli\u00e1n', 'title': 'Gerente de Compras',
                'subject': 'Suministro de Tuber\u00eda HDPE 315mm-630mm para sistema de desag\u00fce',
                'quality': 3, 'source': 1, 'value': '4500000',
                'state': 0, 'status': 1,
            },
            {
                'firstname': 'Manuel', 'lastname': 'Bravo Espinoza',
                'email': 'm.bravo@pinabete.com.mx', 'phone': '844-413-5000',
                'company': 'Proyecto Minero El Pinabete', 'title': 'Director de Operaciones',
                'subject': 'Sistema completo de ventilaci\u00f3n para nueva mina subterr\u00e1nea 3 niveles',
                'quality': 3, 'source': 6, 'value': '8500000',
                'state': 0, 'status': 1,
            },
            {
                'firstname': 'Arturo', 'lastname': 'Garza Ponce',
                'email': 'a.garza@constructoragp.com.mx', 'phone': '81-1234-5600',
                'company': 'Constructora Garza Ponce', 'title': 'Director de Proyectos',
                'subject': 'Suministro acero estructural para nave industrial 5,000m2',
                'quality': 2, 'source': 7, 'value': '6200000',
                'state': 0, 'status': 2,
            },
            {
                'firstname': 'Isabel', 'lastname': 'Duarte Cano',
                'email': 'i.duarte@herradura.com.mx', 'phone': '662-259-0800',
                'company': 'Minera La Herradura', 'title': 'Gerente de Seguridad',
                'subject': 'Programa integral de EPP para 800 trabajadores de mina a cielo abierto',
                'quality': 2, 'source': 8, 'value': '3200000',
                'state': 0, 'status': 1,
            },
            {
                'firstname': 'Pedro', 'lastname': 'Moctezuma Rivera',
                'email': 'p.moctezuma@cemosmx.com', 'phone': '222-309-7000',
                'company': 'Cementos Moctezuma', 'title': 'Jefe de Mantenimiento',
                'subject': 'Sistema de bandas transportadoras para l\u00ednea de producci\u00f3n caliza',
                'quality': 3, 'source': 1, 'value': '12000000',
                'state': 0, 'status': 2,
            },
            # Qualified leads (2)
            {
                'firstname': 'Ra\u00fal', 'lastname': 'Ontiveros Medina',
                'email': 'r.ontiveros@penasquito.com.mx', 'phone': '493-933-2000',
                'company': 'Pe\u00f1asquito (Newmont)', 'title': 'Superintendente de Planta',
                'subject': 'Ampliaci\u00f3n sistema de bombeo para expansi\u00f3n fase 3 mina Pe\u00f1asquito',
                'quality': 3, 'source': 1, 'value': '15000000',
                'state': 1, 'status': 3,
            },
            {
                'firstname': 'Liliana', 'lastname': 'Rangel Soto',
                'email': 'l.rangel@grupobal.com.mx', 'phone': '55-5229-1000',
                'company': 'Grupo BAL', 'title': 'Directora de Compras Corporativas',
                'subject': 'Contrato marco de suministro de explosivos y accesorios de voladura 2026',
                'quality': 3, 'source': 6, 'value': '22000000',
                'state': 1, 'status': 3,
            },
            # Disqualified lead (1)
            {
                'firstname': 'Tom\u00e1s', 'lastname': 'Piedra L\u00f3pez',
                'email': 't.piedra@minaspiedra.com', 'phone': '618-555-1234',
                'company': 'Minas Piedra y Asociados', 'title': 'Due\u00f1o',
                'subject': 'Cotizaci\u00f3n equipamiento b\u00e1sico para peque\u00f1a mina artesanal',
                'quality': 1, 'source': 8, 'value': '50000',
                'state': 2, 'status': 6,
            },
        ]

        leads = []
        today = datetime.now().date()

        for lead_data in leads_data:
            if not Lead.objects.filter(emailaddress1=lead_data['email']).exists():
                owner = random.choice(users) if users else admin
                close_date = today + timedelta(days=random.randint(30, 180))

                lead = Lead.objects.create(
                    firstname=lead_data['firstname'],
                    lastname=lead_data['lastname'],
                    emailaddress1=lead_data['email'],
                    telephone1=lead_data['phone'],
                    companyname=lead_data['company'],
                    jobtitle=lead_data['title'],
                    subject=lead_data['subject'],
                    leadqualitycode=lead_data['quality'],
                    leadsourcecode=lead_data['source'],
                    estimatedvalue=Decimal(lead_data['value']),
                    estimatedclosedate=close_date,
                    statecode=lead_data['state'],
                    statuscode=lead_data['status'],
                    ownerid=owner,
                    createdby=admin,
                    modifiedby=admin,
                )
                leads.append(lead)

        return leads

    def create_opportunities(self, accounts, contacts, leads, users, admin):
        """Create 8 opportunities for mining/construction industry."""
        opportunities = []
        today = datetime.now().date()

        opps_data = [
            # Open opportunities (5)
            {
                'name': 'Grupo M\u00e9xico - Suministro HDPE Buenavista del Cobre',
                'account_idx': 0, 'revenue': '15000000', 'stage': 1, 'probability': 70,
                'days': 60, 'state': 0,
            },
            {
                'name': 'Pe\u00f1oles - EPP y Seguridad Mina Bismark',
                'account_idx': 1, 'revenue': '3500000', 'stage': 0, 'probability': 45,
                'days': 120, 'state': 0,
            },
            {
                'name': 'Fresnillo - Sistema de Bombeo Saucito',
                'account_idx': 2, 'revenue': '8000000', 'stage': 2, 'probability': 80,
                'days': 45, 'state': 0,
            },
            {
                'name': 'Cemex - Bandas Transportadoras Planta Tepeaca',
                'account_idx': 6, 'revenue': '12000000', 'stage': 1, 'probability': 60,
                'days': 90, 'state': 0,
            },
            {
                'name': 'Torex Gold - Cables y Ventilaci\u00f3n Media Luna',
                'account_idx': 5, 'revenue': '6000000', 'stage': 2, 'probability': 75,
                'days': 50, 'state': 0,
            },
            # Won opportunities (3)
            {
                'name': 'Minera Autl\u00e1n - Soporte de Roca Molango',
                'account_idx': 7, 'revenue': '2500000', 'stage': 3, 'probability': 100,
                'days': -15, 'state': 1,
            },
            {
                'name': 'First Majestic - Perforaci\u00f3n San Dimas',
                'account_idx': 4, 'revenue': '4500000', 'stage': 3, 'probability': 100,
                'days': -30, 'state': 1,
            },
            {
                'name': 'Constructora ICA - Acero Estructural Tren Maya',
                'account_idx': 8, 'revenue': '18000000', 'stage': 3, 'probability': 100,
                'days': -20, 'state': 1,
            },
        ]

        for i, opp_data in enumerate(opps_data):
            account = accounts[opp_data['account_idx']] if opp_data['account_idx'] < len(accounts) else None
            owner = random.choice(users) if users else admin
            close_date = today + timedelta(days=opp_data['days'])

            # Find a contact from the same account
            contact = None
            if account:
                account_contacts = [c for c in contacts if c.parentcustomerid == account]
                contact = account_contacts[0] if account_contacts else None

            opportunity = Opportunity.objects.create(
                name=opp_data['name'],
                accountid=account,
                contactid=contact,
                estimatedrevenue=Decimal(opp_data['revenue']),
                estimatedclosedate=close_date,
                salesstage=opp_data['stage'],
                probability=opp_data['probability'],
                statecode=opp_data['state'],
                statuscode=OpportunityStatusCode.WON if opp_data['state'] == 1 else OpportunityStatusCode.IN_PROGRESS,
                actualrevenue=Decimal(opp_data['revenue']) if opp_data['state'] == 1 else None,
                actualclosedate=close_date if opp_data['state'] == 1 else None,
                ownerid=owner,
                createdby=admin,
                modifiedby=admin,
            )
            opportunities.append(opportunity)

        return opportunities

    def create_quotes(self, opportunities, accounts, contacts, users, admin):
        """Create quotes from won and open opportunities with mining product line items."""
        quotes = []
        today = datetime.now().date()
        quote_counter = 1

        # Get won opportunities to create quotes from
        won_opps = [opp for opp in opportunities if opp.statecode == OpportunityStateCode.WON]

        # Define mining product line items for each won opportunity
        won_line_items = {
            # Minera Autl\u00e1n - Soporte de Roca Molango
            0: [
                {'name': 'Split Set 2.4m', 'desc': 'Perno split set galvanizado 39mm x 2.4m', 'qty': 5000, 'price': Decimal('120.00')},
                {'name': 'Perno de Resina 2.4m', 'desc': 'Perno roscado con resina 22mm x 2.4m', 'qty': 3000, 'price': Decimal('165.00')},
                {'name': 'Malla Electrosoldada 4x4"', 'desc': 'Malla electrosoldada calibre 4 rollo', 'qty': 800, 'price': Decimal('450.00')},
                {'name': 'Shotcrete por m\u00b3', 'desc': 'Concreto lanzado por metro c\u00fabico', 'qty': 200, 'price': Decimal('2800.00')},
                {'name': 'Fibra de Acero 20kg', 'desc': 'Fibra de acero para refuerzo shotcrete', 'qty': 150, 'price': Decimal('4500.00')},
            ],
            # First Majestic - Perforaci\u00f3n San Dimas
            1: [
                {'name': 'Broca de Botones 45mm', 'desc': 'Broca de botones bal\u00edsticos 45mm rosca R32', 'qty': 200, 'price': Decimal('2500.00')},
                {'name': 'Barra de Perforaci\u00f3n T38 3.66m', 'desc': 'Barra extensi\u00f3n T38 hexagonal 3.66m', 'qty': 150, 'price': Decimal('8500.00')},
                {'name': 'Barra de Perforaci\u00f3n T38 1.83m', 'desc': 'Barra extensi\u00f3n T38 hexagonal 1.83m', 'qty': 120, 'price': Decimal('5200.00')},
                {'name': 'Acoplamiento T38', 'desc': 'Acoplamiento hembra-hembra T38', 'qty': 100, 'price': Decimal('3800.00')},
                {'name': 'Aceite de Perforaci\u00f3n 200L', 'desc': 'Aceite hidr\u00e1ulico perforaci\u00f3n tambor 200L', 'qty': 30, 'price': Decimal('3200.00')},
            ],
            # Constructora ICA - Acero Estructural Tren Maya
            2: [
                {'name': 'Viga W10x49 por metro', 'desc': 'Viga IPR W10x49 acero A572 Gr50', 'qty': 500, 'price': Decimal('12500.00')},
                {'name': 'Viga W8x31 por metro', 'desc': 'Viga IPR W8x31 acero A572 Gr50', 'qty': 800, 'price': Decimal('8500.00')},
                {'name': 'Placa de Acero 3/4" 4x8 pies', 'desc': 'Placa acero A36 3/4" espesor', 'qty': 300, 'price': Decimal('6800.00')},
                {'name': 'PTR 4x4" Cal.11 por metro', 'desc': 'Perfil tubular rectangular 4x4" cal.11', 'qty': 600, 'price': Decimal('2200.00')},
            ],
        }

        for idx, opp in enumerate(won_opps):
            owner = opp.ownerid or (random.choice(users) if users else admin)

            # Create quote
            quote = Quote.objects.create(
                name=f"{opp.name} - Cotizaci\u00f3n",
                quotenumber=f"Q-2026-{quote_counter:04d}",
                opportunityid=opp,
                accountid=opp.accountid,
                contactid=opp.contactid,
                effectivefrom=today,
                effectiveto=today + timedelta(days=90),
                discountpercentage=Decimal('5.00') if quote_counter % 2 == 0 else Decimal('0.00'),
                statecode=QuoteStateCode.WON,
                statuscode=QuoteStatusCode.WON,
                closedon=timezone.make_aware(datetime.combine(opp.actualclosedate, time())) if opp.actualclosedate else None,
                description=f"Cotizaci\u00f3n para {opp.name}",
                ownerid=owner,
                createdby=admin,
                modifiedby=admin,
            )

            # Add quote details (line items)
            line_items = won_line_items.get(idx, [
                {'name': 'Tuber\u00eda HDPE PE-100 PN10 315mm', 'desc': 'Tuber\u00eda HDPE 315mm barra 12m', 'qty': 100, 'price': Decimal('5800.00')},
                {'name': 'Termofusi\u00f3n HDPE por Junta', 'desc': 'Servicio termofusi\u00f3n a tope', 'qty': 99, 'price': Decimal('8500.00')},
            ])

            for seq, item in enumerate(line_items, 1):
                subtotal = Decimal(str(item['qty'])) * item['price']
                tax_amount = subtotal * Decimal('0.16')  # 16% IVA
                QuoteDetail.objects.create(
                    quoteid=quote,
                    productname=item['name'],
                    productdescription=item['desc'],
                    quantity=Decimal(str(item['qty'])),
                    priceperunit=item['price'],
                    tax=tax_amount,
                    manualdiscountamount=Decimal('0.00'),
                    sequencenumber=seq,
                )

            # Calculate totals
            quote.calculate_totals()
            quote.save()

            quotes.append(quote)
            quote_counter += 1

        # Create some draft/active quotes from open opportunities
        open_opps = [opp for opp in opportunities if opp.statecode == OpportunityStateCode.OPEN][:2]

        open_line_items = {
            # Grupo M\u00e9xico - HDPE
            0: [
                {'name': 'Tuber\u00eda HDPE PE-100 PN10 630mm', 'desc': 'Tuber\u00eda HDPE 630mm barra 12m', 'qty': 200, 'price': Decimal('12500.00')},
                {'name': 'Tuber\u00eda HDPE PE-100 PN10 500mm', 'desc': 'Tuber\u00eda HDPE 500mm barra 12m', 'qty': 150, 'price': Decimal('8800.00')},
                {'name': 'Tuber\u00eda HDPE PE-100 PN10 315mm', 'desc': 'Tuber\u00eda HDPE 315mm barra 12m', 'qty': 300, 'price': Decimal('5800.00')},
                {'name': 'Instalaci\u00f3n Tuber\u00eda HDPE por ml', 'desc': 'Servicio instalaci\u00f3n incluye termofusi\u00f3n', 'qty': 3000, 'price': Decimal('350.00')},
            ],
            # Pe\u00f1oles - EPP
            1: [
                {'name': 'Casco Minero con L\u00e1mpara LED', 'desc': 'Casco minero con l\u00e1mpara LED integrada', 'qty': 500, 'price': Decimal('4500.00')},
                {'name': 'Autorescatador 60 min', 'desc': 'Autorescatador de ox\u00edgeno qu\u00edmico', 'qty': 500, 'price': Decimal('8500.00')},
                {'name': 'Detector Multigas Port\u00e1til', 'desc': 'Detector 4 gases port\u00e1til', 'qty': 50, 'price': Decimal('8500.00')},
            ],
        }

        for idx, opp in enumerate(open_opps):
            owner = opp.ownerid or (random.choice(users) if users else admin)

            quote = Quote.objects.create(
                name=f"{opp.name} - Propuesta",
                quotenumber=f"Q-2026-{quote_counter:04d}",
                opportunityid=opp,
                accountid=opp.accountid,
                contactid=opp.contactid,
                effectivefrom=today,
                effectiveto=today + timedelta(days=60),
                statecode=QuoteStateCode.ACTIVE if quote_counter % 2 == 0 else QuoteStateCode.DRAFT,
                statuscode=QuoteStatusCode.IN_REVIEW if quote_counter % 2 == 0 else QuoteStatusCode.IN_PROGRESS,
                description=f"Propuesta comercial para {opp.name}",
                ownerid=owner,
                createdby=admin,
                modifiedby=admin,
            )

            line_items = open_line_items.get(idx, [
                {'name': 'Bomba Sumergible 50HP', 'desc': 'Bomba sumergible 50HP acero inox', 'qty': 2, 'price': Decimal('185000.00')},
            ])

            for seq, item in enumerate(line_items, 1):
                subtotal = Decimal(str(item['qty'])) * item['price']
                tax_amount = subtotal * Decimal('0.16')
                QuoteDetail.objects.create(
                    quoteid=quote,
                    productname=item['name'],
                    productdescription=item['desc'],
                    quantity=Decimal(str(item['qty'])),
                    priceperunit=item['price'],
                    tax=tax_amount,
                    manualdiscountamount=Decimal('0.00'),
                    sequencenumber=seq,
                )

            quote.calculate_totals()
            quote.save()

            quotes.append(quote)
            quote_counter += 1

        return quotes

    def create_orders(self, quotes, users, admin):
        """Create orders from won quotes."""
        orders = []
        today = datetime.now().date()
        order_counter = 1

        # Get won quotes to create orders from
        won_quotes = [q for q in quotes if q.statecode == QuoteStateCode.WON]

        for quote in won_quotes:
            owner = quote.ownerid or (random.choice(users) if users else admin)

            # Create order from quote
            order = SalesOrder.objects.create(
                name=quote.name.replace('Cotizaci\u00f3n', 'Orden'),
                ordernumber=f"SO-2026-{order_counter:04d}",
                quoteid=quote,
                opportunityid=quote.opportunityid,
                accountid=quote.accountid,
                contactid=quote.contactid,
                totalamount=quote.totalamount,
                totaldiscountamount=quote.totaldiscountamount,
                totaltax=quote.totaltax,
                totallineitemamount=quote.totallineitemamount,
                requestdeliveryby=today + timedelta(days=30),
                statecode=OrderStateCode.FULFILLED if order_counter % 2 == 1 else OrderStateCode.SUBMITTED,
                statuscode=OrderStatusCode.COMPLETE if order_counter % 2 == 1 else OrderStatusCode.IN_PROGRESS,
                datefulfilled=timezone.make_aware(datetime.combine(today + timedelta(days=15), time())) if order_counter % 2 == 1 else None,
                description=f"Orden generada desde {quote.quotenumber}",
                ownerid=owner,
                createdby=admin,
                modifiedby=admin,
            )

            # Copy quote details to order details
            for quote_detail in quote.quote_details.all():
                SalesOrderDetail.objects.create(
                    salesorderid=order,
                    productname=quote_detail.productname,
                    productdescription=quote_detail.productdescription,
                    quantity=quote_detail.quantity,
                    priceperunit=quote_detail.priceperunit,
                    manualdiscountamount=quote_detail.manualdiscountamount,
                    tax=quote_detail.tax,
                    sequencenumber=quote_detail.sequencenumber,
                )

            orders.append(order)
            order_counter += 1

        return orders

    def create_invoices(self, orders, users, admin):
        """Create invoices from fulfilled orders."""
        invoices = []
        today = datetime.now().date()
        invoice_counter = 1

        # Get fulfilled orders to create invoices from
        fulfilled_orders = [o for o in orders if o.statecode == OrderStateCode.FULFILLED]

        for order in fulfilled_orders:
            owner = order.ownerid or (random.choice(users) if users else admin)

            # Determine payment status
            is_paid = invoice_counter % 3 == 0  # 1/3 will be paid
            is_partial = invoice_counter % 3 == 1  # 1/3 will be partial

            total_paid = Decimal('0.00')
            if is_paid:
                total_paid = order.totalamount
            elif is_partial:
                total_paid = order.totalamount * Decimal('0.60')  # 60% paid

            # Create invoice from order
            invoice = Invoice.objects.create(
                name=order.name.replace('Orden', 'Factura'),
                invoicenumber=f"INV-2026-{invoice_counter:04d}",
                salesorderid=order,
                opportunityid=order.opportunityid,
                accountid=order.accountid,
                contactid=order.contactid,
                totalamount=order.totalamount,
                totaldiscountamount=order.totaldiscountamount,
                totaltax=order.totaltax,
                totallineitemamount=order.totallineitemamount,
                totalamountless=order.totallineitemamount - order.totaldiscountamount,
                totalpaid=total_paid,
                totalamountdue=order.totalamount - total_paid,
                datedelivered=order.datefulfilled if order.datefulfilled else today,
                duedate=today + timedelta(days=30),
                paidon=today if is_paid else None,
                statecode=InvoiceStateCode.PAID if is_paid else InvoiceStateCode.ACTIVE,
                statuscode=InvoiceStatusCode.COMPLETE if is_paid else (InvoiceStatusCode.PARTIAL if is_partial else InvoiceStatusCode.NEW),
                description=f"Factura generada desde {order.ordernumber}",
                ownerid=owner,
                createdby=admin,
                modifiedby=admin,
            )

            # Copy order details to invoice details
            for order_detail in order.order_details.all():
                InvoiceDetail.objects.create(
                    invoiceid=invoice,
                    productname=order_detail.productname,
                    productdescription=order_detail.productdescription,
                    quantity=order_detail.quantity,
                    priceperunit=order_detail.priceperunit,
                    manualdiscountamount=order_detail.manualdiscountamount,
                    tax=order_detail.tax,
                    sequencenumber=order_detail.sequencenumber,
                )

            # Update order state to INVOICED
            order.statecode = OrderStateCode.INVOICED
            order.save(update_fields=['statecode'])

            invoices.append(invoice)
            invoice_counter += 1

        return invoices

    def print_summary(self):
        """Print summary of created data."""
        self.stdout.write(self.style.SUCCESS('\n=============== DATABASE SUMMARY ==============='))

        self.stdout.write(self.style.SUCCESS('\n[Core Entities]'))
        self.stdout.write(f'  Users: {SystemUser.objects.count()}')
        self.stdout.write(f'  Accounts: {Account.objects.count()}')
        self.stdout.write(f'  Contacts: {Contact.objects.count()}')

        self.stdout.write(self.style.SUCCESS('\n[Product Catalog]'))
        self.stdout.write(f'  Products: {Product.objects.count()}')
        self.stdout.write(f'     - Families: {Product.objects.filter(productstructure=2).count()}')
        self.stdout.write(f'     - Individual Products: {Product.objects.filter(productstructure=1).count()}')
        self.stdout.write(f'  Price Lists: {PriceList.objects.count()}')
        self.stdout.write(f'  Price List Items: {PriceListItem.objects.count()}')

        self.stdout.write(self.style.SUCCESS('\n[Sales Pipeline]'))
        self.stdout.write(f'  Leads: {Lead.objects.count()}')
        self.stdout.write(f'     - Open: {Lead.objects.filter(statecode=LeadStateCode.OPEN).count()}')
        self.stdout.write(f'     - Qualified: {Lead.objects.filter(statecode=LeadStateCode.QUALIFIED).count()}')
        self.stdout.write(f'     - Disqualified: {Lead.objects.filter(statecode=LeadStateCode.DISQUALIFIED).count()}')

        self.stdout.write(f'  Opportunities: {Opportunity.objects.count()}')
        self.stdout.write(f'     - Open: {Opportunity.objects.filter(statecode=OpportunityStateCode.OPEN).count()}')
        self.stdout.write(f'     - Won: {Opportunity.objects.filter(statecode=OpportunityStateCode.WON).count()}')
        self.stdout.write(f'     - Lost: {Opportunity.objects.filter(statecode=OpportunityStateCode.LOST).count()}')

        self.stdout.write(f'  Quotes: {Quote.objects.count()}')
        self.stdout.write(f'     - Draft: {Quote.objects.filter(statecode=QuoteStateCode.DRAFT).count()}')
        self.stdout.write(f'     - Active: {Quote.objects.filter(statecode=QuoteStateCode.ACTIVE).count()}')
        self.stdout.write(f'     - Won: {Quote.objects.filter(statecode=QuoteStateCode.WON).count()}')

        self.stdout.write(f'  Orders: {SalesOrder.objects.count()}')
        self.stdout.write(f'     - Submitted: {SalesOrder.objects.filter(statecode=OrderStateCode.SUBMITTED).count()}')
        self.stdout.write(f'     - Fulfilled: {SalesOrder.objects.filter(statecode=OrderStateCode.FULFILLED).count()}')
        self.stdout.write(f'     - Invoiced: {SalesOrder.objects.filter(statecode=OrderStateCode.INVOICED).count()}')

        self.stdout.write(f'  Invoices: {Invoice.objects.count()}')
        self.stdout.write(f'     - Active: {Invoice.objects.filter(statecode=InvoiceStateCode.ACTIVE).count()}')
        self.stdout.write(f'     - Paid: {Invoice.objects.filter(statecode=InvoiceStateCode.PAID).count()}')

        self.stdout.write(self.style.SUCCESS('\n[Financial Summary (MXN)]'))
        total_revenue = Opportunity.objects.filter(statecode=OpportunityStateCode.WON).aggregate(
            total=models.Sum('actualrevenue')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Opportunity Revenue: MXN ${total_revenue:,.2f}')

        total_quotes = Quote.objects.filter(statecode=QuoteStateCode.WON).aggregate(
            total=models.Sum('totalamount')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Quote Value (Won): MXN ${total_quotes:,.2f}')

        total_orders = SalesOrder.objects.aggregate(
            total=models.Sum('totalamount')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Order Value: MXN ${total_orders:,.2f}')

        total_invoiced = Invoice.objects.aggregate(
            total=models.Sum('totalamount')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Invoiced: MXN ${total_invoiced:,.2f}')

        total_paid = Invoice.objects.aggregate(
            total=models.Sum('totalpaid')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Paid: MXN ${total_paid:,.2f}')

        total_due = Invoice.objects.aggregate(
            total=models.Sum('totalamountdue')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Outstanding: MXN ${total_due:,.2f}')

        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Complete Sales Pipeline Ready!'))
        self.stdout.write(self.style.SUCCESS('   Lead -> Opportunity -> Quote -> Order -> Invoice'))
        self.stdout.write(self.style.SUCCESS('\n[READY] Ready to test in Postman!'))
