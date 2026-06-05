"""Contract tests for the CDU report endpoint (full breakdown for PDF/print)."""
from decimal import Decimal

import pytest
from django.test import Client

from apps.proyeccion.tests.factories import (
    BudgetConceptFactory,
    EstimationProjectFactory,
    UnitCostBreakdownFactory,
)
from apps.proyeccion.models import BreakdownCategoryCode
from apps.users.tests.factories import SystemUserFactory


@pytest.fixture
def authed_client(db):
    user = SystemUserFactory()
    c = Client()
    c.force_login(user)
    return c


def _url(project):
    return f"/api/proyeccion/projects/{project.estimationprojectid}/cdu-report/"


@pytest.mark.django_db
@pytest.mark.contract
def test_cdu_report_returns_concepts_with_lines_and_total(authed_client):
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project, code="A1", quantity=Decimal('100'))
    UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.MATERIALS,
                             linenumber=1, quantity=Decimal('2'), unitprice=Decimal('10'),
                             yieldvalue=Decimal('1'), amount=Decimal('20'))
    UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.LABOR,
                             linenumber=1, quantity=Decimal('1'), unitprice=Decimal('30'),
                             yieldvalue=Decimal('1'), amount=Decimal('30'))

    r = authed_client.get(_url(project))
    assert r.status_code == 200
    body = r.json()
    assert len(body["concepts"]) == 1
    c = body["concepts"][0]
    assert c["code"] == "A1"
    assert len(c["lines"]) == 2
    # cdu_total = sum of line amounts (20 + 30)
    assert Decimal(str(c["cdu_total"])) == Decimal('50')


@pytest.mark.django_db
@pytest.mark.contract
def test_cdu_report_lines_ordered_by_category(authed_client):
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project, code="A1")
    # Insert out of order: Labor (4) then Materials (1) — report must order Materials first.
    UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.LABOR, linenumber=1)
    UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.MATERIALS, linenumber=1)

    r = authed_client.get(_url(project))
    cats = [ln["categorycode"] for ln in r.json()["concepts"][0]["lines"]]
    assert cats == sorted(cats)
    assert cats[0] == int(BreakdownCategoryCode.MATERIALS)


@pytest.mark.django_db
@pytest.mark.contract
def test_cdu_report_includes_empty_concepts(authed_client):
    """Concepts without breakdowns still appear (with empty lines, cdu_total 0)."""
    project = EstimationProjectFactory()
    BudgetConceptFactory(projectid=project, code="A1")  # no breakdowns
    r = authed_client.get(_url(project))
    body = r.json()
    assert len(body["concepts"]) == 1
    assert body["concepts"][0]["lines"] == []
    assert Decimal(str(body["concepts"][0]["cdu_total"])) == Decimal('0')


@pytest.mark.django_db
@pytest.mark.contract
def test_cdu_report_excludes_softdeleted_lines(authed_client):
    project = EstimationProjectFactory()
    concept = BudgetConceptFactory(projectid=project, code="A1")
    UnitCostBreakdownFactory(conceptid=concept, amount=Decimal('20'), statecode=0)
    UnitCostBreakdownFactory(conceptid=concept, amount=Decimal('99'), statecode=1)  # deleted
    r = authed_client.get(_url(project))
    c = r.json()["concepts"][0]
    assert len(c["lines"]) == 1
    assert Decimal(str(c["cdu_total"])) == Decimal('20')
