"""
TDD tests for PR #2 (Capa B): insurance fields, ProjectRisk, ProjectAssetUsage.

RED phase — these tests MUST fail before any implementation.
"""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from apps.projects.tests.factories import ActiveProjectFactory
from apps.users.tests.factories import SalespersonFactory


# ============================================================================
# Helpers
# ============================================================================

def _project(user=None):
    user = user or SalespersonFactory()
    return ActiveProjectFactory(ownerid=user, createdby=user, modifiedby=user)


# ============================================================================
# Insurance fields on ConstructionProject
# ============================================================================

@pytest.mark.unit
class TestInsuranceFields:
    """ConstructionProject stores carinsurance and liabilityinsurance flat fields."""

    def test_carinsurance_fields_exist(self, db):
        from apps.projects.models import ConstructionProject
        p = _project()
        p.carinsurance_amount = Decimal('50000.00')
        p.carinsurance_policycost = Decimal('1200.00')
        p.carinsurance_validitystartdate = date(2026, 1, 1)
        p.carinsurance_validityenddate = date(2027, 1, 1)
        p.save()

        refreshed = ConstructionProject.objects.get(pk=p.pk)
        assert refreshed.carinsurance_amount == Decimal('50000.00')
        assert refreshed.carinsurance_policycost == Decimal('1200.00')
        assert refreshed.carinsurance_validitystartdate == date(2026, 1, 1)
        assert refreshed.carinsurance_validityenddate == date(2027, 1, 1)

    def test_liabilityinsurance_fields_exist(self, db):
        from apps.projects.models import ConstructionProject
        p = _project()
        p.liabilityinsurance_amount = Decimal('80000.00')
        p.liabilityinsurance_policycost = Decimal('2000.00')
        p.liabilityinsurance_validitystartdate = date(2026, 3, 1)
        p.liabilityinsurance_validityenddate = date(2027, 3, 1)
        p.save()

        refreshed = ConstructionProject.objects.get(pk=p.pk)
        assert refreshed.liabilityinsurance_amount == Decimal('80000.00')
        assert refreshed.liabilityinsurance_validitystartdate == date(2026, 3, 1)

    def test_insurance_fields_nullable(self, db):
        """Insurance fields are optional — project saves fine without them."""
        from apps.projects.models import ConstructionProject
        p = _project()
        refreshed = ConstructionProject.objects.get(pk=p.pk)
        assert refreshed.carinsurance_amount is None
        assert refreshed.liabilityinsurance_amount is None


# ============================================================================
# ProjectRisk model
# ============================================================================

@pytest.mark.unit
class TestProjectRiskModel:
    """ProjectRisk stores risk records linked to a project."""

    def test_create_risk(self, db):
        from apps.projects.models import ProjectRisk, RiskStatusCode
        p = _project()
        risk = ProjectRisk.objects.create(
            projectid=p,
            description='Retraso por lluvias en temporada',
            production_variance=Decimal('-150000.00'),
            cost_variance=Decimal('50000.00'),
            result_variance=Decimal('-200000.00'),
            statuscode=RiskStatusCode.OPEN,
            createdby=p.ownerid,
            modifiedby=p.ownerid,
        )
        assert risk.riskid is not None
        assert str(risk.riskid)  # valid UUID
        assert risk.projectid_id == p.pk

    def test_risk_defaults_open(self, db):
        from apps.projects.models import ProjectRisk, RiskStatusCode
        p = _project()
        risk = ProjectRisk.objects.create(
            projectid=p,
            description='Riesgo de alza de precios',
            createdby=p.ownerid,
            modifiedby=p.ownerid,
        )
        assert risk.statuscode == RiskStatusCode.OPEN

    def test_risk_variances_default_zero(self, db):
        from apps.projects.models import ProjectRisk
        p = _project()
        risk = ProjectRisk.objects.create(
            projectid=p,
            description='Sin cuantificar aún',
            createdby=p.ownerid,
            modifiedby=p.ownerid,
        )
        assert risk.production_variance == Decimal('0')
        assert risk.cost_variance == Decimal('0')
        assert risk.result_variance == Decimal('0')

    def test_risk_status_transitions(self, db):
        from apps.projects.models import ProjectRisk, RiskStatusCode
        p = _project()
        risk = ProjectRisk.objects.create(
            projectid=p,
            description='Riesgo de accidente',
            createdby=p.ownerid,
            modifiedby=p.ownerid,
        )
        for code in (
            RiskStatusCode.MITIGATED,
            RiskStatusCode.MATERIALIZED,
            RiskStatusCode.CLOSED,
        ):
            risk.statuscode = code
            risk.save()
            risk.refresh_from_db()
            assert risk.statuscode == code

    def test_risks_cascade_delete_with_project(self, db):
        from apps.projects.models import ProjectRisk
        p = _project()
        ProjectRisk.objects.create(
            projectid=p,
            description='Riesgo temporal',
            createdby=p.ownerid,
            modifiedby=p.ownerid,
        )
        pk = p.pk
        p.delete()
        assert ProjectRisk.objects.filter(projectid_id=pk).count() == 0

    def test_risks_ordered_by_createdon_desc(self, db):
        from apps.projects.models import ProjectRisk
        assert ProjectRisk._meta.ordering == ['-createdon']


# ============================================================================
# ProjectAssetUsage model
# ============================================================================

@pytest.mark.unit
class TestProjectAssetUsageModel:
    """ProjectAssetUsage stores asset category entries per project."""

    def test_create_asset_usage(self, db):
        from apps.projects.models import ProjectAssetUsage, AssetCategoryCode
        p = _project()
        usage = ProjectAssetUsage.objects.create(
            projectid=p,
            category=AssetCategoryCode.AC1_COMPUTING,
            description='2 laptops y 1 impresora',
            plannedamount=Decimal('45000.00'),
            createdby=p.ownerid,
            modifiedby=p.ownerid,
        )
        assert usage.assetusageid is not None
        assert usage.projectid_id == p.pk
        assert usage.category == AssetCategoryCode.AC1_COMPUTING

    def test_all_six_categories_valid(self, db):
        from apps.projects.models import ProjectAssetUsage, AssetCategoryCode
        p = _project()
        categories = [
            AssetCategoryCode.AC1_COMPUTING,
            AssetCategoryCode.AC2_MACHINERY_MINOR,
            AssetCategoryCode.AC3_MACHINERY_MAJOR,
            AssetCategoryCode.AC4_CAMP_FURNITURE,
            AssetCategoryCode.AC5_SITE_EQUIPMENT,
            AssetCategoryCode.AC6_VEHICLES,
        ]
        for cat in categories:
            ProjectAssetUsage.objects.create(
                projectid=p, category=cat, description=f'Uso {cat}',
                createdby=p.ownerid, modifiedby=p.ownerid,
            )
        assert ProjectAssetUsage.objects.filter(projectid=p).count() == 6

    def test_planned_amount_defaults_zero(self, db):
        from apps.projects.models import ProjectAssetUsage, AssetCategoryCode
        p = _project()
        usage = ProjectAssetUsage.objects.create(
            projectid=p,
            category=AssetCategoryCode.AC6_VEHICLES,
            description='Pickup 4x4',
            createdby=p.ownerid,
            modifiedby=p.ownerid,
        )
        assert usage.plannedamount == Decimal('0')

    def test_asset_usages_ordered_by_category(self, db):
        from apps.projects.models import ProjectAssetUsage, AssetCategoryCode
        p = _project()
        for cat in (
            AssetCategoryCode.AC6_VEHICLES,
            AssetCategoryCode.AC1_COMPUTING,
            AssetCategoryCode.AC3_MACHINERY_MAJOR,
        ):
            ProjectAssetUsage.objects.create(
                projectid=p, category=cat, description=f'Item {cat}',
                createdby=p.ownerid, modifiedby=p.ownerid,
            )
        usages = list(ProjectAssetUsage.objects.filter(projectid=p))
        cats = [u.category for u in usages]
        assert cats == sorted(cats)

    def test_asset_usages_cascade_delete_with_project(self, db):
        from apps.projects.models import ProjectAssetUsage, AssetCategoryCode
        p = _project()
        ProjectAssetUsage.objects.create(
            projectid=p, category=AssetCategoryCode.AC2_MACHINERY_MINOR,
            description='Compresor', createdby=p.ownerid, modifiedby=p.ownerid,
        )
        pk = p.pk
        p.delete()
        assert ProjectAssetUsage.objects.filter(projectid_id=pk).count() == 0


# ============================================================================
# RiskService
# ============================================================================

@pytest.mark.unit
class TestRiskService:
    """RiskService CRUD over ProjectRisk."""

    def test_create_risk(self, db):
        from apps.projects.services import RiskService
        from apps.projects.schemas import CreateRiskDto
        from apps.projects.models import RiskStatusCode
        p = _project()
        dto = CreateRiskDto(
            projectid=p.projectid,
            description='Riesgo de huelga',
            production_variance=Decimal('-100000'),
            cost_variance=Decimal('0'),
            result_variance=Decimal('-100000'),
        )
        risk = RiskService.create_risk(dto, p.ownerid)
        assert risk.riskid is not None
        assert risk.statuscode == RiskStatusCode.OPEN

    def test_list_risks_for_project(self, db):
        from apps.projects.services import RiskService
        from apps.projects.schemas import CreateRiskDto
        p = _project()
        for i in range(3):
            RiskService.create_risk(
                CreateRiskDto(projectid=p.projectid, description=f'R{i}'),
                p.ownerid,
            )
        risks = RiskService.list_risks(p.projectid)
        assert len(risks) == 3

    def test_update_risk(self, db):
        from apps.projects.services import RiskService
        from apps.projects.schemas import CreateRiskDto, UpdateRiskDto
        from apps.projects.models import RiskStatusCode
        p = _project()
        risk = RiskService.create_risk(
            CreateRiskDto(projectid=p.projectid, description='Inicial'),
            p.ownerid,
        )
        updated = RiskService.update_risk(
            risk.riskid,
            UpdateRiskDto(statuscode=RiskStatusCode.MITIGATED, description='Mitigado'),
            p.ownerid,
        )
        assert updated.statuscode == RiskStatusCode.MITIGATED
        assert updated.description == 'Mitigado'

    def test_delete_risk(self, db):
        from apps.projects.services import RiskService
        from apps.projects.schemas import CreateRiskDto
        from apps.projects.models import ProjectRisk
        p = _project()
        risk = RiskService.create_risk(
            CreateRiskDto(projectid=p.projectid, description='A borrar'),
            p.ownerid,
        )
        RiskService.delete_risk(risk.riskid)
        assert not ProjectRisk.objects.filter(pk=risk.riskid).exists()

    def test_delete_risk_not_found(self, db):
        from apps.projects.services import RiskService
        from core.exceptions import NotFound
        with pytest.raises(NotFound):
            RiskService.delete_risk(uuid4())


# ============================================================================
# AssetUsageService
# ============================================================================

@pytest.mark.unit
class TestAssetUsageService:
    """AssetUsageService CRUD over ProjectAssetUsage."""

    def test_create_asset_usage(self, db):
        from apps.projects.services import AssetUsageService
        from apps.projects.schemas import CreateAssetUsageDto
        from apps.projects.models import AssetCategoryCode
        p = _project()
        dto = CreateAssetUsageDto(
            projectid=p.projectid,
            category=AssetCategoryCode.AC3_MACHINERY_MAJOR,
            description='Excavadora Cat 320',
            plannedamount=Decimal('600000'),
        )
        usage = AssetUsageService.create_asset_usage(dto, p.ownerid)
        assert usage.assetusageid is not None
        assert usage.category == AssetCategoryCode.AC3_MACHINERY_MAJOR

    def test_list_asset_usages(self, db):
        from apps.projects.services import AssetUsageService
        from apps.projects.schemas import CreateAssetUsageDto
        from apps.projects.models import AssetCategoryCode
        p = _project()
        for cat in (AssetCategoryCode.AC1_COMPUTING, AssetCategoryCode.AC4_CAMP_FURNITURE):
            AssetUsageService.create_asset_usage(
                CreateAssetUsageDto(
                    projectid=p.projectid, category=cat, description=f'Item {cat}'
                ),
                p.ownerid,
            )
        usages = AssetUsageService.list_asset_usages(p.projectid)
        assert len(usages) == 2

    def test_update_asset_usage(self, db):
        from apps.projects.services import AssetUsageService
        from apps.projects.schemas import CreateAssetUsageDto, UpdateAssetUsageDto
        from apps.projects.models import AssetCategoryCode
        p = _project()
        usage = AssetUsageService.create_asset_usage(
            CreateAssetUsageDto(
                projectid=p.projectid,
                category=AssetCategoryCode.AC5_SITE_EQUIPMENT,
                description='Andamios',
            ),
            p.ownerid,
        )
        updated = AssetUsageService.update_asset_usage(
            usage.assetusageid,
            UpdateAssetUsageDto(plannedamount=Decimal('30000'), description='Andamios tubulares'),
            p.ownerid,
        )
        assert updated.plannedamount == Decimal('30000')
        assert updated.description == 'Andamios tubulares'

    def test_delete_asset_usage(self, db):
        from apps.projects.services import AssetUsageService
        from apps.projects.schemas import CreateAssetUsageDto
        from apps.projects.models import AssetCategoryCode, ProjectAssetUsage
        p = _project()
        usage = AssetUsageService.create_asset_usage(
            CreateAssetUsageDto(
                projectid=p.projectid,
                category=AssetCategoryCode.AC6_VEHICLES,
                description='Camioneta',
            ),
            p.ownerid,
        )
        AssetUsageService.delete_asset_usage(usage.assetusageid)
        assert not ProjectAssetUsage.objects.filter(pk=usage.assetusageid).exists()

    def test_delete_asset_usage_not_found(self, db):
        from apps.projects.services import AssetUsageService
        from core.exceptions import NotFound
        with pytest.raises(NotFound):
            AssetUsageService.delete_asset_usage(uuid4())
