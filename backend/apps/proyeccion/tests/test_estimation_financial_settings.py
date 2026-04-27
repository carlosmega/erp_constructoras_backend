import pytest
from decimal import Decimal
from apps.proyeccion.models import EstimationFinancialSettings
from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationFinancialSettingsModel:
    def test_can_create_with_defaults(self):
        project = EstimationProjectFactory()
        settings = EstimationFinancialSettings.objects.create(projectid=project)
        assert settings.advanceamountnotax == Decimal('0')
        assert settings.advanceentryperiod == 1
        assert settings.advanceamortizationrate == Decimal('0')
        assert settings.imssretentionrate == Decimal('0.0500')
        assert settings.otherretentionrate == Decimal('0')
        assert settings.retentionreturnperiod is None
        assert settings.directpaymentlag == 0
        assert settings.indirectpaymentlag == 0
        assert settings.financecostrate == Decimal('0.001000')

    def test_one_to_one_relation(self):
        project = EstimationProjectFactory()
        EstimationFinancialSettings.objects.create(projectid=project)
        with pytest.raises(Exception):  # IntegrityError under Postgres, similar under SQLite
            EstimationFinancialSettings.objects.create(projectid=project)

    def test_str_includes_project(self):
        project = EstimationProjectFactory(name='Test Obra X')
        settings = EstimationFinancialSettings.objects.create(projectid=project)
        assert 'Test Obra X' in str(settings) or str(project.estimationprojectid)[:8] in str(settings)


from apps.proyeccion.services import EstimationFinancialSettingsService


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationFinancialSettingsService:
    def test_get_or_create_creates_with_defaults_first_time(self):
        project = EstimationProjectFactory()
        settings = EstimationFinancialSettingsService.get_or_create(project.estimationprojectid)
        assert settings.imssretentionrate == Decimal('0.0500')
        assert EstimationFinancialSettings.objects.filter(projectid=project).count() == 1

    def test_get_or_create_idempotent(self):
        project = EstimationProjectFactory()
        s1 = EstimationFinancialSettingsService.get_or_create(project.estimationprojectid)
        s2 = EstimationFinancialSettingsService.get_or_create(project.estimationprojectid)
        assert s1.settingsid == s2.settingsid
        assert EstimationFinancialSettings.objects.filter(projectid=project).count() == 1

    def test_update_applies_whitelisted_fields(self):
        project = EstimationProjectFactory()
        EstimationFinancialSettingsService.get_or_create(project.estimationprojectid)
        updated = EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {
                'imssretentionrate': Decimal('0.10'),
                'advanceamountnotax': Decimal('150000'),
                'directpaymentlag': 2,
            },
            user=None,
        )
        assert updated.imssretentionrate == Decimal('0.10')
        assert updated.advanceamountnotax == Decimal('150000')
        assert updated.directpaymentlag == 2

    def test_update_ignores_non_whitelisted_keys(self):
        project = EstimationProjectFactory()
        EstimationFinancialSettingsService.get_or_create(project.estimationprojectid)
        updated = EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {
                'imssretentionrate': Decimal('0.07'),
                'settingsid': 'malicious-uuid',
                'projectid': 'other-project',
                'unknown_field': 'whatever',
            },
            user=None,
        )
        assert updated.imssretentionrate == Decimal('0.07')
        assert str(updated.settingsid) != 'malicious-uuid'
        assert updated.projectid_id == project.estimationprojectid

    def test_update_creates_settings_lazily_if_absent(self):
        project = EstimationProjectFactory()
        # No prior get_or_create — update must materialize defaults first
        updated = EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'financecostrate': Decimal('0.002000')},
            user=None,
        )
        assert updated.financecostrate == Decimal('0.002000')
        assert updated.imssretentionrate == Decimal('0.0500')  # default


@pytest.mark.unit
@pytest.mark.django_db
def test_update_ignores_removed_category_lags():
    """category_lags was removed; updates referencing it are silently ignored."""
    from apps.proyeccion.services import EstimationFinancialSettingsService
    from apps.proyeccion.tests.factories import EstimationProjectFactory, SystemUserFactory
    project = EstimationProjectFactory()
    user = SystemUserFactory()
    settings = EstimationFinancialSettingsService.get_or_create(project.estimationprojectid)
    EstimationFinancialSettingsService.update(
        project.estimationprojectid,
        {'category_lags': {'direct': {'P1': 5}}, 'directpaymentlag': 2},
        user=user,
    )
    settings.refresh_from_db()
    assert settings.directpaymentlag == 2
    assert not hasattr(settings, 'category_lags')
