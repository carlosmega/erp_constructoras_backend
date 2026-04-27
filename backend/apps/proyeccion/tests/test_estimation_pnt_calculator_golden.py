"""Golden end-to-end test — full PNT computation with known inputs and expected outputs."""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from apps.proyeccion.services import (
    EstimationPNTCalculator, EstimationFinancialSettingsService, EstimationBillingRuleService,
)
from apps.proyeccion.tests.factories import EstimationProjectFactory, make_concept_for_project


@pytest.mark.django_db
@pytest.mark.workflow
def test_golden_end_to_end():
    """4-period project: 1 direct cost line + 1 indirect, 1 alternative, 2 billing rules.

    Verifies the entire chain: rollups → cobros → pagos → caja → resultado.
    """
    from apps.proyeccion.models import (
        ProjectionPeriod, OfferAlternative,
        UnitCostBreakdown, IndirectCostDetail, CostDistribution, WorkPlanEntry,
    )

    # 1. Project + 4 fortnightly periods
    project = EstimationProjectFactory(periodtype=1, periodcount=4)
    base = date(2026, 1, 1)
    for i in range(4):
        ProjectionPeriod.objects.create(
            projectid=project, periodnumber=i + 1,
            periodlabel=f'Q{(i % 2) + 1:02d} ENE-26' if i < 2 else f'Q{(i % 2) + 1:02d} FEB-26',
            startdate=base + timedelta(days=i * 14),
            enddate=base + timedelta(days=i * 14 + 13),
            periodtype=1,
        )

    # 2. One chosen alternative
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name='Base',
        transversalpercent=Decimal('0.05'), profitpercent=Decimal('0.10'),
        coefficient=Decimal('1.15'),
        directcosttotal=Decimal('1000'), indirectcosttotal=Decimal('200'),
        constructioncost=Decimal('1200'), salepricenet=Decimal('1380'),
        taxamount=Decimal('220.80'), salepricetotal=Decimal('1600.80'),
        ischosen=True,
    )

    # 3. One direct line: $1000 distributed 25% per period
    concept = make_concept_for_project(project, code='C-001', description='Concrete', unit='m3')
    breakdown = UnitCostBreakdown.objects.create(
        conceptid=concept, categorycode=1, linenumber=1, description='Concrete',
        unit='m3', quantity=Decimal('1'), unitprice=Decimal('1000'),
        yieldvalue=Decimal('1'), amount=Decimal('1000'),
    )
    indirect = IndirectCostDetail.objects.create(
        projectid=project, categorycode='C1', linenumber=1, description='Office',
        monthlycost=Decimal('100'), units=Decimal('1'), months=Decimal('2'),
        amount=Decimal('200'),
    )
    for n in range(1, 5):
        CostDistribution.objects.create(
            projectid=project, linetype=0, breakdownid=breakdown,
            periodnumber=n, fraction=Decimal('0.25'), isderived=True,
        )
        CostDistribution.objects.create(
            projectid=project, linetype=1, indirectcostid=indirect,
            periodnumber=n, fraction=Decimal('0.25'), isderived=True,
        )

    # 4. WorkPlan: $1380 sale distributed 25% per period
    for n in range(1, 5):
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=n,
            periodlabel=f'P{n:02d}',
            entrytype=0, distributedquantity=Decimal('0.25'), distributedamount=Decimal('345'),
        )

    # 5. Settings: 5% IMSS retention, return at period 4, 50% advance amortization, 100 advance
    EstimationFinancialSettingsService.update(
        project.estimationprojectid,
        {
            'imssretentionrate': Decimal('0.05'),
            'retentionreturnperiod': 4,
            'advanceamountnotax': Decimal('100'),
            'advanceentryperiod': 1,
            'advanceamortizationrate': Decimal('0.10'),
            'directpaymentlag': 0,
            'indirectpaymentlag': 0,
        },
        user=None,
    )

    # 6. Billing rules: 60% lag 0, 40% lag 1
    EstimationBillingRuleService.replace(
        project.estimationprojectid,
        [{'sequence': 1, 'percent': Decimal('0.6'), 'lagperiods': 0},
         {'sequence': 2, 'percent': Decimal('0.4'), 'lagperiods': 1}],
        user=None,
    )

    # 7. Compute and assert
    calc = EstimationPNTCalculator(project.estimationprojectid)
    report = calc.compute()

    rows = {r.code: r.values for r in report.rows}

    # Producción = 345 per period
    assert rows['PRODUCCION'] == [Decimal('345')] * 4

    # Costo directo = -250 per period (negative)
    assert rows['COSTO_DIRECTO'] == [Decimal('-250.0000')] * 4

    # Costo indirecto = -50 per period
    assert rows['COSTO_INDIRECTO'] == [Decimal('-50.0000')] * 4

    # Period 1 production 345: rule1 (60%, lag 0) → P1=207; rule2 (40%, lag 1) → P2=138
    # Period 2 production 345: rule1 → P2=207; rule2 → P3=138
    # Period 3 production 345: rule1 → P3=207; rule2 → P4=138
    # Period 4 production 345: rule1 → P4=207; rule2 → P5 (out of range, fuera_horizonte=138)
    expected_fact = [Decimal('207'), Decimal('345'), Decimal('345'), Decimal('345')]
    assert rows['COBRO_FACTURACION'] == expected_fact
    assert report.stats['cobros_fuera_horizonte'] == Decimal('138')

    # Anticipo concedido en P1
    assert rows['ANTICIPO_CONCEDIDO'][0] == Decimal('100')
    assert sum(rows['ANTICIPO_CONCEDIDO'][1:]) == Decimal('0')

    # Devolución IMSS en P4: total IMSS = -0.05 × sum(fact) = -0.05 × 1242 = -62.10 → devolución +62.10
    assert rows['DEVOLUCION'][3] == Decimal('62.1000')

    # Caja acumulada terminal — verifica que computa y es Decimal
    assert isinstance(rows['CAJA_ACUMULADA'][-1], Decimal)
    # Stats sanity
    assert report.stats['pnt_min'] is not None
    assert report.stats['pnt_max'] is not None
