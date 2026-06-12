import pytest
from datetime import date
from apps.proyeccion.models import ProjectionPeriod, EstimationProject
from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.django_db
@pytest.mark.unit
def test_projection_period_model_basic_fields():
    project = EstimationProjectFactory()
    period = ProjectionPeriod.objects.create(
        projectid=project,
        periodnumber=1,
        periodlabel="Q1 ENE-26",
        startdate=date(2026, 1, 1),
        enddate=date(2026, 1, 15),
        periodtype=1,
    )
    assert period.periodid is not None
    assert period.periodnumber == 1
    assert period.periodlabel == "Q1 ENE-26"
    assert str(period.startdate) == "2026-01-01"


@pytest.mark.django_db
@pytest.mark.unit
def test_projection_period_unique_per_project():
    project = EstimationProjectFactory()
    ProjectionPeriod.objects.create(
        projectid=project, periodnumber=1, periodlabel="P1",
        startdate=date(2026, 1, 1), enddate=date(2026, 1, 15), periodtype=1,
    )
    with pytest.raises(Exception):  # IntegrityError from unique_together
        ProjectionPeriod.objects.create(
            projectid=project, periodnumber=1, periodlabel="P1 dup",
            startdate=date(2026, 1, 16), enddate=date(2026, 1, 31), periodtype=1,
        )


@pytest.mark.django_db
@pytest.mark.unit
def test_estimation_project_periodcount_default_zero():
    project = EstimationProjectFactory()
    assert project.periodcount == 0


from apps.proyeccion.services import PeriodService


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_creates_weekly_periods():
    project = EstimationProjectFactory(
        estimatedstartdate=date(2026, 1, 5),
        estimatedenddate=date(2026, 2, 1),
        periodtype=0,  # weekly
    )
    result = PeriodService.regenerate_projection_periods(project)
    # Semanas de calendario, meses completos: ene S1–S4 + feb S1–S4 = 8.
    assert result['created'] == 8
    project.refresh_from_db()
    assert project.periodcount == 8
    periods = list(ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'))
    assert len(periods) == 8
    assert periods[0].periodlabel.startswith('S01')
    assert periods[0].startdate == date(2026, 1, 1)
    assert periods[0].enddate == date(2026, 1, 7)


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_creates_fortnightly_periods():
    project = EstimationProjectFactory(
        estimatedstartdate=date(2026, 1, 1),
        estimatedenddate=date(2026, 3, 31),
        periodtype=1,  # fortnightly
    )
    result = PeriodService.regenerate_projection_periods(project)
    assert result['created'] == 6  # ~6 fortnights in 3 months
    periods = list(ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'))
    assert periods[0].periodlabel == 'Q01 ENE-26'


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_fortnightly_is_calendar_anchored():
    """Quincenas de calendario (Q1=1–15, Q2=16–fin de mes), misma convención que
    ImputationPeriod de Operaciones. El generador viejo avanzaba 15 días corridos
    y en meses de 31 días producía una tercera 'quincena' del mes (EST-2026-004
    en prod: Q03/Q04/Q05 todas de JUL)."""
    project = EstimationProjectFactory(
        estimatedstartdate=date(2026, 6, 2),
        estimatedenddate=date(2026, 8, 31),
        periodtype=1,  # fortnightly
    )
    result = PeriodService.regenerate_projection_periods(project)
    assert result['created'] == 6  # jun, jul, ago × 2 quincenas
    periods = list(ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'))

    # Exactamente 2 períodos por mes — julio (31 días) NO produce un tercero.
    july = [p for p in periods if p.startdate.month == 7]
    assert len(july) == 2
    assert (july[0].startdate, july[0].enddate) == (date(2026, 7, 1), date(2026, 7, 15))
    assert (july[1].startdate, july[1].enddate) == (date(2026, 7, 16), date(2026, 7, 31))
    assert july[0].periodlabel == 'Q03 JUL-26'
    assert july[1].periodlabel == 'Q04 JUL-26'

    # Mes completo: arranca el día 1 del mes de inicio aunque el proyecto empiece el 2.
    assert periods[0].startdate == date(2026, 6, 1)
    # Q2 de agosto cierra en el último día del mes.
    assert periods[-1].enddate == date(2026, 8, 31)


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_weekly_is_calendar_anchored():
    """Semanas de calendario S1=1–7, S2=8–14, S3=15–21, S4=22–fin de mes (S4
    absorbe los días extra), misma convención que Operaciones: 4 por mes."""
    project = EstimationProjectFactory(
        estimatedstartdate=date(2026, 1, 5),
        estimatedenddate=date(2026, 1, 31),
        periodtype=0,  # weekly
    )
    result = PeriodService.regenerate_projection_periods(project)
    assert result['created'] == 4
    periods = list(ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'))
    assert (periods[0].startdate, periods[0].enddate) == (date(2026, 1, 1), date(2026, 1, 7))
    assert (periods[3].startdate, periods[3].enddate) == (date(2026, 1, 22), date(2026, 1, 31))
    assert periods[0].periodlabel == 'S01 ENE-26'


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_without_dates_raises():
    project = EstimationProjectFactory(estimatedstartdate=None, estimatedenddate=None)
    with pytest.raises(ValueError, match="fechas"):
        PeriodService.regenerate_projection_periods(project)


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_preserves_periodnumbers_on_extension():
    project = EstimationProjectFactory(
        estimatedstartdate=date(2026, 1, 1), estimatedenddate=date(2026, 2, 28),
        periodtype=1,
    )
    PeriodService.regenerate_projection_periods(project)
    count_before = ProjectionPeriod.objects.filter(projectid=project).count()

    project.estimatedenddate = date(2026, 4, 30)
    project.save()
    PeriodService.regenerate_projection_periods(project)
    count_after = ProjectionPeriod.objects.filter(projectid=project).count()
    assert count_after > count_before
