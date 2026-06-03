import pytest
from decimal import Decimal

from apps.proyeccion.models import IndirectCostDetail, EstimationFinancialSettings
from apps.proyeccion.schemas import ComputeBondsOverridesDto
from apps.proyeccion.services import IndirectCostDetailService
from apps.proyeccion.tests.factories import EstimationProjectFactory, EstimationFinancialSettingsFactory
from apps.users.tests.factories import SystemUserFactory


@pytest.fixture
def user(db):
    return SystemUserFactory()


@pytest.fixture
def project(db, user):
    # Contrato s/IVA = 1,000,000 ; Anticipo s/IVA = 300,000
    p = EstimationProjectFactory(estimatedcontractamount=Decimal('1000000'), ownerid=user)
    EstimationFinancialSettingsFactory(
        projectid=p, advanceamountnotax=Decimal('300000'),
    )
    return p


def _by_key(project):
    return {d.formulakey: d for d in IndirectCostDetail.objects.filter(projectid=project)}


@pytest.mark.integration
def test_compute_bonds_formulas(project, user):
    dto = ComputeBondsOverridesDto()
    lines = IndirectCostDetailService.compute_bond_and_tax_lines(
        project.estimationprojectid, user, overrides=dto)
    assert len(lines) == 5
    by = _by_key(project)
    assert by['bond_anticipo'].amount == Decimal('4524.00')       # 300000*1.16*0.013
    assert by['bond_anticipo'].categorycode == 'C7'
    assert by['bond_cumplimiento'].amount == Decimal('17000.00')  # 1000000*0.017
    assert by['bond_vicios'].amount == Decimal('3900.00')         # 300000*0.013
    assert by['insurance_rc'].amount == Decimal('1276.00')        # 1000000*1.16*0.0011
    assert by['tax_isr'].amount == Decimal('27540.00')            # 1000000*0.0918*0.30
    assert by['tax_isr'].categorycode == 'C8'
    assert by['tax_isr'].units == Decimal('1')
    assert by['tax_isr'].months == Decimal('1')
    assert by['tax_isr'].monthlycost == Decimal('27540.00')


@pytest.mark.integration
def test_compute_bonds_idempotent(project, user):
    dto = ComputeBondsOverridesDto()
    IndirectCostDetailService.compute_bond_and_tax_lines(project.estimationprojectid, user, overrides=dto)
    IndirectCostDetailService.compute_bond_and_tax_lines(project.estimationprojectid, user, overrides=dto)
    assert IndirectCostDetail.objects.filter(projectid=project).count() == 5


@pytest.mark.integration
def test_compute_bonds_overwrites_manual_edit(project, user):
    dto = ComputeBondsOverridesDto()
    IndirectCostDetailService.compute_bond_and_tax_lines(project.estimationprojectid, user, overrides=dto)
    line = IndirectCostDetail.objects.get(projectid=project, formulakey='bond_anticipo')
    line.monthlycost = Decimal('999999'); line.amount = Decimal('999999'); line.save()
    IndirectCostDetailService.compute_bond_and_tax_lines(project.estimationprojectid, user, overrides=dto)
    line.refresh_from_db()
    assert line.amount == Decimal('4524.00')


@pytest.mark.integration
def test_compute_bonds_overrides(project, user):
    dto = ComputeBondsOverridesDto(
        contract_notax=Decimal('2000000'), advance_notax=Decimal('0'),
        bonded_value=Decimal('500000'), rate_cumplimiento=Decimal('0.02'))
    IndirectCostDetailService.compute_bond_and_tax_lines(project.estimationprojectid, user, overrides=dto)
    by = _by_key(project)
    assert by['bond_cumplimiento'].amount == Decimal('10000.00')  # 500000*0.02
    assert by['tax_isr'].amount == Decimal('55080.00')            # 2000000*0.0918*0.30
    assert by['bond_anticipo'].amount == Decimal('0.00')


@pytest.mark.integration
def test_compute_bonds_zero_bases(db, user):
    p = EstimationProjectFactory(estimatedcontractamount=Decimal('0'), ownerid=user)
    dto = ComputeBondsOverridesDto()
    lines = IndirectCostDetailService.compute_bond_and_tax_lines(p.estimationprojectid, user, overrides=dto)
    assert len(lines) == 5
    assert all(line.amount == Decimal('0.00') for line in lines)


@pytest.mark.contract
def test_compute_bonds_endpoint(project, user):
    from django.test import Client
    c = Client()
    c.force_login(user)
    url = f"/api/proyeccion/projects/{project.estimationprojectid}/indirect-cost-details/compute-bonds/"
    resp = c.post(url, data={}, content_type="application/json")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
    keys = {row["formulakey"] for row in body}
    assert keys == {"bond_anticipo", "bond_cumplimiento", "bond_vicios", "insurance_rc", "tax_isr"}
