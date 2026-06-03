import pytest
from decimal import Decimal

from apps.proyeccion.models import IndirectCostDetail, ChecklistStatusCode
from apps.proyeccion.schemas import CreateIndirectCostDetailDto, UpdateIndirectCostDetailDto
from apps.proyeccion.services import IndirectCostDetailService
from apps.proyeccion.tests.factories import EstimationProjectFactory
from apps.users.tests.factories import SystemUserFactory


@pytest.fixture
def user(db):
    return SystemUserFactory()


@pytest.fixture
def project(db, user):
    return EstimationProjectFactory(estimatedcontractamount=Decimal('1000000'), ownerid=user)


@pytest.mark.integration
def test_amount_zero_when_not_applies(project, user):
    dto = CreateIndirectCostDetailDto(
        projectid=project.estimationprojectid, categorycode='C7',
        description='X', monthlycost=Decimal('500'), units=Decimal('1'),
        months=Decimal('2'), applies=ChecklistStatusCode.NA)
    line = IndirectCostDetailService.create_detail(dto, user)
    assert line.amount == Decimal('0')


@pytest.mark.integration
def test_amount_manual_when_applies(project, user):
    dto = CreateIndirectCostDetailDto(
        projectid=project.estimationprojectid, categorycode='C7',
        description='X', monthlycost=Decimal('500'), units=Decimal('1'),
        months=Decimal('2'), applies=ChecklistStatusCode.YES)
    line = IndirectCostDetailService.create_detail(dto, user)
    assert line.amount == Decimal('1000')


@pytest.mark.integration
def test_amount_percent_driven(project, user):
    dto = CreateIndirectCostDetailDto(
        projectid=project.estimationprojectid, categorycode='C8',
        description='Supervisión', applies=ChecklistStatusCode.YES,
        percentofsale=Decimal('1.5'))
    line = IndirectCostDetailService.create_detail(dto, user)
    assert line.amount == Decimal('15000.00')


@pytest.mark.integration
def test_update_toggle_preserves_inputs(project, user):
    dto = CreateIndirectCostDetailDto(
        projectid=project.estimationprojectid, categorycode='C7',
        description='X', monthlycost=Decimal('500'), units=Decimal('1'),
        months=Decimal('2'), applies=ChecklistStatusCode.YES)
    line = IndirectCostDetailService.create_detail(dto, user)
    line = IndirectCostDetailService.update_detail(
        line.indirectcostid, UpdateIndirectCostDetailDto(applies=ChecklistStatusCode.NA), user)
    assert line.amount == Decimal('0')
    assert line.monthlycost == Decimal('500')
    line = IndirectCostDetailService.update_detail(
        line.indirectcostid, UpdateIndirectCostDetailDto(applies=ChecklistStatusCode.YES), user)
    assert line.amount == Decimal('1000')


@pytest.mark.integration
def test_calculator_lines_apply(project, user):
    from apps.proyeccion.schemas import ComputeBondsOverridesDto
    lines = IndirectCostDetailService.compute_bond_and_tax_lines(
        project.estimationprojectid, user, overrides=ComputeBondsOverridesDto())
    assert len(lines) == 5
    assert all(l.applies == ChecklistStatusCode.YES for l in lines)


@pytest.mark.integration
def test_set_checklist_state_toggle_and_percent(project, user):
    dto = CreateIndirectCostDetailDto(
        projectid=project.estimationprojectid, categorycode='C8',
        description='Supervisión', applies=ChecklistStatusCode.NA)
    line = IndirectCostDetailService.create_detail(dto, user)
    assert line.amount == Decimal('0')
    line = IndirectCostDetailService.set_checklist_state(
        line.indirectcostid, user, applies=ChecklistStatusCode.YES, percentofsale=Decimal('2'))
    assert line.applies == ChecklistStatusCode.YES
    assert line.amount == Decimal('20000.00')  # 2% of 1,000,000


@pytest.mark.integration
def test_seed_external_checklist(project, user):
    lines = IndirectCostDetailService.seed_external_checklist(project.estimationprojectid, user)
    assert len(lines) == 20
    by_desc = {l.description: l for l in lines}
    assert by_desc['Fianza Anticipo (Aprox 1.3% del valor del anticipo c/IVA)'].formulakey == 'bond_anticipo'
    assert by_desc['Fianza Anticipo (Aprox 1.3% del valor del anticipo c/IVA)'].categorycode == 'C7'
    assert by_desc['Impuestos (Aprox 0.0918 x 0.30 del contrato sin IVA)'].formulakey == 'tax_isr'
    assert by_desc['Impuestos (Aprox 0.0918 x 0.30 del contrato sin IVA)'].categorycode == 'C8'
    assert all(l.applies == ChecklistStatusCode.NA for l in lines)
    assert all(l.amount == Decimal('0') for l in lines)


@pytest.mark.integration
def test_seed_is_idempotent(project, user):
    IndirectCostDetailService.seed_external_checklist(project.estimationprojectid, user)
    IndirectCostDetailService.seed_external_checklist(project.estimationprojectid, user)
    count = IndirectCostDetail.objects.filter(
        projectid=project, description__startswith='Fianza Anticipo').count()
    assert count == 1


@pytest.mark.integration
def test_calculator_upserts_onto_seeded_line(project, user):
    from apps.proyeccion.schemas import ComputeBondsOverridesDto
    IndirectCostDetailService.seed_external_checklist(project.estimationprojectid, user)
    IndirectCostDetailService.compute_bond_and_tax_lines(
        project.estimationprojectid, user, overrides=ComputeBondsOverridesDto())
    line = IndirectCostDetail.objects.get(projectid=project, formulakey='bond_anticipo')
    assert line.applies == ChecklistStatusCode.YES
    assert IndirectCostDetail.objects.filter(projectid=project, formulakey='bond_anticipo').count() == 1


@pytest.mark.unit
def test_external_name_category_mapping():
    from apps.proyeccion.services import external_name_to_category
    assert external_name_to_category('Fianza de anticipo') == 'C7'
    assert external_name_to_category('Seguro de obra') == 'C7'
    assert external_name_to_category('Gastos financieros') == 'C7'
    assert external_name_to_category('Gastos de licitacion') == 'C7'
    assert external_name_to_category('Permisos municipales') == 'C8'
    assert external_name_to_category('Impuestos (ISR provisional)') == 'C8'
