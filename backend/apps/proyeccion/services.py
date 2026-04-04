"""Budget estimation (proyeccion) business logic service layer."""

from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from collections import defaultdict
from django.db import models, transaction
from django.db.models import QuerySet, Max, Sum, Q, F

from apps.proyeccion.models import (
    EstimationProject,
    EstimationStateCode,
    ConceptFamily,
    ConceptSubfamily,
    BudgetConcept,
    UnitCostBreakdown,
    IndirectCostDetail,
    IndirectCostTemplate,
    OfferAlternative,
    ExternalCostItem,
    SupplyCatalogItem,
    EquipmentYield,
    WorkPlanEntry,
    BreakdownCategoryCode,
    ProjectSizeCode,
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
    FamilyTemplateSet,
    FamilyTemplateItem,
)
from apps.proyeccion.schemas import (
    CreateConceptFamilyDto,
    UpdateConceptFamilyDto,
    CreateConceptSubfamilyDto,
    UpdateConceptSubfamilyDto,
    CreateBudgetConceptDto,
    UpdateBudgetConceptDto,
    CreateUnitCostBreakdownDto,
    UpdateUnitCostBreakdownDto,
    CreateIndirectCostDetailDto,
    UpdateIndirectCostDetailDto,
    CreateOfferAlternativeDto,
    UpdateOfferAlternativeDto,
    UpdateExternalCostItemDto,
    CreateSupplyCatalogItemDto,
    UpdateSupplyCatalogItemDto,
    CreateEquipmentYieldDto,
    UpdateEquipmentYieldDto,
    CreateWorkPlanEntryDto,
    UpdateWorkPlanEntryDto,
    SaveProjectAsTemplateDto,
    ApplyFamilyTemplateDto,
)
from core.exceptions import ValidationError, NotFound


class EstimationProjectService:
    """Service for EstimationProject CRUD and conversion to ConstructionProject."""

    @staticmethod
    def list_projects(user, statecode=None, search=None):
        """List estimation projects with optional filters."""
        qs = EstimationProject.objects.select_related('accountid', 'ownerid', 'createdby', 'modifiedby')
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        if search:
            qs = qs.filter(models.Q(name__icontains=search) | models.Q(estimationnumber__icontains=search))
        return qs

    @staticmethod
    def get_project(project_id, user):
        """Get a single estimation project by ID."""
        try:
            return EstimationProject.objects.select_related(
                'accountid', 'ownerid', 'generatedprojectid', 'createdby', 'modifiedby'
            ).get(estimationprojectid=project_id)
        except EstimationProject.DoesNotExist:
            raise NotFound(f"Estimation project with ID {project_id} not found")

    @staticmethod
    def create_project(dto, user):
        """Create a new estimation project with auto-generated number (EST-YYYY-NNN)."""
        year = datetime.now().year
        max_num = EstimationProject.objects.filter(
            estimationnumber__startswith=f'EST-{year}-'
        ).count()
        next_num = max_num + 1
        estimation_number = f'EST-{year}-{next_num:03d}'

        project = EstimationProject(
            estimationnumber=estimation_number,
            name=dto.name,
            description=dto.description,
            accountid_id=dto.accountid,
            opportunityid_id=dto.opportunityid,
            presentationdate=dto.presentationdate,
            estimatedstartdate=dto.estimatedstartdate,
            estimatedenddate=dto.estimatedenddate,
            durationmonths=dto.durationmonths or 0,
            projecttype=dto.projecttype or 0,
            biddingtype=dto.biddingtype or 0,
            periodtype=dto.periodtype or 0,
            estimatedcontractamount=dto.estimatedcontractamount or 0,
            exchangerate_mxn_usd=dto.exchangerate_mxn_usd,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        project.save()
        return project

    @staticmethod
    def update_project(project_id, dto, user):
        """Update an estimation project. Cannot update if already converted."""
        project = EstimationProjectService.get_project(project_id, user)

        if project.statecode == EstimationStateCode.CONVERTED:
            raise ValidationError("Cannot update a converted estimation project")

        update_fields = [
            'name', 'description', 'presentationdate', 'estimatedstartdate',
            'estimatedenddate', 'durationmonths', 'projecttype', 'biddingtype',
            'periodtype', 'estimatedcontractamount', 'exchangerate_mxn_usd', 'statecode',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(project, field, value)

        # Handle FK fields separately
        if dto.accountid is not None:
            project.accountid_id = dto.accountid
        if dto.opportunityid is not None:
            project.opportunityid_id = dto.opportunityid

        project.modifiedby = user
        project.save()
        return project

    @staticmethod
    def delete_project(project_id, user):
        """Soft-delete an estimation project (set to Canceled). Cannot delete if converted."""
        project = EstimationProjectService.get_project(project_id, user)
        if project.statecode == EstimationStateCode.CONVERTED:
            raise ValidationError("Cannot delete a converted estimation project")
        project.statecode = EstimationStateCode.CANCELED
        project.modifiedby = user
        project.save()
        return project

    @staticmethod
    @transaction.atomic
    def convert_to_project(project_id, dto, user):
        """Convert an accepted estimation into a ConstructionProject with budgets."""
        from apps.projects.models import ConstructionProject
        from apps.budgets.models import CostCategory, ImputationCode, CostTypeCode
        from apps.budgets.services import CostCategoryService

        estimation = EstimationProjectService.get_project(project_id, user)

        if estimation.statecode == EstimationStateCode.CONVERTED:
            raise ValidationError("Estimation already converted")
        if estimation.statecode == EstimationStateCode.CANCELED:
            raise ValidationError("Cannot convert a canceled estimation")

        # 1. Generate project number
        year = datetime.now().year
        max_num = ConstructionProject.objects.filter(
            projectnumber__startswith=f'PRY-{year}-'
        ).count()
        next_num = max_num + 1
        project_number = f'PRY-{year}-{next_num:03d}'

        # 2. Create ConstructionProject
        project = ConstructionProject(
            projectnumber=project_number,
            name=estimation.name,
            description=estimation.description,
            accountid=estimation.accountid,
            opportunityid=estimation.opportunityid,
            presentationdate=estimation.presentationdate,
            startdate=dto.startdate,
            contractenddate=dto.contractenddate,
            expectedenddate=dto.expectedenddate,
            durationmonths=estimation.durationmonths,
            projecttype=estimation.projecttype,
            biddingtype=estimation.biddingtype,
            periodtype=estimation.periodtype,
            contractamount_notax=dto.contractamount_notax,
            contractamount_withtax=dto.contractamount_withtax,
            advancepayment_notax=dto.advancepayment_notax,
            advancepayment_withtax=dto.advancepayment_withtax,
            exchangerate_mxn_usd=estimation.exchangerate_mxn_usd,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        project.save()

        # 3. Seed cost categories (P1-P10, C1-C8)
        categories = CostCategoryService.seed_default_categories(project.projectid, user)

        # Build category lookup by code
        cat_map = {cat.code: cat for cat in categories}

        # 4. Convert BudgetConcepts -> ImputationCodes (direct costs)
        concepts = BudgetConcept.objects.filter(
            projectid=estimation.estimationprojectid,
            statecode=0,
        ).select_related(
            'subfamilyid', 'subfamilyid__familyid'
        ).order_by('subfamilyid__familyid__sortorder', 'subfamilyid__sortorder', 'sequencenumber')

        seq_counters = {}  # Track sequence per category
        direct_codes = []
        for concept in concepts:
            # Map concept to P4 (Materiales) as default direct category
            cat_code = 'P4'
            category = cat_map.get(cat_code)
            if not category:
                continue

            key = (str(project.projectid), str(category.categoryid))
            seq_counters[key] = seq_counters.get(key, 0) + 1
            seq = seq_counters[key]

            code_str = f"{cat_code}-{seq}"

            direct_codes.append(ImputationCode(
                projectid=project,
                categoryid=category,
                costtype=CostTypeCode.DIRECT,
                code=code_str,
                sequencenumber=seq,
                name=concept.description,
                unit=concept.unit,
                contractcode=concept.code,
                contractunitprice=concept.clientunitprice or concept.unitprice,
                quantity=concept.quantity,
                unitcost=concept.clientunitprice or concept.unitprice,
                sourceconceptid=concept,
                totalbudget=concept.totalamount,
                createdby=user,
                modifiedby=user,
            ))
        if direct_codes:
            ImputationCode.objects.bulk_create(direct_codes)

        # 5. Convert IndirectCostDetails -> ImputationCodes (indirect costs)
        indirect_details = IndirectCostDetail.objects.filter(
            projectid=estimation.estimationprojectid,
            statecode=0,
        ).order_by('categorycode', 'linenumber')

        seq_counters_indirect = {}
        indirect_codes = []
        for detail in indirect_details:
            category = cat_map.get(detail.categorycode)
            if not category:
                continue

            key = str(category.categoryid)
            seq_counters_indirect[key] = seq_counters_indirect.get(key, 0) + 1
            seq = seq_counters_indirect[key]

            code_str = f"{detail.categorycode}-{seq}"

            indirect_codes.append(ImputationCode(
                projectid=project,
                categoryid=category,
                costtype=CostTypeCode.INDIRECT,
                code=code_str,
                sequencenumber=seq,
                name=detail.description,
                description=detail.area,
                monthlycost=detail.monthlycost,
                units=detail.units,
                executionmonths=int(detail.months) if detail.months else None,
                totalbudget=detail.amount,
                createdby=user,
                modifiedby=user,
            ))
        if indirect_codes:
            ImputationCode.objects.bulk_create(indirect_codes)

        # 6. Update estimation state
        estimation.statecode = EstimationStateCode.CONVERTED
        estimation.generatedprojectid = project
        estimation.modifiedby = user
        estimation.save()

        return estimation


# Default external cost checklist items
DEFAULT_EXTERNAL_COSTS = [
    'Fianza de sostenimiento de oferta',
    'Fianza de anticipo',
    'Fianza de cumplimiento',
    'Fianza de vicios ocultos',
    'Seguro de responsabilidad civil',
    'Seguro de obra',
    'Seguro de equipo',
    'Gastos notariales',
    'Permisos de construccion',
    'Licencias ambientales',
    'Permisos municipales',
    'Derechos de via',
    'Estudios topograficos',
    'Estudios de mecanica de suelos',
    'Estudios de impacto ambiental',
    'Dictamen estructural',
    'Gastos de licitacion',
    'Supervision externa',
    'Laboratorio de control de calidad',
    'Gastos financieros',
]


class ConceptCatalogService:
    """Service class for ConceptFamily, ConceptSubfamily, and BudgetConcept."""

    # -------------------------------------------------------------------------
    # Families
    # -------------------------------------------------------------------------

    @staticmethod
    def list_families(project_id: UUID, user) -> QuerySet[ConceptFamily]:
        """List all concept families for a project."""
        return ConceptFamily.objects.filter(
            projectid=project_id
        ).select_related('createdby', 'modifiedby')

    @staticmethod
    def create_family(dto: CreateConceptFamilyDto, user) -> ConceptFamily:
        """Create a new concept family."""
        family = ConceptFamily(
            projectid_id=dto.projectid,
            name=dto.name,
            code=dto.code,
            sortorder=dto.sortorder or 0,
            createdby=user,
            modifiedby=user,
        )
        family.save()
        return family

    @staticmethod
    def update_family(family_id: UUID, dto: UpdateConceptFamilyDto, user) -> ConceptFamily:
        """Update an existing concept family."""
        try:
            family = ConceptFamily.objects.get(familyid=family_id)
        except ConceptFamily.DoesNotExist:
            raise NotFound(f"ConceptFamily with ID {family_id} not found")

        update_fields = ['name', 'code', 'sortorder', 'statecode']
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(family, field, value)

        family.modifiedby = user
        family.save()
        return family

    @staticmethod
    def delete_family(family_id: UUID, user) -> ConceptFamily:
        """Soft delete a concept family (statecode=1)."""
        try:
            family = ConceptFamily.objects.get(familyid=family_id)
        except ConceptFamily.DoesNotExist:
            raise NotFound(f"ConceptFamily with ID {family_id} not found")

        family.statecode = 1
        family.modifiedby = user
        family.save()
        return family

    # -------------------------------------------------------------------------
    # Subfamilies
    # -------------------------------------------------------------------------

    @staticmethod
    def list_subfamilies(family_id: UUID, user) -> QuerySet[ConceptSubfamily]:
        """List all subfamilies for a family."""
        return ConceptSubfamily.objects.filter(
            familyid=family_id
        ).select_related('familyid', 'createdby', 'modifiedby')

    @staticmethod
    def create_subfamily(dto: CreateConceptSubfamilyDto, user) -> ConceptSubfamily:
        """Create a new concept subfamily."""
        # Resolve projectid from the parent family if not provided
        if not dto.projectid:
            try:
                family = ConceptFamily.objects.get(familyid=dto.familyid)
            except ConceptFamily.DoesNotExist:
                raise NotFound(f"Concept family with ID {dto.familyid} not found")
            dto.projectid = family.projectid_id

        subfamily = ConceptSubfamily(
            familyid_id=dto.familyid,
            projectid_id=dto.projectid,
            name=dto.name,
            code=dto.code,
            sortorder=dto.sortorder or 0,
            createdby=user,
            modifiedby=user,
        )
        subfamily.save()
        return subfamily

    @staticmethod
    def update_subfamily(subfamily_id: UUID, dto: UpdateConceptSubfamilyDto, user) -> ConceptSubfamily:
        """Update an existing concept subfamily."""
        try:
            subfamily = ConceptSubfamily.objects.get(subfamilyid=subfamily_id)
        except ConceptSubfamily.DoesNotExist:
            raise NotFound(f"ConceptSubfamily with ID {subfamily_id} not found")

        update_fields = ['name', 'code', 'sortorder', 'statecode']
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(subfamily, field, value)

        subfamily.modifiedby = user
        subfamily.save()
        return subfamily

    # -------------------------------------------------------------------------
    # Concepts
    # -------------------------------------------------------------------------

    @staticmethod
    def list_concepts(
        project_id: UUID,
        user,
        subfamilyid: Optional[UUID] = None,
    ) -> QuerySet[BudgetConcept]:
        """List all budget concepts for a project, optionally filtered by subfamily."""
        queryset = BudgetConcept.objects.filter(projectid=project_id)

        if subfamilyid is not None:
            queryset = queryset.filter(subfamilyid=subfamilyid)

        return queryset.select_related(
            'subfamilyid', 'subfamilyid__familyid', 'createdby', 'modifiedby'
        )

    @staticmethod
    def get_concept(concept_id: UUID, user) -> BudgetConcept:
        """Get a single budget concept by ID."""
        try:
            return BudgetConcept.objects.select_related(
                'subfamilyid', 'subfamilyid__familyid', 'createdby', 'modifiedby'
            ).get(conceptid=concept_id)
        except BudgetConcept.DoesNotExist:
            raise NotFound(f"BudgetConcept with ID {concept_id} not found")

    @staticmethod
    def create_concept(dto: CreateBudgetConceptDto, user) -> BudgetConcept:
        """Create a new budget concept with auto-generated code and sequence number."""
        # Fetch the subfamily and family for code generation
        try:
            subfamily = ConceptSubfamily.objects.select_related('familyid').get(
                subfamilyid=dto.subfamilyid
            )
        except ConceptSubfamily.DoesNotExist:
            raise ValidationError(f"ConceptSubfamily with ID {dto.subfamilyid} not found")

        family = subfamily.familyid

        # Calculate next sequence number within this subfamily
        max_seq = BudgetConcept.objects.filter(
            subfamilyid=dto.subfamilyid,
        ).aggregate(max_seq=Max('sequencenumber'))['max_seq'] or 0
        next_seq = max_seq + 1

        # Auto-generate code: F{family_code}-S{subfamily_code}-{seq}
        code = f"F{family.code}-S{subfamily.code}-{next_seq}"

        concept = BudgetConcept(
            projectid_id=dto.projectid,
            subfamilyid_id=dto.subfamilyid,
            code=code,
            sequencenumber=next_seq,
            description=dto.description,
            unit=dto.unit,
            quantity=dto.quantity,
            directunitcost=Decimal('0'),
            indirectunitcost=Decimal('0'),
            utilityunitcost=Decimal('0'),
            unitprice=Decimal('0'),
            totalamount=Decimal('0'),
            clientunitprice=dto.clientunitprice,
            breakdownmethod=dto.breakdownmethod or 0,
            isprintable=dto.isprintable if dto.isprintable is not None else True,
            createdby=user,
            modifiedby=user,
        )
        concept.save()
        return concept

    @staticmethod
    def update_concept(concept_id: UUID, dto: UpdateBudgetConceptDto, user) -> BudgetConcept:
        """Update an existing budget concept."""
        try:
            concept = BudgetConcept.objects.get(conceptid=concept_id)
        except BudgetConcept.DoesNotExist:
            raise NotFound(f"BudgetConcept with ID {concept_id} not found")

        update_fields = [
            'description', 'unit', 'quantity', 'directunitcost', 'indirectunitcost',
            'utilityunitcost', 'unitprice', 'totalamount', 'clientunitprice',
            'breakdownmethod', 'isprintable', 'statecode',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(concept, field, value)

        concept.modifiedby = user
        concept.save()
        return concept

    @staticmethod
    def delete_concept(concept_id: UUID, user) -> BudgetConcept:
        """Soft delete a budget concept (statecode=1)."""
        try:
            concept = BudgetConcept.objects.get(conceptid=concept_id)
        except BudgetConcept.DoesNotExist:
            raise NotFound(f"BudgetConcept with ID {concept_id} not found")

        concept.statecode = 1
        concept.modifiedby = user
        concept.save()
        return concept

    @staticmethod
    def recalculate_concept(concept_id: UUID, user) -> BudgetConcept:
        """Recalculate concept costs from its unit cost breakdowns.

        Sums breakdown amounts by category to get directunitcost, then computes:
        - unitprice = directunitcost + indirectunitcost + utilityunitcost
        - totalamount = unitprice * quantity
        """
        try:
            concept = BudgetConcept.objects.get(conceptid=concept_id)
        except BudgetConcept.DoesNotExist:
            raise NotFound(f"BudgetConcept with ID {concept_id} not found")

        # Sum all active breakdown amounts grouped by category
        breakdowns = UnitCostBreakdown.objects.filter(
            conceptid=concept_id,
            statecode=0,
        )

        total_direct = breakdowns.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        concept.directunitcost = total_direct
        concept.unitprice = concept.directunitcost + concept.indirectunitcost + concept.utilityunitcost
        concept.totalamount = concept.unitprice * concept.quantity

        concept.modifiedby = user
        concept.save()
        return concept


class UnitCostBreakdownService:
    """Service class for UnitCostBreakdown business logic."""

    @staticmethod
    def list_breakdowns(concept_id: UUID, user) -> QuerySet[UnitCostBreakdown]:
        """List all breakdown lines for a concept."""
        return UnitCostBreakdown.objects.filter(
            conceptid=concept_id
        ).select_related('supplyid')

    @staticmethod
    def create_breakdown(dto: CreateUnitCostBreakdownDto, user) -> UnitCostBreakdown:
        """Create a new breakdown line with computed amount and auto linenumber."""
        # Validate categorycode
        if dto.categorycode not in [c.value for c in BreakdownCategoryCode]:
            raise ValidationError(f"Invalid category code: {dto.categorycode}")

        # Calculate next linenumber within this concept and category
        max_line = UnitCostBreakdown.objects.filter(
            conceptid=dto.conceptid,
            categorycode=dto.categorycode,
        ).aggregate(max_line=Max('linenumber'))['max_line'] or 0
        next_line = max_line + 1

        # Compute amount = quantity * unitprice * yieldvalue
        quantity = dto.quantity or Decimal('0')
        unitprice = dto.unitprice or Decimal('0')
        yieldvalue = dto.yieldvalue or Decimal('1')
        amount = quantity * unitprice * yieldvalue

        breakdown = UnitCostBreakdown(
            conceptid_id=dto.conceptid,
            categorycode=dto.categorycode,
            linenumber=next_line,
            description=dto.description,
            unit=dto.unit,
            quantity=quantity,
            unitprice=unitprice,
            yieldvalue=yieldvalue,
            amount=amount,
            supplyid_id=dto.supplyid,
        )
        breakdown.save()
        return breakdown

    @staticmethod
    def update_breakdown(breakdown_id: UUID, dto: UpdateUnitCostBreakdownDto, user) -> UnitCostBreakdown:
        """Update a breakdown line and recompute amount."""
        try:
            breakdown = UnitCostBreakdown.objects.get(breakdownid=breakdown_id)
        except UnitCostBreakdown.DoesNotExist:
            raise NotFound(f"UnitCostBreakdown with ID {breakdown_id} not found")

        update_fields = [
            'categorycode', 'description', 'unit', 'quantity',
            'unitprice', 'yieldvalue', 'statecode',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(breakdown, field, value)

        # Handle supplyid FK separately (can be set to None)
        if dto.supplyid is not None:
            breakdown.supplyid_id = dto.supplyid

        # Recompute amount
        breakdown.amount = breakdown.quantity * breakdown.unitprice * breakdown.yieldvalue

        breakdown.save()
        return breakdown

    @staticmethod
    def delete_breakdown(breakdown_id: UUID, user) -> UnitCostBreakdown:
        """Soft delete a breakdown line (statecode=1)."""
        try:
            breakdown = UnitCostBreakdown.objects.get(breakdownid=breakdown_id)
        except UnitCostBreakdown.DoesNotExist:
            raise NotFound(f"UnitCostBreakdown with ID {breakdown_id} not found")

        breakdown.statecode = 1
        breakdown.save()
        return breakdown

    @staticmethod
    @transaction.atomic
    def auto_generate_hm_epp(concept_id: UUID, user) -> list[UnitCostBreakdown]:
        """Auto-create HerramientaMenor + EPP lines at 3% of labor cost.

        If category 4 (Labor) breakdowns exist, add:
        - Category 6 (Minor Tools) at 3% of total labor cost
        - Category 7 (PPE) at 3% of total labor cost
        """
        # Check if labor breakdowns exist (category 4)
        labor_total = UnitCostBreakdown.objects.filter(
            conceptid=concept_id,
            categorycode=BreakdownCategoryCode.LABOR,
            statecode=0,
        ).aggregate(total=Sum('amount'))['total']

        if not labor_total or labor_total <= 0:
            return []

        hm_epp_amount = labor_total * Decimal('0.03')
        created = []

        for cat_code, cat_desc in [
            (BreakdownCategoryCode.MINOR_TOOLS, 'Herramienta Menor (3% M.O.)'),
            (BreakdownCategoryCode.PPE, 'EPP (3% M.O.)'),
        ]:
            # Calculate next linenumber
            max_line = UnitCostBreakdown.objects.filter(
                conceptid=concept_id,
                categorycode=cat_code,
            ).aggregate(max_line=Max('linenumber'))['max_line'] or 0
            next_line = max_line + 1

            breakdown = UnitCostBreakdown(
                conceptid_id=concept_id,
                categorycode=cat_code,
                linenumber=next_line,
                description=cat_desc,
                unit='%',
                quantity=Decimal('1'),
                unitprice=hm_epp_amount,
                yieldvalue=Decimal('1'),
                amount=hm_epp_amount,
            )
            breakdown.save()
            created.append(breakdown)

        return created


class IndirectCostDetailService:
    """Service class for IndirectCostDetail business logic."""

    @staticmethod
    def list_details(
        project_id: UUID,
        user,
        categorycode: Optional[str] = None,
    ) -> QuerySet[IndirectCostDetail]:
        """List indirect cost details for a project, optionally filtered by category."""
        queryset = IndirectCostDetail.objects.filter(projectid=project_id)

        if categorycode is not None:
            queryset = queryset.filter(categorycode=categorycode)

        return queryset.select_related('createdby', 'modifiedby')

    @staticmethod
    def create_detail(dto: CreateIndirectCostDetailDto, user) -> IndirectCostDetail:
        """Create a new indirect cost detail line with computed amount and auto linenumber."""
        # Calculate next linenumber within this project and category
        max_line = IndirectCostDetail.objects.filter(
            projectid=dto.projectid,
            categorycode=dto.categorycode,
        ).aggregate(max_line=Max('linenumber'))['max_line'] or 0
        next_line = max_line + 1

        # Compute amount = monthlycost * units * months
        monthlycost = dto.monthlycost or Decimal('0')
        units = dto.units or Decimal('1')
        months = dto.months or Decimal('0')
        amount = monthlycost * units * months

        detail = IndirectCostDetail(
            projectid_id=dto.projectid,
            categorycode=dto.categorycode,
            linenumber=next_line,
            imputationcode=dto.imputationcode or '',
            area=dto.area or '',
            description=dto.description,
            monthlycost=monthlycost,
            units=units,
            months=months,
            amount=amount,
            createdby=user,
            modifiedby=user,
        )
        detail.save()
        return detail

    @staticmethod
    def update_detail(detail_id: UUID, dto: UpdateIndirectCostDetailDto, user) -> IndirectCostDetail:
        """Update an indirect cost detail line and recompute amount."""
        try:
            detail = IndirectCostDetail.objects.get(indirectcostid=detail_id)
        except IndirectCostDetail.DoesNotExist:
            raise NotFound(f"IndirectCostDetail with ID {detail_id} not found")

        update_fields = [
            'categorycode', 'imputationcode', 'area', 'description',
            'monthlycost', 'units', 'months', 'statecode',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(detail, field, value)

        # Recompute amount
        detail.amount = detail.monthlycost * detail.units * detail.months

        detail.modifiedby = user
        detail.save()
        return detail

    @staticmethod
    def delete_detail(detail_id: UUID, user) -> IndirectCostDetail:
        """Soft delete an indirect cost detail (statecode=1)."""
        try:
            detail = IndirectCostDetail.objects.get(indirectcostid=detail_id)
        except IndirectCostDetail.DoesNotExist:
            raise NotFound(f"IndirectCostDetail with ID {detail_id} not found")

        detail.statecode = 1
        detail.modifiedby = user
        detail.save()
        return detail

    @staticmethod
    @transaction.atomic
    def apply_template(project_id: UUID, projectsize: int, user) -> list[IndirectCostDetail]:
        """Copy indirect cost lines from IndirectCostTemplate matching projectsize."""
        if projectsize not in [c.value for c in ProjectSizeCode]:
            raise ValidationError(f"Invalid project size: {projectsize}")

        templates = IndirectCostTemplate.objects.filter(
            projectsize=projectsize,
            statecode=0,
        ).order_by('categorycode', 'sortorder')

        if not templates.exists():
            raise ValidationError(f"No templates found for project size {projectsize}")

        created = []
        # Track linenumber per category
        line_counters = defaultdict(int)

        # Get existing max linenumbers per category
        existing_maxes = IndirectCostDetail.objects.filter(
            projectid=project_id,
        ).values('categorycode').annotate(max_line=Max('linenumber'))

        for entry in existing_maxes:
            line_counters[entry['categorycode']] = entry['max_line']

        for template in templates:
            line_counters[template.categorycode] += 1
            amount = template.monthlycost * template.units * template.months

            detail = IndirectCostDetail(
                projectid_id=project_id,
                categorycode=template.categorycode,
                linenumber=line_counters[template.categorycode],
                description=template.description,
                monthlycost=template.monthlycost,
                units=template.units,
                months=template.months,
                amount=amount,
                createdby=user,
                modifiedby=user,
            )
            created.append(detail)

        IndirectCostDetail.objects.bulk_create(created)
        return created

    @staticmethod
    def get_total(project_id: UUID, user) -> Decimal:
        """Get total indirect cost amount for a project."""
        total = IndirectCostDetail.objects.filter(
            projectid=project_id,
            statecode=0,
        ).aggregate(total=Sum('amount'))['total']
        return total or Decimal('0')

    @staticmethod
    @transaction.atomic
    def prorate_to_concepts(project_id: UUID, user) -> list[BudgetConcept]:
        """Distribute total indirect cost across concepts proportionally by direct cost.

        Each concept gets: indirectunitcost = (concept.directunitcost / total_direct) * total_indirect
        Then unitprice and totalamount are recalculated.
        """
        total_indirect = IndirectCostDetailService.get_total(project_id, user)

        concepts = BudgetConcept.objects.filter(
            projectid=project_id,
            statecode=0,
        )

        # Calculate total direct cost across all concepts
        total_direct = Decimal('0')
        for concept in concepts:
            total_direct += concept.directunitcost * concept.quantity

        if total_direct <= 0:
            return list(concepts)

        updated = []
        for concept in concepts:
            concept_direct_total = concept.directunitcost * concept.quantity
            proportion = concept_direct_total / total_direct
            concept_indirect_share = total_indirect * proportion

            # Distribute as unit cost
            if concept.quantity > 0:
                concept.indirectunitcost = concept_indirect_share / concept.quantity
            else:
                concept.indirectunitcost = Decimal('0')

            concept.unitprice = concept.directunitcost + concept.indirectunitcost + concept.utilityunitcost
            concept.totalamount = concept.unitprice * concept.quantity
            concept.modifiedby = user
            updated.append(concept)

        BudgetConcept.objects.bulk_update(
            updated,
            ['indirectunitcost', 'unitprice', 'totalamount', 'modifiedby', 'modifiedon'],
        )
        return updated


class OfferAlternativeService:
    """Service class for OfferAlternative business logic."""

    @staticmethod
    def list_alternatives(project_id: UUID, user) -> QuerySet[OfferAlternative]:
        """List all offer alternatives for a project."""
        return OfferAlternative.objects.filter(
            projectid=project_id
        ).select_related('createdby', 'modifiedby')

    @staticmethod
    def create_alternative(dto: CreateOfferAlternativeDto, user) -> OfferAlternative:
        """Create a new offer alternative. Max 4 per project."""
        existing_count = OfferAlternative.objects.filter(
            projectid=dto.projectid,
            statecode=0,
        ).count()

        if existing_count >= 4:
            raise ValidationError("Maximum 4 active alternatives per project")

        # Auto-assign alternative number
        max_num = OfferAlternative.objects.filter(
            projectid=dto.projectid,
        ).aggregate(max_num=Max('alternativenumber'))['max_num'] or 0
        next_num = max_num + 1

        # Compute totals from project concepts + indirects
        concepts = BudgetConcept.objects.filter(
            projectid=dto.projectid,
            statecode=0,
        )
        direct_total = concepts.aggregate(
            total=Sum(F('directunitcost') * F('quantity'), output_field=models.DecimalField())
        )['total'] or Decimal('0')

        indirect_total = IndirectCostDetail.objects.filter(
            projectid=dto.projectid,
            statecode=0,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        construction_cost = direct_total + indirect_total

        transversal = dto.transversalpercent or Decimal('0')
        profit = dto.profitpercent or Decimal('0')

        # coefficient = 1 + transversal/100 + profit/100
        coefficient = Decimal('1') + transversal / Decimal('100') + profit / Decimal('100')
        sale_price_net = construction_cost * coefficient
        tax_amount = sale_price_net * Decimal('0.16')
        sale_price_total = sale_price_net + tax_amount

        alternative = OfferAlternative(
            projectid_id=dto.projectid,
            alternativenumber=next_num,
            name=dto.name,
            description=dto.description or '',
            transversalpercent=transversal,
            profitpercent=profit,
            coefficient=coefficient,
            directcosttotal=direct_total,
            indirectcosttotal=indirect_total,
            constructioncost=construction_cost,
            salepricenet=sale_price_net,
            taxamount=tax_amount,
            salepricetotal=sale_price_total,
            authorizationname=dto.authorizationname or '',
            authorizationposition=dto.authorizationposition or '',
            createdby=user,
            modifiedby=user,
        )
        alternative.save()
        return alternative

    @staticmethod
    def update_alternative(alternative_id: UUID, dto: UpdateOfferAlternativeDto, user) -> OfferAlternative:
        """Update an offer alternative and recompute derived fields."""
        try:
            alternative = OfferAlternative.objects.get(alternativeid=alternative_id)
        except OfferAlternative.DoesNotExist:
            raise NotFound(f"OfferAlternative with ID {alternative_id} not found")

        update_fields = [
            'name', 'description', 'transversalpercent', 'profitpercent',
            'authorizationname', 'authorizationposition', 'statecode',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(alternative, field, value)

        # Recompute coefficient and derived totals
        alternative.coefficient = (
            Decimal('1')
            + alternative.transversalpercent / Decimal('100')
            + alternative.profitpercent / Decimal('100')
        )
        alternative.constructioncost = alternative.directcosttotal + alternative.indirectcosttotal
        alternative.salepricenet = alternative.constructioncost * alternative.coefficient
        alternative.taxamount = alternative.salepricenet * Decimal('0.16')
        alternative.salepricetotal = alternative.salepricenet + alternative.taxamount

        alternative.modifiedby = user
        alternative.save()
        return alternative

    @staticmethod
    def delete_alternative(alternative_id: UUID, user) -> OfferAlternative:
        """Soft delete an offer alternative (statecode=1)."""
        try:
            alternative = OfferAlternative.objects.get(alternativeid=alternative_id)
        except OfferAlternative.DoesNotExist:
            raise NotFound(f"OfferAlternative with ID {alternative_id} not found")

        alternative.statecode = 1
        alternative.modifiedby = user
        alternative.save()
        return alternative

    @staticmethod
    @transaction.atomic
    def choose_alternative(alternative_id: UUID, user) -> OfferAlternative:
        """Set one alternative as chosen, unset all others for the same project."""
        try:
            alternative = OfferAlternative.objects.get(alternativeid=alternative_id)
        except OfferAlternative.DoesNotExist:
            raise NotFound(f"OfferAlternative with ID {alternative_id} not found")

        # Unset all others
        OfferAlternative.objects.filter(
            projectid=alternative.projectid,
        ).update(ischosen=False)

        # Set this one
        alternative.ischosen = True
        alternative.modifiedby = user
        alternative.save()
        return alternative


class ExternalCostService:
    """Service class for ExternalCostItem business logic."""

    @staticmethod
    def list_costs(project_id: UUID, user) -> QuerySet[ExternalCostItem]:
        """List all external cost items for a project."""
        return ExternalCostItem.objects.filter(
            projectid=project_id
        )

    @staticmethod
    @transaction.atomic
    def initialize_checklist(project_id: UUID, user) -> list[ExternalCostItem]:
        """Create default external cost checklist items (~20 items)."""
        existing = ExternalCostItem.objects.filter(projectid=project_id).exists()
        if existing:
            raise ValidationError("External cost checklist already initialized for this project")

        items = []
        for idx, name in enumerate(DEFAULT_EXTERNAL_COSTS, start=1):
            item = ExternalCostItem(
                projectid_id=project_id,
                itemname=name,
                applies=0,  # N/A by default
                percentofsale=None,
                amount=Decimal('0'),
                sortorder=idx,
            )
            items.append(item)

        ExternalCostItem.objects.bulk_create(items)
        return items

    @staticmethod
    def update_cost(cost_id: UUID, dto: UpdateExternalCostItemDto, user) -> ExternalCostItem:
        """Update an external cost item."""
        try:
            cost = ExternalCostItem.objects.get(externalcostid=cost_id)
        except ExternalCostItem.DoesNotExist:
            raise NotFound(f"ExternalCostItem with ID {cost_id} not found")

        update_fields = ['applies', 'percentofsale', 'amount', 'statecode']
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(cost, field, value)

        cost.save()
        return cost


class SupplyExplosionService:
    """Service class for supply explosion reports (read-only, computed)."""

    @staticmethod
    def generate_auxiliary(project_id: UUID, user) -> list[dict]:
        """Generate the auxiliary supply explosion: iterate all UnitCostBreakdowns for a project.

        Returns a list of dicts matching SupplyExplosionItemSchema.
        """
        breakdowns = UnitCostBreakdown.objects.filter(
            conceptid__projectid=project_id,
            statecode=0,
        ).select_related('conceptid', 'supplyid')

        results = []
        for bd in breakdowns:
            concept = bd.conceptid
            results.append({
                'conceptid': concept.conceptid,
                'conceptcode': concept.code,
                'conceptdescription': concept.description,
                'categorycode': bd.categorycode,
                'supplyid': bd.supplyid.supplyid if bd.supplyid else None,
                'supplycode': bd.supplyid.code if bd.supplyid else None,
                'description': bd.description,
                'unit': bd.unit,
                'quantity': bd.quantity,
                'unitprice': bd.unitprice,
                'amount': bd.amount,
            })

        return results

    @staticmethod
    def generate_consolidated(project_id: UUID, user) -> list[dict]:
        """Generate consolidated supply explosion grouped by supply code.

        Returns a list of dicts matching SupplyExplosionConsolidatedSchema.
        """
        breakdowns = UnitCostBreakdown.objects.filter(
            conceptid__projectid=project_id,
            statecode=0,
            supplyid__isnull=False,
        ).select_related('supplyid')

        # Group by supply code
        groups = defaultdict(lambda: {
            'description': '',
            'unit': '',
            'totalquantity': Decimal('0'),
            'totalamount': Decimal('0'),
            'concepts': set(),
        })

        for bd in breakdowns:
            supply = bd.supplyid
            key = supply.code
            group = groups[key]
            group['description'] = supply.description
            group['unit'] = supply.unit
            group['totalquantity'] += bd.quantity
            group['totalamount'] += bd.amount
            group['concepts'].add(bd.conceptid_id)

        results = []
        for supplycode, data in sorted(groups.items()):
            total_qty = data['totalquantity']
            total_amt = data['totalamount']
            avg_price = total_amt / total_qty if total_qty > 0 else Decimal('0')

            results.append({
                'supplycode': supplycode,
                'description': data['description'],
                'unit': data['unit'],
                'totalquantity': total_qty,
                'averageprice': avg_price,
                'totalamount': total_amt,
                'conceptcount': len(data['concepts']),
            })

        return results


class WorkPlanService:
    """Service class for WorkPlanEntry business logic."""

    @staticmethod
    def list_entries(
        project_id: UUID,
        user,
        conceptid: Optional[UUID] = None,
    ) -> QuerySet[WorkPlanEntry]:
        """List work plan entries for a project, optionally filtered by concept."""
        queryset = WorkPlanEntry.objects.filter(projectid=project_id)

        if conceptid is not None:
            queryset = queryset.filter(conceptid=conceptid)

        return queryset.select_related('conceptid', 'createdby', 'modifiedby')

    @staticmethod
    def create_entry(dto: CreateWorkPlanEntryDto, user) -> WorkPlanEntry:
        """Create a work plan entry with computed distributedamount."""
        # Fetch concept to get unitprice
        try:
            concept = BudgetConcept.objects.get(conceptid=dto.conceptid)
        except BudgetConcept.DoesNotExist:
            raise NotFound(f"BudgetConcept with ID {dto.conceptid} not found")

        distributed_amount = dto.distributedquantity * concept.unitprice

        entry = WorkPlanEntry(
            conceptid_id=dto.conceptid,
            projectid_id=dto.projectid,
            periodnumber=dto.periodnumber,
            periodlabel=dto.periodlabel,
            distributedquantity=dto.distributedquantity,
            distributedamount=distributed_amount,
            createdby=user,
            modifiedby=user,
        )
        entry.save()
        return entry

    @staticmethod
    def update_entry(entry_id: UUID, dto: UpdateWorkPlanEntryDto, user) -> WorkPlanEntry:
        """Update a work plan entry and recompute amount."""
        try:
            entry = WorkPlanEntry.objects.select_related('conceptid').get(
                workplanentryid=entry_id
            )
        except WorkPlanEntry.DoesNotExist:
            raise NotFound(f"WorkPlanEntry with ID {entry_id} not found")

        if dto.distributedquantity is not None:
            entry.distributedquantity = dto.distributedquantity
            entry.distributedamount = dto.distributedquantity * entry.conceptid.unitprice

        entry.modifiedby = user
        entry.save()
        return entry

    @staticmethod
    def delete_entry(entry_id: UUID, user) -> None:
        """Hard delete a work plan entry."""
        try:
            entry = WorkPlanEntry.objects.get(workplanentryid=entry_id)
        except WorkPlanEntry.DoesNotExist:
            raise NotFound(f"WorkPlanEntry with ID {entry_id} not found")

        entry.delete()

    @staticmethod
    @transaction.atomic
    def bulk_distribute(project_id: UUID, entries_data: list, user) -> list[WorkPlanEntry]:
        """Bulk create/update work plan entries.

        Validates that sum of distributedquantity per concept <= concept.quantity.
        entries_data: list of dicts with {conceptid, periodnumber, periodlabel, distributedquantity}
        """
        # Group entries by concept for validation
        concept_quantities = defaultdict(Decimal)
        for entry_data in entries_data:
            concept_quantities[entry_data['conceptid']] += Decimal(str(entry_data['distributedquantity']))

        # Validate totals per concept
        for concept_id_val, total_qty in concept_quantities.items():
            try:
                concept = BudgetConcept.objects.get(conceptid=concept_id_val)
            except BudgetConcept.DoesNotExist:
                raise NotFound(f"BudgetConcept with ID {concept_id_val} not found")

            # Get existing distributed quantity for this concept (excluding entries being replaced)
            existing_periods = {
                e['periodnumber']
                for e in entries_data
                if str(e['conceptid']) == str(concept_id_val)
            }
            existing_qty = WorkPlanEntry.objects.filter(
                conceptid=concept_id_val,
                projectid=project_id,
            ).exclude(
                periodnumber__in=existing_periods
            ).aggregate(total=Sum('distributedquantity'))['total'] or Decimal('0')

            if existing_qty + total_qty > concept.quantity:
                raise ValidationError(
                    f"Total distributed quantity ({existing_qty + total_qty}) exceeds "
                    f"concept quantity ({concept.quantity}) for concept {concept.code}"
                )

        # Create or update entries
        created_or_updated = []
        for entry_data in entries_data:
            concept_id_val = entry_data['conceptid']
            period_num = entry_data['periodnumber']
            period_label = entry_data['periodlabel']
            dist_qty = Decimal(str(entry_data['distributedquantity']))

            # Fetch concept for amount calculation
            concept = BudgetConcept.objects.get(conceptid=concept_id_val)
            dist_amount = dist_qty * concept.unitprice

            entry, _created = WorkPlanEntry.objects.update_or_create(
                conceptid_id=concept_id_val,
                periodnumber=period_num,
                defaults={
                    'projectid_id': project_id,
                    'periodlabel': period_label,
                    'distributedquantity': dist_qty,
                    'distributedamount': dist_amount,
                    'createdby': user,
                    'modifiedby': user,
                },
            )
            created_or_updated.append(entry)

        return created_or_updated


class TemporalDistributionService:
    """Service class for temporal distribution reports (read-only, computed)."""

    @staticmethod
    def calculate(project_id: UUID, user) -> list[dict]:
        """Aggregate workplan entries by period, compute invoiced, costs, results with cumulatives.

        Returns a list of dicts matching TemporalDistributionSchema.
        """
        entries = WorkPlanEntry.objects.filter(
            projectid=project_id,
        ).select_related('conceptid').order_by('periodnumber')

        # Group by period
        periods = defaultdict(lambda: {
            'periodlabel': '',
            'invoicedamount': Decimal('0'),
            'costamount': Decimal('0'),
        })

        for entry in entries:
            period = periods[entry.periodnumber]
            period['periodlabel'] = entry.periodlabel

            concept = entry.conceptid
            # Invoiced amount = distributedquantity * client unit price (or unitprice if no client price)
            client_price = concept.clientunitprice if concept.clientunitprice else concept.unitprice
            period['invoicedamount'] += entry.distributedquantity * client_price

            # Cost amount = distributedquantity * direct unit cost
            period['costamount'] += entry.distributedquantity * concept.directunitcost

        # Build result with cumulatives
        results = []
        cumulative_invoiced = Decimal('0')
        cumulative_cost = Decimal('0')
        cumulative_result = Decimal('0')

        for period_num in sorted(periods.keys()):
            data = periods[period_num]
            invoiced = data['invoicedamount']
            cost = data['costamount']
            result = invoiced - cost

            cumulative_invoiced += invoiced
            cumulative_cost += cost
            cumulative_result += result

            results.append({
                'periodnumber': period_num,
                'periodlabel': data['periodlabel'],
                'invoicedamount': invoiced,
                'costamount': cost,
                'resultamount': result,
                'cumulativeinvoiced': cumulative_invoiced,
                'cumulativecost': cumulative_cost,
                'cumulativeresult': cumulative_result,
            })

        return results


class CashFlowService:
    """Service class for cash flow reports (read-only, computed)."""

    @staticmethod
    def calculate(
        project_id: UUID,
        user,
        advance_percent: Decimal = Decimal('0'),
        payment_delay: int = 0,
        payment_frequency: int = 1,
    ) -> list[dict]:
        """Compute cash flow: income (with advance and delayed payments), expenses, net flow.

        Parameters:
        - advance_percent: % of total sale received as advance in period 0
        - payment_delay: number of periods to delay income receipts
        - payment_frequency: collect income every N periods

        Returns a list of dicts matching CashFlowEntrySchema.
        """
        # Get temporal distribution as base data
        distribution = TemporalDistributionService.calculate(project_id, user)

        if not distribution:
            return []

        # Calculate total sale for advance
        total_invoiced = sum(d['invoicedamount'] for d in distribution)
        advance_amount = total_invoiced * advance_percent / Decimal('100')

        # Build raw income per period (before delay)
        max_period = max(d['periodnumber'] for d in distribution)
        raw_income = defaultdict(Decimal)
        raw_expense = defaultdict(Decimal)
        period_labels = {}

        for d in distribution:
            pn = d['periodnumber']
            period_labels[pn] = d['periodlabel']
            raw_expense[pn] = d['costamount']

            # Income = invoiced amount, reduced by advance proportion
            remaining_invoiced = d['invoicedamount'] * (Decimal('1') - advance_percent / Decimal('100'))
            raw_income[pn] = remaining_invoiced

        # Apply payment delay and frequency
        delayed_income = defaultdict(Decimal)

        # Add advance in period 1 (first period)
        first_period = min(period_labels.keys()) if period_labels else 1
        if advance_amount > 0:
            delayed_income[first_period] += advance_amount

        for pn in sorted(raw_income.keys()):
            target_period = pn + payment_delay

            # Apply frequency: only collect every N periods
            if payment_frequency > 1:
                # Accumulate to the next collection period
                periods_since_start = target_period - first_period
                remainder = periods_since_start % payment_frequency
                if remainder != 0:
                    target_period += (payment_frequency - remainder)

            delayed_income[target_period] += raw_income[pn]

        # Determine full range of periods
        all_periods = sorted(set(list(raw_expense.keys()) + list(delayed_income.keys())))

        # Build cash flow entries
        results = []
        cumulative_position = Decimal('0')

        for pn in all_periods:
            income = delayed_income.get(pn, Decimal('0'))
            expense = raw_expense.get(pn, Decimal('0'))
            net_flow = income - expense
            cumulative_position += net_flow

            label = period_labels.get(pn, f"Period {pn}")

            results.append({
                'periodnumber': pn,
                'periodlabel': label,
                'income': income,
                'expense': expense,
                'netflow': net_flow,
                'cumulativeposition': cumulative_position,
                'isriskzone': cumulative_position < 0,
            })

        return results


class SupplyCatalogService:
    """Service class for SupplyCatalogItem business logic."""

    @staticmethod
    def list_items(
        user,
        search: Optional[str] = None,
        supplytype: Optional[int] = None,
    ) -> QuerySet[SupplyCatalogItem]:
        """List supply catalog items with optional text search and type filter."""
        queryset = SupplyCatalogItem.objects.filter(statecode=0)

        if supplytype is not None:
            queryset = queryset.filter(supplytype=supplytype)

        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(description__icontains=search)
            )

        return queryset.select_related('createdby', 'modifiedby')

    @staticmethod
    def create_item(dto: CreateSupplyCatalogItemDto, user) -> SupplyCatalogItem:
        """Create a new supply catalog item."""
        item = SupplyCatalogItem(
            code=dto.code,
            description=dto.description,
            unit=dto.unit,
            supplytype=dto.supplytype,
            referenceprice=dto.referenceprice or Decimal('0'),
            referencedate=dto.referencedate,
            geographiczone=dto.geographiczone or '',
            createdby=user,
            modifiedby=user,
        )
        item.save()
        return item

    @staticmethod
    def update_item(item_id: UUID, dto: UpdateSupplyCatalogItemDto, user) -> SupplyCatalogItem:
        """Update a supply catalog item."""
        try:
            item = SupplyCatalogItem.objects.get(supplyid=item_id)
        except SupplyCatalogItem.DoesNotExist:
            raise NotFound(f"SupplyCatalogItem with ID {item_id} not found")

        update_fields = [
            'code', 'description', 'unit', 'supplytype',
            'referenceprice', 'referencedate', 'geographiczone', 'statecode',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(item, field, value)

        item.modifiedby = user
        item.save()
        return item

    @staticmethod
    def delete_item(item_id: UUID, user) -> SupplyCatalogItem:
        """Soft delete a supply catalog item (statecode=1)."""
        try:
            item = SupplyCatalogItem.objects.get(supplyid=item_id)
        except SupplyCatalogItem.DoesNotExist:
            raise NotFound(f"SupplyCatalogItem with ID {item_id} not found")

        item.statecode = 1
        item.modifiedby = user
        item.save()
        return item


class EquipmentYieldService:
    """Service class for EquipmentYield business logic."""

    @staticmethod
    def list_yields(
        user,
        category: Optional[str] = None,
    ) -> QuerySet[EquipmentYield]:
        """List equipment yields with optional category filter."""
        queryset = EquipmentYield.objects.filter(statecode=0)

        if category is not None:
            queryset = queryset.filter(category=category)

        return queryset.select_related('createdby', 'modifiedby')

    @staticmethod
    def create_yield(dto: CreateEquipmentYieldDto, user) -> EquipmentYield:
        """Create an equipment yield record with computed fields.

        Calculations:
        - realyield = theoreticalyield * trafficfactor
        - dailyfuelconsumption = fuelconsumption * effectivehours
        - monthlycubicmeters = realyield * effectivehours * effectivedays * numberofequipment
        - monthlydiesel = dailyfuelconsumption * effectivedays * numberofequipment
        - costpercubicmeter = monthlycost / monthlycubicmeters (if > 0)
        """
        theoretical = dto.theoreticalyield or Decimal('0')
        traffic = dto.trafficfactor or Decimal('0.8')
        fuel = dto.fuelconsumption or Decimal('0')
        hours = dto.effectivehours or Decimal('0')
        days = dto.effectivedays or Decimal('0')
        num_equip = dto.numberofequipment or 1
        monthly_cost = dto.monthlycost or Decimal('0')

        real_yield = theoretical * traffic
        daily_fuel = fuel * hours
        monthly_cubic = real_yield * hours * days * num_equip
        monthly_diesel = daily_fuel * days * num_equip
        cost_per_cubic = monthly_cost / monthly_cubic if monthly_cubic > 0 else Decimal('0')

        equipment = EquipmentYield(
            category=dto.category,
            description=dto.description,
            suppliername=dto.suppliername or '',
            monthlycost=monthly_cost,
            numberofequipment=num_equip,
            theoreticalyield=theoretical,
            effectivehours=hours,
            realyield=real_yield,
            fuelconsumption=fuel,
            dailyfuelconsumption=daily_fuel,
            effectivedays=days,
            trafficfactor=traffic,
            monthlycubicmeters=monthly_cubic,
            monthlydiesel=monthly_diesel,
            costpercubicmeter=cost_per_cubic,
            createdby=user,
            modifiedby=user,
        )
        equipment.save()
        return equipment

    @staticmethod
    def update_yield(yield_id: UUID, dto: UpdateEquipmentYieldDto, user) -> EquipmentYield:
        """Update an equipment yield record and recompute calculated fields."""
        try:
            equipment = EquipmentYield.objects.get(equipmentyieldid=yield_id)
        except EquipmentYield.DoesNotExist:
            raise NotFound(f"EquipmentYield with ID {yield_id} not found")

        update_fields = [
            'category', 'description', 'suppliername', 'monthlycost',
            'numberofequipment', 'theoreticalyield', 'effectivehours',
            'fuelconsumption', 'effectivedays', 'trafficfactor', 'statecode',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(equipment, field, value)

        # Recompute calculated fields
        equipment.realyield = equipment.theoreticalyield * equipment.trafficfactor
        equipment.dailyfuelconsumption = equipment.fuelconsumption * equipment.effectivehours
        equipment.monthlycubicmeters = (
            equipment.realyield
            * equipment.effectivehours
            * equipment.effectivedays
            * equipment.numberofequipment
        )
        equipment.monthlydiesel = (
            equipment.dailyfuelconsumption
            * equipment.effectivedays
            * equipment.numberofequipment
        )
        equipment.costpercubicmeter = (
            equipment.monthlycost / equipment.monthlycubicmeters
            if equipment.monthlycubicmeters > 0
            else Decimal('0')
        )

        equipment.modifiedby = user
        equipment.save()
        return equipment

    @staticmethod
    def delete_yield(yield_id: UUID, user) -> EquipmentYield:
        """Soft delete an equipment yield record (statecode=1)."""
        try:
            equipment = EquipmentYield.objects.get(equipmentyieldid=yield_id)
        except EquipmentYield.DoesNotExist:
            raise NotFound(f"EquipmentYield with ID {yield_id} not found")

        equipment.statecode = 1
        equipment.modifiedby = user
        equipment.save()
        return equipment


class ConceptPriceCatalogService:
    """Service class for ConceptPriceCatalogItem and ConceptPriceReference."""

    @staticmethod
    def _next_code(source: int) -> str:
        """Generate the next auto-incremented code for a source."""
        prefix = {0: 'SICT', 1: 'HIST', 2: 'MAN'}.get(source, 'HIST')
        last = (
            ConceptPriceCatalogItem.objects
            .filter(code__startswith=f'{prefix}-')
            .order_by('-code')
            .values_list('code', flat=True)
            .first()
        )
        if last:
            try:
                num = int(last.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"{prefix}-{num:05d}"

    @staticmethod
    def list_items(
        user,
        search: Optional[str] = None,
        source: Optional[int] = None,
        unit: Optional[str] = None,
    ) -> QuerySet[ConceptPriceCatalogItem]:
        """List catalog items with optional filters."""
        queryset = ConceptPriceCatalogItem.objects.filter(statecode=0)

        if source is not None:
            queryset = queryset.filter(source=source)

        if unit:
            queryset = queryset.filter(unit__iexact=unit)

        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(description__icontains=search)
            )

        return queryset.select_related('createdby', 'modifiedby')

    @staticmethod
    def get_item(item_id: UUID) -> ConceptPriceCatalogItem:
        """Get a single catalog item with its references."""
        try:
            return ConceptPriceCatalogItem.objects.prefetch_related(
                'price_references'
            ).get(catalogitemid=item_id)
        except ConceptPriceCatalogItem.DoesNotExist:
            from core.exceptions import NotFound
            raise NotFound(f"ConceptPriceCatalogItem with ID {item_id} not found")

    @staticmethod
    def create_item(dto, user) -> ConceptPriceCatalogItem:
        """Create a new catalog item."""
        code = dto.code or ConceptPriceCatalogService._next_code(dto.source)
        item = ConceptPriceCatalogItem(
            code=code,
            description=dto.description,
            unit=dto.unit,
            source=dto.source,
            category=dto.category or '',
            createdby=user,
            modifiedby=user,
        )
        item.save()
        return item

    @staticmethod
    def update_item(item_id: UUID, dto, user) -> ConceptPriceCatalogItem:
        """Update a catalog item."""
        try:
            item = ConceptPriceCatalogItem.objects.get(catalogitemid=item_id)
        except ConceptPriceCatalogItem.DoesNotExist:
            from core.exceptions import NotFound
            raise NotFound(f"ConceptPriceCatalogItem with ID {item_id} not found")

        for field in ['code', 'description', 'unit', 'source', 'category', 'statecode']:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(item, field, value)

        item.modifiedby = user
        item.save()
        return item

    @staticmethod
    def delete_item(item_id: UUID, user) -> ConceptPriceCatalogItem:
        """Soft delete a catalog item."""
        try:
            item = ConceptPriceCatalogItem.objects.get(catalogitemid=item_id)
        except ConceptPriceCatalogItem.DoesNotExist:
            from core.exceptions import NotFound
            raise NotFound(f"ConceptPriceCatalogItem with ID {item_id} not found")

        item.statecode = 1
        item.modifiedby = user
        item.save()
        return item

    # --- Price References ---

    @staticmethod
    def list_references(
        catalog_item_id: UUID,
    ) -> QuerySet[ConceptPriceReference]:
        """List references for a specific catalog item."""
        return ConceptPriceReference.objects.filter(
            catalogitemid=catalog_item_id,
            statecode=0,
        ).select_related('createdby', 'modifiedby')

    @staticmethod
    def create_reference(dto, user) -> ConceptPriceReference:
        """Create a price reference and update parent stats."""
        ref = ConceptPriceReference(
            catalogitemid_id=dto.catalogitemid,
            projectname=dto.projectname,
            projectlocation=dto.projectlocation or '',
            unitprice=dto.unitprice,
            quantity=dto.quantity,
            totalamount=dto.totalamount,
            referencedate=dto.referencedate,
            notes=dto.notes or '',
            createdby=user,
            modifiedby=user,
        )
        ref.save()

        # Update parent stats
        parent = ref.catalogitemid
        parent.update_price_stats()
        parent.save()

        return ref

    @staticmethod
    def delete_reference(reference_id: UUID, user) -> ConceptPriceReference:
        """Soft delete a reference and update parent stats."""
        try:
            ref = ConceptPriceReference.objects.select_related(
                'catalogitemid'
            ).get(referenceid=reference_id)
        except ConceptPriceReference.DoesNotExist:
            from core.exceptions import NotFound
            raise NotFound(f"ConceptPriceReference with ID {reference_id} not found")

        ref.statecode = 1
        ref.modifiedby = user
        ref.save()

        # Update parent stats
        parent = ref.catalogitemid
        parent.update_price_stats()
        parent.save()

        return ref

    @staticmethod
    @transaction.atomic
    def bulk_import(items: list, user) -> dict:
        """Bulk import concepts with their project references.

        Each item: {description, unit, source, category?, references: [{projectname, unitprice, quantity?, totalamount?}]}
        Returns: {created: int, references_created: int}
        """
        created = 0
        refs_created = 0

        for item_data in items:
            code = ConceptPriceCatalogService._next_code(
                item_data.get('source', CatalogSourceCode.HISTORICO)
            )

            catalog_item = ConceptPriceCatalogItem(
                code=code,
                description=item_data['description'],
                unit=item_data['unit'],
                source=item_data.get('source', CatalogSourceCode.HISTORICO),
                category=item_data.get('category', ''),
                createdby=user,
                modifiedby=user,
            )
            catalog_item.save()
            created += 1

            references = item_data.get('references', [])
            for ref_data in references:
                if not ref_data.get('unitprice') or ref_data['unitprice'] <= 0:
                    continue
                ref = ConceptPriceReference(
                    catalogitemid=catalog_item,
                    projectname=ref_data['projectname'],
                    projectlocation=ref_data.get('projectlocation', ''),
                    unitprice=ref_data['unitprice'],
                    quantity=ref_data.get('quantity'),
                    totalamount=ref_data.get('totalamount'),
                    referencedate=ref_data.get('referencedate'),
                    createdby=user,
                    modifiedby=user,
                )
                ref.save()
                refs_created += 1

            # Update stats
            catalog_item.update_price_stats()
            catalog_item.save()

        return {'created': created, 'references_created': refs_created}


class FamilyTemplateService:
    """Service for managing reusable family/subfamily templates."""

    @staticmethod
    def list_template_sets(user, category=None, search=None):
        from django.db.models import Count
        qs = FamilyTemplateSet.objects.filter(statecode=0).annotate(
            _family_count=Count('items__familycode', filter=Q(items__statecode=0), distinct=True),
            _subfamily_count=Count('items', filter=Q(items__statecode=0)),
        )
        if category:
            qs = qs.filter(category=category)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs.prefetch_related('items')

    @staticmethod
    def get_template_set(template_set_id, user):
        try:
            return FamilyTemplateSet.objects.prefetch_related('items').get(
                templatesetid=template_set_id, statecode=0
            )
        except FamilyTemplateSet.DoesNotExist:
            raise NotFound(f"FamilyTemplateSet with ID {template_set_id} not found")

    @staticmethod
    def create_template_set(dto, user):
        ts = FamilyTemplateSet(
            name=dto.name,
            description=dto.description or '',
            category=dto.category,
            issystem=False,
            createdby=user,
            modifiedby=user,
        )
        ts.save()
        return ts

    @staticmethod
    def delete_template_set(template_set_id, user):
        try:
            ts = FamilyTemplateSet.objects.get(templatesetid=template_set_id)
        except FamilyTemplateSet.DoesNotExist:
            raise NotFound(f"FamilyTemplateSet with ID {template_set_id} not found")
        if ts.issystem:
            raise ValidationError("No se pueden eliminar plantillas del sistema.")
        ts.statecode = 1  # Inactive
        ts.modifiedby = user
        ts.save()
        return ts

    @staticmethod
    @transaction.atomic
    def save_project_as_template(dto: SaveProjectAsTemplateDto, user):
        """Extract families+subfamilies from a project and save as a new template."""
        families = ConceptFamily.objects.filter(
            projectid=dto.projectid, statecode=0
        ).order_by('sortorder')

        if not families.exists():
            raise ValidationError("El proyecto no tiene familias para guardar como plantilla.")

        ts = FamilyTemplateSet(
            name=dto.name,
            description=dto.description or '',
            category=dto.category,
            issystem=False,
            createdby=user,
            modifiedby=user,
        )
        ts.save()

        items = []
        for family in families:
            subfamilies = ConceptSubfamily.objects.filter(
                familyid=family, statecode=0
            ).order_by('sortorder')
            if subfamilies.exists():
                for sf in subfamilies:
                    items.append(FamilyTemplateItem(
                        templatesetid=ts,
                        familycode=family.code,
                        familyname=family.name,
                        subfamilycode=sf.code,
                        subfamilyname=sf.name,
                        familysortorder=family.sortorder,
                        subfamilysortorder=sf.sortorder,
                    ))
            else:
                items.append(FamilyTemplateItem(
                    templatesetid=ts,
                    familycode=family.code,
                    familyname=family.name,
                    subfamilycode='',
                    subfamilyname='',
                    familysortorder=family.sortorder,
                    subfamilysortorder=0,
                ))
        FamilyTemplateItem.objects.bulk_create(items)
        return ts

    @staticmethod
    @transaction.atomic
    def apply_template_to_project(dto: ApplyFamilyTemplateDto, user):
        """Create families+subfamilies in a project from a template. Skips existing codes."""
        try:
            ts = FamilyTemplateSet.objects.prefetch_related('items').get(
                templatesetid=dto.templatesetid, statecode=0
            )
        except FamilyTemplateSet.DoesNotExist:
            raise NotFound("Plantilla no encontrada")

        items = ts.items.filter(statecode=0)
        if dto.familycodes:
            items = items.filter(familycode__in=dto.familycodes)

        existing_codes = set(
            ConceptFamily.objects.filter(
                projectid=dto.projectid, statecode=0
            ).values_list('code', flat=True)
        )

        # Group items by family
        families_map = defaultdict(list)
        for item in items.order_by('familysortorder', 'subfamilysortorder'):
            if item.familycode not in existing_codes:
                families_map[
                    (item.familycode, item.familyname, item.familysortorder)
                ].append(item)

        created = []
        for (fcode, fname, fsort), sub_items in families_map.items():
            family = ConceptFamily(
                projectid_id=dto.projectid,
                name=fname,
                code=fcode,
                sortorder=fsort,
                createdby=user,
                modifiedby=user,
            )
            family.save()
            created.append(family)

            for item in sub_items:
                if item.subfamilycode:
                    ConceptSubfamily(
                        familyid=family,
                        projectid_id=dto.projectid,
                        name=item.subfamilyname,
                        code=item.subfamilycode,
                        sortorder=item.subfamilysortorder,
                        createdby=user,
                        modifiedby=user,
                    ).save()

        return created
