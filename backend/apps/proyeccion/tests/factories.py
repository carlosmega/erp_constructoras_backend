"""Factory Boy factories for Proyeccion models."""

import factory
from factory.django import DjangoModelFactory
from decimal import Decimal

from apps.proyeccion.models import (
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
    EstimationProject,
    ConceptFamily,
    ConceptSubfamily,
    FamilyTemplateSet,
    FamilyTemplateItem,
)
from apps.users.tests.factories import SalespersonFactory, SystemUserFactory


class ConceptPriceCatalogItemFactory(DjangoModelFactory):
    """Factory for creating ConceptPriceCatalogItem instances."""

    class Meta:
        model = ConceptPriceCatalogItem

    code = factory.Sequence(lambda n: f'HIST-{n + 1:05d}')
    description = factory.Faker('sentence', nb_words=12)
    unit = factory.Iterator(['m2', 'ml', 'pza', 'm3', 'kg', 'evento', 'salida'])
    source = CatalogSourceCode.HISTORICO
    category = ''
    averageprice = Decimal('0')
    minprice = Decimal('0')
    maxprice = Decimal('0')
    referencecount = 0
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class SICTCatalogItemFactory(ConceptPriceCatalogItemFactory):
    """Factory for SICT-sourced catalog items."""

    code = factory.Sequence(lambda n: f'SICT-{n + 1:05d}')
    source = CatalogSourceCode.SICT


class ManualCatalogItemFactory(ConceptPriceCatalogItemFactory):
    """Factory for manually-entered catalog items."""

    code = factory.Sequence(lambda n: f'MAN-{n + 1:05d}')
    source = CatalogSourceCode.MANUAL


class ConceptPriceReferenceFactory(DjangoModelFactory):
    """Factory for creating ConceptPriceReference instances."""

    class Meta:
        model = ConceptPriceReference

    catalogitemid = factory.SubFactory(ConceptPriceCatalogItemFactory)
    projectname = factory.Iterator([
        'Cumbres Elite', 'Swiss Lab Mty', 'Valle',
        'Polab Morelos', 'Jenner Texcoco', 'La Selva Tripp',
    ])
    projectlocation = ''
    unitprice = factory.Faker(
        'pydecimal', left_digits=5, right_digits=2, positive=True,
        min_value=50, max_value=50000,
    )
    quantity = factory.Faker(
        'pydecimal', left_digits=3, right_digits=2, positive=True,
        min_value=1, max_value=500,
    )
    totalamount = factory.LazyAttribute(
        lambda o: o.unitprice * o.quantity if o.quantity else None
    )
    notes = ''
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class EstimationProjectFactory(DjangoModelFactory):
    """Factory for creating EstimationProject instances."""

    class Meta:
        model = EstimationProject

    name = factory.Sequence(lambda n: f'Test Project {n + 1}')
    description = factory.Faker('sentence', nb_words=8)
    estimationnumber = factory.Sequence(lambda n: f'EST-2026-{n + 1:03d}')
    ownerid = factory.SubFactory(SystemUserFactory)
    createdby = factory.LazyAttribute(lambda o: o.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.ownerid)
    statecode = 0


class ConceptFamilyFactory(DjangoModelFactory):
    """Factory for creating ConceptFamily instances."""

    class Meta:
        model = ConceptFamily

    projectid = factory.SubFactory(EstimationProjectFactory)
    name = factory.Sequence(lambda n: f'Family {n + 1}')
    code = factory.Sequence(lambda n: f'F{n + 1:02d}')
    sortorder = factory.Sequence(lambda n: n)
    statecode = 0
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class ConceptSubfamilyFactory(DjangoModelFactory):
    """Factory for creating ConceptSubfamily instances."""

    class Meta:
        model = ConceptSubfamily

    familyid = factory.SubFactory(ConceptFamilyFactory)
    projectid = factory.LazyAttribute(lambda o: o.familyid.projectid)
    name = factory.Sequence(lambda n: f'Subfamily {n + 1}')
    code = factory.Sequence(lambda n: f'SF{n + 1:02d}')
    sortorder = factory.Sequence(lambda n: n)
    statecode = 0
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class FamilyTemplateSetFactory(DjangoModelFactory):
    """Factory for creating FamilyTemplateSet instances."""

    class Meta:
        model = FamilyTemplateSet

    name = factory.Sequence(lambda n: f'Template Set {n + 1}')
    description = factory.Faker('sentence', nb_words=6)
    category = 'custom'
    issystem = False
    statecode = 0
    createdby = factory.SubFactory(SystemUserFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class FamilyTemplateItemFactory(DjangoModelFactory):
    """Factory for creating FamilyTemplateItem instances."""

    class Meta:
        model = FamilyTemplateItem

    templatesetid = factory.SubFactory(FamilyTemplateSetFactory)
    familycode = factory.Sequence(lambda n: f'F{n + 1:02d}')
    familyname = factory.Sequence(lambda n: f'Family {n + 1}')
    subfamilycode = factory.Sequence(lambda n: f'SF{n + 1:02d}')
    subfamilyname = factory.Sequence(lambda n: f'Subfamily {n + 1}')
    familysortorder = factory.Sequence(lambda n: n)
    subfamilysortorder = factory.Sequence(lambda n: n)
    statecode = 0
