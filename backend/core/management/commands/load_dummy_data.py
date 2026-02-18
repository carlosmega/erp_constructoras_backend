"""
Django management command to load dummy data into the CRM.

Usage:
    python manage.py load_dummy_data
    python manage.py load_dummy_data --clear  # Clear existing data first
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta, time
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


class Command(BaseCommand):
    help = 'Load dummy data into the CRM database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before loading dummy data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to load dummy data...'))

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
                'fullname': 'Roberto Martínez',
                'password': 'manager123',
                'role': 'Sales Manager'
            },
            {
                'email': 'vendedor1@crm.com',
                'fullname': 'Ana García',
                'password': 'vendedor123',
                'role': 'Salesperson'
            },
            {
                'email': 'vendedor2@crm.com',
                'fullname': 'Carlos López',
                'password': 'vendedor123',
                'role': 'Salesperson'
            },
            {
                'email': 'marketing@crm.com',
                'fullname': 'Laura Hernández',
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

    def create_accounts(self, users, admin):
        """Create sample B2B accounts."""
        accounts_data = [
            {
                'name': 'Microsoft México',
                'accountnumber': 'ACC-001',
                'email': 'contacto@microsoft.com.mx',
                'phone': '55-5000-7000',
                'website': 'https://microsoft.com/mx',
                'city': 'Ciudad de México',
                'state': 'CDMX',
                'revenue': Decimal('50000000.00'),
                'employees': 5000,
            },
            {
                'name': 'Google México',
                'accountnumber': 'ACC-002',
                'email': 'info@google.com.mx',
                'phone': '55-4000-3000',
                'website': 'https://google.com.mx',
                'city': 'Ciudad de México',
                'state': 'CDMX',
                'revenue': Decimal('30000000.00'),
                'employees': 3000,
            },
            {
                'name': 'Grupo Bimbo',
                'accountnumber': 'ACC-003',
                'email': 'contacto@bimbo.com',
                'phone': '55-5268-6600',
                'website': 'https://grupobimbo.com',
                'city': 'Ciudad de México',
                'state': 'CDMX',
                'revenue': Decimal('80000000.00'),
                'employees': 10000,
            },
            {
                'name': 'Cemex',
                'accountnumber': 'ACC-004',
                'email': 'info@cemex.com',
                'phone': '81-8888-8888',
                'website': 'https://cemex.com',
                'city': 'Monterrey',
                'state': 'Nuevo León',
                'revenue': Decimal('45000000.00'),
                'employees': 7500,
            },
            {
                'name': 'América Móvil',
                'accountnumber': 'ACC-005',
                'email': 'contacto@americamovil.com',
                'phone': '55-2581-4444',
                'website': 'https://americamovil.com',
                'city': 'Ciudad de México',
                'state': 'CDMX',
                'revenue': Decimal('60000000.00'),
                'employees': 8000,
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
                    address1_country='México',
                    revenue=acc_data['revenue'],
                    numberofemployees=acc_data['employees'],
                    ownerid=owner,
                    createdby=admin,
                    modifiedby=admin,
                )
                accounts.append(account)

        return accounts

    def create_contacts(self, accounts, users, admin):
        """Create sample contacts."""
        contacts_data = [
            # Microsoft contacts
            {'firstname': 'Juan', 'lastname': 'Pérez', 'email': 'juan.perez@microsoft.com.mx', 'phone': '55-5000-7001', 'mobile': '55-1234-5678', 'title': 'Director de Ventas', 'account_idx': 0},
            {'firstname': 'María', 'lastname': 'González', 'email': 'maria.gonzalez@microsoft.com.mx', 'phone': '55-5000-7002', 'mobile': '55-8765-4321', 'title': 'Gerente de Marketing', 'account_idx': 0},

            # Google contacts
            {'firstname': 'Carlos', 'lastname': 'Ramírez', 'email': 'carlos.ramirez@google.com.mx', 'phone': '55-4000-3001', 'mobile': '55-9876-5432', 'title': 'VP de Tecnología', 'account_idx': 1},

            # Bimbo contacts
            {'firstname': 'Laura', 'lastname': 'Martínez', 'email': 'laura.martinez@bimbo.com', 'phone': '55-5268-6601', 'mobile': '55-5555-6666', 'title': 'Directora de Compras', 'account_idx': 2},
            {'firstname': 'Roberto', 'lastname': 'Sánchez', 'email': 'roberto.sanchez@bimbo.com', 'phone': '55-5268-6602', 'mobile': '55-7777-8888', 'title': 'CFO', 'account_idx': 2},

            # Cemex contacts
            {'firstname': 'Patricia', 'lastname': 'Torres', 'email': 'patricia.torres@cemex.com', 'phone': '81-8888-8801', 'mobile': '81-1111-2222', 'title': 'Gerente de Proyectos', 'account_idx': 3},

            # América Móvil contacts
            {'firstname': 'Miguel', 'lastname': 'Hernández', 'email': 'miguel.hernandez@americamovil.com', 'phone': '55-2581-4401', 'mobile': '55-3333-4444', 'title': 'Director de Operaciones', 'account_idx': 4},

            # Independent contacts (no account)
            {'firstname': 'Ana', 'lastname': 'López', 'email': 'ana.lopez@gmail.com', 'phone': '55-9999-8888', 'mobile': '55-4444-5555', 'title': 'Consultor Independiente', 'account_idx': None},
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
        """Create sample leads in various states."""
        leads_data = [
            # Open leads
            {'firstname': 'Diego', 'lastname': 'Ruiz', 'email': 'diego.ruiz@startup.com', 'phone': '55-1111-2222', 'company': 'TechStart México', 'title': 'CEO', 'quality': 3, 'source': 8, 'value': '250000', 'state': 0, 'status': 1},
            {'firstname': 'Sofía', 'lastname': 'Morales', 'email': 'sofia.morales@innovatech.com', 'phone': '55-3333-4444', 'company': 'InnovaTech', 'title': 'CTO', 'quality': 2, 'source': 6, 'value': '180000', 'state': 0, 'status': 1},
            {'firstname': 'Fernando', 'lastname': 'Castro', 'email': 'fernando.castro@digitalplus.com', 'phone': '55-5555-6666', 'company': 'Digital Plus', 'title': 'Director', 'quality': 3, 'source': 7, 'value': '320000', 'state': 0, 'status': 2},

            # Qualified leads
            {'firstname': 'Gabriela', 'lastname': 'Ortiz', 'email': 'gabriela.ortiz@cloudmx.com', 'phone': '55-7777-8888', 'company': 'Cloud MX', 'title': 'VP Ventas', 'quality': 3, 'source': 8, 'value': '400000', 'state': 1, 'status': 3},

            # Disqualified leads
            {'firstname': 'Ricardo', 'lastname': 'Vargas', 'email': 'ricardo.vargas@oldtech.com', 'phone': '55-9999-0000', 'company': 'OldTech SA', 'title': 'Gerente', 'quality': 1, 'source': 1, 'value': '50000', 'state': 2, 'status': 6},
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
                    subject=f"Interesado en soluciones empresariales - {lead_data['company']}",
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
        """Create sample opportunities in various stages."""
        opportunities = []
        today = datetime.now().date()

        opps_data = [
            # Open opportunities
            {'name': 'Microsoft - Modernización Cloud', 'account_idx': 0, 'revenue': '1500000', 'stage': 1, 'probability': 70, 'days': 60, 'state': 0},
            {'name': 'Google - Migración a GCP', 'account_idx': 1, 'revenue': '800000', 'stage': 0, 'probability': 40, 'days': 120, 'state': 0},
            {'name': 'Bimbo - Sistema ERP', 'account_idx': 2, 'revenue': '2500000', 'stage': 2, 'probability': 85, 'days': 45, 'state': 0},
            {'name': 'Cemex - Analytics Platform', 'account_idx': 3, 'revenue': '600000', 'stage': 1, 'probability': 60, 'days': 90, 'state': 0},

            # Won opportunities
            {'name': 'América Móvil - CRM Implementation', 'account_idx': 4, 'revenue': '1200000', 'stage': 3, 'probability': 100, 'days': -15, 'state': 1},
            {'name': 'Microsoft - Azure Training', 'account_idx': 0, 'revenue': '350000', 'stage': 3, 'probability': 100, 'days': -30, 'state': 1},
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
        """Create sample quotes from won opportunities."""
        quotes = []
        today = datetime.now().date()
        quote_counter = 1

        # Get won opportunities to create quotes from
        won_opps = [opp for opp in opportunities if opp.statecode == OpportunityStateCode.WON]

        for opp in won_opps:
            owner = opp.ownerid or (random.choice(users) if users else admin)

            # Create quote
            quote = Quote.objects.create(
                name=f"{opp.name} - Quote",
                quotenumber=f"Q-2024-{quote_counter:04d}",
                opportunityid=opp,
                accountid=opp.accountid,
                contactid=opp.contactid,
                effectivefrom=today,
                effectiveto=today + timedelta(days=90),
                discountpercentage=Decimal('5.00') if quote_counter % 2 == 0 else Decimal('0.00'),
                statecode=QuoteStateCode.WON,
                statuscode=QuoteStatusCode.WON,
                closedon=timezone.make_aware(datetime.combine(opp.actualclosedate, time())) if opp.actualclosedate else None,
                description=f"Quote for {opp.name}",
                ownerid=owner,
                createdby=admin,
                modifiedby=admin,
            )

            # Add quote details (line items)
            products = [
                {'name': 'Software License - Enterprise', 'qty': 50, 'price': Decimal('500.00')},
                {'name': 'Implementation Service', 'qty': 160, 'price': Decimal('150.00')},
                {'name': 'Training Package', 'qty': 40, 'price': Decimal('100.00')},
                {'name': 'Annual Support', 'qty': 1, 'price': Decimal('12000.00')},
            ]

            for idx, product in enumerate(products[:random.randint(2, 4)], 1):
                QuoteDetail.objects.create(
                    quoteid=quote,
                    productname=product['name'],
                    productdescription=f"Professional {product['name'].lower()}",
                    quantity=product['qty'],
                    priceperunit=product['price'],
                    tax=product['qty'] * product['price'] * Decimal('0.16'),  # 16% IVA
                    manualdiscountamount=Decimal('0.00'),
                    sequencenumber=idx,
                )

            # Calculate totals
            quote.calculate_totals()
            quote.save()

            quotes.append(quote)
            quote_counter += 1

        # Create some draft/active quotes from open opportunities
        open_opps = [opp for opp in opportunities if opp.statecode == OpportunityStateCode.OPEN][:2]
        for opp in open_opps:
            owner = opp.ownerid or (random.choice(users) if users else admin)

            quote = Quote.objects.create(
                name=f"{opp.name} - Proposal",
                quotenumber=f"Q-2024-{quote_counter:04d}",
                opportunityid=opp,
                accountid=opp.accountid,
                contactid=opp.contactid,
                effectivefrom=today,
                effectiveto=today + timedelta(days=60),
                statecode=QuoteStateCode.ACTIVE if quote_counter % 2 == 0 else QuoteStateCode.DRAFT,
                statuscode=QuoteStatusCode.IN_REVIEW if quote_counter % 2 == 0 else QuoteStatusCode.IN_PROGRESS,
                description=f"Draft proposal for {opp.name}",
                ownerid=owner,
                createdby=admin,
                modifiedby=admin,
            )

            # Add a couple of line items
            QuoteDetail.objects.create(
                quoteid=quote,
                productname='Software License - Basic',
                quantity=Decimal('25'),
                priceperunit=Decimal('300.00'),
                tax=Decimal('1200.00'),
                sequencenumber=1,
            )

            quote.calculate_totals()
            quote.save()

            quotes.append(quote)
            quote_counter += 1

        return quotes

    def create_orders(self, quotes, users, admin):
        """Create sample orders from won quotes."""
        orders = []
        today = datetime.now().date()
        order_counter = 1

        # Get won quotes to create orders from
        won_quotes = [q for q in quotes if q.statecode == QuoteStateCode.WON]

        for quote in won_quotes:
            owner = quote.ownerid or (random.choice(users) if users else admin)

            # Create order from quote
            order = SalesOrder.objects.create(
                name=quote.name.replace('Quote', 'Order'),
                ordernumber=f"SO-2024-{order_counter:04d}",
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
                description=f"Order generated from {quote.quotenumber}",
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
        """Create sample invoices from fulfilled orders."""
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
                name=order.name.replace('Order', 'Invoice'),
                invoicenumber=f"INV-2024-{invoice_counter:04d}",
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
                description=f"Invoice generated from {order.ordernumber}",
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

        self.stdout.write(self.style.SUCCESS('\n[Financial Summary]'))
        total_revenue = Opportunity.objects.filter(statecode=OpportunityStateCode.WON).aggregate(
            total=models.Sum('actualrevenue')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Opportunity Revenue: ${total_revenue:,.2f}')

        total_quotes = Quote.objects.filter(statecode=QuoteStateCode.WON).aggregate(
            total=models.Sum('totalamount')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Quote Value (Won): ${total_quotes:,.2f}')

        total_orders = SalesOrder.objects.aggregate(
            total=models.Sum('totalamount')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Order Value: ${total_orders:,.2f}')

        total_invoiced = Invoice.objects.aggregate(
            total=models.Sum('totalamount')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Invoiced: ${total_invoiced:,.2f}')

        total_paid = Invoice.objects.aggregate(
            total=models.Sum('totalpaid')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Paid: ${total_paid:,.2f}')

        total_due = Invoice.objects.aggregate(
            total=models.Sum('totalamountdue')
        )['total'] or Decimal('0')
        self.stdout.write(f'  Total Outstanding: ${total_due:,.2f}')

        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Complete Sales Pipeline Ready!'))
        self.stdout.write(self.style.SUCCESS('   Lead -> Opportunity -> Quote -> Order -> Invoice'))
        self.stdout.write(self.style.SUCCESS('\n[READY] Ready to test in Postman!'))
