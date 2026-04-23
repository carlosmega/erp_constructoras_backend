"""Unit tests for Budget models."""

import pytest
from decimal import Decimal
from datetime import date
from django.db import IntegrityError

from apps.budgets.models import (
    CostCategory,
    CostTypeCode,
    ImputationCode,
    PersonnelTypeCode,
    ImputationPeriod,
    PeriodTypeCode,
)
from apps.budgets.tests.factories import (
    CostCategoryFactory,
    IndirectCostCategoryFactory,
    ImputationCodeFactory,
    IndirectImputationCodeFactory,
    ImputationPeriodFactory,
)
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestCostTypeCodeEnum:
    """Tests for CostTypeCode enum."""

    def test_direct_value(self):
        assert CostTypeCode.DIRECT.value == 0
        assert CostTypeCode.DIRECT.label == 'Direct'

    def test_indirect_value(self):
        assert CostTypeCode.INDIRECT.value == 1
        assert CostTypeCode.INDIRECT.label == 'Indirect'


@pytest.mark.unit
class TestPersonnelTypeCodeEnum:
    """Tests for PersonnelTypeCode enum."""

    def test_office_staff_value(self):
        assert PersonnelTypeCode.OFFICE_STAFF.value == 0
        assert PersonnelTypeCode.OFFICE_STAFF.label == 'Office Staff'

    def test_field_staff_value(self):
        assert PersonnelTypeCode.FIELD_STAFF.value == 1
        assert PersonnelTypeCode.FIELD_STAFF.label == 'Field Staff'


@pytest.mark.unit
class TestPeriodTypeCodeEnum:
    """Tests for PeriodTypeCode enum."""

    def test_weekly_value(self):
        assert PeriodTypeCode.WEEKLY.value == 0
        assert PeriodTypeCode.WEEKLY.label == 'Weekly'

    def test_fortnightly_value(self):
        assert PeriodTypeCode.FORTNIGHTLY.value == 1
        assert PeriodTypeCode.FORTNIGHTLY.label == 'Fortnightly'


@pytest.mark.unit
class TestCostCategoryModel:
    """Tests for CostCategory model."""

    def test_create_direct_category(self, db):
        category = CostCategoryFactory(
            costtype=CostTypeCode.DIRECT,
            code='P1',
            name='Subcontratos',
        )
        assert category.categoryid is not None
        assert category.costtype == CostTypeCode.DIRECT
        assert category.code == 'P1'
        assert category.name == 'Subcontratos'
        assert category.statecode == 0

    def test_create_indirect_category(self, db):
        category = IndirectCostCategoryFactory(
            code='C1',
            name='Personal',
        )
        assert category.categoryid is not None
        assert category.costtype == CostTypeCode.INDIRECT
        assert category.code == 'C1'

    def test_str_representation(self, db):
        category = CostCategoryFactory(code='P4', name='Materiales')
        assert str(category) == 'P4 - Materiales'

    def test_unique_together_project_code(self, db):
        category = CostCategoryFactory(code='P1')
        with pytest.raises(IntegrityError):
            CostCategoryFactory(
                projectid=category.projectid,
                code='P1',
            )

    def test_audit_fields(self, db):
        category = CostCategoryFactory()
        assert category.createdon is not None
        assert category.modifiedon is not None
        assert category.createdby is not None
        assert category.modifiedby is not None


@pytest.mark.unit
class TestImputationCodeModel:
    """Tests for ImputationCode model."""

    def test_create_direct_code(self, db):
        code = ImputationCodeFactory(
            name='Concrete Supply',
            totalbudget=Decimal('50000.00'),
        )
        assert code.imputationcodeid is not None
        assert code.costtype == CostTypeCode.DIRECT
        assert code.zoneid is not None
        assert code.totalbudget == Decimal('50000.00')
        assert code.statecode == 0

    def test_create_indirect_code(self, db):
        code = IndirectImputationCodeFactory(
            name='Site Manager',
        )
        assert code.imputationcodeid is not None
        assert code.costtype == CostTypeCode.INDIRECT
        assert code.zoneid is None

    def test_str_representation(self, db):
        code = ImputationCodeFactory(code='TAM-P4-1', name='Concrete Supply')
        assert str(code) == 'TAM-P4-1 - Concrete Supply'

    def test_unique_together_project_code(self, db):
        code = ImputationCodeFactory(code='TAM-P4-1')
        with pytest.raises(IntegrityError):
            ImputationCodeFactory(
                projectid=code.projectid,
                code='TAM-P4-1',
            )

    def test_default_computed_fields(self, db):
        code = ImputationCodeFactory()
        assert code.totalspent == Decimal('0')
        assert code.percentused == Decimal('0')

    def test_optional_personnel_fields(self, db):
        code = IndirectImputationCodeFactory(
            personnelname='John Doe',
            personnelrole='Site Manager',
            personneltype=PersonnelTypeCode.FIELD_STAFF,
            monthlycost=Decimal('45000.00'),
            units=Decimal('1.00'),
        )
        assert code.personnelname == 'John Doe'
        assert code.personnelrole == 'Site Manager'
        assert code.personneltype == PersonnelTypeCode.FIELD_STAFF
        assert code.monthlycost == Decimal('45000.00')


@pytest.mark.unit
class TestImputationPeriodModel:
    """Tests for ImputationPeriod model."""

    def test_create_fortnightly_period(self, db):
        period = ImputationPeriodFactory(
            periodtype=PeriodTypeCode.FORTNIGHTLY,
            year=2026,
            month=1,
            periodnumber=1,
            label='ENE 2026 Q1',
            startdate=date(2026, 1, 1),
            enddate=date(2026, 1, 15),
        )
        assert period.periodid is not None
        assert period.periodtype == PeriodTypeCode.FORTNIGHTLY
        assert period.label == 'ENE 2026 Q1'
        assert period.startdate == date(2026, 1, 1)
        assert period.enddate == date(2026, 1, 15)
        assert period.statecode == 0

    def test_create_weekly_period(self, db):
        period = ImputationPeriodFactory(
            periodtype=PeriodTypeCode.WEEKLY,
            year=2026,
            month=3,
            periodnumber=1,
            label='MAR 2026 S1',
            startdate=date(2026, 3, 1),
            enddate=date(2026, 3, 7),
        )
        assert period.periodtype == PeriodTypeCode.WEEKLY
        assert period.label == 'MAR 2026 S1'

    def test_str_representation(self, db):
        period = ImputationPeriodFactory(label='ENE 2026 Q1')
        assert str(period) == 'ENE 2026 Q1'

    def test_unique_together_project_year_month_number(self, db):
        period = ImputationPeriodFactory(
            year=2026,
            month=1,
            periodnumber=1,
        )
        with pytest.raises(IntegrityError):
            ImputationPeriodFactory(
                projectid=period.projectid,
                year=2026,
                month=1,
                periodnumber=1,
            )

    def test_audit_fields(self, db):
        period = ImputationPeriodFactory()
        assert period.createdon is not None
        assert period.modifiedon is not None
        assert period.createdby is not None


@pytest.mark.unit
class TestCostCategoryFactory:
    """Tests for CostCategory factories."""

    def test_direct_factory(self, db):
        category = CostCategoryFactory()
        assert category.costtype == CostTypeCode.DIRECT
        assert category.code.startswith('P')

    def test_indirect_factory(self, db):
        category = IndirectCostCategoryFactory()
        assert category.costtype == CostTypeCode.INDIRECT
        assert category.code.startswith('C')


@pytest.mark.django_db
@pytest.mark.unit
def test_costcategory_has_defaultpaymentlag_with_zero_default():
    category = CostCategoryFactory()
    assert category.defaultpaymentlag == 0


@pytest.mark.django_db
@pytest.mark.unit
def test_costcategory_accepts_custom_paymentlag():
    category = CostCategoryFactory(defaultpaymentlag=30)
    category.refresh_from_db()
    assert category.defaultpaymentlag == 30
