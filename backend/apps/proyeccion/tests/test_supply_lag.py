"""Tests for supply lag fields in SupplyExplosionService (consolidated + bulk set_supply_lag)."""

import pytest
from decimal import Decimal

from apps.proyeccion.models import UnitCostBreakdown
from apps.proyeccion.services import SupplyExplosionService
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory, ConceptFamilyFactory, ConceptSubfamilyFactory,
    BudgetConceptFactory, UnitCostBreakdownFactory, SupplyCatalogItemFactory,
)
from apps.users.tests.factories import SystemUserFactory


@pytest.fixture
def user(db):
    return SystemUserFactory()


@pytest.fixture
def project_with_supply(db, user):
    p = EstimationProjectFactory(ownerid=user)
    fam = ConceptFamilyFactory(projectid=p)
    sub = ConceptSubfamilyFactory(familyid=fam, projectid=p)
    c1 = BudgetConceptFactory(projectid=p, subfamilyid=sub, quantity=Decimal('1'))
    c2 = BudgetConceptFactory(projectid=p, subfamilyid=sub, quantity=Decimal('1'))
    supply = SupplyCatalogItemFactory(code='CEM-01', description='Cemento', unit='kg', supplytype=1)
    UnitCostBreakdownFactory(conceptid=c1, supplyid=supply, categorycode=1, quantity=Decimal('2'), amount=Decimal('100'), paymentlagperiods=None)
    UnitCostBreakdownFactory(conceptid=c2, supplyid=supply, categorycode=1, quantity=Decimal('3'), amount=Decimal('150'), paymentlagperiods=None)
    return p, supply


@pytest.mark.integration
def test_consolidated_includes_supplyid_and_lag(project_with_supply, user):
    p, supply = project_with_supply
    rows = SupplyExplosionService.generate_consolidated(p.estimationprojectid, user)
    row = next(r for r in rows if r['supplycode'] == 'CEM-01')
    assert row['supplyid'] == supply.supplyid
    assert row['paymentlagperiods'] is None


@pytest.mark.integration
def test_set_supply_lag_bulk_updates_all_lines(project_with_supply, user):
    p, supply = project_with_supply
    n = SupplyExplosionService.set_supply_lag(p.estimationprojectid, supply.supplyid, 3, user)
    assert n == 2
    lines = UnitCostBreakdown.objects.filter(conceptid__projectid=p, supplyid=supply)
    assert all(l.paymentlagperiods == 3 for l in lines)
    assert all(l.lineversion >= 1 for l in lines)
    rows = SupplyExplosionService.generate_consolidated(p.estimationprojectid, user)
    row = next(r for r in rows if r['supplycode'] == 'CEM-01')
    assert row['paymentlagperiods'] == 3


@pytest.mark.integration
def test_consolidated_lag_none_when_mixed(project_with_supply, user):
    p, supply = project_with_supply
    lines = list(UnitCostBreakdown.objects.filter(conceptid__projectid=p, supplyid=supply))
    lines[0].paymentlagperiods = 2; lines[0].save()
    lines[1].paymentlagperiods = 5; lines[1].save()
    rows = SupplyExplosionService.generate_consolidated(p.estimationprojectid, user)
    row = next(r for r in rows if r['supplycode'] == 'CEM-01')
    assert row['paymentlagperiods'] is None


@pytest.mark.integration
def test_set_supply_lag_validates_range(project_with_supply, user):
    p, supply = project_with_supply
    with pytest.raises(Exception):
        SupplyExplosionService.set_supply_lag(p.estimationprojectid, supply.supplyid, 999, user)
    SupplyExplosionService.set_supply_lag(p.estimationprojectid, supply.supplyid, None, user)
