"""Unit tests for Budget services."""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from apps.budgets.models import (
    CostCategory,
    CostTypeCode,
    ImputationCode,
    ImputationPeriod,
    PeriodTypeCode,
)
from apps.budgets.services import (
    CostCategoryService,
    ImputationCodeService,
    PeriodService,
)
from apps.budgets.schemas import (
    CreateCostCategoryDto,
    CreateImputationCodeDto,
    UpdateImputationCodeDto,
)
from apps.budgets.tests.factories import (
    CostCategoryFactory,
    IndirectCostCategoryFactory,
    ImputationCodeFactory,
    IndirectImputationCodeFactory,
    ImputationPeriodFactory,
)
from apps.projects.tests.factories import ConstructionProjectFactory, ProjectZoneFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, NotFound


def _create_project_and_zone(user, periodtype=PeriodTypeCode.FORTNIGHTLY):
    """Helper to create a project and zone for testing."""
    project = ConstructionProjectFactory(
        ownerid=user,
        startdate=date(2026, 1, 1),
        contractenddate=date(2026, 3, 31),
        periodtype=periodtype,
    )

    zone = ProjectZoneFactory(
        projectid=project,
        name='Tampico',
        prefix='TAM',
    )

    return project, zone


@pytest.mark.unit
class TestCostCategoryService:
    """Tests for CostCategoryService."""

    def test_seed_default_categories(self, db, salesperson):
        """Seed defaults should create all 18 standard categories."""
        project, zone = _create_project_and_zone(salesperson)

        categories = CostCategoryService.seed_default_categories(
            project.projectid, salesperson
        )

        assert len(categories) == 18

        # Verify direct categories (P1-P10)
        codes = [c.code for c in categories]
        for i in range(1, 11):
            assert f'P{i}' in codes

        # Verify indirect categories (C1-C8)
        for i in range(1, 9):
            assert f'C{i}' in codes

        # Verify they are persisted
        db_count = CostCategory.objects.filter(projectid=project.projectid).count()
        assert db_count == 18

    def test_seed_default_categories_names(self, db, salesperson):
        """Verify standard category names."""
        project, zone = _create_project_and_zone(salesperson)

        categories = CostCategoryService.seed_default_categories(
            project.projectid, salesperson
        )

        by_code = {c.code: c for c in categories}
        assert by_code['P1'].name == 'Subcontratos'
        assert by_code['P4'].name == 'Materiales'
        assert by_code['C1'].name == 'Personal'
        assert by_code['C8'].name == 'Proyectos/Gestiones/Impuestos'

    def test_seed_default_categories_cost_types(self, db, salesperson):
        """Verify P-codes are Direct and C-codes are Indirect."""
        project, zone = _create_project_and_zone(salesperson)

        categories = CostCategoryService.seed_default_categories(
            project.projectid, salesperson
        )

        for cat in categories:
            if cat.code.startswith('P'):
                assert cat.costtype == CostTypeCode.DIRECT
            else:
                assert cat.costtype == CostTypeCode.INDIRECT

    def test_create_custom_category(self, db, salesperson):
        """Create a custom category."""
        project, zone = _create_project_and_zone(salesperson)

        dto = CreateCostCategoryDto(
            projectid=project.projectid,
            costtype=CostTypeCode.DIRECT,
            code='P11',
            name='Custom Direct',
            description='A custom category',
            sortorder=19,
        )

        category = CostCategoryService.create_category(dto, salesperson)

        assert category.categoryid is not None
        assert category.code == 'P11'
        assert category.name == 'Custom Direct'
        assert category.costtype == CostTypeCode.DIRECT
        assert category.description == 'A custom category'

    def test_list_categories(self, db, salesperson):
        """List categories returns all for a project."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)

        result = CostCategoryService.list_categories(project.projectid, salesperson)

        assert result.count() == 18


@pytest.mark.unit
class TestImputationCodeService:
    """Tests for ImputationCodeService."""

    def test_create_direct_code_format(self, db, salesperson):
        """Direct code format: {zone.prefix}-{category.code}-{seq}."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='P4')

        dto = CreateImputationCodeDto(
            projectid=project.projectid,
            categoryid=category.categoryid,
            zoneid=zone.zoneid,
            costtype=CostTypeCode.DIRECT,
            name='Concrete Supply',
            totalbudget=Decimal('50000.00'),
        )

        code = ImputationCodeService.create_code(dto, salesperson)

        assert code.code == 'TAM-P4-1'
        assert code.sequencenumber == 1
        assert code.costtype == CostTypeCode.DIRECT
        assert code.zoneid == zone

    def test_create_indirect_code_format(self, db, salesperson):
        """Indirect code format: {category.code}-{seq}."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='C1')

        dto = CreateImputationCodeDto(
            projectid=project.projectid,
            categoryid=category.categoryid,
            zoneid=None,
            costtype=CostTypeCode.INDIRECT,
            name='Site Manager',
            totalbudget=Decimal('120000.00'),
        )

        code = ImputationCodeService.create_code(dto, salesperson)

        assert code.code == 'C1-1'
        assert code.sequencenumber == 1
        assert code.costtype == CostTypeCode.INDIRECT
        assert code.zoneid is None

    def test_auto_sequencing_direct(self, db, salesperson):
        """Sequence increments per (project, category, zone)."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='P4')

        for i in range(3):
            dto = CreateImputationCodeDto(
                projectid=project.projectid,
                categoryid=category.categoryid,
                zoneid=zone.zoneid,
                costtype=CostTypeCode.DIRECT,
                name=f'Item {i + 1}',
                totalbudget=Decimal('10000.00'),
            )
            code = ImputationCodeService.create_code(dto, salesperson)
            assert code.sequencenumber == i + 1
            assert code.code == f'TAM-P4-{i + 1}'

    def test_auto_sequencing_indirect(self, db, salesperson):
        """Sequence increments per (project, category) for indirect."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='C1')

        for i in range(3):
            dto = CreateImputationCodeDto(
                projectid=project.projectid,
                categoryid=category.categoryid,
                costtype=CostTypeCode.INDIRECT,
                name=f'Person {i + 1}',
                totalbudget=Decimal('50000.00'),
            )
            code = ImputationCodeService.create_code(dto, salesperson)
            assert code.sequencenumber == i + 1
            assert code.code == f'C1-{i + 1}'

    def test_direct_requires_zone(self, db, salesperson):
        """Direct cost codes must have a zone."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='P4')

        dto = CreateImputationCodeDto(
            projectid=project.projectid,
            categoryid=category.categoryid,
            zoneid=None,
            costtype=CostTypeCode.DIRECT,
            name='No Zone Direct',
            totalbudget=Decimal('10000.00'),
        )

        with pytest.raises(ValidationError, match='Zone is required'):
            ImputationCodeService.create_code(dto, salesperson)

    def test_indirect_rejects_zone(self, db, salesperson):
        """Indirect cost codes must not have a zone."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='C1')

        dto = CreateImputationCodeDto(
            projectid=project.projectid,
            categoryid=category.categoryid,
            zoneid=zone.zoneid,
            costtype=CostTypeCode.INDIRECT,
            name='Zoned Indirect',
            totalbudget=Decimal('10000.00'),
        )

        with pytest.raises(ValidationError, match='Zone must not be set'):
            ImputationCodeService.create_code(dto, salesperson)

    def test_update_code(self, db, salesperson):
        """Update an imputation code."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='P4')

        create_dto = CreateImputationCodeDto(
            projectid=project.projectid,
            categoryid=category.categoryid,
            zoneid=zone.zoneid,
            costtype=CostTypeCode.DIRECT,
            name='Original Name',
            totalbudget=Decimal('50000.00'),
        )
        code = ImputationCodeService.create_code(create_dto, salesperson)

        update_dto = UpdateImputationCodeDto(
            name='Updated Name',
            totalbudget=Decimal('75000.00'),
        )
        updated = ImputationCodeService.update_code(
            code.imputationcodeid, update_dto, salesperson
        )

        assert updated.name == 'Updated Name'
        assert updated.totalbudget == Decimal('75000.00')
        assert updated.remainingbudget == Decimal('75000.00')

    def test_get_code_by_id(self, db, salesperson):
        """Get code by ID."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)
        category = CostCategory.objects.get(projectid=project.projectid, code='P4')

        dto = CreateImputationCodeDto(
            projectid=project.projectid,
            categoryid=category.categoryid,
            zoneid=zone.zoneid,
            costtype=CostTypeCode.DIRECT,
            name='Find Me',
            totalbudget=Decimal('10000.00'),
        )
        code = ImputationCodeService.create_code(dto, salesperson)

        found = ImputationCodeService.get_code_by_id(code.imputationcodeid, salesperson)
        assert found.imputationcodeid == code.imputationcodeid
        assert found.name == 'Find Me'

    def test_get_code_by_id_not_found(self, db, salesperson):
        """Get nonexistent code raises NotFound."""
        with pytest.raises(NotFound, match='not found'):
            ImputationCodeService.get_code_by_id(uuid4(), salesperson)

    def test_list_codes_with_filters(self, db, salesperson):
        """List codes with costtype and category filters."""
        project, zone = _create_project_and_zone(salesperson)
        CostCategoryService.seed_default_categories(project.projectid, salesperson)

        cat_p4 = CostCategory.objects.get(projectid=project.projectid, code='P4')
        cat_c1 = CostCategory.objects.get(projectid=project.projectid, code='C1')

        # Create direct codes
        for i in range(2):
            dto = CreateImputationCodeDto(
                projectid=project.projectid,
                categoryid=cat_p4.categoryid,
                zoneid=zone.zoneid,
                costtype=CostTypeCode.DIRECT,
                name=f'Direct {i}',
                totalbudget=Decimal('10000.00'),
            )
            ImputationCodeService.create_code(dto, salesperson)

        # Create indirect code
        dto = CreateImputationCodeDto(
            projectid=project.projectid,
            categoryid=cat_c1.categoryid,
            costtype=CostTypeCode.INDIRECT,
            name='Indirect 1',
            totalbudget=Decimal('10000.00'),
        )
        ImputationCodeService.create_code(dto, salesperson)

        # Filter by costtype
        direct = ImputationCodeService.list_codes(
            project.projectid, salesperson, costtype=CostTypeCode.DIRECT
        )
        assert direct.count() == 2

        indirect = ImputationCodeService.list_codes(
            project.projectid, salesperson, costtype=CostTypeCode.INDIRECT
        )
        assert indirect.count() == 1

        # Filter by category
        p4_codes = ImputationCodeService.list_codes(
            project.projectid, salesperson, categoryid=cat_p4.categoryid
        )
        assert p4_codes.count() == 2


@pytest.mark.unit
class TestPeriodService:
    """Tests for PeriodService."""

    def test_initialize_fortnightly_periods(self, db, salesperson):
        """Initialize fortnightly periods: 2 per month, Jan-Mar = 6 periods."""
        project, zone = _create_project_and_zone(
            salesperson, periodtype=PeriodTypeCode.FORTNIGHTLY
        )

        periods = PeriodService.initialize_periods(project.projectid, salesperson)

        # 3 months * 2 periods = 6
        assert len(periods) == 6

        # Check first period
        p1 = periods[0]
        assert p1.label == 'ENE 2026 Q1'
        assert p1.startdate == date(2026, 1, 1)
        assert p1.enddate == date(2026, 1, 15)
        assert p1.periodnumber == 1
        assert p1.sortorder == 1

        # Check second period
        p2 = periods[1]
        assert p2.label == 'ENE 2026 Q2'
        assert p2.startdate == date(2026, 1, 16)
        assert p2.enddate == date(2026, 1, 31)
        assert p2.periodnumber == 2

        # Check last period (March Q2)
        p_last = periods[-1]
        assert p_last.label == 'MAR 2026 Q2'
        assert p_last.startdate == date(2026, 3, 16)
        assert p_last.enddate == date(2026, 3, 31)

    def test_initialize_weekly_periods(self, db, salesperson):
        """Initialize weekly periods: 4 per month, Jan-Mar = 12 periods."""
        project, zone = _create_project_and_zone(
            salesperson, periodtype=PeriodTypeCode.WEEKLY
        )

        periods = PeriodService.initialize_periods(project.projectid, salesperson)

        # 3 months * 4 periods = 12
        assert len(periods) == 12

        # Check first week
        s1 = periods[0]
        assert s1.label == 'ENE 2026 S1'
        assert s1.startdate == date(2026, 1, 1)
        assert s1.enddate == date(2026, 1, 7)
        assert s1.periodnumber == 1

        # Check second week
        s2 = periods[1]
        assert s2.label == 'ENE 2026 S2'
        assert s2.startdate == date(2026, 1, 8)
        assert s2.enddate == date(2026, 1, 14)

        # Check fourth week (last day = 31 for Jan)
        s4 = periods[3]
        assert s4.label == 'ENE 2026 S4'
        assert s4.startdate == date(2026, 1, 22)
        assert s4.enddate == date(2026, 1, 31)

    def test_initialize_periods_already_exist(self, db, salesperson):
        """Cannot initialize if periods already exist."""
        project, zone = _create_project_and_zone(salesperson)
        PeriodService.initialize_periods(project.projectid, salesperson)

        with pytest.raises(ValidationError, match='already initialized'):
            PeriodService.initialize_periods(project.projectid, salesperson)

    def test_initialize_periods_missing_dates(self, db, salesperson):
        """Cannot initialize without project dates."""
        project = ConstructionProjectFactory(
            ownerid=salesperson,
            startdate=None,
            contractenddate=None,
        )

        with pytest.raises(ValidationError, match='start date and contract end date'):
            PeriodService.initialize_periods(project.projectid, salesperson)

    def test_extend_periods(self, db, salesperson):
        """Extend periods by 2 months."""
        project, zone = _create_project_and_zone(
            salesperson, periodtype=PeriodTypeCode.FORTNIGHTLY
        )

        # Initialize Jan-Mar (6 periods)
        PeriodService.initialize_periods(project.projectid, salesperson)

        # Extend by 2 months (Apr-May = 4 new periods)
        new_periods = PeriodService.extend_periods(project.projectid, 2, salesperson)

        assert len(new_periods) == 4

        # First new period should be April Q1
        assert new_periods[0].label == 'ABR 2026 Q1'
        assert new_periods[0].startdate == date(2026, 4, 1)

        # Total should now be 10
        total = ImputationPeriod.objects.filter(projectid=project.projectid).count()
        assert total == 10

    def test_extend_periods_no_existing(self, db, salesperson):
        """Cannot extend without existing periods."""
        project, zone = _create_project_and_zone(salesperson)

        with pytest.raises(ValidationError, match='No existing periods'):
            PeriodService.extend_periods(project.projectid, 2, salesperson)

    def test_extend_periods_invalid_months(self, db, salesperson):
        """Cannot extend by 0 or negative months."""
        project, zone = _create_project_and_zone(salesperson)
        PeriodService.initialize_periods(project.projectid, salesperson)

        with pytest.raises(ValidationError, match='positive integer'):
            PeriodService.extend_periods(project.projectid, 0, salesperson)

    def test_close_period(self, db, salesperson):
        """Close a period sets statecode=1."""
        project, zone = _create_project_and_zone(salesperson)
        periods = PeriodService.initialize_periods(project.projectid, salesperson)

        closed = PeriodService.close_period(periods[0].periodid, salesperson)

        assert closed.statecode == 1

    def test_close_period_already_closed(self, db, salesperson):
        """Cannot close an already closed period."""
        project, zone = _create_project_and_zone(salesperson)
        periods = PeriodService.initialize_periods(project.projectid, salesperson)
        PeriodService.close_period(periods[0].periodid, salesperson)

        with pytest.raises(ValidationError, match='already closed'):
            PeriodService.close_period(periods[0].periodid, salesperson)

    def test_reopen_period(self, db, salesperson):
        """Reopen a closed period sets statecode=0."""
        project, zone = _create_project_and_zone(salesperson)
        periods = PeriodService.initialize_periods(project.projectid, salesperson)
        PeriodService.close_period(periods[0].periodid, salesperson)

        reopened = PeriodService.reopen_period(periods[0].periodid, salesperson)

        assert reopened.statecode == 0

    def test_reopen_period_already_open(self, db, salesperson):
        """Cannot reopen an already open period."""
        project, zone = _create_project_and_zone(salesperson)
        periods = PeriodService.initialize_periods(project.projectid, salesperson)

        with pytest.raises(ValidationError, match='already open'):
            PeriodService.reopen_period(periods[0].periodid, salesperson)

    def test_close_period_not_found(self, db, salesperson):
        """Close nonexistent period raises NotFound."""
        with pytest.raises(NotFound, match='not found'):
            PeriodService.close_period(uuid4(), salesperson)

    def test_list_periods(self, db, salesperson):
        """List periods returns all for a project in order."""
        project, zone = _create_project_and_zone(salesperson)
        PeriodService.initialize_periods(project.projectid, salesperson)

        result = PeriodService.list_periods(project.projectid, salesperson)

        assert result.count() == 6
        # Should be ordered by sortorder
        sortorders = list(result.values_list('sortorder', flat=True))
        assert sortorders == sorted(sortorders)

    def test_period_labels_spanish(self, db, salesperson):
        """Period labels use Spanish month abbreviations."""
        project = ConstructionProjectFactory(
            ownerid=salesperson,
            startdate=date(2026, 1, 1),
            contractenddate=date(2026, 12, 31),
            periodtype=PeriodTypeCode.FORTNIGHTLY,
        )

        periods = PeriodService.initialize_periods(project.projectid, salesperson)

        labels = [p.label for p in periods]
        assert 'ENE 2026 Q1' in labels
        assert 'FEB 2026 Q1' in labels
        assert 'MAR 2026 Q1' in labels
        assert 'ABR 2026 Q1' in labels
        assert 'MAY 2026 Q1' in labels
        assert 'JUN 2026 Q1' in labels
        assert 'JUL 2026 Q1' in labels
        assert 'AGO 2026 Q1' in labels
        assert 'SEP 2026 Q1' in labels
        assert 'OCT 2026 Q1' in labels
        assert 'NOV 2026 Q1' in labels
        assert 'DIC 2026 Q1' in labels
