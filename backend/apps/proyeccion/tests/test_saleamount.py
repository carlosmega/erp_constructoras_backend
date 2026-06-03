"""TDD tests for saleamount field on EstimationProjectSchema + list_projects annotation."""

import pytest
from decimal import Decimal

from apps.proyeccion.schemas import EstimationProjectSchema
from apps.proyeccion.services import EstimationProjectService
from apps.proyeccion.tests.factories import EstimationProjectFactory, OfferAlternativeFactory
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
