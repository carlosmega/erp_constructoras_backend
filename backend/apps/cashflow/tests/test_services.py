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


from apps.cashflow.services.billing_rule import BillingRuleService
from apps.cashflow.models import ProjectBillingRule
from core.exceptions import ValidationError


@pytest.mark.django_db
@pytest.mark.unit
def test_replace_stores_rules_atomically():
    project = ConstructionProjectFactory()
    rules = [
        {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 0},
        {'sequence': 2, 'percent': Decimal('0.3'), 'lagperiods': 1},
        {'sequence': 3, 'percent': Decimal('0.2'), 'lagperiods': 2},
    ]
    saved = BillingRuleService.replace(project.projectid, rules)
    assert len(saved) == 3
    assert ProjectBillingRule.objects.filter(projectid=project).count() == 3


@pytest.mark.django_db
@pytest.mark.unit
def test_replace_rejects_sum_not_100():
    project = ConstructionProjectFactory()
    bad = [
        {'sequence': 1, 'percent': Decimal('0.6'), 'lagperiods': 0},
        {'sequence': 2, 'percent': Decimal('0.3'), 'lagperiods': 1},
    ]
    with pytest.raises(ValidationError, match='100'):
        BillingRuleService.replace(project.projectid, bad)


@pytest.mark.django_db
@pytest.mark.unit
def test_replace_rejects_empty_list():
    project = ConstructionProjectFactory()
    with pytest.raises(ValidationError, match='al menos'):
        BillingRuleService.replace(project.projectid, [])


@pytest.mark.django_db
@pytest.mark.unit
def test_replace_rejects_duplicate_sequences():
    project = ConstructionProjectFactory()
    bad = [
        {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 0},
        {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 1},
    ]
    with pytest.raises(ValidationError, match='[Ss]ecuencia'):
        BillingRuleService.replace(project.projectid, bad)


@pytest.mark.django_db
@pytest.mark.unit
def test_replace_overwrites_previous_rules():
    project = ConstructionProjectFactory()
    BillingRuleService.replace(project.projectid, [
        {'sequence': 1, 'percent': Decimal('1'), 'lagperiods': 0},
    ])
    BillingRuleService.replace(project.projectid, [
        {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 0},
        {'sequence': 2, 'percent': Decimal('0.5'), 'lagperiods': 1},
    ])
    assert ProjectBillingRule.objects.filter(projectid=project).count() == 2
