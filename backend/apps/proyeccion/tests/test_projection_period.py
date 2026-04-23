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
    assert result['created'] == 4  # 4 weeks
    project.refresh_from_db()
    assert project.periodcount == 4
    periods = list(ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'))
    assert len(periods) == 4
    assert periods[0].periodlabel.startswith('S01')
    assert periods[0].startdate == date(2026, 1, 5)
    assert periods[0].enddate == date(2026, 1, 11)


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
