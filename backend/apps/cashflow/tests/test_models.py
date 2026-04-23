"""Tests for cashflow models."""
import pytest
from decimal import Decimal
from django.db import IntegrityError

from apps.cashflow.tests.factories import (
    ProjectFinancialSettingsFactory,
    ProjectBillingRuleFactory,
)
from apps.projects.tests.factories import ConstructionProjectFactory


@pytest.mark.unit
class TestProjectFinancialSettings:
    """Tests for ProjectFinancialSettings model."""

    def test_defaults(self, db):
        s = ProjectFinancialSettingsFactory()
        s.refresh_from_db()
        assert s.imssretentionrate == Decimal('0.0500')
        assert s.otherretentionrate == Decimal('0.0000')
        assert s.advanceamortizationrate == Decimal('0.0000')
        assert s.anticipoentryperiod == 1
        assert s.financecostrate == Decimal('0.001000')

    def test_unique_per_project(self, db):
        s1 = ProjectFinancialSettingsFactory()
        with pytest.raises(IntegrityError):
            ProjectFinancialSettingsFactory(projectid=s1.projectid)


@pytest.mark.unit
class TestProjectBillingRule:
    """Tests for ProjectBillingRule model."""

    def test_stores_percent_and_lag(self, db):
        rule = ProjectBillingRuleFactory(percent=Decimal('0.5000'), lagperiods=2)
        rule.refresh_from_db()
        assert rule.percent == Decimal('0.5000')
        assert rule.lagperiods == 2

    def test_sequence_unique_per_project(self, db):
        project = ConstructionProjectFactory()
        ProjectBillingRuleFactory(projectid=project, sequence=1)
        with pytest.raises(IntegrityError):
            ProjectBillingRuleFactory(projectid=project, sequence=1)
