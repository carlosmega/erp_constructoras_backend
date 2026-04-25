import pytest
from decimal import Decimal
from apps.proyeccion.services import EstimationPNTCalculator
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory, EstimationBillingRuleFactory, build_pnt_ready_project,
)


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorInit:
    def test_raises_when_no_periods(self):
        project = EstimationProjectFactory()
        with pytest.raises(ValueError, match='Plan de Obra'):
            EstimationPNTCalculator(project.estimationprojectid)

    def test_loads_periods_in_order(self):
        project, periods = build_pnt_ready_project(periods=3)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        assert calc.N == 3
        assert [p.periodnumber for p in calc.periods] == [1, 2, 3]

    def test_default_billing_rule_when_none_persisted(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        # Default implícito: 100%/lag 0
        assert len(calc.billing_rules) == 1
        assert calc.billing_rules[0].percent == Decimal('1')
        assert calc.billing_rules[0].lagperiods == 0

    def test_loads_persisted_billing_rules(self):
        project, _ = build_pnt_ready_project(periods=2)
        EstimationBillingRuleFactory(projectid=project, sequence=1, percent=Decimal('0.5'), lagperiods=0)
        EstimationBillingRuleFactory(projectid=project, sequence=2, percent=Decimal('0.5'), lagperiods=1)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        assert len(calc.billing_rules) == 2
        assert calc.billing_rules[0].sequence == 1


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorOverrides:
    def test_apply_overrides_modifies_in_memory_only(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        original_rate = calc.settings.imssretentionrate
        calc._apply_overrides({'imssretentionrate': '0.20'})
        assert calc.settings.imssretentionrate == Decimal('0.20')
        # Refetch from DB — must be unchanged
        from apps.proyeccion.models import EstimationFinancialSettings
        fresh = EstimationFinancialSettings.objects.get(projectid=project)
        assert fresh.imssretentionrate == original_rate

    def test_overrides_billing_rules(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        calc._apply_overrides({
            'billing_rules': [
                {'sequence': 1, 'percent': '0.6', 'lagperiods': 0},
                {'sequence': 2, 'percent': '0.4', 'lagperiods': 2},
            ],
        })
        assert len(calc.billing_rules) == 2
        assert calc.billing_rules[1].lagperiods == 2

    def test_overrides_ignore_non_whitelisted(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        calc._apply_overrides({'unknown_key': 'whatever', 'settingsid': 'x'})
        # No exception, no change
        assert calc.settings.imssretentionrate == Decimal('0.0500')
