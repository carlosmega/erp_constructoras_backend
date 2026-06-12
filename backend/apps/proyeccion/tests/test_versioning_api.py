"""API contract tests for EstimationVersion endpoints — Task 5."""

import pytest

from apps.proyeccion.models import EstimationVersion
from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.django_db
@pytest.mark.contract
def test_versions_crud_flow(auth_client):
    project = EstimationProjectFactory()
    base = f"/api/proyeccion/projects/{project.estimationprojectid}/versions/"

    # Crear
    r = auth_client.post(base, data={"note": "hito 1"}, content_type="application/json")
    assert r.status_code == 200
    assert r.json()["versionnumber"] == 1

    # Listar (sin snapshot)
    r = auth_client.get(base)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and "snapshot" not in body[0]

    # Detalle (con snapshot)
    r = auth_client.get(base + "1/")
    assert r.status_code == 200
    assert "snapshot" in r.json()

    # Restore
    r = auth_client.post(base + "1/restore/")
    assert r.status_code == 200
    assert r.json()["backup_versionnumber"] == 2


@pytest.mark.django_db
@pytest.mark.contract
def test_restore_converted_returns_400(auth_client):
    from apps.projects.tests.factories import ConstructionProjectFactory

    project = EstimationProjectFactory()
    base = f"/api/proyeccion/projects/{project.estimationprojectid}/versions/"
    auth_client.post(base, data={"note": ""}, content_type="application/json")
    project.generatedprojectid = ConstructionProjectFactory()
    project.save()
    r = auth_client.post(base + "1/restore/")
    assert r.status_code == 400
