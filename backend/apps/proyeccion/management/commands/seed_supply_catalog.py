"""Seed SupplyCatalogItem with realistic Mexican construction supplies."""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.proyeccion.models import SupplyCatalogItem, SupplyTypeCode


# (description, unit, price_min, price_max)
MATERIALS = [
    ('Cemento Portland CPC 30R saco 50 kg', 'saco', 220, 280),
    ('Cemento Portland CPC 40 saco 50 kg', 'saco', 240, 310),
    ('Cal hidratada saco 25 kg', 'saco', 95, 130),
    ('Arena de rio cribada', 'm3', 320, 420),
    ('Grava 3/4 triturada', 'm3', 380, 480),
    ('Grava 1/2 triturada', 'm3', 390, 490),
    ('Tepetate', 'm3', 180, 240),
    ('Tabique rojo recocido 6x12x24', 'pza', 4.5, 6.5),
    ('Tabicon de concreto 12x14x28', 'pza', 7, 10),
    ('Block hueco de concreto 15x20x40', 'pza', 13, 18),
    ('Block ligero 12x20x40', 'pza', 14, 19),
    ('Varilla corrugada #3 (3/8\") 12 m', 'pza', 145, 185),
    ('Varilla corrugada #4 (1/2\") 12 m', 'pza', 245, 310),
    ('Varilla corrugada #5 (5/8\") 12 m', 'pza', 380, 460),
    ('Varilla corrugada #6 (3/4\") 12 m', 'pza', 540, 660),
    ('Alambre recocido cal. 18 kg', 'kg', 32, 45),
    ('Alambron 1/4 kg', 'kg', 28, 40),
    ('Clavo de acero 2.5\" kg', 'kg', 38, 52),
    ('Concreto premezclado f\'c=200 kg/cm2', 'm3', 2400, 2800),
    ('Concreto premezclado f\'c=250 kg/cm2', 'm3', 2600, 3050),
    ('Concreto premezclado f\'c=300 kg/cm2', 'm3', 2850, 3300),
    ('Mortero cemento-arena 1:5', 'm3', 1850, 2200),
    ('Yeso saco 40 kg', 'saco', 110, 150),
    ('Pintura vinilica blanca cubeta 19 L', 'cubeta', 980, 1450),
    ('Esmalte alquidalico negro 1 L', 'lt', 145, 195),
    ('Impermeabilizante acrilico cubeta 19 L', 'cubeta', 1400, 1900),
    ('PVC sanitario 4\" tubo 6 m', 'pza', 280, 360),
    ('PVC hidraulico 1/2\" tubo 6 m', 'pza', 95, 130),
    ('Cable THW 12 AWG metro', 'm', 24, 34),
    ('Cable THW 10 AWG metro', 'm', 35, 48),
    ('Tubo conduit PVC 3/4\" 3 m', 'pza', 38, 55),
    ('Apagador sencillo', 'pza', 28, 45),
    ('Contacto duplex polarizado', 'pza', 32, 55),
    ('Loseta ceramica 30x30 piso', 'm2', 150, 240),
    ('Azulejo bano 20x30', 'm2', 180, 280),
    ('Adhesivo para piso saco 20 kg', 'saco', 165, 230),
    ('Boquilla saco 5 kg', 'saco', 75, 110),
    ('Acero estructural A36 perfil IR', 'kg', 28, 38),
    ('Lamina galvanizada cal 26 acanalada', 'm2', 195, 260),
    ('Madera de pino 1\"x4\" pie tablar', 'pt', 18, 28),
]

LABOR = [
    ('Oficial albanil', 'jor', 650, 850),
    ('Ayudante general', 'jor', 450, 580),
    ('Maestro de obra', 'jor', 950, 1300),
    ('Cabo de obra', 'jor', 800, 1050),
    ('Oficial fierrero', 'jor', 700, 900),
    ('Oficial carpintero', 'jor', 700, 920),
    ('Oficial electricista', 'jor', 750, 980),
    ('Oficial plomero', 'jor', 720, 950),
    ('Oficial pintor', 'jor', 650, 850),
    ('Soldador certificado', 'jor', 1100, 1500),
    ('Operador de equipo pesado', 'jor', 950, 1300),
    ('Topografo', 'jor', 1200, 1700),
    ('Cadenero', 'jor', 550, 720),
    ('Velador', 'jor', 380, 500),
]

MACHINERY = [
    ('Retroexcavadora CAT 416', 'hr', 850, 1200),
    ('Excavadora hidraulica CAT 320', 'hr', 1400, 1900),
    ('Bulldozer D6', 'hr', 1500, 2100),
    ('Motoconformadora 140K', 'hr', 1300, 1750),
    ('Compactador vibratorio 10 ton', 'hr', 950, 1300),
    ('Camion volteo 7 m3', 'hr', 550, 780),
    ('Camion volteo 14 m3', 'hr', 750, 1050),
    ('Camion pipa de agua 10000 L', 'hr', 600, 850),
    ('Revolvedora de concreto 1 saco', 'hr', 95, 145),
    ('Vibrador para concreto', 'hr', 65, 110),
    ('Pulidora para concreto', 'hr', 85, 130),
    ('Generador electrico 25 KVA', 'hr', 180, 260),
    ('Compresor neumatico 185 PCM', 'hr', 220, 320),
    ('Bomba sumergible 2\"', 'hr', 95, 150),
    ('Andamio tubular cuerpo', 'dia', 65, 95),
    ('Cimbra de contacto m2', 'm2', 45, 75),
]

SUBCONTRACT = [
    ('Subcontrato instalacion electrica residencial', 'lote', 18000, 45000),
    ('Subcontrato instalacion hidrosanitaria', 'lote', 22000, 55000),
    ('Subcontrato impermeabilizacion azotea', 'm2', 180, 280),
    ('Subcontrato cancel de aluminio', 'm2', 1200, 1900),
    ('Subcontrato herreria estructural', 'kg', 38, 55),
    ('Subcontrato pintura exterior', 'm2', 85, 145),
    ('Subcontrato colocacion de piso ceramico', 'm2', 120, 195),
    ('Subcontrato yeso y tirol', 'm2', 95, 165),
    ('Subcontrato demolicion controlada', 'm3', 280, 480),
    ('Subcontrato barrenacion para pilas', 'ml', 380, 620),
    ('Subcontrato mecanica de suelos sondeo SPT', 'ml', 1800, 2800),
    ('Subcontrato topografia y trazo', 'lote', 15000, 38000),
]

HAULING = [
    ('Acarreo de material 1er km', 'm3-km', 22, 35),
    ('Acarreo de material km adicional', 'm3-km', 8, 14),
    ('Acarreo de escombro a tiradero', 'm3', 180, 280),
    ('Acarreo en carretilla 20 m', 'm3', 65, 95),
    ('Carga manual a camion', 'm3', 95, 145),
    ('Carga mecanica a camion', 'm3', 35, 55),
]

CATALOG = {
    SupplyTypeCode.MATERIAL: ('MAT', MATERIALS),
    SupplyTypeCode.LABOR: ('MO', LABOR),
    SupplyTypeCode.MACHINERY: ('EQ', MACHINERY),
    SupplyTypeCode.SUBCONTRACT: ('SUB', SUBCONTRACT),
    SupplyTypeCode.HAULING: ('ACA', HAULING),
}

ZONES = ['CDMX', 'Monterrey', 'Guadalajara', 'Tampico', 'Puebla', '']


class Command(BaseCommand):
    help = 'Seed SupplyCatalogItem with realistic Mexican construction supplies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing catalog items before seeding',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=None,
            help='Random seed for reproducible output',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['seed'] is not None:
            random.seed(options['seed'])

        if options['clear']:
            count = SupplyCatalogItem.objects.count()
            SupplyCatalogItem.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {count} existing items'))

        created = 0
        skipped = 0
        today = date.today()

        for supplytype, (prefix, items) in CATALOG.items():
            for idx, (description, unit, pmin, pmax) in enumerate(items, start=1):
                code = f'{prefix}-{idx:04d}'
                if SupplyCatalogItem.objects.filter(code=code).exists():
                    skipped += 1
                    continue

                price = Decimal(str(round(random.uniform(pmin, pmax), 2)))
                ref_date = today - timedelta(days=random.randint(0, 365))

                SupplyCatalogItem.objects.create(
                    code=code,
                    description=description,
                    unit=unit,
                    supplytype=supplytype,
                    referenceprice=price,
                    referencedate=ref_date,
                    geographiczone=random.choice(ZONES),
                )
                created += 1

        total = SupplyCatalogItem.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {created} items (skipped {skipped} existing). Total in catalog: {total}'
            )
        )
