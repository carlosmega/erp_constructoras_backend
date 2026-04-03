"""Seed machinery module with realistic construction equipment data."""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.machinery.models import (
    EquipmentCategory,
    EquipmentBrand,
    EquipmentModel,
    Equipment,
    EquipmentInsurance,
    EquipmentStateCode,
    OwnershipTypeCode,
    OperationalStatusCode,
    InsuranceTypeCode,
    InsuranceStateCode,
)
from apps.users.models import SystemUser


CATEGORIES = [
    {'code': 'EXC', 'name': 'Excavadora', 'description': 'Excavadoras hidráulicas de orugas y ruedas', 'fuel': Decimal('25.00')},
    {'code': 'CFR', 'name': 'Cargador Frontal', 'description': 'Cargadores frontales sobre ruedas', 'fuel': Decimal('20.00')},
    {'code': 'RET', 'name': 'Retroexcavadora', 'description': 'Retroexcavadoras tipo backhoe', 'fuel': Decimal('12.00')},
    {'code': 'BUL', 'name': 'Bulldozer', 'description': 'Tractores de orugas con hoja topadora', 'fuel': Decimal('30.00')},
    {'code': 'MOT', 'name': 'Motoniveladora', 'description': 'Motoniveladoras para conformación de terreno', 'fuel': Decimal('18.00')},
    {'code': 'ROD', 'name': 'Rodillo Compactador', 'description': 'Rodillos vibratorios y neumáticos', 'fuel': Decimal('15.00')},
    {'code': 'CAM', 'name': 'Camión de Volteo', 'description': 'Camiones articulados y rígidos de volteo', 'fuel': Decimal('22.00')},
    {'code': 'GRU', 'name': 'Grúa', 'description': 'Grúas móviles, torre y sobre orugas', 'fuel': Decimal('28.00')},
    {'code': 'PIP', 'name': 'Pipa de Agua', 'description': 'Camiones cisterna para riego y abastecimiento', 'fuel': Decimal('18.00')},
    {'code': 'MZC', 'name': 'Mezcladora de Concreto', 'description': 'Mezcladoras y ollas revolvedoras', 'fuel': Decimal('16.00')},
    {'code': 'PER', 'name': 'Perforadora', 'description': 'Equipos de perforación para minería y cimentación', 'fuel': Decimal('35.00')},
    {'code': 'PLC', 'name': 'Planta de Concreto', 'description': 'Plantas dosificadoras de concreto', 'fuel': Decimal('10.00')},
]

BRANDS = [
    {'code': 'CAT', 'name': 'Caterpillar', 'country': 'Estados Unidos'},
    {'code': 'KOM', 'name': 'Komatsu', 'country': 'Japón'},
    {'code': 'VOL', 'name': 'Volvo', 'country': 'Suecia'},
    {'code': 'JDE', 'name': 'John Deere', 'country': 'Estados Unidos'},
    {'code': 'CAS', 'name': 'Case', 'country': 'Estados Unidos'},
    {'code': 'LBT', 'name': 'Liebherr', 'country': 'Suiza'},
    {'code': 'HIT', 'name': 'Hitachi', 'country': 'Japón'},
    {'code': 'DOO', 'name': 'Doosan', 'country': 'Corea del Sur'},
    {'code': 'KNR', 'name': 'Kenworth', 'country': 'Estados Unidos'},
    {'code': 'FLR', 'name': 'Freightliner', 'country': 'Estados Unidos'},
]

# (brand_code, model_name, category_code)
MODELS = [
    # Caterpillar
    ('CAT', '320F', 'EXC'), ('CAT', '336F', 'EXC'), ('CAT', '349F', 'EXC'),
    ('CAT', '950GC', 'CFR'), ('CAT', '966M', 'CFR'),
    ('CAT', '420F2', 'RET'),
    ('CAT', 'D6T', 'BUL'), ('CAT', 'D8T', 'BUL'),
    ('CAT', '140M', 'MOT'), ('CAT', '160M', 'MOT'),
    ('CAT', 'CS56B', 'ROD'), ('CAT', 'CP56B', 'ROD'),
    ('CAT', '745', 'CAM'),
    # Komatsu
    ('KOM', 'PC200-8', 'EXC'), ('KOM', 'PC300-8', 'EXC'), ('KOM', 'PC490-11', 'EXC'),
    ('KOM', 'WA380-8', 'CFR'), ('KOM', 'WA470-8', 'CFR'),
    ('KOM', 'D65PX-18', 'BUL'),
    ('KOM', 'GD655-7', 'MOT'),
    ('KOM', 'HM400-5', 'CAM'),
    # Volvo
    ('VOL', 'EC210D', 'EXC'), ('VOL', 'EC350E', 'EXC'),
    ('VOL', 'L120H', 'CFR'), ('VOL', 'L180H', 'CFR'),
    ('VOL', 'A30G', 'CAM'), ('VOL', 'A40G', 'CAM'),
    ('VOL', 'SD115B', 'ROD'),
    # John Deere
    ('JDE', '210G', 'EXC'), ('JDE', '350G', 'EXC'),
    ('JDE', '310SL', 'RET'), ('JDE', '410L', 'RET'),
    ('JDE', '644K', 'CFR'),
    ('JDE', '850K', 'BUL'),
    ('JDE', '672G', 'MOT'),
    # Case
    ('CAS', 'CX210D', 'EXC'), ('CAS', 'CX350D', 'EXC'),
    ('CAS', '580SN', 'RET'), ('CAS', '590SN', 'RET'),
    ('CAS', '821G', 'CFR'),
    # Liebherr
    ('LBT', 'R920', 'EXC'), ('LBT', 'R945', 'EXC'),
    ('LBT', 'LTM 1100-5.2', 'GRU'), ('LBT', 'LTM 1300-6.2', 'GRU'),
    ('LBT', 'PR736', 'BUL'),
    # Hitachi
    ('HIT', 'ZX210-6', 'EXC'), ('HIT', 'ZX350-6', 'EXC'),
    ('HIT', 'ZW220-6', 'CFR'),
    # Doosan
    ('DOO', 'DX225LC-5', 'EXC'), ('DOO', 'DX340LC-5', 'EXC'),
    ('DOO', 'DL250-5', 'CFR'),
    # Kenworth
    ('KNR', 'T800', 'CAM'), ('KNR', 'T880', 'CAM'),
    # Freightliner
    ('FLR', 'M2 106', 'CAM'), ('FLR', '122SD', 'CAM'),
]

# (brand_code, model_name, ownership, status, year, serial, hours, cost, purchasedate)
EQUIPMENT_DATA = [
    ('CAT', '320F', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2022, 'CAT320F-2022-MX001', 3500, Decimal('2850000'), date(2022, 3, 15)),
    ('CAT', '336F', OwnershipTypeCode.PROPIO, OperationalStatusCode.ASIGNADO_A_PROYECTO, 2021, 'CAT336F-2021-MX002', 5200, Decimal('4200000'), date(2021, 6, 20)),
    ('CAT', '950GC', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2023, 'CAT950GC-2023-MX003', 1800, Decimal('3100000'), date(2023, 1, 10)),
    ('CAT', 'D6T', OwnershipTypeCode.PROPIO, OperationalStatusCode.ASIGNADO_A_PROYECTO, 2020, 'CATD6T-2020-MX004', 7800, Decimal('5500000'), date(2020, 9, 5)),
    ('CAT', '140M', OwnershipTypeCode.PROPIO, OperationalStatusCode.EN_MANTENIMIENTO, 2019, 'CAT140M-2019-MX005', 9200, Decimal('3800000'), date(2019, 4, 22)),
    ('KOM', 'PC200-8', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2023, 'KOMPC200-2023-MX006', 1200, Decimal('2600000'), date(2023, 7, 1)),
    ('KOM', 'WA380-8', OwnershipTypeCode.PROPIO, OperationalStatusCode.ASIGNADO_A_PROYECTO, 2022, 'KOMWA380-2022-MX007', 3100, Decimal('3400000'), date(2022, 11, 15)),
    ('KOM', 'HM400-5', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2021, 'KOMHM400-2021-MX008', 4500, Decimal('6200000'), date(2021, 2, 28)),
    ('VOL', 'EC350E', OwnershipTypeCode.RENTADO_DE_TERCERO, OperationalStatusCode.ASIGNADO_A_PROYECTO, 2024, 'VOLEC350E-2024-MX009', 450, None, None),
    ('VOL', 'A30G', OwnershipTypeCode.RENTADO_DE_TERCERO, OperationalStatusCode.DISPONIBLE, 2023, 'VOLA30G-2023-MX010', 920, None, None),
    ('JDE', '310SL', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2022, 'JDE310SL-2022-MX011', 2800, Decimal('1900000'), date(2022, 5, 10)),
    ('JDE', '850K', OwnershipTypeCode.PROPIO, OperationalStatusCode.FUERA_DE_SERVICIO, 2018, 'JDE850K-2018-MX012', 12500, Decimal('4800000'), date(2018, 8, 20)),
    ('CAS', '580SN', OwnershipTypeCode.RENTADO_DE_TERCERO, OperationalStatusCode.ASIGNADO_A_PROYECTO, 2024, 'CAS580SN-2024-MX013', 380, None, None),
    ('LBT', 'LTM 1100-5.2', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2021, 'LBTLTM1100-2021-MX014', 2100, Decimal('12500000'), date(2021, 12, 1)),
    ('HIT', 'ZX210-6', OwnershipTypeCode.PROPIO, OperationalStatusCode.ASIGNADO_A_PROYECTO, 2023, 'HITZX210-2023-MX015', 1600, Decimal('2700000'), date(2023, 3, 18)),
    ('DOO', 'DX225LC-5', OwnershipTypeCode.RENTADO_DE_TERCERO, OperationalStatusCode.DISPONIBLE, 2024, 'DOODX225-2024-MX016', 200, None, None),
    ('KNR', 'T800', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2022, 'KNRT800-2022-MX017', 85000, Decimal('2200000'), date(2022, 2, 14)),
    ('FLR', '122SD', OwnershipTypeCode.PROPIO, OperationalStatusCode.ASIGNADO_A_PROYECTO, 2023, 'FLR122SD-2023-MX018', 42000, Decimal('2800000'), date(2023, 6, 30)),
    ('CAT', 'CS56B', OwnershipTypeCode.PROPIO, OperationalStatusCode.DISPONIBLE, 2022, 'CATCS56B-2022-MX019', 2400, Decimal('1800000'), date(2022, 9, 12)),
    ('VOL', 'L120H', OwnershipTypeCode.PROPIO, OperationalStatusCode.RENTADO_A_CLIENTE, 2021, 'VOLL120H-2021-MX020', 4800, Decimal('3600000'), date(2021, 4, 5)),
]

INSURANCE_DATA = [
    # (equipment_index, type, company, policy, start, expiry, annual, monthly, insured, state)
    (0, InsuranceTypeCode.TODO_RIESGO, 'Seguros Atlas', 'POL-2026-001', date(2026, 1, 1), date(2026, 12, 31), Decimal('85000'), Decimal('7083.33'), Decimal('2850000'), InsuranceStateCode.VIGENTE),
    (0, InsuranceTypeCode.RESPONSABILIDAD_CIVIL, 'GNP Seguros', 'POL-2025-045', date(2025, 1, 1), date(2025, 12, 31), Decimal('35000'), Decimal('2916.67'), Decimal('5000000'), InsuranceStateCode.VENCIDA),
    (1, InsuranceTypeCode.TODO_RIESGO, 'Seguros Monterrey', 'POL-2026-012', date(2026, 1, 1), date(2026, 12, 31), Decimal('120000'), Decimal('10000.00'), Decimal('4200000'), InsuranceStateCode.VIGENTE),
    (3, InsuranceTypeCode.DANO_FISICO, 'Zurich Seguros', 'POL-2026-023', date(2026, 3, 1), date(2027, 2, 28), Decimal('95000'), Decimal('7916.67'), Decimal('5500000'), InsuranceStateCode.VIGENTE),
    (7, InsuranceTypeCode.TODO_RIESGO, 'AXA Seguros', 'POL-2026-034', date(2026, 1, 15), date(2027, 1, 14), Decimal('150000'), Decimal('12500.00'), Decimal('6200000'), InsuranceStateCode.VIGENTE),
    (13, InsuranceTypeCode.TODO_RIESGO, 'Chubb Seguros', 'POL-2026-056', date(2026, 1, 1), date(2026, 12, 31), Decimal('280000'), Decimal('23333.33'), Decimal('12500000'), InsuranceStateCode.VIGENTE),
    (13, InsuranceTypeCode.TRANSPORTE, 'Mapfre', 'POL-2026-057', date(2026, 2, 1), date(2027, 1, 31), Decimal('45000'), Decimal('3750.00'), Decimal('12500000'), InsuranceStateCode.VIGENTE),
    (14, InsuranceTypeCode.DANO_FISICO, 'Seguros Atlas', 'POL-2026-067', date(2026, 4, 1), date(2027, 3, 31), Decimal('72000'), Decimal('6000.00'), Decimal('2700000'), InsuranceStateCode.VIGENTE),
]


class Command(BaseCommand):
    help = 'Seed machinery module with realistic construction equipment data'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing machinery data before seeding')

    @transaction.atomic
    def handle(self, *args, **options):
        # Get admin user (System Administrator role or first user)
        from apps.users.models import SecurityRole
        admin_role = SecurityRole.objects.filter(name='System Administrator').first()
        admin_user = None
        if admin_role:
            admin_user = SystemUser.objects.filter(securityroleid=admin_role).first()
        if not admin_user:
            admin_user = SystemUser.objects.first()
        if not admin_user:
            self.stderr.write('No users found. Please create a user first.')
            return

        if options['clear']:
            self.stdout.write('Clearing existing machinery data...')
            EquipmentInsurance.objects.all().delete()
            Equipment.objects.all().delete()
            EquipmentModel.objects.all().delete()
            EquipmentBrand.objects.all().delete()
            EquipmentCategory.objects.all().delete()

        # 1. Seed categories
        cat_map = {}
        for cat_data in CATEGORIES:
            cat, created = EquipmentCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'estimatedfuelconsumption': cat_data['fuel'],
                    'statecode': EquipmentStateCode.ACTIVE,
                    'ownerid': admin_user,
                    'createdby': admin_user,
                    'modifiedby': admin_user,
                }
            )
            cat_map[cat_data['code']] = cat
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Category {cat_data["code"]} - {cat_data["name"]}: {status}')

        # 2. Seed brands
        brand_map = {}
        for brand_data in BRANDS:
            brand, created = EquipmentBrand.objects.get_or_create(
                code=brand_data['code'],
                defaults={
                    'name': brand_data['name'],
                    'country': brand_data['country'],
                    'statecode': EquipmentStateCode.ACTIVE,
                    'ownerid': admin_user,
                    'createdby': admin_user,
                    'modifiedby': admin_user,
                }
            )
            brand_map[brand_data['code']] = brand
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Brand {brand_data["code"]} - {brand_data["name"]}: {status}')

        # 3. Seed models
        model_map = {}
        for brand_code, model_name, cat_code in MODELS:
            brand = brand_map[brand_code]
            category = cat_map.get(cat_code)
            eq_model, created = EquipmentModel.objects.get_or_create(
                brandid=brand,
                name=model_name,
                defaults={
                    'categoryid': category,
                    'statecode': EquipmentStateCode.ACTIVE,
                    'ownerid': admin_user,
                    'createdby': admin_user,
                    'modifiedby': admin_user,
                }
            )
            model_map[(brand_code, model_name)] = eq_model
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Model {brand_code} {model_name}: {status}')

        # 4. Seed equipment
        equipment_list = []
        seq = Equipment.objects.count()
        for brand_code, model_name, ownership, op_status, year, serial, hours, cost, pdate in EQUIPMENT_DATA:
            if Equipment.objects.filter(serialnumber=serial).exists():
                eq = Equipment.objects.get(serialnumber=serial)
                equipment_list.append(eq)
                self.stdout.write(f'  Equipment {eq.equipmentnumber}: exists')
                continue

            seq += 1
            brand = brand_map[brand_code]
            eq_model = model_map[(brand_code, model_name)]
            category = eq_model.categoryid or cat_map['EXC']

            eq = Equipment(
                equipmentnumber=f'MAQ-{seq:03d}',
                categoryid=category,
                ownershiptype=ownership,
                brandid=brand,
                modelid=eq_model,
                brand=brand.name,
                model=model_name,
                year=year,
                serialnumber=serial,
                currenthourmeter=Decimal(str(hours)),
                operationalstatus=op_status,
                acquisitioncost=cost,
                purchasedate=pdate,
                estimatedusefullifehours=20000 if cost else None,
                salvagevalue=Decimal(str(int(cost * Decimal('0.1')))) if cost else None,
                statecode=EquipmentStateCode.ACTIVE,
                ownerid=admin_user,
                createdby=admin_user,
                modifiedby=admin_user,
            )
            eq.save()
            equipment_list.append(eq)
            self.stdout.write(f'  Equipment {eq.equipmentnumber} ({brand.name} {model_name}): created')

        # 5. Seed insurance
        for eq_idx, ins_type, company, policy, start, expiry, annual, monthly, insured, state in INSURANCE_DATA:
            if eq_idx >= len(equipment_list):
                continue
            eq = equipment_list[eq_idx]
            if EquipmentInsurance.objects.filter(policynumber=policy).exists():
                self.stdout.write(f'  Insurance {policy}: exists')
                continue

            insurance = EquipmentInsurance(
                equipmentid=eq,
                insurancetype=ins_type,
                insurancecompany=company,
                policynumber=policy,
                startdate=start,
                expirydate=expiry,
                annualpremium=annual,
                monthlypremium=monthly,
                insuredamount=insured,
                statecode=state,
                createdby=admin_user,
                modifiedby=admin_user,
            )
            insurance.save()
            self.stdout.write(f'  Insurance {policy} ({company}): created')

        # 6. Seed justification reasons
        from apps.machinery.services import JustificationReasonService
        reasons_created = JustificationReasonService.seed_default_reasons(admin_user)
        self.stdout.write(
            f'  Justification reasons seeded: {len(reasons_created)} created'
        )

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed complete: {EquipmentCategory.objects.count()} categories, '
            f'{EquipmentBrand.objects.count()} brands, '
            f'{EquipmentModel.objects.count()} models, '
            f'{Equipment.objects.count()} equipment, '
            f'{EquipmentInsurance.objects.count()} insurance policies, '
            f'{len(reasons_created)} justification reasons created'
        ))
