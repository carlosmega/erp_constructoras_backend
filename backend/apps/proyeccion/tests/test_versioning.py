import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.proyeccion.models import EstimationVersion, OfferAlternative, UnitCostBreakdown
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory,
    BudgetConceptFactory,
    UnitCostBreakdownFactory,
    IndirectCostDetailFactory,
    ProjectionPeriodFactory,
)


@pytest.mark.django_db
@pytest.mark.unit
def test_estimation_version_basic_fields():
    project = EstimationProjectFactory()
    v = EstimationVersion.objects.create(
        projectid=project, versionnumber=1, note="Oferta enviada",
        schema_version=1, snapshot={"project": {}},
        saleamount=Decimal("100"), directtotal=Decimal("60"),
        indirecttotal=Decimal("10"), margintotal=Decimal("30"), conceptcount=5,
    )
    assert v.versionid is not None
    assert v.isauto is False
    assert v.snapshot == {"project": {}}


@pytest.mark.django_db
@pytest.mark.unit
def test_estimation_version_number_unique_per_project():
    project = EstimationProjectFactory()
    EstimationVersion.objects.create(
        projectid=project, versionnumber=1, schema_version=1, snapshot={},
    )
    with pytest.raises(IntegrityError):
        EstimationVersion.objects.create(
            projectid=project, versionnumber=1, schema_version=1, snapshot={},
        )


@pytest.mark.django_db
@pytest.mark.unit
def test_dump_graph_captures_all_sections_and_preserves_uuids():
    from apps.proyeccion.versioning import dump_graph, SCHEMA_VERSION
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project)
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("123.4567"))
    bd_deleted = UnitCostBreakdownFactory(conceptid=concept, statecode=1)
    ind = IndirectCostDetailFactory(projectid=project)

    snap = dump_graph(project)

    assert snap["schema_version"] == SCHEMA_VERSION
    # Todas las secciones presentes (aunque vacías)
    for key in ("project", "families", "subfamilies", "concepts", "breakdowns",
                "indirects", "alternatives", "alternative_adjustments",
                "financial_settings", "billing_rules", "workplan_entries",
                "projection_periods", "cost_distributions"):
        assert key in snap, key
    # UUIDs preservados como string
    assert snap["project"]["estimationprojectid"] == str(project.estimationprojectid)
    assert any(c["conceptid"] == str(concept.conceptid) for c in snap["concepts"])
    # Incluye soft-deleted con su statecode (restauración fiel)
    states = {b["breakdownid"]: b["statecode"] for b in snap["breakdowns"]}
    assert states[str(bd.breakdownid)] == 0
    assert states[str(bd_deleted.breakdownid)] == 1
    # Indirectos presentes
    assert any(i["indirectcostid"] == str(ind.indirectcostid) for i in snap["indirects"])
    # Decimales como string (sin pérdida)
    bd_row = next(b for b in snap["breakdowns"] if b["breakdownid"] == str(bd.breakdownid))
    assert bd_row["amount"] == "123.4567"
    # Todo el snapshot es JSON-serializable
    import json
    json.dumps(snap)


@pytest.mark.django_db
@pytest.mark.unit
def test_create_version_assigns_sequential_numbers_and_summary():
    from apps.proyeccion.versioning import EstimationVersionService
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(
        projectid=project, quantity=Decimal("10"),
        directunitcost=Decimal("100"),
    )
    IndirectCostDetailFactory(projectid=project, amount=Decimal("200"))
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name="Base",
        ischosen=True, salepricenet=Decimal("2000"),
    )

    v1 = EstimationVersionService.create_version(project, user=None, note="primera")
    v2 = EstimationVersionService.create_version(project, user=None)

    assert (v1.versionnumber, v2.versionnumber) == (1, 2)
    assert v1.note == "primera"
    assert v1.isauto is False
    assert v1.saleamount == Decimal("2000")
    assert v1.directtotal == Decimal("1000")   # 100 × 10
    assert v1.indirecttotal == Decimal("200")
    assert v1.margintotal == Decimal("800")    # 2000 − 1000 − 200
    assert v1.conceptcount == 1
    assert v1.snapshot["project"]["estimationprojectid"] == str(project.estimationprojectid)


@pytest.mark.django_db
@pytest.mark.unit
def test_create_version_writes_audit_log():
    from apps.proyeccion.versioning import EstimationVersionService
    from apps.audit.models import AuditLog
    project = EstimationProjectFactory()
    v = EstimationVersionService.create_version(project, user=None, note="x")
    log = AuditLog.objects.get(entity='estimationversion', recordid=v.versionid)
    assert log.action == 'create'


# ---------------------------------------------------------------------------
# Task 4: restore_version tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.workflow
def test_restore_round_trip_restores_identical_graph():
    """El test central del feature: crear versión → mutar todo → restaurar →
    el grafo queda idéntico (UUIDs incluidos) y los rollups cuadran."""
    from apps.proyeccion.versioning import EstimationVersionService
    from apps.proyeccion.services import CostDistributionService
    from apps.proyeccion.models import CostLineType, CostDistribution

    project = EstimationProjectFactory(periodcount=2)
    ProjectionPeriodFactory(projectid=project, periodnumber=1)
    ProjectionPeriodFactory(projectid=project, periodnumber=2)
    concept = BudgetConceptFactory(projectid=project, quantity=Decimal("1"))
    bd = UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("1000"))
    CostDistribution.objects.create(
        projectid=project, linetype=CostLineType.BREAKDOWN,
        breakdownid=bd, periodnumber=1, fraction=Decimal("1"), isderived=False,
    )
    rollups_before = CostDistributionService.compute_rollups(project)
    original_bd_id = bd.breakdownid

    v1 = EstimationVersionService.create_version(project, user=None, note="hito")

    # Mutar: borrar la línea, cambiar el concepto, agregar basura
    bd.delete()
    concept.description = "MUTADO"
    concept.save()
    UnitCostBreakdownFactory(conceptid=concept, amount=Decimal("999"))

    result = EstimationVersionService.restore_version(project, v1.versionnumber, user=None)

    # Respaldo automático creado ANTES de restaurar (captura el estado mutado)
    backup = EstimationVersion.objects.get(projectid=project, versionnumber=result['backup_versionnumber'])
    assert backup.isauto is True
    assert any(Decimal(b["amount"]) == Decimal("999")
               for b in backup.snapshot["breakdowns"])

    # Grafo restaurado: UUID original de la línea de vuelta, mutación deshecha
    assert UnitCostBreakdown.objects.filter(breakdownid=original_bd_id).exists()
    concept.refresh_from_db()
    assert concept.description != "MUTADO"
    assert UnitCostBreakdown.objects.filter(conceptid=concept).count() == 1
    # La celda manual de distribución regresó
    cell = CostDistribution.objects.get(breakdownid=original_bd_id, periodnumber=1)
    assert cell.isderived is False
    # Rollups idénticos al momento del snapshot
    rollups_after = CostDistributionService.compute_rollups(project)
    assert rollups_after['direct_total'] == rollups_before['direct_total']


@pytest.mark.django_db
@pytest.mark.unit
def test_restore_blocked_when_project_converted():
    from apps.proyeccion.versioning import EstimationVersionService
    from apps.projects.tests.factories import ConstructionProjectFactory
    project = EstimationProjectFactory()
    v = EstimationVersionService.create_version(project, user=None)
    project.generatedprojectid = ConstructionProjectFactory()
    project.save()
    with pytest.raises(ValueError, match="convertido"):
        EstimationVersionService.restore_version(project, v.versionnumber, user=None)


@pytest.mark.django_db
@pytest.mark.unit
def test_restore_rejects_newer_schema_version():
    from apps.proyeccion.versioning import EstimationVersionService
    project = EstimationProjectFactory()
    v = EstimationVersionService.create_version(project, user=None)
    EstimationVersion.objects.filter(pk=v.pk).update(schema_version=999)
    with pytest.raises(ValueError, match="schema"):
        EstimationVersionService.restore_version(project, v.versionnumber, user=None)


@pytest.mark.django_db
@pytest.mark.unit
def test_restore_nulls_supply_link_if_catalog_item_gone():
    from apps.proyeccion.versioning import EstimationVersionService
    from apps.proyeccion.models import SupplyCatalogItem
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project)
    supply = SupplyCatalogItem.objects.create(
        code='SUP-X', description='Insumo X', unit='lt', supplytype=1,
    )
    bd = UnitCostBreakdownFactory(conceptid=concept, supplyid=supply)
    original_bd_id = bd.breakdownid  # save before delete() sets pk to None
    v = EstimationVersionService.create_version(project, user=None)
    bd.delete()
    supply.delete()
    EstimationVersionService.restore_version(project, v.versionnumber, user=None)
    restored = UnitCostBreakdown.objects.get(breakdownid=original_bd_id)
    assert restored.supplyid_id is None
