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
