"""
Django management command to generate mining/construction industry products for Mexico.
Generates 12 product families, ~130 individual products, and 3 price lists.
Usage: python manage.py generate_dummy_products
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from apps.products.models import Product, PriceList, PriceListItem
from apps.users.models import SystemUser
import random


class Command(BaseCommand):
    help = 'Genera productos de mineria/construccion y listas de precios para Mexico'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '============================================================'
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            '  Generando Catalogo de Productos - Mineria/Construccion MX'
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            '============================================================'
        ))
        self.stdout.write('')

        # Get a user to assign as creator
        try:
            owner = SystemUser.objects.filter(isdisabled=False).first()
            if not owner:
                self.stdout.write(self.style.ERROR(
                    '[ERROR] No se encontro ningun usuario activo. '
                    'Ejecute load_dummy_data primero.'
                ))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'[ERROR] Error al obtener usuario: {e}'
            ))
            return

        self.stdout.write(f'[INFO] Usuario asignado: {owner}')
        self.stdout.write('')

        # Counters
        families_created = 0
        families_existing = 0
        products_created = 0
        products_existing = 0

        # =====================================================================
        # STEP 1: Create Product Families (productstructure=2)
        # =====================================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            '--- Paso 1: Creando Familias de Productos ---'
        ))

        families_data = [
            {
                'name': 'Tuberias HDPE',
                'productnumber': 'FAM-HDPE',
                'description': 'Tuberias de polietileno de alta densidad PE-100 para mineria, agua y saneamiento',
            },
            {
                'name': 'Cables para Minas',
                'productnumber': 'FAM-CAB',
                'description': 'Cables electricos y de comunicacion especializados para operaciones mineras subterraneas',
            },
            {
                'name': 'Seguridad y EPP',
                'productnumber': 'FAM-SEG',
                'description': 'Equipo de proteccion personal y seguridad para mineria y construccion',
            },
            {
                'name': 'Explosivos y Voladura',
                'productnumber': 'FAM-EXP',
                'description': 'Materiales explosivos, accesorios de voladura y sistemas de iniciacion',
            },
            {
                'name': 'Ventilacion Minera',
                'productnumber': 'FAM-VEN',
                'description': 'Ventiladores, ductos y sistemas de monitoreo de gases para ventilacion subterranea',
            },
            {
                'name': 'Perforacion',
                'productnumber': 'FAM-PER',
                'description': 'Brocas, barras, acoplamientos y accesorios para perforacion de roca',
            },
            {
                'name': 'Soporte de Roca',
                'productnumber': 'FAM-SOP',
                'description': 'Pernos, mallas, concreto lanzado y marcos para sostenimiento de excavaciones',
            },
            {
                'name': 'Bandas Transportadoras',
                'productnumber': 'FAM-BAN',
                'description': 'Bandas, polines, tensores y accesorios para transporte de material a granel',
            },
            {
                'name': 'Bombas y Desague',
                'productnumber': 'FAM-BOM',
                'description': 'Bombas sumergibles, centrifugas, de lodos y accesorios para desague minero',
            },
            {
                'name': 'Acero Estructural',
                'productnumber': 'FAM-ACE',
                'description': 'Vigas, canales, angulos, placas y perfiles de acero para construccion e infraestructura',
            },
            {
                'name': 'Productos Quimicos',
                'productnumber': 'FAM-QUI',
                'description': 'Reactivos quimicos para flotacion, lixiviacion y tratamiento de minerales',
            },
            {
                'name': 'Servicios Mineros',
                'productnumber': 'FAM-SVC',
                'description': 'Servicios de ingenieria, instalacion, mantenimiento y capacitacion para mineria',
            },
        ]

        family_map = {}  # productnumber prefix -> Product family instance

        for fam_data in families_data:
            family, created = Product.objects.get_or_create(
                productnumber=fam_data['productnumber'],
                defaults={
                    'name': fam_data['name'],
                    'description': fam_data['description'],
                    'productstructure': 2,  # Product Family
                    'producttypecode': 1,   # Sales Inventory
                    'statecode': 0,         # Active
                    'statuscode': 1,
                    'createdby': owner,
                    'modifiedby': owner,
                }
            )
            # Extract the prefix from 'FAM-HDPE' -> 'HDPE'
            prefix = fam_data['productnumber'].replace('FAM-', '')
            family_map[prefix] = family

            if created:
                families_created += 1
                self.stdout.write(
                    f'  [OK] Familia creada: {family.name}'
                )
            else:
                families_existing += 1
                self.stdout.write(
                    f'  [--] Familia ya existe: {family.name}'
                )

        self.stdout.write('')

        # =====================================================================
        # STEP 2: Create Individual Products (productstructure=1)
        # =====================================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            '--- Paso 2: Creando Productos Individuales ---'
        ))

        all_products = []  # Will collect all created/fetched products for price lists

        # -----------------------------------------------------------------
        # Helper to create products for a category
        # -----------------------------------------------------------------
        def create_products(category_name, family_prefix, items):
            """Create products for a given category and return the list."""
            nonlocal products_created, products_existing
            self.stdout.write(f'\n  [{family_prefix}] {category_name}:')
            category_products = []
            for item in items:
                defaults = {
                    'name': item['name'],
                    'description': item.get('description', ''),
                    'price': Decimal(str(item['price'])),
                    'standardcost': Decimal(str(item['standardcost'])),
                    'currentcost': Decimal(str(item.get('currentcost', item['standardcost']))),
                    'quantityonhand': Decimal(str(item.get('quantityonhand', 0))),
                    'productstructure': 1,  # Product
                    'producttypecode': item.get('producttypecode', 1),
                    'vendorname': item.get('vendorname', ''),
                    'size': item.get('size', ''),
                    'color': item.get('color', ''),
                    'style': item.get('style', ''),
                    'suppliername': item.get('vendorname', ''),
                    'parentproductid': family_map.get(family_prefix),
                    'statecode': 0,   # Active
                    'statuscode': 1,
                    'createdby': owner,
                    'modifiedby': owner,
                }
                product, created = Product.objects.get_or_create(
                    productnumber=item['productnumber'],
                    defaults=defaults
                )
                category_products.append(product)
                if created:
                    products_created += 1
                    self.stdout.write(
                        f'    [OK] {product.productnumber} - {product.name} '
                        f'(${product.price:,.2f})'
                    )
                else:
                    products_existing += 1
                    self.stdout.write(
                        f'    [--] Ya existe: {product.productnumber} - {product.name}'
                    )
            return category_products

        # -----------------------------------------------------------------
        # Helper for standard cost calculation (55-65% of price)
        # -----------------------------------------------------------------
        def sc(price, factor=None):
            """Calculate standard cost as 55-65% of price."""
            if factor is None:
                factor = random.uniform(0.55, 0.65)
            return Decimal(str(round(price * factor, 2)))

        # =================================================================
        # CATEGORY 1: Tuberias HDPE (SKU: HDPE-)
        # =================================================================
        hdpe_products = []

        # Small (rolls 100m, PN16)
        small_hdpe = [
            ('20mm', 185), ('25mm', 220), ('32mm', 350),
            ('40mm', 480), ('50mm', 650), ('63mm', 950),
        ]
        for size_str, price in small_hdpe:
            hdpe_products.append({
                'name': f'Tuberia HDPE PE-100 {size_str} PN16 Rollo 100m',
                'productnumber': f'HDPE-{size_str.replace("mm", "")}',
                'description': f'Tuberia de polietileno de alta densidad PE-100, diametro {size_str}, presion nominal PN16, presentacion en rollo de 100 metros. Apta para conduccion de agua, drenaje y aplicaciones mineras.',
                'price': price,
                'standardcost': sc(price),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'Polimex',
                'size': size_str,
                'color': 'Negro',
                'style': 'PE-100 PN16',
            })

        # Medium (bars 6m, PN16)
        medium_hdpe = [
            ('75mm', 1250), ('90mm', 1450), ('110mm', 1850),
            ('125mm', 2200), ('140mm', 2800),
        ]
        for size_str, price in medium_hdpe:
            hdpe_products.append({
                'name': f'Tuberia HDPE PE-100 {size_str} PN16 Barra 6m',
                'productnumber': f'HDPE-{size_str.replace("mm", "")}',
                'description': f'Tuberia de polietileno de alta densidad PE-100, diametro {size_str}, presion nominal PN16, presentacion en barra de 6 metros. Para conduccion de agua a presion y redes de distribucion minera.',
                'price': price,
                'standardcost': sc(price),
                'quantityonhand': random.randint(30, 300),
                'vendorname': 'Polimex',
                'size': size_str,
                'color': 'Negro',
                'style': 'PE-100 PN16',
            })

        # Large (bars 12m, PN10)
        large_hdpe = [
            ('160mm', 3200), ('200mm', 3800), ('225mm', 4200),
            ('250mm', 4800), ('280mm', 5200),
        ]
        for size_str, price in large_hdpe:
            hdpe_products.append({
                'name': f'Tuberia HDPE PE-100 {size_str} PN10 Barra 12m',
                'productnumber': f'HDPE-{size_str.replace("mm", "")}',
                'description': f'Tuberia de polietileno de alta densidad PE-100, diametro {size_str}, presion nominal PN10, presentacion en barra de 12 metros. Para conduccion de agua, relaves y drenaje en operaciones mineras.',
                'price': price,
                'standardcost': sc(price),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Polimex',
                'size': size_str,
                'color': 'Negro',
                'style': 'PE-100 PN10',
            })

        # Extra Large (bars 12m, PN10)
        xl_hdpe = [
            ('315mm', 5800), ('355mm', 6500), ('400mm', 7200),
            ('450mm', 8000), ('500mm', 8800),
        ]
        for size_str, price in xl_hdpe:
            hdpe_products.append({
                'name': f'Tuberia HDPE PE-100 {size_str} PN10 Barra 12m',
                'productnumber': f'HDPE-{size_str.replace("mm", "")}',
                'description': f'Tuberia de polietileno de alta densidad PE-100, diametro {size_str}, presion nominal PN10, presentacion en barra de 12 metros. Para lineas principales de agua, desague y conduccion de relaves en minas.',
                'price': price,
                'standardcost': sc(price),
                'quantityonhand': random.randint(10, 100),
                'vendorname': 'Polimex',
                'size': size_str,
                'color': 'Negro',
                'style': 'PE-100 PN10',
            })

        # XXL (bars 12m, PN10)
        xxl_hdpe = [
            ('560mm', 9800), ('630mm', 12500), ('710mm', 15000),
            ('800mm', 18500), ('900mm', 22000), ('1000mm', 28000),
            ('1200mm', 38000),
        ]
        for size_str, price in xxl_hdpe:
            hdpe_products.append({
                'name': f'Tuberia HDPE PE-100 {size_str} PN10 Barra 12m',
                'productnumber': f'HDPE-{size_str.replace("mm", "")}',
                'description': f'Tuberia de polietileno de alta densidad PE-100, diametro {size_str}, presion nominal PN10, presentacion en barra de 12 metros. Para lineas troncales de desague, conduccion de relaves y proyectos de gran diametro en mineria e infraestructura hidraulica.',
                'price': price,
                'standardcost': sc(price),
                'quantityonhand': random.randint(5, 50),
                'vendorname': 'Polimex',
                'size': size_str,
                'color': 'Negro',
                'style': 'PE-100 PN10',
            })

        all_products.extend(
            create_products('Tuberias HDPE', 'HDPE', hdpe_products)
        )

        # =================================================================
        # CATEGORY 2: Cables para Minas (SKU: CAB-)
        # =================================================================
        cable_products = [
            {
                'name': 'Cable de Potencia Minero 4/0 AWG 5kV',
                'productnumber': 'CAB-POT-4-0-5KV',
                'description': 'Cable de potencia tipo minero calibre 4/0 AWG, aislamiento 5kV, cubierta resistente a aceites y abrasion. Para alimentacion de equipos pesados en mina subterranea.',
                'price': 4500, 'standardcost': sc(4500),
                'quantityonhand': random.randint(100, 2000),
                'vendorname': 'Condumex', 'size': '4/0 AWG 5kV',
                'color': 'Negro', 'style': 'Tipo Minero',
            },
            {
                'name': 'Cable de Potencia Minero 2/0 AWG 5kV',
                'productnumber': 'CAB-POT-2-0-5KV',
                'description': 'Cable de potencia tipo minero calibre 2/0 AWG, aislamiento 5kV, flexible y resistente a condiciones subterraneas.',
                'price': 3200, 'standardcost': sc(3200),
                'quantityonhand': random.randint(100, 2000),
                'vendorname': 'Condumex', 'size': '2/0 AWG 5kV',
                'color': 'Negro', 'style': 'Tipo Minero',
            },
            {
                'name': 'Cable de Potencia 1/0 AWG 600V',
                'productnumber': 'CAB-POT-1-0-600V',
                'description': 'Cable de potencia calibre 1/0 AWG, aislamiento 600V, para distribucion electrica en mina y superficie.',
                'price': 1850, 'standardcost': sc(1850),
                'quantityonhand': random.randint(200, 3000),
                'vendorname': 'Viakon', 'size': '1/0 AWG 600V',
                'color': 'Negro', 'style': 'Industrial',
            },
            {
                'name': 'Cable Tipo Teck 2/0 AWG',
                'productnumber': 'CAB-TECK-2-0',
                'description': 'Cable tipo Teck calibre 2/0 AWG con armadura de aluminio interlock, para instalaciones mineras permanentes.',
                'price': 2850, 'standardcost': sc(2850),
                'quantityonhand': random.randint(100, 1500),
                'vendorname': 'Phelps Dodge', 'size': '2/0 AWG',
                'color': 'Negro', 'style': 'Tipo Teck',
            },
            {
                'name': 'Cable Tipo Teck 4/0 AWG',
                'productnumber': 'CAB-TECK-4-0',
                'description': 'Cable tipo Teck calibre 4/0 AWG con armadura de aluminio interlock, para alimentadores principales en mina.',
                'price': 3800, 'standardcost': sc(3800),
                'quantityonhand': random.randint(80, 1200),
                'vendorname': 'Phelps Dodge', 'size': '4/0 AWG',
                'color': 'Negro', 'style': 'Tipo Teck',
            },
            {
                'name': 'Cable para Jumbo Perforador 4/0 AWG',
                'productnumber': 'CAB-JUMBO-4-0',
                'description': 'Cable extra flexible para jumbo de perforacion, calibre 4/0 AWG, resistente a arrastre y flexion continua.',
                'price': 4200, 'standardcost': sc(4200),
                'quantityonhand': random.randint(50, 800),
                'vendorname': 'Condumex', 'size': '4/0 AWG',
                'color': 'Negro', 'style': 'Extra Flexible',
            },
            {
                'name': 'Cable Flexible de Arrastre 2/0 AWG',
                'productnumber': 'CAB-ARRASTRE-2-0',
                'description': 'Cable flexible de arrastre para scooptram y equipos moviles, calibre 2/0 AWG, alta resistencia mecanica.',
                'price': 3500, 'standardcost': sc(3500),
                'quantityonhand': random.randint(50, 1000),
                'vendorname': 'Condumex', 'size': '2/0 AWG',
                'color': 'Negro', 'style': 'Arrastre Minero',
            },
            {
                'name': 'Cable de Comunicacion Minero 12 pares',
                'productnumber': 'CAB-COM-12P',
                'description': 'Cable de comunicacion multipar para mina subterranea, 12 pares, blindaje general, resistente a humedad.',
                'price': 850, 'standardcost': sc(850),
                'quantityonhand': random.randint(200, 5000),
                'vendorname': 'Viakon', 'size': '12 pares',
                'color': 'Gris', 'style': 'Comunicacion Minero',
            },
            {
                'name': 'Cable de Fibra Optica Armado 12 hilos',
                'productnumber': 'CAB-FO-12H',
                'description': 'Cable de fibra optica monomodo armado con 12 hilos, para redes de datos y comunicacion en mina subterranea.',
                'price': 1200, 'standardcost': sc(1200),
                'quantityonhand': random.randint(100, 3000),
                'vendorname': 'Phelps Dodge', 'size': '12 hilos',
                'color': 'Negro', 'style': 'Fibra Optica Armado',
            },
            {
                'name': 'Cable de Control Blindado 12x16 AWG',
                'productnumber': 'CAB-CTRL-12X16',
                'description': 'Cable de control multiconductor blindado 12 conductores calibre 16 AWG, para instrumentacion y control en mina.',
                'price': 650, 'standardcost': sc(650),
                'quantityonhand': random.randint(200, 5000),
                'vendorname': 'Viakon', 'size': '12x16 AWG',
                'color': 'Negro', 'style': 'Control Blindado',
            },
            {
                'name': 'Cable de Instrumentacion 4 pares',
                'productnumber': 'CAB-INST-4P',
                'description': 'Cable de instrumentacion apantallado de 4 pares trenzados, para señales analogicas y digitales en ambientes mineros.',
                'price': 450, 'standardcost': sc(450),
                'quantityonhand': random.randint(300, 8000),
                'vendorname': 'Viakon', 'size': '4 pares',
                'color': 'Azul', 'style': 'Instrumentacion',
            },
            {
                'name': 'Cable Portatil de Extension 3x10 AWG',
                'productnumber': 'CAB-EXT-3X10',
                'description': 'Cable portatil de extension para herramientas y equipos temporales, 3 conductores calibre 10 AWG, uso rudo.',
                'price': 250, 'standardcost': sc(250),
                'quantityonhand': random.randint(500, 10000),
                'vendorname': 'Condumex', 'size': '3x10 AWG',
                'color': 'Naranja', 'style': 'Portatil Uso Rudo',
            },
        ]
        all_products.extend(
            create_products('Cables para Minas', 'CAB', cable_products)
        )

        # =================================================================
        # CATEGORY 3: Seguridad/EPP (SKU: SEG-)
        # =================================================================
        seg_products = [
            {
                'name': 'Casco Minero con Lampara LED',
                'productnumber': 'SEG-CASCO-LED',
                'description': 'Casco de seguridad minera con lampara LED integrada recargable, ventilacion, barbiquejo de 4 puntos. Certificacion NOM.',
                'price': 4500, 'standardcost': sc(4500),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'MSA Mexico', 'size': 'Universal',
                'color': 'Blanco', 'style': 'Minero con Lampara',
            },
            {
                'name': 'Autorescatador 60 min',
                'productnumber': 'SEG-AUTORESC-60',
                'description': 'Autorescatador de oxigeno quimico con 60 minutos de autonomia, para evacuacion de emergencia en mina subterranea.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Drager Mexico', 'size': 'Unico',
                'color': 'Naranja', 'style': 'Emergencia',
            },
            {
                'name': 'Arnes de Seguridad Minero',
                'productnumber': 'SEG-ARNES-MIN',
                'description': 'Arnes de cuerpo completo para trabajo en alturas y espacios confinados en mina, 5 puntos de anclaje, certificado NOM-009.',
                'price': 3500, 'standardcost': sc(3500),
                'quantityonhand': random.randint(30, 300),
                'vendorname': 'MSA Mexico', 'size': 'M/L',
                'color': 'Negro/Amarillo', 'style': 'Cuerpo Completo',
            },
            {
                'name': 'Botas de Seguridad Minera',
                'productnumber': 'SEG-BOTAS-MIN',
                'description': 'Botas de seguridad dielectricas con casco de acero, suela antiderrapante, resistentes a acidos y aceites. Para uso en mina.',
                'price': 2200, 'standardcost': sc(2200),
                'quantityonhand': random.randint(100, 800),
                'vendorname': 'Honeywell Mexico', 'size': '25-30 MX',
                'color': 'Negro', 'style': 'Industrial Minero',
            },
            {
                'name': 'Guantes de Nitrilo Industrial',
                'productnumber': 'SEG-GUANTES-NIT',
                'description': 'Guantes de nitrilo de alta resistencia para manejo de quimicos, aceites y materiales abrasivos. Caja con 100 piezas.',
                'price': 85, 'standardcost': sc(85),
                'quantityonhand': random.randint(500, 5000),
                'vendorname': 'Honeywell Mexico', 'size': 'M/L/XL',
                'color': 'Azul', 'style': 'Nitrilo Industrial',
            },
            {
                'name': 'Overol FR Antiestatico',
                'productnumber': 'SEG-OVEROL-FR',
                'description': 'Overol ignifugo (flame resistant) y antiestatico para trabajo en mina subterranea, con cintas reflectantes.',
                'price': 1800, 'standardcost': sc(1800),
                'quantityonhand': random.randint(50, 400),
                'vendorname': '3M Mexico', 'size': 'M/L/XL/XXL',
                'color': 'Azul Marino', 'style': 'FR Antiestatico',
            },
            {
                'name': 'Respirador Media Cara con Filtros P100',
                'productnumber': 'SEG-RESP-P100',
                'description': 'Respirador de media cara reutilizable con filtros P100 para particulas, polvos y neblinas en ambiente minero.',
                'price': 650, 'standardcost': sc(650),
                'quantityonhand': random.randint(100, 1000),
                'vendorname': '3M Mexico', 'size': 'M/L',
                'color': 'Gris/Magenta', 'style': 'Media Cara P100',
            },
            {
                'name': 'Detector Multigas 4 canales',
                'productnumber': 'SEG-DETECTOR-4G',
                'description': 'Detector portatil de 4 gases (O2, CO, H2S, LEL) con alarma sonora, visual y vibratoria. Certificacion ATEX.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(10, 100),
                'vendorname': 'MSA Mexico', 'size': 'Portatil',
                'color': 'Negro/Amarillo', 'style': 'Multigas ATEX',
            },
            {
                'name': 'Lentes de Seguridad Antiempanantes',
                'productnumber': 'SEG-LENTES-AE',
                'description': 'Lentes de seguridad con recubrimiento antiempanante y anti-rayaduras, proteccion UV, ligeros y comodos.',
                'price': 185, 'standardcost': sc(185),
                'quantityonhand': random.randint(200, 3000),
                'vendorname': 'Honeywell Mexico', 'size': 'Universal',
                'color': 'Transparente', 'style': 'Antiempanante',
            },
            {
                'name': 'Tapones Auditivos con Cordon',
                'productnumber': 'SEG-TAPONES-CD',
                'description': 'Tapones auditivos reutilizables con cordon, NRR 32 dB, para ambientes de alto ruido en minas y plantas de trituracion.',
                'price': 85, 'standardcost': sc(85),
                'quantityonhand': random.randint(1000, 10000),
                'vendorname': '3M Mexico', 'size': 'Universal',
                'color': 'Naranja', 'style': 'Reutilizable NRR32',
            },
            {
                'name': 'Chaleco Reflectante Clase 3',
                'productnumber': 'SEG-CHALECO-C3',
                'description': 'Chaleco de alta visibilidad clase 3 con cintas reflectantes 360 grados, multiples bolsillos, para operaciones en superficie.',
                'price': 350, 'standardcost': sc(350),
                'quantityonhand': random.randint(200, 2000),
                'vendorname': '3M Mexico', 'size': 'M/L/XL',
                'color': 'Amarillo Fluorescente', 'style': 'Alta Visibilidad Clase 3',
            },
            {
                'name': 'Kit de Primeros Auxilios Industrial',
                'productnumber': 'SEG-KIT-PAUX',
                'description': 'Kit completo de primeros auxilios para 50 personas, incluye insumos para quemaduras, heridas, fracturas y emergencias mineras.',
                'price': 1500, 'standardcost': sc(1500),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Honeywell Mexico', 'size': 'Grande',
                'color': 'Rojo/Blanco', 'style': 'Industrial 50 personas',
            },
        ]
        all_products.extend(
            create_products('Seguridad y EPP', 'SEG', seg_products)
        )

        # =================================================================
        # CATEGORY 4: Explosivos y Voladura (SKU: EXP-)
        # =================================================================
        exp_products = [
            {
                'name': 'Emulsion Explosiva Tipo 1',
                'productnumber': 'EXP-EMUL-T1',
                'description': 'Emulsion explosiva encartuchada tipo 1 para voladura en roca dura, alta velocidad de detonacion. Resistente al agua.',
                'price': 850, 'standardcost': sc(850),
                'quantityonhand': random.randint(500, 5000),
                'vendorname': 'Dyno Nobel Mexico', 'size': '1-1/4" x 8"',
                'color': 'Rojo', 'style': 'Encartuchada',
            },
            {
                'name': 'Emulsion a Granel por tonelada',
                'productnumber': 'EXP-EMUL-GRANEL',
                'description': 'Emulsion explosiva a granel para carga mecanizada en barrenos de gran diametro. Precio por tonelada metrica.',
                'price': 4500, 'standardcost': sc(4500),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'Orica Mexico', 'size': 'Tonelada',
                'color': '', 'style': 'A Granel',
            },
            {
                'name': 'ANFO Estandar',
                'productnumber': 'EXP-ANFO-STD',
                'description': 'ANFO (Nitrato de Amonio + Combustible) estandar para voladura en roca seca. Saco de 25 kg.',
                'price': 2800, 'standardcost': sc(2800),
                'quantityonhand': random.randint(200, 3000),
                'vendorname': 'Austin Powder', 'size': 'Saco 25 kg',
                'color': '', 'style': 'Estandar',
            },
            {
                'name': 'Cordon Detonante 10g/m',
                'productnumber': 'EXP-CORDON-10G',
                'description': 'Cordon detonante de 10 gramos por metro lineal, nucleo de PETN, para iniciacion de columnas explosivas. Rollo de 500m.',
                'price': 350, 'standardcost': sc(350),
                'quantityonhand': random.randint(100, 2000),
                'vendorname': 'Dyno Nobel Mexico', 'size': '10g/m x 500m',
                'color': 'Amarillo', 'style': 'Cordon PETN',
            },
            {
                'name': 'Detonador Electronico Programable',
                'productnumber': 'EXP-DET-ELEC',
                'description': 'Detonador electronico programable con retardo de precision de 1ms, para voladuras controladas de alta eficiencia.',
                'price': 1200, 'standardcost': sc(1200),
                'quantityonhand': random.randint(500, 8000),
                'vendorname': 'Orica Mexico', 'size': 'Unitario',
                'color': '', 'style': 'Electronico Programable',
            },
            {
                'name': 'Booster de Pentolita 150g',
                'productnumber': 'EXP-BOOSTER-150',
                'description': 'Booster multiplicador de pentolita 150g para iniciacion de columnas de ANFO y emulsion a granel.',
                'price': 450, 'standardcost': sc(450),
                'quantityonhand': random.randint(1000, 10000),
                'vendorname': 'Austin Powder', 'size': '150g',
                'color': 'Naranja', 'style': 'Pentolita',
            },
            {
                'name': 'Mecha de Seguridad',
                'productnumber': 'EXP-MECHA-SEG',
                'description': 'Mecha de seguridad con nucleo de polvora negra, velocidad de combustion controlada. Rollo de 200m.',
                'price': 380, 'standardcost': sc(380),
                'quantityonhand': random.randint(100, 1500),
                'vendorname': 'Dyno Nobel Mexico', 'size': 'Rollo 200m',
                'color': 'Verde', 'style': 'Polvora Negra',
            },
            {
                'name': 'Sistema de Voladura Electronica',
                'productnumber': 'EXP-SIST-ELEC',
                'description': 'Sistema completo de voladura electronica: explosor programable, cables de conexion, software de diseño y maleta de transporte.',
                'price': 28000, 'standardcost': sc(28000),
                'quantityonhand': random.randint(5, 20),
                'vendorname': 'Orica Mexico', 'size': 'Kit Completo',
                'color': '', 'style': 'Sistema Electronico',
            },
            {
                'name': 'Accesorios de Voladura Kit',
                'productnumber': 'EXP-ACC-KIT',
                'description': 'Kit de accesorios para voladura: atacadores, conectores, cinta de empalme, etiquetas de seguridad y guias.',
                'price': 2500, 'standardcost': sc(2500),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Austin Powder', 'size': 'Kit',
                'color': '', 'style': 'Kit Accesorios',
            },
            {
                'name': 'Retardos de Superficie',
                'productnumber': 'EXP-RETARDO-SUP',
                'description': 'Retardos de superficie (conectores de retardo) para secuenciacion de voladuras, varios tiempos disponibles. Caja de 200 pzas.',
                'price': 680, 'standardcost': sc(680),
                'quantityonhand': random.randint(100, 3000),
                'vendorname': 'Dyno Nobel Mexico', 'size': 'Caja 200 pzas',
                'color': 'Varios', 'style': 'Superficie MS',
            },
        ]
        all_products.extend(
            create_products('Explosivos y Voladura', 'EXP', exp_products)
        )

        # =================================================================
        # CATEGORY 5: Ventilacion Minera (SKU: VEN-)
        # =================================================================
        ven_products = [
            {
                'name': 'Ventilador Axial Principal 200HP',
                'productnumber': 'VEN-AXIAL-200HP',
                'description': 'Ventilador axial principal de 200 HP para ventilacion de mina subterranea, flujo de 150 m3/s, alta eficiencia.',
                'price': 850000, 'standardcost': sc(850000),
                'quantityonhand': random.randint(1, 5),
                'vendorname': 'Howden Mexico', 'size': '200 HP',
                'color': '', 'style': 'Axial Principal',
            },
            {
                'name': 'Ventilador Axial Auxiliar 75HP',
                'productnumber': 'VEN-AXIAL-75HP',
                'description': 'Ventilador axial auxiliar de 75 HP para ventilacion de frentes de trabajo, flujo de 45 m3/s.',
                'price': 285000, 'standardcost': sc(285000),
                'quantityonhand': random.randint(2, 10),
                'vendorname': 'Howden Mexico', 'size': '75 HP',
                'color': '', 'style': 'Axial Auxiliar',
            },
            {
                'name': 'Ventilador Auxiliar 30HP',
                'productnumber': 'VEN-AUX-30HP',
                'description': 'Ventilador auxiliar de 30 HP para ventilacion secundaria y refuerzo en areas de trabajo.',
                'price': 95000, 'standardcost': sc(95000),
                'quantityonhand': random.randint(5, 20),
                'vendorname': 'TLT-Turbo', 'size': '30 HP',
                'color': '', 'style': 'Auxiliar Compacto',
            },
            {
                'name': 'Ducto Flexible de Ventilacion 1000mm',
                'productnumber': 'VEN-DUCTO-F1000',
                'description': 'Ducto flexible de ventilacion diametro 1000mm, material PVC reforzado con espiral de acero. Tramo de 20m.',
                'price': 15000, 'standardcost': sc(15000),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Korfmann', 'size': '1000mm x 20m',
                'color': 'Amarillo', 'style': 'Flexible PVC',
            },
            {
                'name': 'Ducto Flexible de Ventilacion 800mm',
                'productnumber': 'VEN-DUCTO-F800',
                'description': 'Ducto flexible de ventilacion diametro 800mm, material PVC reforzado con espiral de acero. Tramo de 20m.',
                'price': 12000, 'standardcost': sc(12000),
                'quantityonhand': random.randint(30, 250),
                'vendorname': 'Korfmann', 'size': '800mm x 20m',
                'color': 'Amarillo', 'style': 'Flexible PVC',
            },
            {
                'name': 'Ducto Rigido Metalico 1200mm',
                'productnumber': 'VEN-DUCTO-R1200',
                'description': 'Ducto rigido metalico de ventilacion diametro 1200mm, acero galvanizado calibre 14, tramo de 3m con bridas.',
                'price': 22000, 'standardcost': sc(22000),
                'quantityonhand': random.randint(10, 100),
                'vendorname': 'Howden Mexico', 'size': '1200mm x 3m',
                'color': 'Galvanizado', 'style': 'Rigido Metalico',
            },
            {
                'name': 'Puerta de Ventilacion con Marco',
                'productnumber': 'VEN-PUERTA-VM',
                'description': 'Puerta de ventilacion con marco metalico para regulacion de flujo de aire en mina subterranea. Incluye herrajes.',
                'price': 45000, 'standardcost': sc(45000),
                'quantityonhand': random.randint(5, 30),
                'vendorname': 'TLT-Turbo', 'size': '2.4m x 2.1m',
                'color': 'Rojo', 'style': 'Con Marco Metalico',
            },
            {
                'name': 'Sensor de Gases Fijo',
                'productnumber': 'VEN-SENSOR-GAS',
                'description': 'Sensor fijo de gases para monitoreo continuo (CO, CO2, NO2, CH4, O2) con transmision a superficie via red.',
                'price': 35000, 'standardcost': sc(35000),
                'quantityonhand': random.randint(10, 80),
                'vendorname': 'Howden Mexico', 'size': 'Fijo',
                'color': '', 'style': 'Multigas Fijo',
            },
        ]
        all_products.extend(
            create_products('Ventilacion Minera', 'VEN', ven_products)
        )

        # =================================================================
        # CATEGORY 6: Perforacion (SKU: PER-)
        # =================================================================
        per_products = [
            {
                'name': 'Broca Triconica 6-1/2"',
                'productnumber': 'PER-TRIC-6.5',
                'description': 'Broca triconica de 6-1/2 pulgadas para perforacion de produccion en roca media a dura. Insertos de carburo de tungsteno.',
                'price': 18500, 'standardcost': sc(18500),
                'quantityonhand': random.randint(10, 100),
                'vendorname': 'Epiroc Mexico', 'size': '6-1/2"',
                'color': '', 'style': 'Triconica Carburo',
            },
            {
                'name': 'Broca Triconica 4-3/4"',
                'productnumber': 'PER-TRIC-4.75',
                'description': 'Broca triconica de 4-3/4 pulgadas para perforacion de exploracion y desarrollo, roca media.',
                'price': 12500, 'standardcost': sc(12500),
                'quantityonhand': random.randint(15, 120),
                'vendorname': 'Sandvik Mexico', 'size': '4-3/4"',
                'color': '', 'style': 'Triconica Carburo',
            },
            {
                'name': 'Broca de Botones 45mm',
                'productnumber': 'PER-BOTON-45',
                'description': 'Broca de botones de 45mm para perforacion de frentes con jumbo, insertos de carburo de tungsteno semibalisticos.',
                'price': 2500, 'standardcost': sc(2500),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'Epiroc Mexico', 'size': '45mm',
                'color': '', 'style': 'Botones Semibalisticos',
            },
            {
                'name': 'Barra de Perforacion T38 3.66m',
                'productnumber': 'PER-BARRA-T38-366',
                'description': 'Barra de perforacion con rosca T38, longitud 3.66m (12 pies), acero tratado termicamente para jumbo de perforacion.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Sandvik Mexico', 'size': 'T38 x 3.66m',
                'color': '', 'style': 'Acero Tratado',
            },
            {
                'name': 'Barra de Perforacion T38 1.83m',
                'productnumber': 'PER-BARRA-T38-183',
                'description': 'Barra de perforacion con rosca T38, longitud 1.83m (6 pies), para perforacion en espacios reducidos.',
                'price': 5200, 'standardcost': sc(5200),
                'quantityonhand': random.randint(30, 250),
                'vendorname': 'Sandvik Mexico', 'size': 'T38 x 1.83m',
                'color': '', 'style': 'Acero Tratado',
            },
            {
                'name': 'Acoplamiento T38',
                'productnumber': 'PER-ACOP-T38',
                'description': 'Acoplamiento (coupling) con rosca T38 hembra-hembra para union de barras de perforacion.',
                'price': 3800, 'standardcost': sc(3800),
                'quantityonhand': random.randint(30, 300),
                'vendorname': 'Epiroc Mexico', 'size': 'T38',
                'color': '', 'style': 'Hembra-Hembra',
            },
            {
                'name': 'Barra Integral 1.2m',
                'productnumber': 'PER-INTEGRAL-120',
                'description': 'Barra integral (con broca incorporada) de 1.2m para perforacion manual con jack leg, diametro de broca 38mm.',
                'price': 2800, 'standardcost': sc(2800),
                'quantityonhand': random.randint(50, 400),
                'vendorname': 'Atlas Copco', 'size': '1.2m x 38mm',
                'color': '', 'style': 'Integral Jack Leg',
            },
            {
                'name': 'Broca de Diamante NQ',
                'productnumber': 'PER-DIAM-NQ',
                'description': 'Broca de diamante calibre NQ (75.7mm) para perforacion de exploracion con diamantina, corona impregnada.',
                'price': 45000, 'standardcost': sc(45000),
                'quantityonhand': random.randint(5, 50),
                'vendorname': 'Sandvik Mexico', 'size': 'NQ 75.7mm',
                'color': '', 'style': 'Diamante Impregnado',
            },
            {
                'name': 'Adaptador de Perforacion R32-T38',
                'productnumber': 'PER-ADAPT-R32T38',
                'description': 'Adaptador de rosca R32 a T38 para intercambiabilidad de aceros de perforacion entre equipos.',
                'price': 4500, 'standardcost': sc(4500),
                'quantityonhand': random.randint(10, 100),
                'vendorname': 'Epiroc Mexico', 'size': 'R32-T38',
                'color': '', 'style': 'Adaptador Rosca',
            },
            {
                'name': 'Aceite para Perforacion (tambor 200L)',
                'productnumber': 'PER-ACEITE-200L',
                'description': 'Aceite de perforacion para lubricacion de barras y brocas, alto rendimiento, tambor de 200 litros.',
                'price': 3200, 'standardcost': sc(3200),
                'quantityonhand': random.randint(10, 80),
                'vendorname': 'Atlas Copco', 'size': 'Tambor 200L',
                'color': '', 'style': 'Lubricante Perforacion',
            },
        ]
        all_products.extend(
            create_products('Perforacion', 'PER', per_products)
        )

        # =================================================================
        # CATEGORY 7: Soporte de Roca (SKU: SOP-)
        # =================================================================
        sop_products = [
            {
                'name': 'Perno Split Set 1.5m',
                'productnumber': 'SOP-SPLIT-150',
                'description': 'Perno de friccion tipo Split Set de 1.5m de longitud, diametro 39mm, para sostenimiento temporal de roca.',
                'price': 85, 'standardcost': sc(85),
                'quantityonhand': random.randint(2000, 10000),
                'vendorname': 'DSI Underground', 'size': '1.5m x 39mm',
                'color': '', 'style': 'Friccion Split Set',
            },
            {
                'name': 'Perno Split Set 2.4m',
                'productnumber': 'SOP-SPLIT-240',
                'description': 'Perno de friccion tipo Split Set de 2.4m de longitud, diametro 39mm, para sostenimiento en terreno fracturado.',
                'price': 120, 'standardcost': sc(120),
                'quantityonhand': random.randint(2000, 10000),
                'vendorname': 'DSI Underground', 'size': '2.4m x 39mm',
                'color': '', 'style': 'Friccion Split Set',
            },
            {
                'name': 'Perno de Resina 2.4m',
                'productnumber': 'SOP-RESINA-240',
                'description': 'Perno de anclaje con resina de 2.4m, diametro 22mm, rosca M20, para sostenimiento permanente en roca competente.',
                'price': 165, 'standardcost': sc(165),
                'quantityonhand': random.randint(1000, 8000),
                'vendorname': 'Jennmar', 'size': '2.4m x 22mm',
                'color': '', 'style': 'Anclaje con Resina',
            },
            {
                'name': 'Malla Electrosoldada 2.4x3m',
                'productnumber': 'SOP-MALLA-ES',
                'description': 'Malla electrosoldada de alambre calibre 8, abertura 100x100mm, panel de 2.4x3m para sostenimiento de roca.',
                'price': 450, 'standardcost': sc(450),
                'quantityonhand': random.randint(500, 5000),
                'vendorname': 'DSI Underground', 'size': '2.4m x 3m',
                'color': 'Galvanizado', 'style': 'Electrosoldada Cal.8',
            },
            {
                'name': 'Malla de Cable',
                'productnumber': 'SOP-MALLA-CAB',
                'description': 'Malla de cable de acero de alta resistencia para sostenimiento de roca en zonas de alta deformacion, panel 2.4x3m.',
                'price': 850, 'standardcost': sc(850),
                'quantityonhand': random.randint(200, 2000),
                'vendorname': 'DSI Underground', 'size': '2.4m x 3m',
                'color': 'Galvanizado', 'style': 'Cable Alta Resistencia',
            },
            {
                'name': 'Concreto Lanzado (Shotcrete) por m3',
                'productnumber': 'SOP-SHOTCRETE',
                'description': 'Concreto lanzado (shotcrete) via humeda con fibra de acero, resistencia 300 kg/cm2. Precio por metro cubico.',
                'price': 2800, 'standardcost': sc(2800),
                'quantityonhand': random.randint(100, 1000),
                'vendorname': 'Minova', 'size': 'Metro cubico',
                'color': 'Gris', 'style': 'Via Humeda con Fibra',
            },
            {
                'name': 'Fibra de Acero para Shotcrete',
                'productnumber': 'SOP-FIBRA-AC',
                'description': 'Fibra de acero con ganchos para refuerzo de concreto lanzado, longitud 50mm, saco de 20 kg.',
                'price': 4500, 'standardcost': sc(4500),
                'quantityonhand': random.randint(100, 1000),
                'vendorname': 'Minova', 'size': 'Saco 20 kg',
                'color': '', 'style': 'Con Ganchos 50mm',
            },
            {
                'name': 'Marco Metalico TH-29',
                'productnumber': 'SOP-MARCO-TH29',
                'description': 'Marco metalico de perfil TH-29 para sostenimiento de galerias en terreno blando, radio de curvatura variable.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Jennmar', 'size': 'TH-29',
                'color': '', 'style': 'Perfil TH Deslizante',
            },
            {
                'name': 'Resina de Anclaje (cartucho)',
                'productnumber': 'SOP-RESINA-CART',
                'description': 'Cartucho de resina de poliester para anclaje de pernos, fraguado rapido 30 segundos, diametro 28mm.',
                'price': 45, 'standardcost': sc(45),
                'quantityonhand': random.randint(5000, 10000),
                'vendorname': 'Minova', 'size': '28mm x 250mm',
                'color': 'Azul', 'style': 'Fraguado Rapido',
            },
            {
                'name': 'Placa de Acero 150x150mm',
                'productnumber': 'SOP-PLACA-150',
                'description': 'Placa de acero galvanizado 150x150mm, espesor 6mm, con orificio central para perno de anclaje.',
                'price': 65, 'standardcost': sc(65),
                'quantityonhand': random.randint(3000, 10000),
                'vendorname': 'DSI Underground', 'size': '150x150x6mm',
                'color': 'Galvanizado', 'style': 'Con Orificio Central',
            },
        ]
        all_products.extend(
            create_products('Soporte de Roca', 'SOP', sop_products)
        )

        # =================================================================
        # CATEGORY 8: Bandas Transportadoras (SKU: BAN-)
        # =================================================================
        ban_products = [
            {
                'name': 'Banda Transportadora EP400/3 1200mm',
                'productnumber': 'BAN-EP400-1200',
                'description': 'Banda transportadora EP400/3 capas, ancho 1200mm, cubierta superior 6mm + inferior 2mm, resistencia a la abrasion.',
                'price': 45000, 'standardcost': sc(45000),
                'quantityonhand': random.randint(5, 30),
                'vendorname': 'Goodyear Mexico', 'size': '1200mm x 100m',
                'color': 'Negro', 'style': 'EP400/3 Capas',
            },
            {
                'name': 'Banda Transportadora EP500/4 1400mm',
                'productnumber': 'BAN-EP500-1400',
                'description': 'Banda transportadora EP500/4 capas, ancho 1400mm, alta resistencia para transporte de mineral grueso.',
                'price': 68000, 'standardcost': sc(68000),
                'quantityonhand': random.randint(3, 20),
                'vendorname': 'Continental Mexico', 'size': '1400mm x 100m',
                'color': 'Negro', 'style': 'EP500/4 Capas',
            },
            {
                'name': 'Banda Transportadora EP315/3 900mm',
                'productnumber': 'BAN-EP315-900',
                'description': 'Banda transportadora EP315/3 capas, ancho 900mm, para transporte de material medio en interior mina.',
                'price': 28000, 'standardcost': sc(28000),
                'quantityonhand': random.randint(5, 25),
                'vendorname': 'Goodyear Mexico', 'size': '900mm x 100m',
                'color': 'Negro', 'style': 'EP315/3 Capas',
            },
            {
                'name': 'Polines de Carga Triple 35 grados',
                'productnumber': 'BAN-POLIN-CARGA',
                'description': 'Juego de polines de carga triple a 35 grados de inclinacion, rodillos de 127mm, para banda de 1200mm.',
                'price': 1200, 'standardcost': sc(1200),
                'quantityonhand': random.randint(100, 1000),
                'vendorname': 'Martin Engineering', 'size': '35° x 1200mm',
                'color': 'Azul', 'style': 'Triple Carga',
            },
            {
                'name': 'Polines de Retorno',
                'productnumber': 'BAN-POLIN-RET',
                'description': 'Polin de retorno liso, rodillo de 127mm de diametro, para soporte de ramal inferior de banda transportadora.',
                'price': 850, 'standardcost': sc(850),
                'quantityonhand': random.randint(100, 1000),
                'vendorname': 'Martin Engineering', 'size': '127mm',
                'color': 'Azul', 'style': 'Retorno Liso',
            },
            {
                'name': 'Tensor de Banda Gravitacional',
                'productnumber': 'BAN-TENSOR-GRAV',
                'description': 'Sistema de tension gravitacional para banda transportadora, incluye contrapeso, polea y estructura.',
                'price': 15000, 'standardcost': sc(15000),
                'quantityonhand': random.randint(5, 30),
                'vendorname': 'Martin Engineering', 'size': 'Estandar',
                'color': '', 'style': 'Gravitacional',
            },
            {
                'name': 'Limpiador de Banda Primario',
                'productnumber': 'BAN-LIMP-PRIM',
                'description': 'Limpiador primario de cuchillas de poliuretano para banda transportadora, montaje en polea de cabeza.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(10, 80),
                'vendorname': 'Martin Engineering', 'size': '1200mm',
                'color': 'Naranja', 'style': 'Primario Poliuretano',
            },
            {
                'name': 'Vulcanizacion de Empalme (servicio)',
                'productnumber': 'BAN-VULC-EMPAL',
                'description': 'Servicio de vulcanizacion en caliente de empalme de banda transportadora, incluye materiales y mano de obra especializada.',
                'price': 125000, 'standardcost': sc(125000),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,  # Miscellaneous Charges (service)
                'vendorname': 'Continental Mexico', 'size': 'Por Empalme',
                'color': '', 'style': 'Vulcanizacion en Caliente',
            },
        ]
        all_products.extend(
            create_products('Bandas Transportadoras', 'BAN', ban_products)
        )

        # =================================================================
        # CATEGORY 9: Bombas y Desague (SKU: BOM-)
        # =================================================================
        bom_products = [
            {
                'name': 'Bomba Sumergible 100HP',
                'productnumber': 'BOM-SUMER-100HP',
                'description': 'Bomba sumergible de 100 HP para desague de mina, acero inoxidable, flujo maximo 200 l/s, cabeza 150m.',
                'price': 385000, 'standardcost': sc(385000),
                'quantityonhand': random.randint(2, 10),
                'vendorname': 'Flygt (Xylem)', 'size': '100 HP',
                'color': '', 'style': 'Sumergible Inox',
            },
            {
                'name': 'Bomba Sumergible 50HP',
                'productnumber': 'BOM-SUMER-50HP',
                'description': 'Bomba sumergible de 50 HP para desague secundario, acero inoxidable, flujo maximo 100 l/s, cabeza 80m.',
                'price': 185000, 'standardcost': sc(185000),
                'quantityonhand': random.randint(3, 15),
                'vendorname': 'Flygt (Xylem)', 'size': '50 HP',
                'color': '', 'style': 'Sumergible Inox',
            },
            {
                'name': 'Bomba Sumergible 25HP',
                'productnumber': 'BOM-SUMER-25HP',
                'description': 'Bomba sumergible de 25 HP para desague de frentes de trabajo y carcamos, flujo maximo 50 l/s.',
                'price': 95000, 'standardcost': sc(95000),
                'quantityonhand': random.randint(5, 20),
                'vendorname': 'Flygt (Xylem)', 'size': '25 HP',
                'color': '', 'style': 'Sumergible',
            },
            {
                'name': 'Bomba Centrifuga Horizontal 150HP',
                'productnumber': 'BOM-CENT-150HP',
                'description': 'Bomba centrifuga horizontal de 150 HP para estaciones de bombeo, manejo de agua limpia y ligeramente turbia.',
                'price': 450000, 'standardcost': sc(450000),
                'quantityonhand': random.randint(1, 8),
                'vendorname': 'Metso', 'size': '150 HP',
                'color': '', 'style': 'Centrifuga Horizontal',
            },
            {
                'name': 'Bomba de Lodos 8x6',
                'productnumber': 'BOM-LODOS-8X6',
                'description': 'Bomba de lodos tipo slurry 8x6 pulgadas, para manejo de pulpas abrasivas con alto contenido de solidos. Revestimiento en alto cromo.',
                'price': 650000, 'standardcost': sc(650000),
                'quantityonhand': random.randint(1, 5),
                'vendorname': 'Warman (Weir)', 'size': '8x6"',
                'color': '', 'style': 'Slurry Alto Cromo',
            },
            {
                'name': 'Impulsor de Alto Cromo',
                'productnumber': 'BOM-IMPULSOR-AC',
                'description': 'Impulsor (impeller) de alto cromo para bomba de lodos, resistente a la abrasion, para bombas Warman serie AH.',
                'price': 45000, 'standardcost': sc(45000),
                'quantityonhand': random.randint(5, 30),
                'vendorname': 'Warman (Weir)', 'size': '8x6',
                'color': '', 'style': 'Alto Cromo 28%',
            },
            {
                'name': 'Sello Mecanico',
                'productnumber': 'BOM-SELLO-MEC',
                'description': 'Sello mecanico de carburo de silicio para bombas centrifugas y sumergibles, previene fugas de agua.',
                'price': 18500, 'standardcost': sc(18500),
                'quantityonhand': random.randint(10, 60),
                'vendorname': 'Metso', 'size': 'Estandar',
                'color': '', 'style': 'Carburo de Silicio',
            },
            {
                'name': 'Tuberia de Descarga 6"',
                'productnumber': 'BOM-TUB-DESC-6',
                'description': 'Tuberia de acero de 6 pulgadas para descarga de bomba, con bridas y empaque, tramo de 6m.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(20, 150),
                'vendorname': 'Metso', 'size': '6" x 6m',
                'color': '', 'style': 'Acero con Bridas',
            },
            {
                'name': 'Valvula Check 8"',
                'productnumber': 'BOM-VALV-CHECK-8',
                'description': 'Valvula check (no retorno) de 8 pulgadas, cuerpo de hierro ductil, disco de acero inoxidable, para lineas de bombeo.',
                'price': 12500, 'standardcost': sc(12500),
                'quantityonhand': random.randint(10, 50),
                'vendorname': 'Metso', 'size': '8"',
                'color': '', 'style': 'Check Hierro Ductil',
            },
            {
                'name': 'Manguera Flexible 4"',
                'productnumber': 'BOM-MANG-FLEX-4',
                'description': 'Manguera flexible de 4 pulgadas para conexiones temporales de bomba, resistente a presion y abrasion. Tramo de 6m.',
                'price': 850, 'standardcost': sc(850),
                'quantityonhand': random.randint(30, 300),
                'vendorname': 'Warman (Weir)', 'size': '4" x 6m',
                'color': 'Negro', 'style': 'Flexible Reforzada',
            },
        ]
        all_products.extend(
            create_products('Bombas y Desague', 'BOM', bom_products)
        )

        # =================================================================
        # CATEGORY 10: Acero Estructural (SKU: ACE-)
        # =================================================================
        ace_products = [
            {
                'name': 'Viga IPR W8x31 ASTM A36',
                'productnumber': 'ACE-IPR-W8X31',
                'description': 'Viga de acero IPR perfil W8x31, norma ASTM A36, longitud 6.10m. Para estructuras, marcos y soportes en mina y construccion.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'DeAcero', 'size': 'W8x31 x 6.10m',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'Viga IPR W10x49 ASTM A36',
                'productnumber': 'ACE-IPR-W10X49',
                'description': 'Viga de acero IPR perfil W10x49, norma ASTM A36, longitud 6.10m. Para estructuras de mayor carga.',
                'price': 12500, 'standardcost': sc(12500),
                'quantityonhand': random.randint(15, 150),
                'vendorname': 'Ternium Mexico', 'size': 'W10x49 x 6.10m',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'Viga IPR W6x20 ASTM A36',
                'productnumber': 'ACE-IPR-W6X20',
                'description': 'Viga de acero IPR perfil W6x20, norma ASTM A36, longitud 6.10m. Para estructuras ligeras y marcos auxiliares.',
                'price': 5800, 'standardcost': sc(5800),
                'quantityonhand': random.randint(30, 250),
                'vendorname': 'AHMSA', 'size': 'W6x20 x 6.10m',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'Canal CPS 6"',
                'productnumber': 'ACE-CPS-6',
                'description': 'Canal de acero CPS (C) de 6 pulgadas, norma ASTM A36, longitud 6.10m. Para largueros, soportes y arriostramientos.',
                'price': 3200, 'standardcost': sc(3200),
                'quantityonhand': random.randint(30, 300),
                'vendorname': 'DeAcero', 'size': 'CPS 6" x 6.10m',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'Angulo L3x3x3/8"',
                'productnumber': 'ACE-ANG-3X3',
                'description': 'Angulo de acero L3x3x3/8 pulgadas, norma ASTM A36, longitud 6.10m. Para conexiones, arriostramientos y marcos.',
                'price': 1850, 'standardcost': sc(1850),
                'quantityonhand': random.randint(50, 400),
                'vendorname': 'Ternium Mexico', 'size': 'L3x3x3/8" x 6.10m',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'Placa de Acero 1/2" 4x8ft',
                'productnumber': 'ACE-PLACA-12',
                'description': 'Placa de acero ASTM A36, espesor 1/2 pulgada (12.7mm), dimension 4x8 pies (1.22x2.44m).',
                'price': 4500, 'standardcost': sc(4500),
                'quantityonhand': random.randint(20, 150),
                'vendorname': 'AHMSA', 'size': '1/2" x 4x8ft',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'Placa de Acero 3/4" 4x8ft',
                'productnumber': 'ACE-PLACA-34',
                'description': 'Placa de acero ASTM A36, espesor 3/4 pulgada (19mm), dimension 4x8 pies (1.22x2.44m).',
                'price': 6800, 'standardcost': sc(6800),
                'quantityonhand': random.randint(10, 100),
                'vendorname': 'AHMSA', 'size': '3/4" x 4x8ft',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'PTR 4x4"',
                'productnumber': 'ACE-PTR-4X4',
                'description': 'Perfil tubular rectangular (PTR) de 4x4 pulgadas, calibre 11 (3mm), longitud 6.10m. Para marcos y estructuras.',
                'price': 2200, 'standardcost': sc(2200),
                'quantityonhand': random.randint(50, 400),
                'vendorname': 'DeAcero', 'size': '4x4" Cal.11 x 6.10m',
                'color': '', 'style': 'Calibre 11',
            },
            {
                'name': 'Solera 3"x3/8"',
                'productnumber': 'ACE-SOLERA-3X38',
                'description': 'Solera de acero de 3 pulgadas de ancho por 3/8 pulgada de espesor, longitud 6.10m. Para refuerzos y conexiones.',
                'price': 850, 'standardcost': sc(850),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'Ternium Mexico', 'size': '3"x3/8" x 6.10m',
                'color': '', 'style': 'ASTM A36',
            },
            {
                'name': 'Redondo Liso 1"',
                'productnumber': 'ACE-REDONDO-1',
                'description': 'Barra redonda lisa de acero de 1 pulgada de diametro, norma ASTM A36, longitud 6.10m. Para anclas, pernos y refuerzos.',
                'price': 950, 'standardcost': sc(950),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'DeAcero', 'size': '1" x 6.10m',
                'color': '', 'style': 'ASTM A36 Liso',
            },
        ]
        all_products.extend(
            create_products('Acero Estructural', 'ACE', ace_products)
        )

        # =================================================================
        # CATEGORY 11: Productos Quimicos (SKU: QUI-)
        # =================================================================
        qui_products = [
            {
                'name': 'Xantato Amilico de Potasio',
                'productnumber': 'QUI-XANTATO-AP',
                'description': 'Xantato amilico de potasio (PAX), colector para flotacion de sulfuros de cobre, plomo y zinc. Tambor de 50 kg.',
                'price': 4500, 'standardcost': sc(4500),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'Cytec (Solvay)', 'size': 'Tambor 50 kg',
                'color': 'Amarillo', 'style': 'Colector Flotacion',
            },
            {
                'name': 'Espumante MIBC',
                'productnumber': 'QUI-MIBC',
                'description': 'Espumante MIBC (Metil Isobutil Carbinol) para generacion de espuma estable en celdas de flotacion. Tambor de 200 litros.',
                'price': 3200, 'standardcost': sc(3200),
                'quantityonhand': random.randint(30, 300),
                'vendorname': 'Cytec (Solvay)', 'size': 'Tambor 200L',
                'color': '', 'style': 'Espumante',
            },
            {
                'name': 'Cal Viva (tonelada)',
                'productnumber': 'QUI-CALVIVA-TON',
                'description': 'Cal viva (oxido de calcio CaO) de alta pureza para regulacion de pH en procesos de flotacion y lixiviacion. Por tonelada.',
                'price': 1800, 'standardcost': sc(1800),
                'quantityonhand': random.randint(100, 1000),
                'vendorname': 'Quimikao', 'size': 'Tonelada',
                'color': 'Blanco', 'style': 'Alta Pureza',
            },
            {
                'name': 'Acido Sulfurico al 98%',
                'productnumber': 'QUI-H2SO4-98',
                'description': 'Acido sulfurico concentrado al 98% para lixiviacion acida de minerales de cobre. Precio por tonelada.',
                'price': 2500, 'standardcost': sc(2500),
                'quantityonhand': random.randint(50, 500),
                'vendorname': 'BASF Mexico', 'size': 'Tonelada',
                'color': '', 'style': 'Grado Industrial 98%',
            },
            {
                'name': 'Floculante Anionico',
                'productnumber': 'QUI-FLOCULANTE',
                'description': 'Floculante polimerico anionico de alto peso molecular para espesamiento y filtracion de relaves. Saco de 25 kg.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': random.randint(50, 400),
                'vendorname': 'BASF Mexico', 'size': 'Saco 25 kg',
                'color': 'Blanco', 'style': 'Anionico Alto PM',
            },
            {
                'name': 'Cianuro de Sodio (tambor)',
                'productnumber': 'QUI-NACN-TAMBOR',
                'description': 'Cianuro de sodio en briquetas para lixiviacion de minerales de oro y plata. Tambor de 100 kg. Manejo especial requerido.',
                'price': 18000, 'standardcost': sc(18000),
                'quantityonhand': random.randint(20, 200),
                'vendorname': 'Cytec (Solvay)', 'size': 'Tambor 100 kg',
                'color': 'Blanco', 'style': 'Briquetas',
            },
            {
                'name': 'Carbon Activado (saco 25kg)',
                'productnumber': 'QUI-CARBON-ACT',
                'description': 'Carbon activado granular de cascara de coco para adsorcion de oro y plata en circuitos CIP/CIL. Saco de 25 kg.',
                'price': 2200, 'standardcost': sc(2200),
                'quantityonhand': random.randint(100, 800),
                'vendorname': 'BASF Mexico', 'size': 'Saco 25 kg',
                'color': 'Negro', 'style': 'Granular Cascara Coco',
            },
            {
                'name': 'Sulfato de Cobre',
                'productnumber': 'QUI-CUSO4',
                'description': 'Sulfato de cobre pentahidratado (CuSO4-5H2O) como activador en flotacion de esfalerita. Saco de 25 kg.',
                'price': 450, 'standardcost': sc(450),
                'quantityonhand': random.randint(200, 2000),
                'vendorname': 'Quimikao', 'size': 'Saco 25 kg',
                'color': 'Azul', 'style': 'Pentahidratado',
            },
        ]
        all_products.extend(
            create_products('Productos Quimicos', 'QUI', qui_products)
        )

        # =================================================================
        # CATEGORY 12: Servicios Mineros (SKU: SVC-)
        # =================================================================
        svc_products = [
            {
                'name': 'Instalacion de Tuberia HDPE por ml',
                'productnumber': 'SVC-INST-HDPE',
                'description': 'Servicio de instalacion de tuberia HDPE incluyendo preparacion de terreno, tendido, termofusion y prueba hidrostatica. Precio por metro lineal.',
                'price': 350, 'standardcost': sc(350),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,
                'vendorname': 'Servicios Propios', 'size': 'Metro Lineal',
                'color': '', 'style': 'Instalacion',
            },
            {
                'name': 'Mantenimiento Preventivo Bombas Anual',
                'productnumber': 'SVC-MANT-BOMBAS',
                'description': 'Servicio anual de mantenimiento preventivo para sistema de bombeo minero, incluye inspeccion, cambio de sellos y pruebas.',
                'price': 125000, 'standardcost': sc(125000),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,
                'vendorname': 'Servicios Propios', 'size': 'Anual',
                'color': '', 'style': 'Mantenimiento Preventivo',
            },
            {
                'name': 'Estudio de Ventilacion Minera',
                'productnumber': 'SVC-EST-VENT',
                'description': 'Estudio completo de ventilacion minera: modelado, simulacion, mediciones de campo y recomendaciones de mejora. Proyecto completo.',
                'price': 185000, 'standardcost': sc(185000),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,
                'vendorname': 'Servicios Propios', 'size': 'Proyecto',
                'color': '', 'style': 'Estudio de Ingenieria',
            },
            {
                'name': 'Capacitacion en Seguridad Minera',
                'productnumber': 'SVC-CAP-SEG',
                'description': 'Programa de capacitacion en seguridad minera para personal operativo, 40 horas. Incluye primeros auxilios, evacuacion y manejo de EPP.',
                'price': 45000, 'standardcost': sc(45000),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,
                'vendorname': 'Servicios Propios', 'size': '40 Horas',
                'color': '', 'style': 'Capacitacion',
            },
            {
                'name': 'Ingenieria de Soporte de Roca',
                'productnumber': 'SVC-ING-SOPORTE',
                'description': 'Servicio de ingenieria geotecnica para diseño de sistemas de soporte de roca, incluye mapeo, clasificacion y diseño de sostenimiento.',
                'price': 85000, 'standardcost': sc(85000),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,
                'vendorname': 'Servicios Propios', 'size': 'Proyecto',
                'color': '', 'style': 'Ingenieria Geotecnica',
            },
            {
                'name': 'Servicio de Termofusion HDPE',
                'productnumber': 'SVC-TERMOFUSION',
                'description': 'Servicio de termofusion (soldadura) de tuberia HDPE con maquina automatica, incluye prueba de calidad de junta.',
                'price': 8500, 'standardcost': sc(8500),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,
                'vendorname': 'Servicios Propios', 'size': 'Por Junta',
                'color': '', 'style': 'Termofusion',
            },
            {
                'name': 'Consultoria en Voladura',
                'productnumber': 'SVC-CONS-VOLAD',
                'description': 'Servicio de consultoria especializada en diseño de voladuras: patron de perforacion, carga, secuencia y evaluacion de resultados.',
                'price': 65000, 'standardcost': sc(65000),
                'quantityonhand': Decimal('0'),
                'producttypecode': 2,
                'vendorname': 'Servicios Propios', 'size': 'Proyecto',
                'color': '', 'style': 'Consultoria Especializada',
            },
        ]
        all_products.extend(
            create_products('Servicios Mineros', 'SVC', svc_products)
        )

        # =====================================================================
        # STEP 3: Create Price Lists
        # =====================================================================
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            '--- Paso 3: Creando Listas de Precios ---'
        ))

        today = timezone.now().date()
        end_of_year = today.replace(year=2026, month=12, day=31)

        price_lists_config = [
            {
                'name': 'Lista de Precios Mineria 2026',
                'description': 'Lista de precios base para operaciones mineras 2026. Precios de catalogo sin descuento.',
                'factor': Decimal('1.00'),
            },
            {
                'name': 'Precios Volumen - Contratos Anuales',
                'description': 'Precios con 10% de descuento para contratos anuales de suministro. Aplica a clientes con volumen garantizado.',
                'factor': Decimal('0.90'),
            },
            {
                'name': 'Precios Construccion e Infraestructura 2026',
                'description': 'Precios con 5% de descuento para proyectos de construccion e infraestructura. Aplica a contratistas y constructoras.',
                'factor': Decimal('0.95'),
            },
        ]

        created_price_lists = []
        for pl_data in price_lists_config:
            pricelist, created = PriceList.objects.get_or_create(
                name=pl_data['name'],
                defaults={
                    'description': pl_data['description'],
                    'begindate': today,
                    'enddate': end_of_year,
                    'statecode': 0,  # Active
                }
            )
            created_price_lists.append({
                'pricelist': pricelist,
                'factor': pl_data['factor'],
                'created': created,
            })
            if created:
                self.stdout.write(
                    f'  [OK] Lista creada: {pricelist.name}'
                )
            else:
                self.stdout.write(
                    f'  [--] Lista ya existe: {pricelist.name}'
                )

        # =====================================================================
        # STEP 4: Link all products to price lists
        # =====================================================================
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            '--- Paso 4: Vinculando Productos a Listas de Precios ---'
        ))

        pli_created = 0
        pli_existing = 0

        for pl_info in created_price_lists:
            pricelist = pl_info['pricelist']
            factor = pl_info['factor']
            self.stdout.write(
                f'\n  [{pricelist.name}] (factor: {factor}):'
            )
            for product in all_products:
                if product.price is not None and product.price > 0:
                    amount = (product.price * factor).quantize(
                        Decimal('0.0001'), rounding=ROUND_HALF_UP
                    )
                    _, created = PriceListItem.objects.get_or_create(
                        pricelevelid=pricelist,
                        productid=product,
                        defaults={
                            'amount': amount,
                        }
                    )
                    if created:
                        pli_created += 1
                    else:
                        pli_existing += 1

            self.stdout.write(
                f'    Productos vinculados a "{pricelist.name}"'
            )

        # =====================================================================
        # SUMMARY
        # =====================================================================
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            '============================================================'
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            '  RESUMEN DE GENERACION'
        ))
        self.stdout.write(self.style.MIGRATE_HEADING(
            '============================================================'
        ))

        total_families = Product.objects.filter(productstructure=2).count()
        total_products = Product.objects.filter(productstructure=1).count()
        total_all = Product.objects.count()
        total_pricelists = PriceList.objects.count()
        total_items = PriceListItem.objects.count()

        self.stdout.write('')
        self.stdout.write(
            f'  Familias de productos creadas:     {families_created} '
            f'(ya existian: {families_existing})'
        )
        self.stdout.write(
            f'  Productos individuales creados:     {products_created} '
            f'(ya existian: {products_existing})'
        )
        self.stdout.write(
            f'  Items de lista de precios creados:  {pli_created} '
            f'(ya existian: {pli_existing})'
        )
        self.stdout.write('')
        self.stdout.write(f'  --- Totales en Base de Datos ---')
        self.stdout.write(f'  Familias de productos (total):     {total_families}')
        self.stdout.write(f'  Productos individuales (total):    {total_products}')
        self.stdout.write(f'  Todos los productos (total):       {total_all}')
        self.stdout.write(f'  Listas de precios (total):         {total_pricelists}')
        self.stdout.write(f'  Items en listas de precios (total): {total_items}')
        self.stdout.write('')

        # Category breakdown
        self.stdout.write(f'  --- Desglose por Categoria ---')
        for fam_data in families_data:
            prefix = fam_data['productnumber'].replace('FAM-', '')
            family = family_map.get(prefix)
            if family:
                count = Product.objects.filter(
                    parentproductid=family, productstructure=1
                ).count()
                self.stdout.write(
                    f'  {fam_data["name"]:<35} {count:>3} productos'
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            '[SUCCESS] Catalogo de productos de mineria/construccion '
            'generado exitosamente.'
        ))
