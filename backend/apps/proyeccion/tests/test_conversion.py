"""Tests for EstimationConversionService — converts an accepted Estudio into a ConstructionProject.

Spec: docs/superpowers/specs/2026-05-17-conversion-estudio-proyecto-design.md
"""

from datetime import date
from decimal import Decimal

import pytest

from django.utils import timezone

from apps.accounts.tests.factories import AccountFactory
from apps.budgets.models import CostCategory, CostTypeCode, ImputationCode, ImputationCodeBudget, ImputationPeriod
from apps.projects.models import ConstructionProject, ProjectStateCode, ProjectZone
from apps.proyeccion.models import (
    CostDistribution,
    CostLineType,
    EstimationFinancialSettings,
    EstimationStateCode,
    ProjectionPeriod,
    WorkPlanEntry,
    WorkPlanEntryType,
)
from apps.proyeccion.services import EstimationConversionService
from apps.proyeccion.tests.factories import (
    BudgetConceptFactory,
    ConceptFamilyFactory,
    ConceptSubfamilyFactory,
    EstimationProjectFactory,
    IndirectCostDetailFactory,
    OfferAlternativeFactory,
    UnitCostBreakdownFactory,
    WorkPlanEntryFactory,
)
from core.exceptions import ValidationError


def _accepted_estimation(
    salesperson,
    *,
    sale_notax=Decimal('1000000'),
    sale_total=Decimal('1160000'),
    advance_amount=Decimal('100000'),
    **overrides,
):
    """Build an estimation that satisfies every pre-condition by default.

    Tests can override any one field to drive a specific failure.
    """
    account = overrides.pop('account', None) or AccountFactory(ownerid=salesperson)
    defaults = dict(
        statecode=EstimationStateCode.ACCEPTED,
        accountid=account,
        estimatedstartdate=date(2026, 1, 1),
        estimatedenddate=date(2026, 6, 30),
        durationmonths=6,
        periodtype=1,  # FORTNIGHTLY
        exchangerate_mxn_usd=Decimal('20'),
        ownerid=salesperson,
    )
    defaults.update(overrides)
    estimation = EstimationProjectFactory(**defaults)
    OfferAlternativeFactory(
        projectid=estimation,
        ischosen=True,
        salepricenet=sale_notax,
        salepricetotal=sale_total,
    )
    EstimationFinancialSettings.objects.create(
        projectid=estimation,
        advanceamountnotax=advance_amount,
        createdby=salesperson,
        modifiedby=salesperson,
    )
    return estimation


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionPreconditions:
    """The service must validate that the estimation is in a convertible state."""

    def test_raises_when_estimation_not_in_accepted_state(self, db, salesperson):
        estimation = EstimationProjectFactory(statecode=EstimationStateCode.DRAFT, ownerid=salesperson)

        with pytest.raises(ValidationError) as exc:
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        message = str(exc.value).lower()
        assert 'accepted' in message or 'aceptado' in message

    def test_raises_when_estimation_has_no_account(self, db, salesperson):
        estimation = _accepted_estimation(salesperson, accountid=None)

        with pytest.raises(ValidationError) as exc:
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert 'account' in str(exc.value).lower()

    def test_raises_when_estimation_has_no_start_date(self, db, salesperson):
        estimation = _accepted_estimation(salesperson, estimatedstartdate=None)

        with pytest.raises(ValidationError) as exc:
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert 'start' in str(exc.value).lower() or 'inicio' in str(exc.value).lower()

    def test_raises_when_estimation_has_no_end_date(self, db, salesperson):
        estimation = _accepted_estimation(salesperson, estimatedenddate=None)

        with pytest.raises(ValidationError) as exc:
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert 'end' in str(exc.value).lower() or 'fin' in str(exc.value).lower()

    def test_raises_when_duration_months_not_positive(self, db, salesperson):
        estimation = _accepted_estimation(salesperson, durationmonths=0)

        with pytest.raises(ValidationError) as exc:
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert 'duration' in str(exc.value).lower() or 'meses' in str(exc.value).lower()

    def test_raises_when_no_chosen_offer_alternative(self, db, salesperson):
        # Set up an estimation with NO chosen alternative.
        account = AccountFactory(ownerid=salesperson)
        estimation = EstimationProjectFactory(
            statecode=EstimationStateCode.ACCEPTED,
            accountid=account,
            estimatedstartdate=date(2026, 1, 1),
            estimatedenddate=date(2026, 6, 30),
            durationmonths=6,
            ownerid=salesperson,
        )
        OfferAlternativeFactory(projectid=estimation, ischosen=False)  # not chosen

        with pytest.raises(ValidationError) as exc:
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert 'alternative' in str(exc.value).lower() or 'alternativa' in str(exc.value).lower()


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionHeader:
    """The service must create a ConstructionProject with header fields copied from the estimation."""

    def test_returns_construction_project_instance(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert isinstance(project, ConstructionProject)
        assert project.projectid is not None  # persisted

    def test_project_number_follows_PRY_YEAR_pattern(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        current_year = timezone.now().year
        assert project.projectnumber.startswith(f'PRY-{current_year}-')

    def test_copies_name_description_account_and_opportunity(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        estimation.description = 'Some description'
        estimation.save()

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.name == estimation.name
        assert project.description == 'Some description'
        assert project.accountid_id == estimation.accountid_id
        assert project.opportunityid_id == estimation.opportunityid_id

    def test_copies_dates_duration_and_period_type(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.startdate == date(2026, 1, 1)
        assert project.contractenddate == date(2026, 6, 30)
        assert project.durationmonths == 6
        assert project.periodtype == 1  # FORTNIGHTLY

    def test_pulls_contract_amount_from_chosen_offer_alternative(self, db, salesperson):
        estimation = _accepted_estimation(
            salesperson,
            sale_notax=Decimal('7818391.45'),
            sale_total=Decimal('9069334.08'),
        )

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.contractamount_notax == Decimal('7818391.45')
        assert project.contractamount_withtax == Decimal('9069334.08')

    def test_pulls_advance_payment_from_financial_settings(self, db, salesperson):
        estimation = _accepted_estimation(salesperson, advance_amount=Decimal('929236.37'))

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.advancepayment_notax == Decimal('929236.37')
        # Advance withtax = notax × 1.16 per spec
        assert project.advancepayment_withtax == Decimal('1077914.1892')

    def test_copies_exchange_rate(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        estimation.exchangerate_mxn_usd = Decimal('21')
        estimation.save()

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.exchangerate_mxn_usd == Decimal('21')

    def test_sets_awarddate_to_today(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.awarddate == timezone.now().date()

    def test_sets_owner_to_invoking_user(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.ownerid_id == salesperson.systemuserid
        assert project.createdby_id == salesperson.systemuserid

    def test_initial_state_is_draft(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert project.statecode == ProjectStateCode.DRAFT


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionZoneAndCategories:
    """The service must seed a default zone and the project's cost categories.

    - 1 ProjectZone 'GEN' (general) for direct cost codes
    - 1 CostCategory direct per ConceptFamily in the estimation (Opción A from spec)
    - 8 standard CostCategory indirects (C1-C8)
    """

    def test_creates_default_GEN_zone(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        zones = list(ProjectZone.objects.filter(projectid=project))
        assert len(zones) == 1
        assert zones[0].prefix == 'GEN'
        assert zones[0].name == 'General'

    def test_creates_one_direct_cost_category_per_family(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        ConceptFamilyFactory(projectid=estimation, name='Pilas de Cimentación', sortorder=1)
        ConceptFamilyFactory(projectid=estimation, name='Mecánicas y Topografías', sortorder=2)
        ConceptFamilyFactory(projectid=estimation, name='Shelter Jiquilpan', sortorder=3)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        directs = list(
            CostCategory.objects.filter(projectid=project, costtype=CostTypeCode.DIRECT).order_by('sortorder')
        )
        assert [c.code for c in directs] == ['P1', 'P2', 'P3']
        assert [c.name for c in directs] == [
            'Pilas de Cimentación',
            'Mecánicas y Topografías',
            'Shelter Jiquilpan',
        ]

    def test_no_direct_categories_when_estimation_has_no_families(self, db, salesperson):
        # Edge case: estimation has 0 ConceptFamily — direct categories list is empty.
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        directs = CostCategory.objects.filter(projectid=project, costtype=CostTypeCode.DIRECT)
        assert directs.count() == 0

    def test_groups_extra_families_under_P10_when_more_than_nine(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        for i in range(12):
            ConceptFamilyFactory(projectid=estimation, name=f'Family {i+1}', sortorder=i+1)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        directs = list(
            CostCategory.objects.filter(projectid=project, costtype=CostTypeCode.DIRECT).order_by('sortorder')
        )
        codes = [c.code for c in directs]
        # P1..P9 then a single P10 "Otros"
        assert codes == ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9', 'P10']
        assert directs[-1].name == 'Otros'

    def test_seeds_eight_standard_indirect_categories(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        indirects = list(
            CostCategory.objects.filter(projectid=project, costtype=CostTypeCode.INDIRECT).order_by('sortorder')
        )
        assert [c.code for c in indirects] == ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8']


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionPeriods:
    """The service must auto-generate ImputationPeriod rows for the new project."""

    def test_creates_imputation_periods_within_project_date_range(self, db, salesperson):
        # 6 months × 2 quincenas = 12 fortnightly periods for Jan-Jun 2026
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        periods = list(ImputationPeriod.objects.filter(projectid=project).order_by('sortorder'))
        assert len(periods) == 12
        assert periods[0].startdate == date(2026, 1, 1)
        # Last period should land within June
        assert periods[-1].enddate.month == 6
        assert periods[-1].enddate.year == 2026

    def test_period_labels_are_in_spanish(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        labels = [p.label for p in ImputationPeriod.objects.filter(projectid=project).order_by('sortorder')]
        # PeriodService formats labels with Spanish month abbreviations (ENE, FEB...)
        assert any('ENE' in label for label in labels)
        assert any('JUN' in label for label in labels)


def _make_concept(estimation, family, *, code, description, quantity, directunit, indirectunit, totalamount):
    """Helper to build a BudgetConcept under a given family in a single line."""
    subfamily = ConceptSubfamilyFactory(familyid=family, projectid=estimation)
    return BudgetConceptFactory(
        projectid=estimation,
        subfamilyid=subfamily,
        code=code,
        description=description,
        unit='m3',
        quantity=Decimal(str(quantity)),
        directunitcost=Decimal(str(directunit)),
        indirectunitcost=Decimal(str(indirectunit)),
        unitprice=Decimal(str(directunit)) + Decimal(str(indirectunit)),
        totalamount=Decimal(str(totalamount)),
    )


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionDirectCodes:
    """The service must create 1 ImputationCode per BudgetConcept with correct field mapping."""

    def test_creates_one_imputation_code_per_concept(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        family = ConceptFamilyFactory(projectid=estimation, name='Pilas', sortorder=1)
        _make_concept(estimation, family, code='A1', description='Concepto 1',
                      quantity=10, directunit=100, indirectunit=20, totalamount=1200)
        _make_concept(estimation, family, code='A2', description='Concepto 2',
                      quantity=5, directunit=200, indirectunit=30, totalamount=1150)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        codes = ImputationCode.objects.filter(projectid=project, costtype=CostTypeCode.DIRECT)
        assert codes.count() == 2

    def test_imputation_code_uses_GEN_zone_and_correct_category(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        family_pilas = ConceptFamilyFactory(projectid=estimation, name='Pilas', sortorder=1)
        family_shelter = ConceptFamilyFactory(projectid=estimation, name='Shelter', sortorder=2)
        _make_concept(estimation, family_pilas, code='A1', description='Pila',
                      quantity=1, directunit=0, indirectunit=0, totalamount=0)
        _make_concept(estimation, family_shelter, code='B1', description='Shelter',
                      quantity=1, directunit=0, indirectunit=0, totalamount=0)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        zone = ProjectZone.objects.get(projectid=project, prefix='GEN')
        cat_p1 = CostCategory.objects.get(projectid=project, code='P1')
        cat_p2 = CostCategory.objects.get(projectid=project, code='P2')

        code_a1 = ImputationCode.objects.get(projectid=project, contractcode='A1')
        code_b1 = ImputationCode.objects.get(projectid=project, contractcode='B1')

        assert code_a1.zoneid_id == zone.zoneid
        assert code_a1.categoryid_id == cat_p1.categoryid
        assert code_b1.categoryid_id == cat_p2.categoryid

    def test_imputation_code_string_uses_GEN_P_seq_pattern(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        family = ConceptFamilyFactory(projectid=estimation, name='Pilas', sortorder=1)
        _make_concept(estimation, family, code='A1', description='c1',
                      quantity=1, directunit=0, indirectunit=0, totalamount=0)
        _make_concept(estimation, family, code='A2', description='c2',
                      quantity=1, directunit=0, indirectunit=0, totalamount=0)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        codes = sorted(
            ImputationCode.objects.filter(projectid=project, costtype=CostTypeCode.DIRECT).values_list('code', flat=True)
        )
        # Sequence is per (project, category, zone) and starts at 1
        assert codes == ['GEN-P1-1', 'GEN-P1-2']

    def test_imputation_code_preserves_source_concept_and_contractcode(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        family = ConceptFamilyFactory(projectid=estimation, name='F', sortorder=1)
        concept = _make_concept(estimation, family, code='A1', description='Excavación',
                                quantity=18.7, directunit=3000, indirectunit=586.42, totalamount=67066.05)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        code = ImputationCode.objects.get(projectid=project, contractcode='A1')
        assert code.sourceconceptid_id == concept.conceptid
        assert code.name == 'Excavación'
        assert code.unit == 'm3'
        assert code.quantity == Decimal('18.7')
        # unitcost = directunitcost + indirectunitcost
        assert code.unitcost == Decimal('3586.42')
        assert code.totalbudget == Decimal('67066.05')


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionDirectBudgets:
    """Per spec §6.6, every direct ImputationCode gets ImputationCodeBudget rows per period.

    Formula: ``plannedamount(concept, period) = SUM(breakdown.amount × concept.quantity × fraction)``.
    plannedvolume comes from ``WorkPlanEntry.distributedquantity`` for entrytype=PLANNED.
    """

    def _seed_concept_with_distribution(self, estimation, family, *, salesperson):
        # 1 concept, quantity=10, with 1 breakdown of amount=$100/unit → total $1000.
        concept = _make_concept(estimation, family, code='A1', description='c',
                                quantity=10, directunit=100, indirectunit=0, totalamount=1000)
        breakdown = UnitCostBreakdownFactory(
            conceptid=concept,
            quantity=Decimal('1'), unitprice=Decimal('100'), yieldvalue=Decimal('1'),
            amount=Decimal('100'),
        )
        # Project has 12 periods (Jan-Jun 2026 quincenal). For the test, all weight
        # lands in period 1 → plannedamount should be $1000 for period 1 and $0 elsewhere.
        for period_num in range(1, 13):
            ProjectionPeriod.objects.create(
                projectid=estimation,
                periodnumber=period_num,
                periodlabel=f'P{period_num}',
                startdate=date(2026, 1, 1),
                enddate=date(2026, 1, 15),
                periodtype=1,
                createdby=salesperson,
                modifiedby=salesperson,
            )
        CostDistribution.objects.create(
            projectid=estimation,
            linetype=CostLineType.BREAKDOWN,
            breakdownid=breakdown,
            periodnumber=1,
            fraction=Decimal('1'),
        )
        return concept

    def test_creates_imputation_code_budget_per_period(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        family = ConceptFamilyFactory(projectid=estimation, name='F', sortorder=1)
        self._seed_concept_with_distribution(estimation, family, salesperson=salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)
        code = ImputationCode.objects.get(projectid=project, contractcode='A1')
        budgets = ImputationCodeBudget.objects.filter(imputationcodeid=code).order_by('periodlabel')

        assert budgets.count() == 12  # 1 row per project period

    def test_planned_amount_follows_breakdown_times_quantity_times_fraction(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        family = ConceptFamilyFactory(projectid=estimation, name='F', sortorder=1)
        self._seed_concept_with_distribution(estimation, family, salesperson=salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)
        code = ImputationCode.objects.get(projectid=project, contractcode='A1')
        first_period = ImputationPeriod.objects.filter(projectid=project).order_by('sortorder').first()
        budget_first = ImputationCodeBudget.objects.get(imputationcodeid=code, periodid=first_period)
        budget_others = ImputationCodeBudget.objects.filter(imputationcodeid=code).exclude(periodid=first_period)

        # breakdown.amount=100 × concept.quantity=10 × fraction(period1)=1 = 1000
        assert budget_first.plannedamount == Decimal('1000.00')
        assert all(b.plannedamount == Decimal('0.00') for b in budget_others)

    def test_planned_volume_comes_from_workplan_entry(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        family = ConceptFamilyFactory(projectid=estimation, name='F', sortorder=1)
        concept = self._seed_concept_with_distribution(estimation, family, salesperson=salesperson)
        WorkPlanEntryFactory(
            conceptid=concept, projectid=estimation,
            periodnumber=1, periodlabel='P1',
            entrytype=WorkPlanEntryType.PLANNED,
            distributedquantity=Decimal('7'),
        )

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)
        code = ImputationCode.objects.get(projectid=project, contractcode='A1')
        first_period = ImputationPeriod.objects.filter(projectid=project).order_by('sortorder').first()
        budget_first = ImputationCodeBudget.objects.get(imputationcodeid=code, periodid=first_period)

        assert budget_first.plannedvolume == Decimal('7.0000')


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionIndirectCodes:
    """The service must create 1 indirect ImputationCode per IndirectCostDetail + per-period budgets.

    Indirect codes have zoneid=None (system convention). Categories map by
    ``IndirectCostDetail.categorycode`` (already in 'C1'..'C8' format) to the
    standard C1..C8 categories seeded earlier.
    """

    def _seed_indirect_with_distribution(self, estimation, *, salesperson, categorycode='C1', amount=3000):
        # Create 12 projection periods to match the project's quincenal calendar.
        for period_num in range(1, 13):
            ProjectionPeriod.objects.create(
                projectid=estimation,
                periodnumber=period_num,
                periodlabel=f'P{period_num}',
                startdate=date(2026, 1, 1),
                enddate=date(2026, 1, 15),
                periodtype=1,
                createdby=salesperson,
                modifiedby=salesperson,
            )
        detail = IndirectCostDetailFactory(
            projectid=estimation,
            categorycode=categorycode,
            description='Personal de oficina',
            area='Gerente',
            monthlycost=Decimal('1000'),
            units=Decimal('1'),
            months=Decimal('3'),
            amount=Decimal(str(amount)),
        )
        # Half in P1, half in P2
        CostDistribution.objects.create(
            projectid=estimation,
            linetype=CostLineType.INDIRECT,
            indirectcostid=detail,
            periodnumber=1,
            fraction=Decimal('0.5'),
        )
        CostDistribution.objects.create(
            projectid=estimation,
            linetype=CostLineType.INDIRECT,
            indirectcostid=detail,
            periodnumber=2,
            fraction=Decimal('0.5'),
        )
        return detail

    def test_creates_one_imputation_code_per_indirect_detail(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        self._seed_indirect_with_distribution(estimation, salesperson=salesperson, categorycode='C1')
        IndirectCostDetailFactory(projectid=estimation, categorycode='C2', amount=Decimal('1500'))

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        codes = ImputationCode.objects.filter(projectid=project, costtype=CostTypeCode.INDIRECT)
        assert codes.count() == 2

    def test_indirect_code_maps_to_C1_C8_category_and_has_no_zone(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        self._seed_indirect_with_distribution(estimation, salesperson=salesperson, categorycode='C3')

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        cat_c3 = CostCategory.objects.get(projectid=project, code='C3')
        code = ImputationCode.objects.get(projectid=project, costtype=CostTypeCode.INDIRECT, categoryid=cat_c3)
        assert code.zoneid is None
        assert code.code.startswith('C3-')

    def test_indirect_code_code_string_uses_C_seq_pattern(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        IndirectCostDetailFactory(projectid=estimation, categorycode='C1', amount=Decimal('100'))
        IndirectCostDetailFactory(projectid=estimation, categorycode='C1', amount=Decimal('200'))
        IndirectCostDetailFactory(projectid=estimation, categorycode='C2', amount=Decimal('300'))

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        codes = sorted(
            ImputationCode.objects.filter(projectid=project, costtype=CostTypeCode.INDIRECT).values_list('code', flat=True)
        )
        assert codes == ['C1-1', 'C1-2', 'C2-1']

    def test_indirect_budget_uses_indirect_amount_times_fraction(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        self._seed_indirect_with_distribution(estimation, salesperson=salesperson, amount=3000)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        code = ImputationCode.objects.get(projectid=project, costtype=CostTypeCode.INDIRECT)
        periods = list(ImputationPeriod.objects.filter(projectid=project).order_by('sortorder'))
        budget_p1 = ImputationCodeBudget.objects.get(imputationcodeid=code, periodid=periods[0])
        budget_p2 = ImputationCodeBudget.objects.get(imputationcodeid=code, periodid=periods[1])
        budget_p3 = ImputationCodeBudget.objects.get(imputationcodeid=code, periodid=periods[2])

        assert budget_p1.plannedamount == Decimal('1500.00')  # 3000 × 0.5
        assert budget_p2.plannedamount == Decimal('1500.00')  # 3000 × 0.5
        assert budget_p3.plannedamount == Decimal('0.00')

    def test_indirect_code_copies_personnel_fields_for_C1(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)
        IndirectCostDetailFactory(
            projectid=estimation,
            categorycode='C1',
            description='Gerente de Proyecto',
            area='Project Manager',
            monthlycost=Decimal('21600'),
            units=Decimal('1'),
            months=Decimal('6'),
            amount=Decimal('129600'),
        )

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        code = ImputationCode.objects.get(projectid=project, costtype=CostTypeCode.INDIRECT)
        # personnel fields populate when the detail is C1
        assert code.name == 'Gerente de Proyecto'
        assert code.personnelrole == 'Project Manager'
        assert code.monthlycost == Decimal('21600.00')
        assert code.units == Decimal('1.00')
        assert code.executionmonths == 6
        assert code.totalbudget == Decimal('129600.00')


@pytest.mark.unit
@pytest.mark.workflow
class TestEstimationConversionLockAndIdempotency:
    """After conversion the estimation must be locked (CONVERTED) and linked to the project.

    Calling convert again raises a dedicated ``AlreadyConvertedError`` carrying the
    existing projectid so the endpoint can return 409 with the link.
    """

    def test_marks_estimation_as_converted(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        estimation.refresh_from_db()
        assert estimation.statecode == EstimationStateCode.CONVERTED

    def test_sets_generatedprojectid_on_estimation(self, db, salesperson):
        estimation = _accepted_estimation(salesperson)

        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        estimation.refresh_from_db()
        assert estimation.generatedprojectid_id == project.projectid

    def test_second_call_raises_already_converted_with_existing_projectid(self, db, salesperson):
        from apps.proyeccion.services import AlreadyConvertedError

        estimation = _accepted_estimation(salesperson)
        project = EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        with pytest.raises(AlreadyConvertedError) as exc:
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        assert exc.value.projectid == project.projectid

    def test_failure_inside_conversion_rolls_back_everything(self, db, salesperson, mocker):
        estimation = _accepted_estimation(salesperson)

        # Force an exception in the last seeded step.
        mocker.patch(
            'apps.proyeccion.services.EstimationConversionService._seed_indirect_imputation_codes_and_budgets',
            side_effect=RuntimeError('boom'),
        )

        with pytest.raises(RuntimeError):
            EstimationConversionService.convert(estimation.estimationprojectid, user=salesperson)

        # No project, no zone, no categories, no periods leaked.
        assert ConstructionProject.objects.count() == 0
        assert ProjectZone.objects.count() == 0
        assert CostCategory.objects.count() == 0
        assert ImputationPeriod.objects.count() == 0
        estimation.refresh_from_db()
        assert estimation.statecode == EstimationStateCode.ACCEPTED  # state did NOT change
        assert estimation.generatedprojectid_id is None


@pytest.mark.contract
@pytest.mark.workflow
class TestEstimationConvertEndpoint:
    """The HTTP endpoint pulls everything from the estimation; no body needed."""

    def _build_accepted(self, system_admin):
        # System-admin-owned data so admin_auth_client can read it without RBAC headaches.
        return _accepted_estimation(system_admin)

    def test_post_convert_returns_200_with_project_summary(self, admin_auth_client, system_admin):
        estimation = self._build_accepted(system_admin)

        response = admin_auth_client.post(
            f'/api/estimation-projects/{estimation.estimationprojectid}/convert/',
            data='{}',
            content_type='application/json',
        )

        assert response.status_code == 200, response.content
        body = response.json()
        assert 'projectid' in body
        assert body['projectnumber'].startswith('PRY-')
        assert body['estimation_locked'] is True
        assert body['summary']['periods_created'] == 12

    def test_post_convert_returns_409_on_already_converted(self, admin_auth_client, system_admin):
        estimation = self._build_accepted(system_admin)
        first = admin_auth_client.post(
            f'/api/estimation-projects/{estimation.estimationprojectid}/convert/',
            data='{}', content_type='application/json',
        )
        assert first.status_code == 200
        project_id = first.json()['projectid']

        second = admin_auth_client.post(
            f'/api/estimation-projects/{estimation.estimationprojectid}/convert/',
            data='{}', content_type='application/json',
        )
        assert second.status_code == 409
        body = second.json()
        # The global AlreadyConvertedError handler returns the existing projectid
        # nested under error.details so the UI can link the user to the project.
        assert body['error']['details']['projectid'] == project_id

    def test_post_convert_returns_400_on_draft_estimation(self, admin_auth_client, system_admin):
        estimation = EstimationProjectFactory(
            statecode=EstimationStateCode.DRAFT,
            ownerid=system_admin,
        )

        response = admin_auth_client.post(
            f'/api/estimation-projects/{estimation.estimationprojectid}/convert/',
            data='{}', content_type='application/json',
        )
        assert response.status_code == 400

    def test_patch_on_converted_estimation_returns_409(self, admin_auth_client, system_admin):
        estimation = self._build_accepted(system_admin)
        admin_auth_client.post(
            f'/api/estimation-projects/{estimation.estimationprojectid}/convert/',
            data='{}', content_type='application/json',
        )

        response = admin_auth_client.patch(
            f'/api/estimation-projects/{estimation.estimationprojectid}/',
            data='{"name": "x"}', content_type='application/json',
        )
        assert response.status_code == 409

    def test_delete_on_converted_estimation_returns_409(self, admin_auth_client, system_admin):
        estimation = self._build_accepted(system_admin)
        admin_auth_client.post(
            f'/api/estimation-projects/{estimation.estimationprojectid}/convert/',
            data='{}', content_type='application/json',
        )

        response = admin_auth_client.delete(
            f'/api/estimation-projects/{estimation.estimationprojectid}/',
        )
        assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.workflow
@pytest.mark.slow
class TestEstimationConversionGolden:
    """End-to-end conversion of a real Estudio loaded from the
    `001. Estudio Obra Fortificación Taludes.xlsx` seed command.

    Verifies the entire pipeline against representative production data
    (1 family, ~63 concepts, ~17 indirects, 3 offer alternatives).
    """

    def test_conversion_of_loaded_estudio_creates_consistent_project(self, db, system_admin):
        from django.core.management import call_command
        from apps.accounts.tests.factories import AccountFactory
        from apps.proyeccion.models import (
            BudgetConcept, EstimationProject, IndirectCostDetail, OfferAlternative,
        )

        # Load the production-shaped estudio (creates everything except Account / FinancialSettings).
        call_command('load_estudio_fortificacion')
        estudio = EstimationProject.objects.get(estimationnumber='EST-2026-001')
        # Add what convert() requires beyond the loader's output.
        estudio.accountid = AccountFactory(ownerid=system_admin)
        estudio.statecode = EstimationStateCode.ACCEPTED
        estudio.save()
        EstimationFinancialSettings.objects.create(
            projectid=estudio,
            advanceamountnotax=Decimal('1857000'),  # ~30% of contract
            createdby=system_admin,
            modifiedby=system_admin,
        )

        # Verify the loader produced the shape we expect.
        n_concepts = BudgetConcept.objects.filter(projectid=estudio).count()
        n_indirects = IndirectCostDetail.objects.filter(projectid=estudio).count()
        chosen = OfferAlternative.objects.get(projectid=estudio, ischosen=True)
        assert n_concepts > 0, "loader produced no concepts"
        assert n_indirects > 0, "loader produced no indirects"

        # Convert.
        project = EstimationConversionService.convert(estudio.estimationprojectid, user=system_admin)

        # Project header reflects the chosen alternative's prices.
        assert project.contractamount_notax == chosen.salepricenet
        assert project.contractamount_withtax == chosen.salepricetotal
        assert project.advancepayment_notax == Decimal('1857000.00')

        # 1 zone GEN + 1 direct CostCategory per family + 8 indirect categories.
        assert ProjectZone.objects.filter(projectid=project).count() == 1
        n_direct_cats = CostCategory.objects.filter(projectid=project, costtype=CostTypeCode.DIRECT).count()
        n_indirect_cats = CostCategory.objects.filter(projectid=project, costtype=CostTypeCode.INDIRECT).count()
        assert n_direct_cats == 1   # the loader creates exactly 1 family
        assert n_indirect_cats == 8

        # 1 ImputationCode per concept (direct) and per IndirectCostDetail (indirect).
        n_direct_codes = ImputationCode.objects.filter(projectid=project, costtype=CostTypeCode.DIRECT).count()
        n_indirect_codes = ImputationCode.objects.filter(projectid=project, costtype=CostTypeCode.INDIRECT).count()
        assert n_direct_codes == n_concepts
        assert n_indirect_codes == n_indirects

        # ImputationPeriods cover the project window (Feb 10 → Apr 10, quincenal ≈ 4-5 periods).
        n_periods = ImputationPeriod.objects.filter(projectid=project).count()
        assert n_periods >= 3

        # ImputationCodeBudget: one row per (code, period) for every direct + indirect.
        n_budgets = ImputationCodeBudget.objects.filter(imputationcodeid__projectid=project).count()
        assert n_budgets == (n_direct_codes + n_indirect_codes) * n_periods

        # Each direct ImputationCode preserves the source BudgetConcept link.
        unlinked_directs = ImputationCode.objects.filter(
            projectid=project, costtype=CostTypeCode.DIRECT, sourceconceptid__isnull=True,
        )
        assert unlinked_directs.count() == 0

        # Estudio is locked + linked.
        estudio.refresh_from_db()
        assert estudio.statecode == EstimationStateCode.CONVERTED
        assert estudio.generatedprojectid_id == project.projectid
