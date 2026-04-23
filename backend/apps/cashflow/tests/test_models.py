"""Tests for cashflow models."""
import pytest
from decimal import Decimal
from django.db import IntegrityError

from apps.cashflow.tests.factories import ProjectFinancialSettingsFactory


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
