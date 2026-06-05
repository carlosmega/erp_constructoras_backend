"""TDD tests for saleamount field on EstimationProjectSchema + list_projects annotation."""

import pytest
from decimal import Decimal

from apps.proyeccion.schemas import EstimationProjectSchema
from apps.proyeccion.services import EstimationProjectService
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory,
    OfferAlternativeFactory,
    BudgetConceptFactory,
)
from apps.users.tests.factories import SystemUserFactory


@pytest.fixture
def user(db):
    return SystemUserFactory()


@pytest.fixture
def project(db, user):
    return EstimationProjectFactory(ownerid=user)


@pytest.mark.integration
def test_saleamount_zero_when_no_chosen(project):
    assert EstimationProjectSchema.resolve_saleamount(project) == Decimal('0')


@pytest.mark.integration
def test_saleamount_is_chosen_salepricenet(project):
    OfferAlternativeFactory(projectid=project, ischosen=False, salepricenet=Decimal('999'), statecode=0)
    OfferAlternativeFactory(projectid=project, ischosen=True, salepricenet=Decimal('1234567.89'), statecode=0)
    assert EstimationProjectSchema.resolve_saleamount(project) == Decimal('1234567.89')


@pytest.mark.integration
def test_list_annotates_saleamount(project, user):
    OfferAlternativeFactory(projectid=project, ischosen=True, salepricenet=Decimal('555000.00'), statecode=0)
    row = EstimationProjectService.list_projects(user).get(pk=project.pk)
    assert row.saleamount_annotated == Decimal('555000.00')
    assert EstimationProjectSchema.resolve_saleamount(row) == Decimal('555000.00')


@pytest.mark.integration
def test_list_saleamount_zero_when_no_chosen(project, user):
    row = EstimationProjectService.list_projects(user).get(pk=project.pk)
    assert row.saleamount_annotated == Decimal('0')
    assert EstimationProjectSchema.resolve_saleamount(row) == Decimal('0')


# --- Fallback to budget total when there is no chosen alternative ---

@pytest.mark.integration
def test_saleamount_falls_back_to_budget_total(project):
    BudgetConceptFactory(projectid=project, totalamount=Decimal('5582304.76'))
    BudgetConceptFactory(projectid=project, totalamount=Decimal('100.00'))
    assert EstimationProjectSchema.resolve_saleamount(project) == Decimal('5582404.76')


@pytest.mark.integration
def test_saleamount_chosen_alternative_beats_budget_total(project):
    BudgetConceptFactory(projectid=project, totalamount=Decimal('5000000.00'))
    OfferAlternativeFactory(projectid=project, ischosen=True, salepricenet=Decimal('1234.56'), statecode=0)
    assert EstimationProjectSchema.resolve_saleamount(project) == Decimal('1234.56')


@pytest.mark.integration
def test_saleamount_budget_total_beats_estimatedcontractamount(db, user):
    project = EstimationProjectFactory(ownerid=user, estimatedcontractamount=Decimal('9999.00'))
    BudgetConceptFactory(projectid=project, totalamount=Decimal('5582404.76'))
    assert EstimationProjectSchema.resolve_saleamount(project) == Decimal('5582404.76')


@pytest.mark.integration
def test_saleamount_falls_back_to_estimatedcontractamount_when_no_budget(db, user):
    project = EstimationProjectFactory(ownerid=user, estimatedcontractamount=Decimal('777.00'))
    assert EstimationProjectSchema.resolve_saleamount(project) == Decimal('777.00')


@pytest.mark.integration
def test_saleamount_ignores_zero_budget_concepts(db, user):
    """A budget that sums to 0 must not mask the estimatedcontractamount fallback."""
    project = EstimationProjectFactory(ownerid=user, estimatedcontractamount=Decimal('777.00'))
    BudgetConceptFactory(projectid=project, totalamount=Decimal('0'))
    assert EstimationProjectSchema.resolve_saleamount(project) == Decimal('777.00')


@pytest.mark.integration
def test_list_annotation_falls_back_to_budget_total(project, user):
    BudgetConceptFactory(projectid=project, totalamount=Decimal('5582404.76'))
    row = EstimationProjectService.list_projects(user).get(pk=project.pk)
    assert row.saleamount_annotated == Decimal('5582404.76')
    assert EstimationProjectSchema.resolve_saleamount(row) == Decimal('5582404.76')


@pytest.mark.integration
def test_list_annotation_falls_back_to_estimatedcontractamount(db, user):
    project = EstimationProjectFactory(ownerid=user, estimatedcontractamount=Decimal('4321.00'))
    row = EstimationProjectService.list_projects(user).get(pk=project.pk)
    assert row.saleamount_annotated == Decimal('4321.00')


@pytest.mark.integration
def test_list_annotation_ignores_canceled_budget_concepts(project, user):
    """statecode!=0 budget concepts must be excluded from the fallback total."""
    BudgetConceptFactory(projectid=project, totalamount=Decimal('5000000.00'), statecode=1)
    row = EstimationProjectService.list_projects(user).get(pk=project.pk)
    assert row.saleamount_annotated == Decimal('0')
