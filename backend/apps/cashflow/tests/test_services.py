"""Tests for cashflow services."""
import pytest
from decimal import Decimal
from apps.projects.tests.factories import ConstructionProjectFactory
from apps.cashflow.services.financial_settings import FinancialSettingsService
from apps.cashflow.models import ProjectFinancialSettings


@pytest.mark.django_db
@pytest.mark.unit
def test_get_or_create_materializes_with_defaults():
    project = ConstructionProjectFactory()
    assert not ProjectFinancialSettings.objects.filter(projectid=project).exists()

    settings = FinancialSettingsService.get_or_create(project.projectid)

    assert settings.imssretentionrate == Decimal('0.0500')
    assert settings.anticipoentryperiod == 1
    assert ProjectFinancialSettings.objects.filter(projectid=project).count() == 1


@pytest.mark.django_db
@pytest.mark.unit
def test_get_or_create_returns_existing_without_duplication():
    project = ConstructionProjectFactory()
    first = FinancialSettingsService.get_or_create(project.projectid)
    second = FinancialSettingsService.get_or_create(project.projectid)
    assert first.settingsid == second.settingsid
    assert ProjectFinancialSettings.objects.filter(projectid=project).count() == 1
