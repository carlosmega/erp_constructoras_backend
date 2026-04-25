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
