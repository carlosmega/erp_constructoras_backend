import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.proyeccion.models import EstimationBillingRule
from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationBillingRuleModel:
    def test_can_create_with_required_fields(self):
        project = EstimationProjectFactory()
        rule = EstimationBillingRule.objects.create(
            projectid=project, sequence=1, percent=Decimal('1.0000'), lagperiods=0,
        )
        assert rule.ruleid is not None
        assert rule.sequence == 1
        assert rule.percent == Decimal('1.0000')
        assert rule.lagperiods == 0

    def test_unique_sequence_per_project(self):
        project = EstimationProjectFactory()
        EstimationBillingRule.objects.create(
            projectid=project, sequence=1, percent=Decimal('0.5'), lagperiods=0,
        )
        with pytest.raises(IntegrityError):
            EstimationBillingRule.objects.create(
                projectid=project, sequence=1, percent=Decimal('0.5'), lagperiods=1,
            )

    def test_percent_range_constraint(self):
        project = EstimationProjectFactory()
        with pytest.raises(IntegrityError):
            EstimationBillingRule.objects.create(
                projectid=project, sequence=1, percent=Decimal('1.5'), lagperiods=0,
            )

    def test_sequence_range_constraint(self):
        project = EstimationProjectFactory()
        with pytest.raises(IntegrityError):
            EstimationBillingRule.objects.create(
                projectid=project, sequence=11, percent=Decimal('0.5'), lagperiods=0,
            )

    def test_lag_range_constraint(self):
        project = EstimationProjectFactory()
        with pytest.raises(IntegrityError):
            EstimationBillingRule.objects.create(
                projectid=project, sequence=1, percent=Decimal('0.5'), lagperiods=121,
            )

    def test_ordering_by_sequence(self):
        project = EstimationProjectFactory()
        EstimationBillingRule.objects.create(projectid=project, sequence=2, percent=Decimal('0.3'), lagperiods=0)
        EstimationBillingRule.objects.create(projectid=project, sequence=1, percent=Decimal('0.7'), lagperiods=0)
        rules = list(EstimationBillingRule.objects.filter(projectid=project))
        assert [r.sequence for r in rules] == [1, 2]


from apps.proyeccion.services import EstimationBillingRuleService


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationBillingRuleService:
    def test_list_returns_ordered_by_sequence(self):
        project = EstimationProjectFactory()
        EstimationBillingRule.objects.create(projectid=project, sequence=2, percent=Decimal('0.3'), lagperiods=1)
        EstimationBillingRule.objects.create(projectid=project, sequence=1, percent=Decimal('0.7'), lagperiods=0)
        rules = EstimationBillingRuleService.list(project.estimationprojectid)
        assert [r.sequence for r in rules] == [1, 2]

    def test_replace_atomic_creates_new_set(self):
        project = EstimationProjectFactory()
        EstimationBillingRule.objects.create(projectid=project, sequence=1, percent=Decimal('1.0'), lagperiods=0)
        new_rules = [
            {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 0},
            {'sequence': 2, 'percent': Decimal('0.3'), 'lagperiods': 1},
            {'sequence': 3, 'percent': Decimal('0.2'), 'lagperiods': 2},
        ]
        result = EstimationBillingRuleService.replace(project.estimationprojectid, new_rules, user=None)
        assert len(result) == 3
        assert sum(r.percent for r in result) == Decimal('1.0')
        assert EstimationBillingRule.objects.filter(projectid=project).count() == 3

    def test_replace_rejects_sum_not_one(self):
        project = EstimationProjectFactory()
        with pytest.raises(ValueError, match='100%'):
            EstimationBillingRuleService.replace(
                project.estimationprojectid,
                [{'sequence': 1, 'percent': Decimal('0.6'), 'lagperiods': 0},
                 {'sequence': 2, 'percent': Decimal('0.3'), 'lagperiods': 1}],
                user=None,
            )

    def test_replace_accepts_sum_with_tolerance(self):
        project = EstimationProjectFactory()
        # Σ = 0.99995 — within ±0.0001 tolerance
        rules = [
            {'sequence': 1, 'percent': Decimal('0.33333'), 'lagperiods': 0},
            {'sequence': 2, 'percent': Decimal('0.33333'), 'lagperiods': 1},
            {'sequence': 3, 'percent': Decimal('0.33334'), 'lagperiods': 2},
        ]
        result = EstimationBillingRuleService.replace(project.estimationprojectid, rules, user=None)
        assert len(result) == 3

    def test_replace_rejects_too_many_rules(self):
        project = EstimationProjectFactory()
        too_many = [{'sequence': i, 'percent': Decimal('0.0909'), 'lagperiods': 0} for i in range(1, 12)]
        with pytest.raises(ValueError, match='10|máximo'):
            EstimationBillingRuleService.replace(project.estimationprojectid, too_many, user=None)

    def test_replace_rejects_empty_list(self):
        project = EstimationProjectFactory()
        with pytest.raises(ValueError, match='al menos|mínimo'):
            EstimationBillingRuleService.replace(project.estimationprojectid, [], user=None)

    def test_replace_rejects_duplicate_sequences(self):
        project = EstimationProjectFactory()
        with pytest.raises(ValueError, match='secuencia|sequence'):
            EstimationBillingRuleService.replace(
                project.estimationprojectid,
                [{'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 0},
                 {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 1}],
                user=None,
            )

    def test_replace_rolls_back_on_failure(self):
        project = EstimationProjectFactory()
        EstimationBillingRule.objects.create(projectid=project, sequence=1, percent=Decimal('1.0'), lagperiods=0)
        try:
            EstimationBillingRuleService.replace(
                project.estimationprojectid,
                [{'sequence': 1, 'percent': Decimal('0.6'), 'lagperiods': 0}],  # Σ ≠ 1
                user=None,
            )
        except ValueError:
            pass
        rules = EstimationBillingRule.objects.filter(projectid=project)
        assert rules.count() == 1
        assert rules.first().percent == Decimal('1.0')
