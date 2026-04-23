"""Seed IndirectCostTemplate with standard C1-C8 defaults per project size.

Values are representative for Mexican construction projects (MXN).
Size 0 = Chica, 1 = Mediana, 2 = Grande.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.proyeccion.models import IndirectCostTemplate


# (categorycode, description, monthlycost, units, months, sortorder)
# Tuned so Chica ~5-7% / Mediana ~8-10% / Grande ~12-15% of a typical contract
TEMPLATES = {
    0: [  # Chica
        ('C1', 'Gerente de proyecto (parcial)',        35000,  0.5,  3, 1),
        ('C1', 'Administrativo oficina central',        18000,  0.3,  3, 2),
        ('C2', 'Residente de obra',                     25000,  1.0,  3, 1),
        ('C2', 'Cabo de obra',                          18000,  1.0,  3, 2),
        ('C2', 'Velador',                               12000,  1.0,  3, 3),
        ('C2', 'Renta de oficina en obra',               6000,  1.0,  3, 4),
        ('C3', 'Fianza de cumplimiento',                 8500,  1.0,  1, 1),
        ('C3', 'Seguro de responsabilidad civil',        6500,  1.0,  1, 2),
        ('C4', 'Imprevistos',                           15000,  1.0,  3, 1),
        ('C5', 'Financiamiento / intereses',            12000,  1.0,  3, 1),
        ('C6', 'Utilidad esperada',                     45000,  1.0,  3, 1),
        ('C7', 'Cargos adicionales (licencias, tramites)', 5000, 1.0,  3, 1),
        ('C8', 'Otros',                                  3000,  1.0,  3, 1),
    ],
    1: [  # Mediana
        ('C1', 'Gerente de proyecto',                   55000,  1.0,  6, 1),
        ('C1', 'Administrativo oficina central',        22000,  0.5,  6, 2),
        ('C1', 'Contador / finanzas (parcial)',         25000,  0.3,  6, 3),
        ('C2', 'Superintendente de obra',               45000,  1.0,  6, 1),
        ('C2', 'Residente de obra',                     28000,  1.0,  6, 2),
        ('C2', 'Topografo y cadenero',                  22000,  1.0,  6, 3),
        ('C2', 'Cabo de obra (2)',                      18000,  2.0,  6, 4),
        ('C2', 'Velador (2)',                           12000,  2.0,  6, 5),
        ('C2', 'Renta de oficina y almacen en obra',    15000,  1.0,  6, 6),
        ('C2', 'Vehiculos de supervision',              18000,  1.0,  6, 7),
        ('C3', 'Fianza de cumplimiento',                25000,  1.0,  1, 1),
        ('C3', 'Fianza de vicios ocultos',              12000,  1.0,  1, 2),
        ('C3', 'Seguro de responsabilidad civil',       18000,  1.0,  1, 3),
        ('C3', 'Seguro de obra civil',                  12000,  1.0,  1, 4),
        ('C4', 'Imprevistos',                           45000,  1.0,  6, 1),
        ('C5', 'Financiamiento / intereses',            35000,  1.0,  6, 1),
        ('C6', 'Utilidad esperada',                    180000,  1.0,  6, 1),
        ('C7', 'Cargos adicionales (licencias, permisos)', 12000, 1.0, 6, 1),
        ('C8', 'Capacitacion y otros',                   6500,  1.0,  6, 1),
    ],
    2: [  # Grande
        ('C1', 'Director de proyecto',                  95000,  1.0, 12, 1),
        ('C1', 'Gerente de proyecto',                   65000,  1.0, 12, 2),
        ('C1', 'Administrativo oficina central',        22000,  1.0, 12, 3),
        ('C1', 'Contador / finanzas',                   35000,  1.0, 12, 4),
        ('C1', 'Recursos humanos (parcial)',            28000,  0.5, 12, 5),
        ('C2', 'Superintendente general',               65000,  1.0, 12, 1),
        ('C2', 'Superintendentes de frente (3)',        45000,  3.0, 12, 2),
        ('C2', 'Residentes de obra (4)',                28000,  4.0, 12, 3),
        ('C2', 'Topografos y cadeneros (2 cuadrillas)', 22000,  4.0, 12, 4),
        ('C2', 'Jefe de calidad',                       35000,  1.0, 12, 5),
        ('C2', 'Laboratorio en obra',                   28000,  1.0, 12, 6),
        ('C2', 'Seguridad e higiene',                   25000,  1.0, 12, 7),
        ('C2', 'Cabos de obra (5)',                     18000,  5.0, 12, 8),
        ('C2', 'Veladores (4)',                         12000,  4.0, 12, 9),
        ('C2', 'Campamento y comedor',                  45000,  1.0, 12, 10),
        ('C2', 'Renta de oficinas y almacenes',         28000,  1.0, 12, 11),
        ('C2', 'Vehiculos de supervision (4)',          18000,  4.0, 12, 12),
        ('C3', 'Fianza de cumplimiento',               180000,  1.0,  1, 1),
        ('C3', 'Fianza de vicios ocultos',              90000,  1.0,  1, 2),
        ('C3', 'Fianza de anticipo',                    85000,  1.0,  1, 3),
        ('C3', 'Seguro de responsabilidad civil',       65000,  1.0,  1, 4),
        ('C3', 'Seguro de obra civil',                  45000,  1.0,  1, 5),
        ('C3', 'Seguro de equipo y maquinaria',         35000,  1.0,  1, 6),
        ('C4', 'Imprevistos',                          250000,  1.0, 12, 1),
        ('C5', 'Financiamiento / intereses',           180000,  1.0, 12, 1),
        ('C5', 'Linea de credito revolvente',           95000,  1.0, 12, 2),
        ('C6', 'Utilidad esperada',                    850000,  1.0, 12, 1),
        ('C7', 'Licencias, permisos y tramites',        35000,  1.0, 12, 1),
        ('C7', 'Estudios complementarios',              28000,  1.0, 12, 2),
        ('C8', 'Capacitacion',                          12000,  1.0, 12, 1),
        ('C8', 'Servicios generales (limpieza, basura)',15000,  1.0, 12, 2),
        ('C8', 'Otros',                                 10000,  1.0, 12, 3),
    ],
}

SIZE_LABELS = {0: 'Chica', 1: 'Mediana', 2: 'Grande'}


class Command(BaseCommand):
    help = 'Seed IndirectCostTemplate with default values for Small/Medium/Large projects'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Delete existing templates first')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            count = IndirectCostTemplate.objects.count()
            IndirectCostTemplate.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {count} existing templates'))

        total_created = 0
        for size, rows in TEMPLATES.items():
            label = SIZE_LABELS[size]
            created_for_size = 0
            for cat, desc, monthly, units, months, sort_order in rows:
                obj, created = IndirectCostTemplate.objects.get_or_create(
                    projectsize=size,
                    categorycode=cat,
                    description=desc,
                    defaults={
                        'name': f'{label} - {desc}',
                        'monthlycost': Decimal(str(monthly)),
                        'units': Decimal(str(units)),
                        'months': Decimal(str(months)),
                        'sortorder': sort_order,
                    },
                )
                if created:
                    created_for_size += 1
                    total_created += 1
            self.stdout.write(f'  {label}: {created_for_size} new (of {len(rows)} total)')

        self.stdout.write(self.style.SUCCESS(f'Created {total_created} templates'))
