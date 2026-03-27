"""Tests for ConceptPriceCatalogService."""

import pytest
from uuid import uuid4
from decimal import Decimal

from apps.proyeccion.models import (
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
)
from apps.proyeccion.services import ConceptPriceCatalogService
from apps.proyeccion.schemas import (
    CreateConceptPriceCatalogItemDto,
    UpdateConceptPriceCatalogItemDto,
    CreateConceptPriceReferenceDto,
)
from apps.users.tests.factories import SalespersonFactory
from .factories import (
    ConceptPriceCatalogItemFactory,
    ConceptPriceReferenceFactory,
)


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceList:
    """Tests for ConceptPriceCatalogService.list_items."""

    def test_list_returns_active_items(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(statecode=0)
        ConceptPriceCatalogItemFactory(statecode=0)
        ConceptPriceCatalogItemFactory(statecode=1)  # inactive

        result = ConceptPriceCatalogService.list_items(user)
        assert result.count() == 2

    def test_list_filter_by_source(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(source=CatalogSourceCode.HISTORICO)
        ConceptPriceCatalogItemFactory(source=CatalogSourceCode.HISTORICO)
        ConceptPriceCatalogItemFactory(source=CatalogSourceCode.SICT)

        result = ConceptPriceCatalogService.list_items(
            user, source=CatalogSourceCode.HISTORICO,
        )
        assert result.count() == 2

    def test_list_filter_by_unit(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(unit='m2')
        ConceptPriceCatalogItemFactory(unit='m2')
        ConceptPriceCatalogItemFactory(unit='pza')

        result = ConceptPriceCatalogService.list_items(user, unit='m2')
        assert result.count() == 2

    def test_list_search_by_description(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(description='Firme de concreto fc 200')
        ConceptPriceCatalogItemFactory(description='Muro de tablaroca')
        ConceptPriceCatalogItemFactory(description='Concreto premezclado')

        result = ConceptPriceCatalogService.list_items(user, search='concreto')
        assert result.count() == 2

    def test_list_search_by_code(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(code='HIST-00042')
        ConceptPriceCatalogItemFactory(code='HIST-00043')

        result = ConceptPriceCatalogService.list_items(user, search='00042')
        assert result.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceCreate:
    """Tests for ConceptPriceCatalogService.create_item."""

    def test_create_with_auto_code(self):
        user = SalespersonFactory()
        dto = CreateConceptPriceCatalogItemDto(
            description='Demolicion de muro de block',
            unit='m2',
            source=CatalogSourceCode.HISTORICO,
        )

        item = ConceptPriceCatalogService.create_item(dto, user)

        assert item.catalogitemid is not None
        assert item.code.startswith('HIST-')
        assert item.description == 'Demolicion de muro de block'
        assert item.unit == 'm2'
        assert item.createdby == user

    def test_create_with_explicit_code(self):
        user = SalespersonFactory()
        dto = CreateConceptPriceCatalogItemDto(
            code='CUSTOM-001',
            description='Test concept',
            unit='pza',
        )

        item = ConceptPriceCatalogService.create_item(dto, user)
        assert item.code == 'CUSTOM-001'

    def test_create_sict_source(self):
        user = SalespersonFactory()
        dto = CreateConceptPriceCatalogItemDto(
            description='Terraceria compactada',
            unit='m3',
            source=CatalogSourceCode.SICT,
        )

        item = ConceptPriceCatalogService.create_item(dto, user)
        assert item.source == CatalogSourceCode.SICT
        assert item.code.startswith('SICT-')

    def test_auto_code_increments(self):
        user = SalespersonFactory()
        dto1 = CreateConceptPriceCatalogItemDto(
            description='Concepto A', unit='m2',
            source=CatalogSourceCode.MANUAL,
        )
        dto2 = CreateConceptPriceCatalogItemDto(
            description='Concepto B', unit='m2',
            source=CatalogSourceCode.MANUAL,
        )

        item1 = ConceptPriceCatalogService.create_item(dto1, user)
        item2 = ConceptPriceCatalogService.create_item(dto2, user)

        num1 = int(item1.code.split('-')[-1])
        num2 = int(item2.code.split('-')[-1])
        assert num2 == num1 + 1


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceUpdate:
    """Tests for ConceptPriceCatalogService.update_item."""

    def test_update_description(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory(description='Original')

        dto = UpdateConceptPriceCatalogItemDto(description='Updated')
        updated = ConceptPriceCatalogService.update_item(
            item.catalogitemid, dto, user,
        )

        assert updated.description == 'Updated'
        assert updated.modifiedby == user

    def test_update_partial(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory(
            description='Original', unit='m2',
        )

        dto = UpdateConceptPriceCatalogItemDto(unit='ml')
        updated = ConceptPriceCatalogService.update_item(
            item.catalogitemid, dto, user,
        )

        assert updated.unit == 'ml'
        assert updated.description == 'Original'  # unchanged

    def test_update_not_found(self):
        user = SalespersonFactory()
        dto = UpdateConceptPriceCatalogItemDto(description='Nope')

        with pytest.raises(Exception, match='not found'):
            ConceptPriceCatalogService.update_item(uuid4(), dto, user)


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceDelete:
    """Tests for ConceptPriceCatalogService.delete_item."""

    def test_soft_delete(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()

        deleted = ConceptPriceCatalogService.delete_item(
            item.catalogitemid, user,
        )

        assert deleted.statecode == 1
        assert deleted.modifiedby == user

    def test_delete_not_found(self):
        user = SalespersonFactory()
        with pytest.raises(Exception, match='not found'):
            ConceptPriceCatalogService.delete_item(uuid4(), user)

    def test_soft_deleted_excluded_from_list(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()
        ConceptPriceCatalogService.delete_item(item.catalogitemid, user)

        result = ConceptPriceCatalogService.list_items(user)
        assert result.count() == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceReferenceService:
    """Tests for ConceptPriceCatalogService reference methods."""

    def test_list_references(self):
        item = ConceptPriceCatalogItemFactory()
        ConceptPriceReferenceFactory(catalogitemid=item, projectname='Alpha')
        ConceptPriceReferenceFactory(catalogitemid=item, projectname='Beta')
        ConceptPriceReferenceFactory(
            catalogitemid=item, projectname='Inactive', statecode=1,
        )

        refs = ConceptPriceCatalogService.list_references(item.catalogitemid)
        assert refs.count() == 2

    def test_create_reference(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()

        dto = CreateConceptPriceReferenceDto(
            catalogitemid=item.catalogitemid,
            projectname='Cumbres Elite',
            unitprice=Decimal('1500.00'),
            quantity=Decimal('10'),
            totalamount=Decimal('15000.00'),
        )

        ref = ConceptPriceCatalogService.create_reference(dto, user)

        assert ref.referenceid is not None
        assert ref.projectname == 'Cumbres Elite'
        assert ref.unitprice == Decimal('1500.00')
        assert ref.createdby == user

    def test_create_reference_updates_parent_stats(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()

        dto1 = CreateConceptPriceReferenceDto(
            catalogitemid=item.catalogitemid,
            projectname='Project A',
            unitprice=Decimal('100.00'),
        )
        dto2 = CreateConceptPriceReferenceDto(
            catalogitemid=item.catalogitemid,
            projectname='Project B',
            unitprice=Decimal('300.00'),
        )

        ConceptPriceCatalogService.create_reference(dto1, user)
        ConceptPriceCatalogService.create_reference(dto2, user)

        item.refresh_from_db()
        assert item.averageprice == Decimal('200')
        assert item.minprice == Decimal('100.00')
        assert item.maxprice == Decimal('300.00')
        assert item.referencecount == 2

    def test_delete_reference(self):
        user = SalespersonFactory()
        ref = ConceptPriceReferenceFactory()

        deleted = ConceptPriceCatalogService.delete_reference(
            ref.referenceid, user,
        )

        assert deleted.statecode == 1

    def test_delete_reference_updates_parent_stats(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()
        ref1 = ConceptPriceReferenceFactory(
            catalogitemid=item, unitprice=Decimal('100'),
        )
        ConceptPriceReferenceFactory(
            catalogitemid=item, unitprice=Decimal('200'),
        )
        item.update_price_stats()
        item.save()
        assert item.referencecount == 2

        ConceptPriceCatalogService.delete_reference(ref1.referenceid, user)

        item.refresh_from_db()
        assert item.referencecount == 1
        assert item.averageprice == Decimal('200')

    def test_delete_reference_not_found(self):
        user = SalespersonFactory()
        with pytest.raises(Exception, match='not found'):
            ConceptPriceCatalogService.delete_reference(uuid4(), user)


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceBulkImport:
    """Tests for ConceptPriceCatalogService.bulk_import."""

    def test_bulk_import_creates_items_and_refs(self):
        user = SalespersonFactory()
        items = [
            {
                'description': 'Firme de concreto fc 200',
                'unit': 'm2',
                'source': CatalogSourceCode.HISTORICO,
                'references': [
                    {'projectname': 'Cumbres Elite', 'unitprice': Decimal('445.00')},
                    {'projectname': 'Valle', 'unitprice': Decimal('368.75')},
                ],
            },
            {
                'description': 'Pintura vinilica en muros',
                'unit': 'm2',
                'source': CatalogSourceCode.HISTORICO,
                'references': [
                    {'projectname': 'Cumbres Elite', 'unitprice': Decimal('88.00')},
                ],
            },
        ]

        result = ConceptPriceCatalogService.bulk_import(items, user)

        assert result['created'] == 2
        assert result['references_created'] == 3

    def test_bulk_import_skips_zero_prices(self):
        user = SalespersonFactory()
        items = [
            {
                'description': 'Concepto con precios mixtos',
                'unit': 'pza',
                'references': [
                    {'projectname': 'A', 'unitprice': Decimal('100')},
                    {'projectname': 'B', 'unitprice': Decimal('0')},  # should skip
                    {'projectname': 'C', 'unitprice': Decimal('-5')},  # should skip
                ],
            },
        ]

        result = ConceptPriceCatalogService.bulk_import(items, user)

        assert result['created'] == 1
        assert result['references_created'] == 1

    def test_bulk_import_computes_stats(self):
        user = SalespersonFactory()
        items = [
            {
                'description': 'Concepto stats test',
                'unit': 'm2',
                'references': [
                    {'projectname': 'A', 'unitprice': Decimal('100')},
                    {'projectname': 'B', 'unitprice': Decimal('200')},
                    {'projectname': 'C', 'unitprice': Decimal('300')},
                ],
            },
        ]

        ConceptPriceCatalogService.bulk_import(items, user)

        item = ConceptPriceCatalogItem.objects.get(
            description='Concepto stats test',
        )
        assert item.averageprice == Decimal('200')
        assert item.minprice == Decimal('100')
        assert item.maxprice == Decimal('300')
        assert item.referencecount == 3

    def test_bulk_import_auto_generates_codes(self):
        user = SalespersonFactory()
        items = [
            {'description': 'Concepto 1', 'unit': 'm2', 'references': [
                {'projectname': 'A', 'unitprice': Decimal('100')},
            ]},
            {'description': 'Concepto 2', 'unit': 'm2', 'references': [
                {'projectname': 'A', 'unitprice': Decimal('200')},
            ]},
        ]

        ConceptPriceCatalogService.bulk_import(items, user)

        codes = list(
            ConceptPriceCatalogItem.objects
            .filter(description__startswith='Concepto')
            .values_list('code', flat=True)
            .order_by('code')
        )
        assert len(codes) == 2
        assert all(c.startswith('HIST-') for c in codes)
