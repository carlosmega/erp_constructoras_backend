import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.proyeccion.models import EstimationVersion
from apps.proyeccion.tests.factories import EstimationProjectFactory


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
