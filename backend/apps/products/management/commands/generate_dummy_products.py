"""
Django management command to generate dummy products and price lists.
Usage: python manage.py generate_dummy_products
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from apps.products.models import Product, PriceList, PriceListItem
from apps.users.models import SystemUser
import random


class Command(BaseCommand):
    help = 'Genera productos y listas de precios dummy para pruebas'

    def handle(self, *args, **options):
        self.stdout.write('[INFO] Generando datos dummy para Products...')

        # Get a user to assign as owner (preferably admin)
        try:
            owner = SystemUser.objects.filter(isdisabled=False).first()
            if not owner:
                self.stdout.write(self.style.ERROR('[ERROR] No se encontró ningún usuario activo'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[ERROR] Error al obtener usuario: {e}'))
            return

        # Sample products data (tech/software focused)
        products_data = [
            {
                'name': 'Microsoft Office 365 Business Premium',
                'productnumber': 'MS-O365-BP-001',
                'description': 'Suscripción anual de Office 365 Business Premium con Teams, Exchange, SharePoint',
                'price': Decimal('299.99'),
                'standardcost': Decimal('180.00'),
                'quantityonhand': 1000,
                'productstructure': 1,  # Product
                'producttypecode': 1,   # Sales Inventory
            },
            {
                'name': 'Microsoft Dynamics 365 Sales Professional',
                'productnumber': 'MS-D365-SP-001',
                'description': 'Licencia mensual de Dynamics 365 Sales Professional',
                'price': Decimal('65.00'),
                'standardcost': Decimal('40.00'),
                'quantityonhand': 500,
                'productstructure': 1,
                'producttypecode': 1,
            },
            {
                'name': 'Azure Cloud Services - Paquete Básico',
                'productnumber': 'AZ-CLOUD-BASIC-001',
                'description': 'Paquete mensual de servicios Azure: VM, Storage, Database',
                'price': Decimal('450.00'),
                'standardcost': Decimal('280.00'),
                'quantityonhand': 999,
                'productstructure': 2,  # Product Bundle
                'producttypecode': 2,   # Services
            },
            {
                'name': 'Consultoría CRM - Implementación',
                'productnumber': 'SERV-CRM-IMPL-001',
                'description': 'Servicio de consultoría para implementación de CRM (40 horas)',
                'price': Decimal('4800.00'),
                'standardcost': Decimal('2400.00'),
                'quantityonhand': 0,  # Service has no inventory
                'productstructure': 1,
                'producttypecode': 2,
            },
            {
                'name': 'Capacitación Office 365 - Curso Básico',
                'productnumber': 'TRAIN-O365-BASIC-001',
                'description': 'Curso de capacitación básica de Office 365 (8 horas)',
                'price': Decimal('800.00'),
                'standardcost': Decimal('400.00'),
                'quantityonhand': 0,
                'productstructure': 1,
                'producttypecode': 2,
            },
            {
                'name': 'Surface Laptop 5 - 13.5" i7 16GB',
                'productnumber': 'HW-SURFACE-LP5-001',
                'description': 'Microsoft Surface Laptop 5, Intel i7, 16GB RAM, 512GB SSD',
                'price': Decimal('1599.99'),
                'standardcost': Decimal('1200.00'),
                'quantityonhand': 25,
                'productstructure': 1,
                'producttypecode': 1,
            },
            {
                'name': 'Power BI Pro - Licencia Mensual',
                'productnumber': 'MS-PBI-PRO-001',
                'description': 'Licencia mensual de Power BI Pro para análisis de datos',
                'price': Decimal('9.99'),
                'standardcost': Decimal('5.00'),
                'quantityonhand': 2000,
                'productstructure': 1,
                'producttypecode': 1,
            },
            {
                'name': 'Soporte Técnico Premium - Mensual',
                'productnumber': 'SERV-SUPPORT-PREM-001',
                'description': 'Soporte técnico premium 24/7 con SLA de 2 horas',
                'price': Decimal('299.00'),
                'standardcost': Decimal('150.00'),
                'quantityonhand': 0,
                'productstructure': 1,
                'producttypecode': 2,
            },
        ]

        # Create products
        created_products = []
        for product_data in products_data:
            product, created = Product.objects.get_or_create(
                productnumber=product_data['productnumber'],
                defaults={
                    **product_data,
                    'createdby': owner,
                    'modifiedby': owner,
                    'statecode': 0,  # Active
                    'statuscode': 1,  # Available
                }
            )
            if created:
                created_products.append(product)
                self.stdout.write(f'[OK] Producto creado: {product.name}')
            else:
                self.stdout.write(f'[INFO] Producto ya existe: {product.name}')

        # Create Price Lists
        price_lists_data = [
            {
                'name': 'Precios Corporativos 2025',
                'description': 'Lista de precios especiales para clientes corporativos',
                'begindate': timezone.now().date(),
                'enddate': timezone.now().date().replace(year=2025, month=12, day=31),
            },
            {
                'name': 'Precios Educación 2025',
                'description': 'Descuentos especiales para instituciones educativas',
                'begindate': timezone.now().date(),
                'enddate': timezone.now().date().replace(year=2025, month=12, day=31),
            },
            {
                'name': 'Promoción Fin de Año 2024',
                'description': 'Precios promocionales de fin de año',
                'begindate': timezone.now().date().replace(month=12, day=1),
                'enddate': timezone.now().date().replace(month=12, day=31),
            },
        ]

        created_pricelists = []
        for pricelist_data in price_lists_data:
            pricelist, created = PriceList.objects.get_or_create(
                name=pricelist_data['name'],
                defaults={
                    **pricelist_data,
                    'statecode': 0,  # Active
                }
            )
            if created:
                created_pricelists.append(pricelist)
                self.stdout.write(f'[OK] Lista de precios creada: {pricelist.name}')
            else:
                self.stdout.write(f'[INFO] Lista de precios ya existe: {pricelist.name}')

        # Create Price List Items (link products to price lists with discounts)
        if created_products and created_pricelists:
            for pricelist in created_pricelists:
                for product in created_products:
                    # Apply different discount percentages based on price list
                    if 'Corporativos' in pricelist.name:
                        discount_factor = Decimal('0.90')  # 10% discount
                    elif 'Educación' in pricelist.name:
                        discount_factor = Decimal('0.80')  # 20% discount
                    elif 'Promoción' in pricelist.name:
                        discount_factor = Decimal('0.85')  # 15% discount
                    else:
                        discount_factor = Decimal('1.00')

                    special_price = product.price * discount_factor if product.price else Decimal('0.00')

                    item, created = PriceListItem.objects.get_or_create(
                        pricelevelid=pricelist,
                        productid=product,
                        defaults={
                            'amount': special_price,
                        }
                    )
                    if created:
                        self.stdout.write(f'[OK] Item agregado: {product.name} a {pricelist.name} (${special_price})')

        # Summary
        total_products = Product.objects.count()
        total_pricelists = PriceList.objects.count()
        total_items = PriceListItem.objects.count()

        self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Generación completada:'))
        self.stdout.write(f'  - Productos totales: {total_products}')
        self.stdout.write(f'  - Listas de precios totales: {total_pricelists}')
        self.stdout.write(f'  - Items en listas: {total_items}')
