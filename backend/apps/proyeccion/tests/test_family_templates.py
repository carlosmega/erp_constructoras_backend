"""Tests for FamilyTemplateService."""

import pytest

from apps.proyeccion.models import (
    FamilyTemplateSet,
    FamilyTemplateItem,
    ConceptFamily,
    ConceptSubfamily,
)
from apps.proyeccion.services import FamilyTemplateService
from apps.proyeccion.schemas import (
    CreateFamilyTemplateSetDto,
    SaveProjectAsTemplateDto,
    ApplyFamilyTemplateDto,
)
from apps.users.tests.factories import SystemUserFactory
from core.exceptions import ValidationError
from .factories import (
    EstimationProjectFactory,
    ConceptFamilyFactory,
    ConceptSubfamilyFactory,
    FamilyTemplateSetFactory,
    FamilyTemplateItemFactory,
)


@pytest.mark.unit
@pytest.mark.django_db
class TestFamilyTemplateServiceList:
    """Tests for FamilyTemplateService.list_template_sets."""

    def test_list_returns_all_active(self):
        user = SystemUserFactory()
        FamilyTemplateSetFactory()
        FamilyTemplateSetFactory()
        FamilyTemplateSetFactory(statecode=1)  # inactive

        result = FamilyTemplateService.list_template_sets(user)
        assert result.count() == 2

    def test_list_filter_by_category(self):
        user = SystemUserFactory()
        FamilyTemplateSetFactory(category='custom')
        FamilyTemplateSetFactory(category='custom')
        FamilyTemplateSetFactory(category='construccion')

        result = FamilyTemplateService.list_template_sets(user, category='custom')
        assert result.count() == 2

    def test_list_filter_by_search_name(self):
        user = SystemUserFactory()
        FamilyTemplateSetFactory(name='Plantilla Edificacion')
        FamilyTemplateSetFactory(name='Plantilla Carreteras')
        FamilyTemplateSetFactory(name='Otra cosa')

        result = FamilyTemplateService.list_template_sets(user, search='plantilla')
        assert result.count() == 2

    def test_list_filter_by_search_description(self):
        user = SystemUserFactory()
        FamilyTemplateSetFactory(description='Familias para obra civil')
        FamilyTemplateSetFactory(description='Familias para mineria')
        FamilyTemplateSetFactory(description='Sin relacion')

        result = FamilyTemplateService.list_template_sets(user, search='familias')
        assert result.count() == 2

    def test_list_excludes_inactive(self):
        user = SystemUserFactory()
        FamilyTemplateSetFactory(statecode=0)
        FamilyTemplateSetFactory(statecode=1)
        FamilyTemplateSetFactory(statecode=1)

        result = FamilyTemplateService.list_template_sets(user)
        assert result.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
class TestFamilyTemplateServiceCreate:
    """Tests for FamilyTemplateService.create_template_set."""

    def test_create_empty_set(self):
        user = SystemUserFactory()
        dto = CreateFamilyTemplateSetDto(
            name='Nueva Plantilla',
            description='Descripcion de prueba',
            category='custom',
        )

        ts = FamilyTemplateService.create_template_set(dto, user)

        assert ts.templatesetid is not None
        assert ts.name == 'Nueva Plantilla'
        assert ts.description == 'Descripcion de prueba'
        assert ts.category == 'custom'
        assert ts.issystem is False
        assert ts.statecode == 0
        assert ts.createdby == user
        assert ts.modifiedby == user
        assert ts.items.count() == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestFamilyTemplateServiceSaveFromProject:
    """Tests for FamilyTemplateService.save_project_as_template."""

    def test_save_project_with_families_and_subfamilies(self):
        user = SystemUserFactory()
        project = EstimationProjectFactory(ownerid=user)

        # Create families with subfamilies
        fam1 = ConceptFamilyFactory(
            projectid=project, code='F01', name='Preliminares', sortorder=1,
        )
        ConceptSubfamilyFactory(
            familyid=fam1, projectid=project,
            code='SF01', name='Limpieza', sortorder=1,
        )
        ConceptSubfamilyFactory(
            familyid=fam1, projectid=project,
            code='SF02', name='Trazo', sortorder=2,
        )

        fam2 = ConceptFamilyFactory(
            projectid=project, code='F02', name='Cimentacion', sortorder=2,
        )
        ConceptSubfamilyFactory(
            familyid=fam2, projectid=project,
            code='SF03', name='Excavacion', sortorder=1,
        )

        dto = SaveProjectAsTemplateDto(
            projectid=project.estimationprojectid,
            name='Plantilla desde proyecto',
            description='Generada automaticamente',
            category='custom',
        )

        ts = FamilyTemplateService.save_project_as_template(dto, user)

        assert ts.templatesetid is not None
        assert ts.name == 'Plantilla desde proyecto'
        items = ts.items.filter(statecode=0).order_by('familysortorder', 'subfamilysortorder')
        assert items.count() == 3

        # Verify first family's subfamilies
        f01_items = items.filter(familycode='F01')
        assert f01_items.count() == 2
        assert list(f01_items.values_list('subfamilycode', flat=True)) == ['SF01', 'SF02']

        # Verify second family's subfamilies
        f02_items = items.filter(familycode='F02')
        assert f02_items.count() == 1
        assert f02_items.first().subfamilyname == 'Excavacion'

    def test_save_project_family_without_subfamilies(self):
        user = SystemUserFactory()
        project = EstimationProjectFactory(ownerid=user)

        ConceptFamilyFactory(
            projectid=project, code='F01', name='Solo Familia', sortorder=1,
        )

        dto = SaveProjectAsTemplateDto(
            projectid=project.estimationprojectid,
            name='Sin subfamilias',
        )

        ts = FamilyTemplateService.save_project_as_template(dto, user)
        items = ts.items.filter(statecode=0)
        assert items.count() == 1
        item = items.first()
        assert item.familycode == 'F01'
        assert item.subfamilycode == ''
        assert item.subfamilyname == ''

    def test_save_project_no_families_raises_error(self):
        user = SystemUserFactory()
        project = EstimationProjectFactory(ownerid=user)

        dto = SaveProjectAsTemplateDto(
            projectid=project.estimationprojectid,
            name='Vacia',
        )

        with pytest.raises(ValidationError):
            FamilyTemplateService.save_project_as_template(dto, user)


@pytest.mark.unit
@pytest.mark.django_db
class TestFamilyTemplateServiceApplyToProject:
    """Tests for FamilyTemplateService.apply_template_to_project."""

    def _create_template_with_items(self, user):
        """Helper: create a template set with 2 families (3 items total)."""
        ts = FamilyTemplateSetFactory(createdby=user, modifiedby=user)
        FamilyTemplateItemFactory(
            templatesetid=ts,
            familycode='F01', familyname='Preliminares',
            subfamilycode='SF01', subfamilyname='Limpieza',
            familysortorder=1, subfamilysortorder=1,
        )
        FamilyTemplateItemFactory(
            templatesetid=ts,
            familycode='F01', familyname='Preliminares',
            subfamilycode='SF02', subfamilyname='Trazo',
            familysortorder=1, subfamilysortorder=2,
        )
        FamilyTemplateItemFactory(
            templatesetid=ts,
            familycode='F02', familyname='Cimentacion',
            subfamilycode='SF03', subfamilyname='Excavacion',
            familysortorder=2, subfamilysortorder=1,
        )
        return ts

    def test_apply_template_to_empty_project(self):
        user = SystemUserFactory()
        project = EstimationProjectFactory(ownerid=user)
        ts = self._create_template_with_items(user)

        dto = ApplyFamilyTemplateDto(
            templatesetid=ts.templatesetid,
            projectid=project.estimationprojectid,
        )

        created = FamilyTemplateService.apply_template_to_project(dto, user)

        assert len(created) == 2  # 2 families
        families = ConceptFamily.objects.filter(
            projectid=project, statecode=0,
        ).order_by('sortorder')
        assert families.count() == 2
        assert families[0].code == 'F01'
        assert families[0].name == 'Preliminares'
        assert families[1].code == 'F02'
        assert families[1].name == 'Cimentacion'

        # Check subfamilies
        sf_f01 = ConceptSubfamily.objects.filter(
            familyid=families[0], statecode=0,
        ).order_by('sortorder')
        assert sf_f01.count() == 2
        assert sf_f01[0].code == 'SF01'
        assert sf_f01[1].code == 'SF02'

        sf_f02 = ConceptSubfamily.objects.filter(
            familyid=families[1], statecode=0,
        ).order_by('sortorder')
        assert sf_f02.count() == 1
        assert sf_f02[0].code == 'SF03'

    def test_apply_template_skips_existing_family_codes(self):
        user = SystemUserFactory()
        project = EstimationProjectFactory(ownerid=user)
        ts = self._create_template_with_items(user)

        # Pre-create F01 in the project
        ConceptFamilyFactory(
            projectid=project, code='F01', name='Ya Existente', sortorder=0,
        )

        dto = ApplyFamilyTemplateDto(
            templatesetid=ts.templatesetid,
            projectid=project.estimationprojectid,
        )

        created = FamilyTemplateService.apply_template_to_project(dto, user)

        # Only F02 should be created
        assert len(created) == 1
        assert created[0].code == 'F02'

        # F01 should remain untouched
        existing_f01 = ConceptFamily.objects.get(
            projectid=project, code='F01',
        )
        assert existing_f01.name == 'Ya Existente'

    def test_apply_template_with_specific_familycodes(self):
        user = SystemUserFactory()
        project = EstimationProjectFactory(ownerid=user)
        ts = self._create_template_with_items(user)

        dto = ApplyFamilyTemplateDto(
            templatesetid=ts.templatesetid,
            projectid=project.estimationprojectid,
            familycodes=['F02'],
        )

        created = FamilyTemplateService.apply_template_to_project(dto, user)

        assert len(created) == 1
        assert created[0].code == 'F02'

        # F01 should NOT be created
        assert not ConceptFamily.objects.filter(
            projectid=project, code='F01',
        ).exists()

    def test_apply_same_template_twice_no_duplicates(self):
        user = SystemUserFactory()
        project = EstimationProjectFactory(ownerid=user)
        ts = self._create_template_with_items(user)

        dto = ApplyFamilyTemplateDto(
            templatesetid=ts.templatesetid,
            projectid=project.estimationprojectid,
        )

        # First application
        created1 = FamilyTemplateService.apply_template_to_project(dto, user)
        assert len(created1) == 2

        # Second application - all codes already exist
        created2 = FamilyTemplateService.apply_template_to_project(dto, user)
        assert len(created2) == 0

        # Still only 2 families
        assert ConceptFamily.objects.filter(
            projectid=project, statecode=0,
        ).count() == 2


@pytest.mark.unit
@pytest.mark.django_db
class TestFamilyTemplateServiceDelete:
    """Tests for FamilyTemplateService.delete_template_set."""

    def test_soft_delete_custom_template(self):
        user = SystemUserFactory()
        ts = FamilyTemplateSetFactory(issystem=False, createdby=user, modifiedby=user)

        result = FamilyTemplateService.delete_template_set(ts.templatesetid, user)

        assert result.statecode == 1
        ts.refresh_from_db()
        assert ts.statecode == 1
        assert ts.modifiedby == user

    def test_delete_system_template_raises_error(self):
        user = SystemUserFactory()
        ts = FamilyTemplateSetFactory(issystem=True, createdby=user, modifiedby=user)

        with pytest.raises(ValidationError, match="sistema"):
            FamilyTemplateService.delete_template_set(ts.templatesetid, user)

        # Verify it's still active
        ts.refresh_from_db()
        assert ts.statecode == 0
