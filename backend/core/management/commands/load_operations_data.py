"""
Django management command to load dummy data for the Operations module.

Construction Projects — Mexico
Includes: Projects, Zones, Suppliers, TeamMembers, Categories,
          ImputationCodes, Periods, Expenses, ExpenseLines, Estimates.

Usage:
    python manage.py load_operations_data
    python manage.py load_operations_data --clear  # Clear existing operations data first
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import uuid
import random

from apps.users.models import SystemUser
from apps.accounts.models import Account
from apps.projects.models import (
    ConstructionProject, ProjectZone, ProjectTeamMember, ProjectSupplier,
)
from apps.budgets.models import CostCategory, ImputationCode, ImputationPeriod
from apps.expenses.models import (
    ProjectExpense, ExpenseLine, ClientEstimate,
)


class Command(BaseCommand):
    help = 'Load dummy data for the Operations module (Construction Projects - Mexico)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing operations data before loading',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Loading Operations dummy data...'))

        if options['clear']:
            self._clear_data()

        with transaction.atomic():
            owner = SystemUser.objects.first()
            if not owner:
                self.stdout.write(self.style.ERROR('No SystemUser found. Run load_dummy_data first.'))
                return

            accounts = list(Account.objects.filter(statecode=0)[:6])
            if len(accounts) < 3:
                self.stdout.write(self.style.ERROR('Need at least 3 accounts. Run load_dummy_data first.'))
                return

            projects = self._create_projects(owner, accounts)
            self._create_zones_and_team(projects, owner, accounts)
            self._create_categories_and_codes(projects)
            self._create_periods(projects)
            self._create_expenses(projects, owner)
            self._create_estimates(projects)

        self.stdout.write(self.style.SUCCESS('Operations dummy data loaded successfully!'))

    def _clear_data(self):
        self.stdout.write(self.style.WARNING('Clearing operations data...'))
        ClientEstimate.objects.all().delete()
        ExpenseLine.objects.all().delete()
        ProjectExpense.objects.all().delete()
        ImputationPeriod.objects.all().delete()
        ImputationCode.objects.all().delete()
        CostCategory.objects.all().delete()
        ProjectSupplier.objects.all().delete()
        ProjectTeamMember.objects.all().delete()
        ProjectZone.objects.all().delete()
        ConstructionProject.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Operations data cleared.'))

    # ── Projects ──────────────────────────────────────────────

    def _create_projects(self, owner, accounts):
        projects_data = [
            {
                'name': 'Autopista Monterrey-Saltillo Tramo II',
                'description': 'Construcción del segundo tramo de la autopista Monterrey-Saltillo, '
                               'incluyendo 3 puentes vehiculares y 2 pasos a desnivel.',
                'statecode': 1,  # ACTIVE
                'accountid': accounts[0],
                'projecttype': 0,  # PUBLIC
                'biddingtype': 0,  # OPEN_BID
                'contractamount_notax': Decimal('185000000.00'),
                'contractamount_withtax': Decimal('214600000.00'),
                'durationmonths': 24,
                'startdate': date(2025, 6, 1),
                'contractenddate': date(2027, 5, 31),
                'expectedenddate': date(2027, 5, 31),
                'presentationdate': date(2025, 3, 15),
                'awarddate': date(2025, 4, 20),
                'advancepayment_notax': Decimal('55500000.00'),
                'advancepayment_withtax': Decimal('64380000.00'),
                'periodtype': 1,  # FORTNIGHTLY
            },
            {
                'name': 'Torre Corporativa Santa Fe',
                'description': 'Edificación de torre de oficinas de 28 niveles en zona Santa Fe, '
                               'CDMX. Incluye estacionamiento subterráneo de 4 niveles.',
                'statecode': 1,  # ACTIVE
                'accountid': accounts[1],
                'projecttype': 1,  # PRIVATE
                'biddingtype': 2,  # DIRECT_AWARD
                'contractamount_notax': Decimal('320000000.00'),
                'contractamount_withtax': Decimal('371200000.00'),
                'durationmonths': 36,
                'startdate': date(2025, 1, 15),
                'contractenddate': date(2028, 1, 14),
                'expectedenddate': date(2027, 12, 31),
                'presentationdate': date(2024, 10, 1),
                'awarddate': date(2024, 11, 15),
                'advancepayment_notax': Decimal('96000000.00'),
                'advancepayment_withtax': Decimal('111360000.00'),
                'periodtype': 0,  # WEEKLY
            },
            {
                'name': 'Hospital Regional Querétaro',
                'description': 'Construcción de hospital de especialidades de 120 camas, '
                               'incluyendo helipuerto y central de energía.',
                'statecode': 1,  # ACTIVE
                'accountid': accounts[2],
                'projecttype': 0,  # PUBLIC
                'biddingtype': 1,  # INVITED_BID
                'contractamount_notax': Decimal('450000000.00'),
                'contractamount_withtax': Decimal('522000000.00'),
                'durationmonths': 30,
                'startdate': date(2025, 3, 1),
                'contractenddate': date(2027, 8, 31),
                'expectedenddate': date(2027, 9, 30),
                'presentationdate': date(2024, 12, 10),
                'awarddate': date(2025, 1, 25),
                'advancepayment_notax': Decimal('135000000.00'),
                'advancepayment_withtax': Decimal('156600000.00'),
                'periodtype': 1,  # FORTNIGHTLY
            },
            {
                'name': 'Planta de Tratamiento de Aguas León',
                'description': 'Diseño y construcción de planta de tratamiento con capacidad '
                               'de 500 L/s para la zona industrial de León, Guanajuato.',
                'statecode': 0,  # DRAFT
                'accountid': accounts[3] if len(accounts) > 3 else accounts[0],
                'projecttype': 0,  # PUBLIC
                'biddingtype': 0,  # OPEN_BID
                'contractamount_notax': Decimal('89000000.00'),
                'contractamount_withtax': Decimal('103240000.00'),
                'durationmonths': 18,
                'startdate': date(2026, 1, 1),
                'contractenddate': date(2027, 6, 30),
                'expectedenddate': date(2027, 6, 30),
                'presentationdate': date(2025, 9, 1),
                'awarddate': None,
                'periodtype': 0,  # WEEKLY
            },
            {
                'name': 'Centro Comercial Paseo Interlomas',
                'description': 'Ampliación y remodelación del centro comercial, agregando '
                               'ala sur con 45 locales comerciales y food court.',
                'statecode': 3,  # COMPLETED
                'accountid': accounts[4] if len(accounts) > 4 else accounts[1],
                'projecttype': 1,  # PRIVATE
                'biddingtype': 2,  # DIRECT_AWARD
                'contractamount_notax': Decimal('72000000.00'),
                'contractamount_withtax': Decimal('83520000.00'),
                'durationmonths': 12,
                'startdate': date(2024, 3, 1),
                'contractenddate': date(2025, 2, 28),
                'expectedenddate': date(2025, 2, 28),
                'presentationdate': date(2024, 1, 10),
                'awarddate': date(2024, 2, 1),
                'periodtype': 1,  # FORTNIGHTLY
            },
        ]

        created = []
        for i, data in enumerate(projects_data):
            number = f'PRY-2025-{i + 10:03d}'
            p = ConstructionProject.objects.create(
                projectnumber=number,
                ownerid=owner,
                **data,
            )
            created.append(p)
            self.stdout.write(f'  Created project: {p.name} ({p.projectnumber})')

        return created

    # ── Zones, Team Members, Suppliers ────────────────────────

    def _create_zones_and_team(self, projects, owner, accounts):
        zone_sets = [
            # Autopista
            [('Monterrey', 'MTY', 'Tramo zona metropolitana Monterrey'),
             ('Saltillo', 'SAL', 'Tramo zona metropolitana Saltillo'),
             ('Intermedio', 'INT', 'Tramo intermedio entre ciudades')],
            # Torre Corporativa
            [('Cimentación', 'CIM', 'Cimentación profunda y sótanos'),
             ('Estructura', 'EST', 'Estructura de concreto y acero'),
             ('Acabados', 'ACA', 'Acabados interiores y exteriores')],
            # Hospital
            [('Edificio Principal', 'EPR', 'Edificio principal de hospitalización'),
             ('Urgencias', 'URG', 'Área de urgencias y trauma'),
             ('Servicios', 'SRV', 'Central de energía y servicios')],
            # Planta de Tratamiento
            [('Tratamiento', 'TRA', 'Área de tratamiento primario y secundario'),
             ('Bombeo', 'BOM', 'Estación de bombeo')],
            # Centro Comercial
            [('Ala Sur', 'SUR', 'Nueva ala sur'),
             ('Food Court', 'FDC', 'Zona de food court')],
        ]

        team_roles = [
            ('Ing. Roberto Martínez', 'ProjectManager', '8181234567', 'roberto.martinez@obra.mx'),
            ('Lic. Patricia Sánchez', 'AdminAssistant', '8181234568', 'patricia.sanchez@obra.mx'),
            ('Ing. Miguel Ángel Torres', 'ProductionManager', '8181234569', 'miguel.torres@obra.mx'),
            ('Ing. Laura Vega', 'SiteEngineer', '8181234570', 'laura.vega@obra.mx'),
            ('Ing. Carlos Medina', 'SafetyOfficer', '8181234571', 'carlos.medina@obra.mx'),
        ]

        supplier_data = [
            ('CEMEX S.A.B.', 'CEM030101AB1', 'Cemex S.A.B. de C.V.'),
            ('Aceros Torreón', 'ATO100515KL3', 'Aceros de Torreón S.A. de C.V.'),
            ('Maquinaria del Norte', 'MNO080320PQ7', 'Maquinaria del Norte S. de R.L.'),
            ('Eléctricos Industriales', 'EIN951210RS5', 'Eléctricos Industriales S.A.'),
        ]

        for i, project in enumerate(projects):
            # Zones
            for sort, (name, prefix, desc) in enumerate(zone_sets[i]):
                ProjectZone.objects.create(
                    projectid=project,
                    name=name,
                    prefix=prefix,
                    description=desc,
                    sortorder=sort,
                )

            # Team members
            for name, role, phone, email in team_roles[:min(4, 5)]:
                ProjectTeamMember.objects.create(
                    projectid=project,
                    name=name,
                    role=role,
                    phone=phone,
                    email=email,
                )

            # Suppliers (use existing accounts)
            for j, (sname, rfc, bname) in enumerate(supplier_data[:min(3, len(accounts))]):
                acct = accounts[j % len(accounts)]
                try:
                    ProjectSupplier.objects.create(
                        projectid=project,
                        accountid=acct,
                        suppliernumber=j + 1,
                        rfc=rfc + str(i),  # Make unique per project
                        businessname=bname,
                    )
                except Exception:
                    pass  # Skip if duplicate RFC

        self.stdout.write(f'  Created zones, team members, and suppliers for {len(projects)} projects')

    # ── Categories & Imputation Codes ─────────────────────────

    def _create_categories_and_codes(self, projects):
        direct_categories = [
            ('P1', 'Preliminares'),
            ('P2', 'Cimentación'),
            ('P3', 'Estructura'),
            ('P4', 'Albañilería'),
            ('P5', 'Instalación Eléctrica'),
            ('P6', 'Instalación Hidráulica'),
            ('P7', 'Instalación Sanitaria'),
            ('P8', 'Acabados'),
            ('P9', 'Carpintería'),
            ('P10', 'Herrería'),
        ]

        indirect_categories = [
            ('C1', 'Personal Técnico y Administrativo'),
            ('C2', 'Equipo de Oficina y Campamento'),
            ('C3', 'Vehículos y Transporte'),
            ('C4', 'Gastos de Oficina'),
            ('C5', 'Seguros y Fianzas'),
            ('C6', 'Servicios Profesionales'),
            ('C7', 'Seguridad e Higiene'),
            ('C8', 'Varios'),
        ]

        for project in projects:
            zones = list(ProjectZone.objects.filter(projectid=project))

            # Direct categories
            for sort, (code, name) in enumerate(direct_categories):
                cat = CostCategory.objects.create(
                    projectid=project,
                    costtype=0,  # DIRECT
                    code=code,
                    name=name,
                    sortorder=sort,
                )
                # Create 2-3 imputation codes per direct category per zone
                seq = 1
                for zone in zones:
                    for k in range(random.randint(1, 3)):
                        budget = Decimal(random.randint(50000, 5000000))
                        ImputationCode.objects.create(
                            projectid=project,
                            categoryid=cat,
                            zoneid=zone,
                            costtype=0,
                            code=f'{zone.prefix}-{code}-{seq}',
                            sequencenumber=seq,
                            name=f'{name} - {zone.name} #{seq}',
                            totalbudget=budget,
                            remainingbudget=budget,
                        )
                        seq += 1

            # Indirect categories
            for sort, (code, name) in enumerate(indirect_categories):
                cat = CostCategory.objects.create(
                    projectid=project,
                    costtype=1,  # INDIRECT
                    code=code,
                    name=name,
                    sortorder=sort + len(direct_categories),
                )
                # Create 2-4 imputation codes per indirect category (no zone)
                for seq in range(1, random.randint(2, 5)):
                    budget = Decimal(random.randint(20000, 1000000))
                    ImputationCode.objects.create(
                        projectid=project,
                        categoryid=cat,
                        zoneid=None,
                        costtype=1,
                        code=f'{code}-{seq}',
                        sequencenumber=seq,
                        name=f'{name} #{seq}',
                        totalbudget=budget,
                        remainingbudget=budget,
                    )

        self.stdout.write(f'  Created categories and imputation codes for {len(projects)} projects')

    # ── Periods ───────────────────────────────────────────────

    def _create_periods(self, projects):
        month_labels = {
            1: 'ENE', 2: 'FEB', 3: 'MAR', 4: 'ABR', 5: 'MAY', 6: 'JUN',
            7: 'JUL', 8: 'AGO', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DIC',
        }

        for project in projects:
            if not project.startdate:
                continue

            start = project.startdate
            period_type = project.periodtype
            months = min(project.durationmonths, 12)  # Limit for seed data
            sort = 0

            current = start
            for m in range(months):
                month_num = ((start.month - 1 + m) % 12) + 1
                year = start.year + ((start.month - 1 + m) // 12)
                label_prefix = month_labels[month_num]

                if period_type == 1:  # FORTNIGHTLY
                    # S1: days 1-15, S2: days 16-end
                    s1_start = date(year, month_num, 1)
                    s1_end = date(year, month_num, 15)
                    s2_start = date(year, month_num, 16)
                    if month_num == 12:
                        s2_end = date(year, 12, 31)
                    else:
                        s2_end = date(year, month_num + 1, 1) - timedelta(days=1)

                    ImputationPeriod.objects.create(
                        projectid=project, periodtype=period_type,
                        year=year, month=month_num, periodnumber=1,
                        label=f'{label_prefix}-S1', startdate=s1_start,
                        enddate=s1_end, sortorder=sort,
                    )
                    sort += 1
                    ImputationPeriod.objects.create(
                        projectid=project, periodtype=period_type,
                        year=year, month=month_num, periodnumber=2,
                        label=f'{label_prefix}-S2', startdate=s2_start,
                        enddate=s2_end, sortorder=sort,
                    )
                    sort += 1
                else:  # WEEKLY
                    # Create 4 weeks per month
                    for w in range(1, 5):
                        w_start = date(year, month_num, 1) + timedelta(days=(w - 1) * 7)
                        w_end = w_start + timedelta(days=6)
                        if month_num == 12:
                            month_end = date(year, 12, 31)
                        else:
                            month_end = date(year, month_num + 1, 1) - timedelta(days=1)
                        if w_end > month_end:
                            w_end = month_end

                        ImputationPeriod.objects.create(
                            projectid=project, periodtype=period_type,
                            year=year, month=month_num, periodnumber=w,
                            label=f'{label_prefix}-S{w}', startdate=w_start,
                            enddate=w_end, sortorder=sort,
                        )
                        sort += 1

        self.stdout.write(f'  Created periods for {len(projects)} projects')

    # ── Expenses ──────────────────────────────────────────────

    def _create_expenses(self, projects, owner):
        supplier_names = [
            ('CEM030101AB1', 'Cemex S.A.B. de C.V.'),
            ('ATO100515KL3', 'Aceros de Torreón S.A. de C.V.'),
            ('MNO080320PQ7', 'Maquinaria del Norte S. de R.L.'),
            ('EIN951210RS5', 'Eléctricos Industriales S.A.'),
            ('FER120401HG2', 'Ferretería Industrial del Bajío'),
        ]

        for project in projects:
            periods = list(ImputationPeriod.objects.filter(projectid=project)[:8])
            codes = list(ImputationCode.objects.filter(projectid=project)[:10])

            if not periods:
                continue

            # Create 8-15 expenses per project
            num_expenses = random.randint(8, 15)
            for e in range(num_expenses):
                period = random.choice(periods)
                doc_type = random.choice([0, 0, 0, 2, 3])  # Mostly invoices
                supplier = random.choice(supplier_names)
                subtotal = Decimal(random.randint(5000, 500000))
                tax = (subtotal * Decimal('0.16')).quantize(Decimal('0.01'))
                net = subtotal + tax

                # Some classified, some not
                imp_code = None
                class_status = 1  # PENDING
                if codes and random.random() > 0.3:
                    imp_code = random.choice(codes)
                    class_status = 2  # CLASSIFIED

                expense = ProjectExpense.objects.create(
                    projectid=project,
                    periodid=period,
                    imputationcodeid=imp_code,
                    classificationstatus=class_status,
                    documenttype=doc_type,
                    supplierrfc=supplier[0],
                    suppliername=supplier[1],
                    invoiceuuid=str(uuid.uuid4()) if doc_type == 0 else None,
                    invoicefolio=f'F-{random.randint(1000, 9999)}' if doc_type == 0 else None,
                    invoicedate=period.startdate if doc_type == 0 else None,
                    subtotal=subtotal,
                    taxamount=tax,
                    netamount=net,
                    currency=0,  # MXN
                    paymentstatus=random.choice([0, 0, 1]),
                    verificationstatus=random.choice([0, 0, 1]),
                    statecode=0,  # ACTIVE
                    ownerid=owner,
                )

                # Create 1-3 lines per expense
                num_lines = random.randint(1, 3)
                line_descriptions = [
                    'Suministro de material', 'Mano de obra', 'Renta de equipo',
                    'Transporte', 'Consumibles', 'Herramienta menor',
                    'Concreto premezclado', 'Acero de refuerzo', 'Cimbra',
                    'Instalación eléctrica', 'Tubería PVC', 'Arena y grava',
                ]
                remaining = subtotal
                for ln in range(num_lines):
                    if ln == num_lines - 1:
                        line_sub = remaining
                    else:
                        line_sub = (subtotal / num_lines).quantize(Decimal('0.01'))
                        remaining -= line_sub

                    line_tax = (line_sub * Decimal('0.16')).quantize(Decimal('0.01'))
                    qty = Decimal(random.randint(1, 50))
                    unit_price = (line_sub / qty).quantize(Decimal('0.0001'))

                    ExpenseLine.objects.create(
                        expenseid=expense,
                        linenumber=ln + 1,
                        description=random.choice(line_descriptions),
                        quantity=qty,
                        unitprice=unit_price,
                        subtotal=line_sub,
                        taxamount=line_tax,
                        netamount=line_sub + line_tax,
                    )

        self.stdout.write(f'  Created expenses and lines for {len(projects)} projects')

    # ── Estimates ─────────────────────────────────────────────

    def _create_estimates(self, projects):
        for project in projects:
            periods = list(ImputationPeriod.objects.filter(projectid=project)[:6])
            if not periods:
                continue

            contract = project.contractamount_notax or Decimal('100000000')
            num_estimates = min(len(periods), random.randint(2, 5))

            for est_num in range(1, num_estimates + 1):
                period = periods[est_num - 1] if est_num <= len(periods) else periods[0]
                estimated = (contract * Decimal(random.randint(5, 15)) / Decimal('100')).quantize(Decimal('0.01'))
                advance_amort = (estimated * Decimal('0.30')).quantize(Decimal('0.01'))
                guarantee = (estimated * Decimal('0.05')).quantize(Decimal('0.01'))
                total_ded = advance_amort + guarantee
                amount_notax = estimated - total_ded
                tax_amt = (amount_notax * Decimal('0.16')).quantize(Decimal('0.01'))
                total_inv = amount_notax + tax_amt
                collectable = total_inv

                paid = random.random() > 0.5 and est_num < num_estimates
                ClientEstimate.objects.create(
                    projectid=project,
                    periodid=period,
                    estimatenumber=est_num,
                    invoicenumber=f'EST-{project.projectnumber}-{est_num:02d}' if paid else None,
                    invoicedate=period.startdate if paid else None,
                    estimationperiod=period.label,
                    estimatetype=0,  # ESTIMATE
                    estimatedamount=estimated,
                    advanceamortization=advance_amort,
                    guaranteefund=guarantee,
                    totaldeductions=total_ded,
                    amountnotax=amount_notax,
                    taxamount=tax_amt,
                    totalinvoiced=total_inv if paid else Decimal('0'),
                    collectableamount=collectable,
                    paymentstatus=1 if paid else 0,
                    paymentdate=period.enddate if paid else None,
                    amountpaid=collectable if paid else Decimal('0'),
                    statecode=1 if paid else 0,  # PAID or ACTIVE
                )

        self.stdout.write(f'  Created estimates for {len(projects)} projects')
