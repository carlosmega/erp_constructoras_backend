import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.proyeccion.models import EstimationVersion
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory,
    BudgetConceptFactory,
    UnitCostBreakdownFactory,
    IndirectCostDetailFactory,
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
    # Decimales como string (sin pérdida)
    bd_row = next(b for b in snap["breakdowns"] if b["breakdownid"] == str(bd.breakdownid))
    assert Decimal(bd_row["amount"]) == Decimal("123.4567")
    # Todo el snapshot es JSON-serializable
    import json
    json.dumps(snap)
