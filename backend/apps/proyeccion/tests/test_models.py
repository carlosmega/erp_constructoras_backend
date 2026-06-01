"""Tests for ConceptPriceCatalog models."""

import pytest
from decimal import Decimal
from django.db import IntegrityError

from apps.proyeccion.models import (
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
)
from .factories import (
    ConceptPriceCatalogItemFactory,
    SICTCatalogItemFactory,
    ManualCatalogItemFactory,
    ConceptPriceReferenceFactory,
)


@pytest.mark.unit
@pytest.mark.django_db
class TestCatalogSourceCodeEnum:
    """Tests for CatalogSourceCode enum values."""

    def test_sict_value(self):
        assert CatalogSourceCode.SICT == 0

    def test_historico_value(self):
        assert CatalogSourceCode.HISTORICO == 1

    def test_manual_value(self):
        assert CatalogSourceCode.MANUAL == 2

    def test_sict_label(self):
        assert CatalogSourceCode.SICT.label == 'SICT'

    def test_historico_label(self):
        assert CatalogSourceCode.HISTORICO.label == 'Histórico'

    def test_manual_label(self):
        assert CatalogSourceCode.MANUAL.label == 'Manual'


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogItemModel:
    """Tests for ConceptPriceCatalogItem model."""

    def test_create_with_factory(self):
        item = ConceptPriceCatalogItemFactory()
        assert item.catalogitemid is not None
        assert item.code.startswith('HIST-')
        assert item.description != ''
        assert item.source == CatalogSourceCode.HISTORICO
        assert item.statecode == 0

    def test_uuid_primary_key(self):
        item = ConceptPriceCatalogItemFactory()
        assert len(str(item.catalogitemid)) == 36  # UUID format

    def test_code_unique_constraint(self):
        ConceptPriceCatalogItemFactory(code='TEST-00001')
        with pytest.raises(IntegrityError):
            ConceptPriceCatalogItemFactory(code='TEST-00001')

    def test_sict_source_factory(self):
        item = SICTCatalogItemFactory()
        assert item.source == CatalogSourceCode.SICT
        assert item.code.startswith('SICT-')

    def test_manual_source_factory(self):
        item = ManualCatalogItemFactory()
        assert item.source == CatalogSourceCode.MANUAL
        assert item.code.startswith('MAN-')

    def test_str_representation(self):
        item = ConceptPriceCatalogItemFactory(
            code='HIST-00042',
            description='Firme de concreto fc=200 kg/cm2 de 10cm de espesor',
        )
        s = str(item)
        assert 'HIST-00042' in s
        assert 'Firme de concreto' in s

    def test_default_price_stats(self):
        item = ConceptPriceCatalogItemFactory()
        assert item.averageprice == Decimal('0')
        assert item.minprice == Decimal('0')
        assert item.maxprice == Decimal('0')
        assert item.referencecount == 0

    def test_ordering_by_code(self):
        ConceptPriceCatalogItemFactory(code='HIST-00003')
        ConceptPriceCatalogItemFactory(code='HIST-00001')
        ConceptPriceCatalogItemFactory(code='HIST-00002')
        items = list(
            ConceptPriceCatalogItem.objects.values_list('code', flat=True)
        )
        assert items == sorted(items)

    def test_audit_fields(self):
        item = ConceptPriceCatalogItemFactory()
        assert item.createdon is not None
        assert item.modifiedon is not None
        assert item.createdby is not None
        assert item.modifiedby is not None

    def test_update_price_stats(self):
        item = ConceptPriceCatalogItemFactory()
        ConceptPriceReferenceFactory(catalogitemid=item, unitprice=Decimal('100'))
        ConceptPriceReferenceFactory(catalogitemid=item, unitprice=Decimal('300'))
        ConceptPriceReferenceFactory(catalogitemid=item, unitprice=Decimal('200'))

        item.update_price_stats()

        assert item.averageprice == Decimal('200')
        assert item.minprice == Decimal('100')
        assert item.maxprice == Decimal('300')
        assert item.referencecount == 3

    def test_update_price_stats_empty(self):
        item = ConceptPriceCatalogItemFactory()
        item.update_price_stats()
        assert item.averageprice == 0
        assert item.referencecount == 0

    def test_update_price_stats_ignores_inactive(self):
        item = ConceptPriceCatalogItemFactory()
        ConceptPriceReferenceFactory(catalogitemid=item, unitprice=Decimal('100'))
        ConceptPriceReferenceFactory(
            catalogitemid=item, unitprice=Decimal('999'), statecode=1,
        )

        item.update_price_stats()

        assert item.referencecount == 1
        assert item.averageprice == Decimal('100')

    def test_description_textfield(self):
        long_desc = 'x' * 2000
        item = ConceptPriceCatalogItemFactory(description=long_desc)
        item.save()
        item.refresh_from_db()
        assert len(item.description) == 2000


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceReferenceModel:
    """Tests for ConceptPriceReference model."""

    def test_create_with_factory(self):
        ref = ConceptPriceReferenceFactory()
        assert ref.referenceid is not None
        assert ref.catalogitemid is not None
        assert ref.projectname != ''
        assert ref.unitprice > 0
        assert ref.statecode == 0

    def test_uuid_primary_key(self):
        ref = ConceptPriceReferenceFactory()
        assert len(str(ref.referenceid)) == 36

    def test_str_representation(self):
        ref = ConceptPriceReferenceFactory(
            projectname='Cumbres Elite',
            unitprice=Decimal('1500.00'),
        )
        s = str(ref)
        assert 'Cumbres Elite' in s
        assert '1500' in s

    def test_cascade_delete(self):
        """Deleting a catalog item should cascade to its references."""
        item = ConceptPriceCatalogItemFactory()
        item_id = item.catalogitemid
        ConceptPriceReferenceFactory(catalogitemid=item)
        ConceptPriceReferenceFactory(catalogitemid=item)
        assert ConceptPriceReference.objects.filter(catalogitemid_id=item_id).count() == 2

        item.delete()
        assert ConceptPriceReference.objects.filter(catalogitemid_id=item_id).count() == 0

    def test_ordering_by_projectname(self):
        item = ConceptPriceCatalogItemFactory()
        ConceptPriceReferenceFactory(catalogitemid=item, projectname='Zeta')
        ConceptPriceReferenceFactory(catalogitemid=item, projectname='Alpha')
        ConceptPriceReferenceFactory(catalogitemid=item, projectname='Beta')
        refs = list(
            ConceptPriceReference.objects
            .filter(catalogitemid=item)
            .values_list('projectname', flat=True)
        )
        assert refs == sorted(refs)

    def test_nullable_quantity(self):
        ref = ConceptPriceReferenceFactory(quantity=None)
        ref.refresh_from_db()
        assert ref.quantity is None

    def test_nullable_totalamount(self):
        ref = ConceptPriceReferenceFactory(totalamount=None)
        ref.refresh_from_db()
        assert ref.totalamount is None

    def test_audit_fields(self):
        ref = ConceptPriceReferenceFactory()
        assert ref.createdon is not None
        assert ref.modifiedon is not None
        assert ref.createdby is not None

    def test_multiple_references_per_item(self):
        item = ConceptPriceCatalogItemFactory()
        for name in ['Cumbres Elite', 'Valle', 'Swiss Lab Mty']:
            ConceptPriceReferenceFactory(catalogitemid=item, projectname=name)
        assert item.price_references.count() == 3


@pytest.mark.unit
@pytest.mark.django_db
def test_unitcostbreakdown_has_payment_lag_fields():
    from apps.proyeccion.tests.factories import UnitCostBreakdownFactory
    line = UnitCostBreakdownFactory()
    assert line.paymentlagperiods is None
    assert line.lineversion == 0
    line.paymentlagperiods = 3
    line.lineversion = 1
    line.save()
    line.refresh_from_db()
    assert line.paymentlagperiods == 3
    assert line.lineversion == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_indirectcostdetail_has_payment_lag_fields():
    from apps.proyeccion.tests.factories import IndirectCostDetailFactory
    line = IndirectCostDetailFactory()
    assert line.paymentlagperiods is None
    assert line.lineversion == 0
    line.paymentlagperiods = 5
    line.lineversion = 1
    line.save()
    line.refresh_from_db()
    assert line.paymentlagperiods == 5
    assert line.lineversion == 1


@pytest.mark.unit
@pytest.mark.django_db
class TestProyeccionAuditTrail:
    """UnitCostBreakdown / ExternalCostItem / FamilyTemplateItem migraron a
    AuditMixin: deben exponer el audit trail CDS de 4 campos
    (createdon/modifiedon + createdby/modifiedby), siendo createdby/modifiedby
    nullable (poblados por la capa de servicio).
    """

    def test_unitcostbreakdown_audit_trail(self):
        from apps.users.tests.factories import SystemUserFactory
        from apps.proyeccion.tests.factories import UnitCostBreakdownFactory

        user = SystemUserFactory()
        bd = UnitCostBreakdownFactory(createdby=user, modifiedby=user)
        bd.refresh_from_db()

        assert bd.createdon is not None and bd.modifiedon is not None
        assert bd.createdby == user and bd.modifiedby == user
        # related_name del mixin: %(class)s_created / %(class)s_modified
        assert bd in user.unitcostbreakdown_created.all()
        assert bd in user.unitcostbreakdown_modified.all()

    def test_externalcostitem_audit_fields_nullable(self):
        from apps.proyeccion.tests.factories import ExternalCostItemFactory

        item = ExternalCostItemFactory()
        item.refresh_from_db()
        # Sin poblar → nullable, no rompe la creación.
        assert item.createdby is None
        assert item.modifiedby is None
        assert item.createdon is not None and item.modifiedon is not None

    def test_familytemplateitem_audit_trail(self):
        from apps.users.tests.factories import SystemUserFactory
        from apps.proyeccion.tests.factories import FamilyTemplateItemFactory

        user = SystemUserFactory()
        item = FamilyTemplateItemFactory(createdby=user)
        item.refresh_from_db()

        assert item.createdby == user
        assert item in user.familytemplateitem_created.all()
