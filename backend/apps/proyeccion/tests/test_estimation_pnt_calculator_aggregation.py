import pytest
from decimal import Decimal
from datetime import date
from apps.proyeccion.services import EstimationPNTCalculator
from apps.proyeccion.tests.factories import build_pnt_ready_project, make_concept_for_project


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorMonthly:
    def test_groups_periods_by_year_month(self):
        project, periods = build_pnt_ready_project(periods=4)
        from apps.proyeccion.models import ProjectionPeriod
        ProjectionPeriod.objects.filter(projectid=project, periodnumber=1).update(
            startdate=date(2026, 1, 1), enddate=date(2026, 1, 14),
        )
        ProjectionPeriod.objects.filter(projectid=project, periodnumber=2).update(
            startdate=date(2026, 1, 15), enddate=date(2026, 1, 28),
        )
        ProjectionPeriod.objects.filter(projectid=project, periodnumber=3).update(
            startdate=date(2026, 2, 1), enddate=date(2026, 2, 14),
        )
        ProjectionPeriod.objects.filter(projectid=project, periodnumber=4).update(
            startdate=date(2026, 2, 15), enddate=date(2026, 2, 28),
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute(granularity='month')
        assert len(report.periods) == 2
        assert report.periods[0]['label'] == '2026-01'
        assert report.periods[1]['label'] == '2026-02'

    def test_flow_rows_sum_within_month(self):
        project, periods = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import ProjectionPeriod, WorkPlanEntry
        for n in [1, 2]:
            ProjectionPeriod.objects.filter(projectid=project, periodnumber=n).update(
                startdate=date(2026, 1, 1 + (n - 1) * 14),
                enddate=date(2026, 1, 14 + (n - 1) * 14),
            )
        concept = make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('100'),
        )
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=2, periodlabel='P02',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('200'),
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute(granularity='month')
        prod = next(r for r in report.rows if r.code == 'PRODUCCION').values
        assert len(prod) == 1
        assert prod[0] == Decimal('300')

    def test_cumulative_rows_take_last_within_month(self):
        project, periods = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import ProjectionPeriod
        for n in [1, 2]:
            ProjectionPeriod.objects.filter(projectid=project, periodnumber=n).update(
                startdate=date(2026, 1, 1 + (n - 1) * 14),
                enddate=date(2026, 1, 14 + (n - 1) * 14),
            )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report_period = calc.compute(granularity='period')
        report_month = calc.compute(granularity='month')
        caja_acc_period = next(r for r in report_period.rows if r.code == 'CAJA_ACUMULADA').values
        caja_acc_month = next(r for r in report_month.rows if r.code == 'CAJA_ACUMULADA').values
        assert caja_acc_month[0] == caja_acc_period[-1]

    def test_invalid_granularity_raises(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        with pytest.raises(ValueError, match='granularity'):
            calc.compute(granularity='quarter')
