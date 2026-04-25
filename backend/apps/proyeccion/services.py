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
    WorkPlanEntryType,
    BreakdownCategoryCode,
    ProjectSizeCode,
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
    FamilyTemplateSet,
    FamilyTemplateItem,
    EstimationFinancialSettings,
    EstimationBillingRule,
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
    def _recalc_concept(concept_id: UUID, user) -> None:
        """Recompute BudgetConcept.directunitcost/unitprice/totalamount from active breakdowns.

        Called after any breakdown mutation so downstream progress indicators
        (e.g. "X de Y conceptos costeados") update without a manual recalc call.
        """
        try:
            concept = BudgetConcept.objects.get(conceptid=concept_id)
        except BudgetConcept.DoesNotExist:
            return

        total_direct = UnitCostBreakdown.objects.filter(
            conceptid=concept_id,
            statecode=0,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        concept.directunitcost = total_direct
        concept.unitprice = (
            concept.directunitcost + concept.indirectunitcost + concept.utilityunitcost
        )
        concept.totalamount = concept.unitprice * concept.quantity
        concept.modifiedby = user
        concept.save(update_fields=[
            'directunitcost', 'unitprice', 'totalamount', 'modifiedby', 'modifiedon',
        ])

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
        UnitCostBreakdownService._recalc_concept(dto.conceptid, user)
        return breakdown

    @staticmethod
    def bulk_create_breakdowns(
        concept_id: UUID, dtos: list[CreateUnitCostBreakdownDto], user
    ) -> list[UnitCostBreakdown]:
        """Create multiple breakdown lines for a concept in a single transaction."""
        from django.db import transaction

        if not dtos:
            return []

        valid_codes = {c.value for c in BreakdownCategoryCode}
        for dto in dtos:
            if dto.categorycode not in valid_codes:
                raise ValidationError(f"Invalid category code: {dto.categorycode}")

        # Pre-compute next line numbers per category to avoid repeated queries
        max_lines = {}
        existing = (
            UnitCostBreakdown.objects.filter(conceptid=concept_id)
            .values('categorycode')
            .annotate(max_line=Max('linenumber'))
        )
        for row in existing:
            max_lines[row['categorycode']] = row['max_line'] or 0

        created: list[UnitCostBreakdown] = []
        with transaction.atomic():
            for dto in dtos:
                next_line = max_lines.get(dto.categorycode, 0) + 1
                max_lines[dto.categorycode] = next_line

                quantity = dto.quantity or Decimal('0')
                unitprice = dto.unitprice or Decimal('0')
                yieldvalue = dto.yieldvalue or Decimal('1')
                amount = quantity * unitprice * yieldvalue

                breakdown = UnitCostBreakdown(
                    conceptid_id=concept_id,
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
                created.append(breakdown)

        UnitCostBreakdownService._recalc_concept(concept_id, user)
        return created

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
        UnitCostBreakdownService._recalc_concept(breakdown.conceptid_id, user)
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
        UnitCostBreakdownService._recalc_concept(breakdown.conceptid_id, user)
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

        UnitCostBreakdownService._recalc_concept(concept_id, user)
        return created

    # -------------------------------------------------------------------------
    # Skeleton generation rules (hardcoded, mirrors frontend config)
    # -------------------------------------------------------------------------
    SKELETON_RULES = [
        {
            'ruleid': 'rule-excavacion',
            'name': 'Excavacion / Terraceria',
            'subfamily_patterns': ['excavac', 'terraceria', 'desmonte', 'despalme', 'deshierbe'],
            'unit_patterns': ['m3', 'm2', 'ha'],
            'include_hm_epp': True,
            'lines': [
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Diesel', 'unit': 'Lt', 'qty': 1, 'price': '23.09', 'yield': '0.862'},
                {'cat': BreakdownCategoryCode.MACHINERY, 'desc': 'Excavadora 336', 'unit': 'Hr', 'qty': 1, 'price': '900', 'yield': '0.034'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Operador 336', 'unit': 'jor', 'qty': 1, 'price': '1071.43', 'yield': '0.00426'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Viatico Operador 336', 'unit': 'semana', 'qty': 1, 'price': '2000', 'yield': '0.00071'},
            ],
        },
        {
            'ruleid': 'rule-concreto',
            'name': 'Concreto',
            'subfamily_patterns': ['concreto', 'ciment', 'colado', 'zapata', 'losa'],
            'unit_patterns': ['m3'],
            'include_hm_epp': True,
            'lines': [
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Cemento Portland CPC 40', 'unit': 'ton', 'qty': 1, 'price': '3200', 'yield': '0.35'},
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Arena', 'unit': 'm3', 'qty': 1, 'price': '280', 'yield': '0.56'},
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Grava 3/4"', 'unit': 'm3', 'qty': 1, 'price': '320', 'yield': '0.756'},
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Agua', 'unit': 'Lt', 'qty': 1, 'price': '0.15', 'yield': '180'},
                {'cat': BreakdownCategoryCode.MACHINERY, 'desc': 'Revolvedora 1 saco', 'unit': 'Hr', 'qty': 1, 'price': '150', 'yield': '0.5'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Cuadrilla (1 oficial + 2 ayudantes)', 'unit': 'jor', 'qty': 1, 'price': '3500', 'yield': '0.125'},
            ],
        },
        {
            'ruleid': 'rule-acero',
            'name': 'Acero Estructural',
            'subfamily_patterns': ['acero', 'armado', 'refuerzo', 'habilitado'],
            'unit_patterns': ['kg', 'ton'],
            'include_hm_epp': True,
            'lines': [
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Acero de refuerzo', 'unit': 'kg', 'qty': 1, 'price': '19', 'yield': '1.05'},
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Alambre recocido', 'unit': 'kg', 'qty': 1, 'price': '28', 'yield': '0.04'},
                {'cat': BreakdownCategoryCode.MACHINERY, 'desc': 'Equipo de corte y doblado', 'unit': 'Hr', 'qty': 1, 'price': '80', 'yield': '0.01'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Armador fierrero', 'unit': 'jor', 'qty': 1, 'price': '850', 'yield': '0.01'},
            ],
        },
        {
            'ruleid': 'rule-malla',
            'name': 'Malla / Gavion',
            'subfamily_patterns': ['malla', 'gavion', 'triple torsion', 'torsion'],
            'unit_patterns': ['m2'],
            'include_hm_epp': True,
            'lines': [
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Malla triple torsion 8x10 calibre 12', 'unit': 'm2', 'qty': 1, 'price': '96', 'yield': '1.2'},
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Cable de acero Galv 1/2"', 'unit': 'ml', 'qty': 1, 'price': '42', 'yield': '0.17'},
                {'cat': BreakdownCategoryCode.MATERIALS, 'desc': 'Varilla corrugada 1/2"', 'unit': 'kg', 'qty': 1, 'price': '19', 'yield': '0.75'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Cuadrilla 1 cabo + 4 instaladores', 'unit': 'jor', 'qty': 1, 'price': '5500', 'yield': '0.01818'},
            ],
        },
        {
            'ruleid': 'rule-acarreo',
            'name': 'Acarreo',
            'subfamily_patterns': ['acarreo', 'carga y acarreo', 'transporte'],
            'unit_patterns': ['m3'],
            'include_hm_epp': True,
            'lines': [
                {'cat': BreakdownCategoryCode.MACHINERY, 'desc': 'Cargador Frontal', 'unit': 'Hr', 'qty': 1, 'price': '900', 'yield': '0.048'},
                {'cat': BreakdownCategoryCode.MACHINERY, 'desc': 'Camion de volteo 14m3', 'unit': 'jor', 'qty': 1, 'price': '6000', 'yield': '0.006'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Operador Cargador Frontal', 'unit': 'jor', 'qty': 1, 'price': '928.57', 'yield': '0.0048'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Viatico Operador Cargador', 'unit': 'semana', 'qty': 1, 'price': '2000', 'yield': '0.0008'},
            ],
        },
        {
            'ruleid': 'rule-topografia',
            'name': 'Topografia',
            'subfamily_patterns': ['topograf', 'trazo', 'nivelacion'],
            'unit_patterns': ['m2', 'ml'],
            'include_hm_epp': True,
            'lines': [
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Topografo + Ayudantes', 'unit': 'jor', 'qty': 1, 'price': '4500', 'yield': '0.003'},
                {'cat': BreakdownCategoryCode.LABOR, 'desc': 'Trabajos de gabinete', 'unit': 'jor', 'qty': 1, 'price': '2500', 'yield': '0.001'},
            ],
        },
    ]

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """Normalize text: lowercase, remove accents."""
        import unicodedata
        normalized = unicodedata.normalize('NFD', text.lower())
        return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

    @classmethod
    def _match_rule_against_text(cls, text: str, unit: str):
        """Try to match a rule against a given text and unit."""
        normalized = cls._normalize_text(text)
        norm_unit = unit.lower().strip()

        for rule in cls.SKELETON_RULES:
            subfamily_match = any(p in normalized for p in rule['subfamily_patterns'])
            if not subfamily_match:
                continue
            if rule['unit_patterns']:
                if norm_unit in rule['unit_patterns']:
                    return rule
            else:
                return rule
        return None

    @classmethod
    def _find_matching_rule(cls, subfamily_name: str, unit: str, description: str = ''):
        """Find a skeleton rule: first by subfamily name, then fallback to concept description."""
        rule = cls._match_rule_against_text(subfamily_name, unit)
        if rule:
            return rule
        if description:
            return cls._match_rule_against_text(description, unit)
        return None

    @classmethod
    @transaction.atomic
    def auto_generate_skeleton(cls, concept_id: UUID, subfamily_name: str, unit: str, user, description: str = '') -> list:
        """Auto-generate skeleton breakdown lines based on subfamily and unit matching rules.
        Falls back to concept description if subfamily doesn't match."""
        rule = cls._find_matching_rule(subfamily_name, unit, description)
        if not rule:
            return []

        created = []
        for line_def in rule['lines']:
            cat_code = line_def['cat']
            max_line = UnitCostBreakdown.objects.filter(
                conceptid=concept_id,
                categorycode=cat_code,
            ).aggregate(max_line=Max('linenumber'))['max_line'] or 0

            qty = Decimal(str(line_def['qty']))
            price = Decimal(line_def['price'])
            yld = Decimal(line_def['yield'])
            amount = qty * price * yld

            breakdown = UnitCostBreakdown(
                conceptid_id=concept_id,
                categorycode=cat_code,
                linenumber=max_line + 1,
                description=line_def['desc'],
                unit=line_def['unit'],
                quantity=qty,
                unitprice=price,
                yieldvalue=yld,
                amount=amount,
            )
            breakdown.save()
            created.append(breakdown)

        # Optionally add HM + EPP lines
        if rule['include_hm_epp']:
            hm_epp = cls.auto_generate_hm_epp(concept_id, user)
            created.extend(hm_epp)

        cls._recalc_concept(concept_id, user)
        return created

    @staticmethod
    def duplicate_line(breakdown_id: UUID, user) -> UnitCostBreakdown:
        """Duplicate an existing breakdown line within the same concept and category."""
        original = UnitCostBreakdown.objects.select_related('supplyid').get(
            breakdownid=breakdown_id, statecode=0
        )
        max_line = UnitCostBreakdown.objects.filter(
            conceptid=original.conceptid,
            categorycode=original.categorycode,
            statecode=0,
        ).aggregate(Max('linenumber'))['linenumber__max'] or 0

        new_line = UnitCostBreakdown(
            conceptid=original.conceptid,
            categorycode=original.categorycode,
            linenumber=max_line + 1,
            description=original.description,
            unit=original.unit,
            quantity=original.quantity,
            unitprice=original.unitprice,
            yieldvalue=original.yieldvalue,
            amount=original.amount,
            supplyid=original.supplyid,
        )
        new_line.save()
        UnitCostBreakdownService._recalc_concept(original.conceptid_id, user)
        return new_line

    @staticmethod
    @transaction.atomic
    def copy_from_concept(target_concept_id: UUID, source_concept_id: UUID, user) -> list[UnitCostBreakdown]:
        """Copy all active breakdown lines from source concept to target concept."""
        source_lines = UnitCostBreakdown.objects.filter(
            conceptid_id=source_concept_id, statecode=0
        ).select_related('supplyid').order_by('categorycode', 'linenumber')

        if not source_lines.exists():
            raise ValidationError("El concepto origen no tiene lineas de desglose.")

        existing = UnitCostBreakdown.objects.filter(
            conceptid_id=target_concept_id, statecode=0
        ).values('categorycode').annotate(max_line=Max('linenumber'))
        max_lines = {row['categorycode']: row['max_line'] for row in existing}

        new_lines = []
        for line in source_lines:
            current_max = max_lines.get(line.categorycode, 0)
            current_max += 1
            max_lines[line.categorycode] = current_max

            new_lines.append(UnitCostBreakdown(
                conceptid_id=target_concept_id,
                categorycode=line.categorycode,
                linenumber=current_max,
                description=line.description,
                unit=line.unit,
                quantity=line.quantity,
                unitprice=line.unitprice,
                yieldvalue=line.yieldvalue,
                amount=line.amount,
                supplyid=line.supplyid,
            ))

        created = UnitCostBreakdown.objects.bulk_create(new_lines)
        UnitCostBreakdownService._recalc_concept(target_concept_id, user)
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
            'supplytype': 0,
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
            group['supplytype'] = supply.supplytype
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
                'supplytype': data['supplytype'],
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
        entrytype: Optional[int] = None,
    ) -> QuerySet[WorkPlanEntry]:
        """List work plan entries for a project, optionally filtered by concept/entrytype."""
        queryset = WorkPlanEntry.objects.filter(projectid=project_id)

        if conceptid is not None:
            queryset = queryset.filter(conceptid=conceptid)
        if entrytype is not None:
            queryset = queryset.filter(entrytype=entrytype)

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
            entrytype=getattr(dto, 'entrytype', WorkPlanEntryType.PLANNED),
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

        entries_data: list of dicts with {conceptid, periodnumber, periodlabel, distributedquantity}

        Note: Previously this validated that sum per concept <= concept.quantity, but the
        Excel source of truth does not enforce that cap on actual production, so we keep
        the check out of the path. The UI still highlights rows that exceed capacity.
        """
        # Validate that every referenced concept exists (fail fast with a clean 404).
        referenced_concepts = {entry_data['conceptid'] for entry_data in entries_data}
        for concept_id_val in referenced_concepts:
            if not BudgetConcept.objects.filter(conceptid=concept_id_val).exists():
                raise NotFound(f"BudgetConcept with ID {concept_id_val} not found")

        created_or_updated = []
        for entry_data in entries_data:
            concept_id_val = entry_data['conceptid']
            period_num = entry_data['periodnumber']
            period_label = entry_data['periodlabel']
            etype = int(entry_data.get('entrytype', WorkPlanEntryType.PLANNED))
            dist_qty = Decimal(str(entry_data['distributedquantity']))

            concept = BudgetConcept.objects.get(conceptid=concept_id_val)
            dist_amount = dist_qty * concept.unitprice

            entry, _created = WorkPlanEntry.objects.update_or_create(
                conceptid_id=concept_id_val,
                periodnumber=period_num,
                entrytype=etype,
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

    # ------------------------------------------------------------------
    # Matrix / Summary aggregations (Excel "Plan de obra" replica)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_value_dict(entries, concept_by_id):
        """Build {'total_qty','total_amount','by_period'} for a list of entries of one entrytype."""
        total_qty = Decimal('0')
        total_amount = Decimal('0')
        by_period = {}
        for e in entries:
            total_qty += e.distributedquantity
            total_amount += e.distributedamount
            by_period[str(e.periodnumber)] = by_period.get(str(e.periodnumber), Decimal('0')) + e.distributedquantity
        return {
            'total_qty': total_qty,
            'total_amount': total_amount,
            'by_period': by_period,
        }

    @staticmethod
    def get_matrix(project_id: UUID, user) -> dict:
        """Return the full (family → subfamily → concept × period) matrix with totals.

        Mirrors the Excel "Plan de obra" layout with both planned and actual blocks.
        """
        concepts = (
            BudgetConcept.objects
            .filter(projectid=project_id)
            .select_related('subfamilyid', 'subfamilyid__familyid')
            .order_by('subfamilyid__familyid__sortorder', 'subfamilyid__sortorder', 'sequencenumber')
        )

        entries = (
            WorkPlanEntry.objects
            .filter(projectid=project_id)
            .only('conceptid_id', 'periodnumber', 'periodlabel', 'entrytype',
                  'distributedquantity', 'distributedamount')
        )

        # Group entries by (conceptid, entrytype)
        grouped = defaultdict(list)
        periods_map = {}
        for e in entries:
            grouped[(str(e.conceptid_id), e.entrytype)].append(e)
            periods_map[e.periodnumber] = e.periodlabel

        periods = [
            {'number': n, 'label': periods_map[n]}
            for n in sorted(periods_map)
        ]

        # Build family/subfamily tree
        family_tree = {}  # familyid -> {family meta, subfamilies: {subfamilyid: {...}}}
        for c in concepts:
            sf = c.subfamilyid
            fm = sf.familyid
            fnode = family_tree.setdefault(str(fm.familyid), {
                'familyid': fm.familyid,
                'code': fm.code,
                'name': fm.name,
                'sortorder': getattr(fm, 'sortorder', 0),
                'contract_amount': Decimal('0'),
                'subfamilies': {},
                'planned_amount': Decimal('0'),
                'actual_amount': Decimal('0'),
                'planned_by_period_amount': defaultdict(lambda: Decimal('0')),
                'actual_by_period_amount': defaultdict(lambda: Decimal('0')),
            })
            sfnode = fnode['subfamilies'].setdefault(str(sf.subfamilyid), {
                'subfamilyid': sf.subfamilyid,
                'code': sf.code,
                'name': sf.name,
                'sortorder': getattr(sf, 'sortorder', 0),
                'concepts': [],
            })

            planned_entries = grouped.get((str(c.conceptid), WorkPlanEntryType.PLANNED), [])
            actual_entries = grouped.get((str(c.conceptid), WorkPlanEntryType.ACTUAL), [])

            planned_val = WorkPlanService._build_value_dict(planned_entries, None)
            actual_val = WorkPlanService._build_value_dict(actual_entries, None)

            sfnode['concepts'].append({
                'conceptid': c.conceptid,
                'code': c.code,
                'description': c.description,
                'unit': c.unit,
                'quantity': c.quantity,
                'unitprice': c.unitprice,
                'totalamount': c.totalamount,
                'planned': planned_val,
                'actual': actual_val,
            })

            fnode['contract_amount'] += c.totalamount or Decimal('0')
            fnode['planned_amount'] += planned_val['total_amount']
            fnode['actual_amount'] += actual_val['total_amount']
            # Per-period amount (SUMPRODUCT equivalent): qty * unitprice
            for pnum, qty in planned_val['by_period'].items():
                fnode['planned_by_period_amount'][pnum] += qty * (c.unitprice or Decimal('0'))
            for pnum, qty in actual_val['by_period'].items():
                fnode['actual_by_period_amount'][pnum] += qty * (c.unitprice or Decimal('0'))

        # Flatten tree to lists with totals
        families = []
        gt_contract = Decimal('0')
        gt_planned = Decimal('0')
        gt_actual = Decimal('0')
        gt_planned_period = defaultdict(lambda: Decimal('0'))
        gt_actual_period = defaultdict(lambda: Decimal('0'))

        for fnode in sorted(family_tree.values(), key=lambda x: (x['sortorder'], x['code'])):
            subfams = sorted(fnode['subfamilies'].values(), key=lambda x: (x['sortorder'], x['code']))
            families.append({
                'familyid': fnode['familyid'],
                'code': fnode['code'],
                'name': fnode['name'],
                'contract_amount': fnode['contract_amount'],
                'subfamilies': [
                    {
                        'subfamilyid': sf['subfamilyid'],
                        'code': sf['code'],
                        'name': sf['name'],
                        'concepts': sf['concepts'],
                    }
                    for sf in subfams
                ],
                'totals': {
                    'planned_amount': fnode['planned_amount'],
                    'actual_amount': fnode['actual_amount'],
                    'planned_by_period_amount': dict(fnode['planned_by_period_amount']),
                    'actual_by_period_amount': dict(fnode['actual_by_period_amount']),
                },
            })
            gt_contract += fnode['contract_amount']
            gt_planned += fnode['planned_amount']
            gt_actual += fnode['actual_amount']
            for k, v in fnode['planned_by_period_amount'].items():
                gt_planned_period[k] += v
            for k, v in fnode['actual_by_period_amount'].items():
                gt_actual_period[k] += v

        return {
            'periods': periods,
            'families': families,
            'grand_totals': {
                'contract_amount': gt_contract,
                'planned_amount': gt_planned,
                'actual_amount': gt_actual,
                'planned_by_period_amount': dict(gt_planned_period),
                'actual_by_period_amount': dict(gt_actual_period),
            },
        }

    @staticmethod
    def get_summary(project_id: UUID, user) -> dict:
        """Compact per-family summary: contract, planned, actual amounts + percents."""
        matrix = WorkPlanService.get_matrix(project_id, user)
        families = []
        for f in matrix['families']:
            contract = f['contract_amount'] or Decimal('0')
            planned = f['totals']['planned_amount']
            actual = f['totals']['actual_amount']
            families.append({
                'familyid': f['familyid'],
                'code': f['code'],
                'name': f['name'],
                'contract_amount': contract,
                'planned_amount': planned,
                'actual_amount': actual,
                'percent_planned': float(planned / contract) if contract else 0.0,
                'percent_actual': float(actual / contract) if contract else 0.0,
            })
        return {
            'families': families,
            'grand_totals': matrix['grand_totals'],
        }


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


# =============================================================================
# ExcelImportService — Analyze & import concepts from Excel
# =============================================================================

class ExcelImportService:
    """Handles Excel upload analysis and concept import into a project."""

    @staticmethod
    def analyze(project_id, file, user):
        """
        Parse an Excel file and match each row against the concept catalog.
        Returns analysis results WITHOUT writing to the database.
        """
        import openpyxl
        from apps.proyeccion.matching import match_concepts

        project = EstimationProject.objects.get(estimationprojectid=project_id)

        # Parse Excel
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active

        # Find header row (look in first 10 rows for "PARTIDA")
        header_row = None
        for row_idx in range(1, min(10, ws.max_row + 1)):
            cell_val = str(ws.cell(row=row_idx, column=1).value or '').strip().upper()
            if 'PARTIDA' in cell_val:
                header_row = row_idx
                break

        if header_row is None:
            from core.exceptions import ValidationError
            raise ValidationError(
                'No se encontro la fila de encabezados. '
                'La primera columna debe contener "PARTIDA".'
            )

        # Parse data rows
        rows = []
        for row_idx in range(header_row + 1, ws.max_row + 1):
            partida = str(ws.cell(row=row_idx, column=1).value or '').strip()
            code = str(ws.cell(row=row_idx, column=2).value or '').strip()
            description = str(ws.cell(row=row_idx, column=3).value or '').strip()
            unit = str(ws.cell(row=row_idx, column=4).value or '').strip()
            quantity_raw = ws.cell(row=row_idx, column=5).value

            if not description:
                continue

            try:
                quantity = float(quantity_raw) if quantity_raw else 0.0
            except (ValueError, TypeError):
                quantity = 0.0

            # Inherit partida from previous row if empty
            if not partida and rows:
                partida = rows[-1]['partida']

            rows.append({
                'row': row_idx,
                'partida': partida,
                'code': code,
                'description': description,
                'unit': unit,
                'quantity': quantity,
            })

        wb.close()

        if not rows:
            from core.exceptions import ValidationError
            raise ValidationError('El archivo no contiene filas de datos.')

        # Match against catalog
        matched_rows = match_concepts(rows)

        # Build partidas list (check against existing subfamilies)
        existing_subfamilies = {
            sf.name.strip().upper(): sf.subfamilyid
            for sf in ConceptSubfamily.objects.filter(
                projectid=project, statecode=0
            )
        }

        partida_names = []
        seen = set()
        for r in matched_rows:
            p = r['partida']
            if p and p not in seen:
                seen.add(p)
                sf_id = existing_subfamilies.get(p.upper())
                partida_names.append({
                    'name': p,
                    'subfamilyid': sf_id,
                    'is_new': sf_id is None,
                })

        # Build response
        concepts = []
        for r in matched_rows:
            candidate = r.get('match_candidate')
            candidate_data = None
            if candidate:
                candidate_data = {
                    'catalogitemid': candidate.catalogitemid,
                    'code': candidate.code,
                    'description': candidate.description,
                    'unit': candidate.unit,
                    'averageprice': float(candidate.averageprice or 0),
                    'classificationl2': candidate.classificationl2 or '',
                    'classificationl3': candidate.classificationl3 or '',
                }

            concepts.append({
                'row': r['row'],
                'partida': r['partida'],
                'code': r['code'],
                'description': r['description'],
                'unit': r['unit'],
                'quantity': r['quantity'],
                'match_status': r['match_status'],
                'match_score': r['match_score'],
                'match_candidate': candidate_data,
            })

        summary = {
            'total': len(concepts),
            'exact': sum(1 for c in concepts if c['match_status'] == 'exact'),
            'partial': sum(1 for c in concepts if c['match_status'] == 'partial'),
            'none': sum(1 for c in concepts if c['match_status'] == 'none'),
        }

        return {
            'partidas': partida_names,
            'concepts': concepts,
            'summary': summary,
        }

    @staticmethod
    @transaction.atomic
    def do_import(project_id, payload, user):
        """
        Import analyzed concepts into the project as BudgetConcepts.
        Creates missing subfamilies if requested.
        """
        project = EstimationProject.objects.get(estimationprojectid=project_id)

        # Get or create the default family for imports
        family = ConceptFamily.objects.filter(
            projectid=project, statecode=0
        ).order_by('sortorder').first()

        if not family:
            family = ConceptFamily.objects.create(
                projectid=project,
                name='GENERAL',
                code='IMP',
                sortorder=0,
                createdby=user,
                modifiedby=user,
            )

        # Resolve partidas -> subfamilies
        existing_sfs = {
            sf.name.strip().upper(): sf
            for sf in ConceptSubfamily.objects.filter(
                projectid=project, statecode=0
            )
        }

        partida_map = {}  # partida_name_upper -> ConceptSubfamily
        subfamilies_created = 0
        next_sort = (
            ConceptSubfamily.objects.filter(projectid=project).count() + 1
        )

        for item in payload.items:
            p_name = item.partida.strip()
            p_upper = p_name.upper()

            if p_upper in partida_map:
                continue

            if p_upper in existing_sfs:
                partida_map[p_upper] = existing_sfs[p_upper]
            elif payload.create_missing_subfamilies:
                # Extract code from partida (e.g., "01. GABINETE" -> code="01", name="GABINETE")
                parts = p_name.split('.', 1)
                sf_code = parts[0].strip() if len(parts) > 1 else str(next_sort).zfill(2)
                sf_name = parts[1].strip() if len(parts) > 1 else p_name

                sf = ConceptSubfamily.objects.create(
                    familyid=family,
                    projectid=project,
                    name=sf_name or p_name,
                    code=sf_code,
                    sortorder=next_sort,
                    createdby=user,
                    modifiedby=user,
                )
                partida_map[p_upper] = sf
                existing_sfs[p_upper] = sf
                subfamilies_created += 1
                next_sort += 1

        # Create BudgetConcepts
        created_count = 0
        matched_count = 0

        for item in payload.items:
            p_upper = item.partida.strip().upper()
            subfamily = partida_map.get(p_upper)
            if not subfamily:
                continue

            # Resolve catalog price if matched
            client_price = None
            if item.accepted_catalog_id and item.use_catalog_price:
                try:
                    cat_item = ConceptPriceCatalogItem.objects.get(
                        catalogitemid=item.accepted_catalog_id
                    )
                    client_price = cat_item.averageprice if cat_item.averageprice > 0 else None
                except ConceptPriceCatalogItem.DoesNotExist:
                    pass

            from apps.proyeccion.schemas import CreateBudgetConceptDto
            dto = CreateBudgetConceptDto(
                projectid=project_id,
                subfamilyid=subfamily.subfamilyid,
                description=item.description,
                unit=item.unit,
                quantity=Decimal(str(item.quantity)) if item.quantity else Decimal('0'),
                breakdownmethod=0,
                clientunitprice=client_price,
                isprintable=True,
            )

            ConceptCatalogService.create_concept(dto, user)
            created_count += 1

            if item.accepted_catalog_id:
                matched_count += 1

        return {
            'created': created_count,
            'subfamilies_created': subfamilies_created,
            'matched': matched_count,
        }


# =============================================================================
# Temporal Distribution — Period Service
# =============================================================================

from datetime import date, timedelta

from apps.proyeccion.models import (
    ProjectionPeriod,
    CostDistribution,
)

SPANISH_MONTHS = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
                  'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']


class PeriodService:
    """Generate and regenerate ProjectionPeriod rows for an EstimationProject."""

    @staticmethod
    def _iter_periods(startdate, enddate, periodtype):
        """Yield (startdate, enddate) tuples covering [startdate, enddate]."""
        delta_days = 7 if periodtype == 0 else 15  # weekly or fortnightly
        cursor = startdate
        n = 0
        while cursor <= enddate:
            period_end = cursor + timedelta(days=delta_days - 1)
            if period_end > enddate:
                period_end = enddate
            yield (cursor, period_end)
            cursor = period_end + timedelta(days=1)
            n += 1
            if n > 500:
                raise RuntimeError("Period generation exceeded 500 periods — aborting")

    @staticmethod
    def _label(periodnumber, start, periodtype):
        prefix = 'S' if periodtype == 0 else 'Q'
        month_abbr = SPANISH_MONTHS[start.month - 1]
        yr = start.year % 100
        return f"{prefix}{periodnumber:02d} {month_abbr}-{yr:02d}"

    @staticmethod
    @transaction.atomic
    def regenerate_projection_periods(project: EstimationProject, *, confirm=False) -> dict:
        """Regenerate ProjectionPeriod[] from project.estimatedstartdate + estimatedenddate + periodtype.

        Returns: {
          'created': N,
          'deleted': M,
          'kept': K,
          'lost_manual_edits': X  # count of CostDistribution isderived=false that were deleted
        }
        Raises: ValueError if dates missing. Also raises ValueError if lost_manual_edits > 0
                and confirm=False (caller must re-invoke with confirm=True).
        """
        if not project.estimatedstartdate or not project.estimatedenddate:
            raise ValueError("Project needs fechas estimadas (start/end) to regenerate periods")

        # Compute new periods
        new_periods = []
        for i, (s, e) in enumerate(PeriodService._iter_periods(
            project.estimatedstartdate, project.estimatedenddate, project.periodtype
        )):
            new_periods.append({
                'periodnumber': i + 1,
                'periodlabel': PeriodService._label(i + 1, s, project.periodtype),
                'startdate': s,
                'enddate': e,
                'periodtype': project.periodtype,
            })
        new_count = len(new_periods)

        # Check what we'd lose: manual edits in period slots that won't exist anymore
        existing_count = ProjectionPeriod.objects.filter(projectid=project).count()
        lost_manual = 0
        if existing_count > new_count:
            lost_manual = CostDistribution.objects.filter(
                projectid=project, isderived=False,
                periodnumber__gt=new_count,
            ).count()
            if lost_manual > 0 and not confirm:
                raise ValueError(
                    f"regenerate would discard {lost_manual} manual distribution edits "
                    f"in periods > {new_count}. Re-invoke with confirm=True to proceed."
                )

        # Delete existing periods (periodnumber > new_count) and their distributions
        ProjectionPeriod.objects.filter(
            projectid=project, periodnumber__gt=new_count
        ).delete()
        CostDistribution.objects.filter(
            projectid=project, periodnumber__gt=new_count
        ).delete()

        # Upsert new periods
        for p in new_periods:
            ProjectionPeriod.objects.update_or_create(
                projectid=project, periodnumber=p['periodnumber'],
                defaults={
                    'periodlabel': p['periodlabel'],
                    'startdate': p['startdate'],
                    'enddate': p['enddate'],
                    'periodtype': p['periodtype'],
                },
            )

        # Update cached count
        project.periodcount = new_count
        project.save(update_fields=['periodcount'])

        return {
            'created': new_count,
            'deleted': max(0, existing_count - new_count),
            'kept': min(existing_count, new_count),
            'lost_manual_edits': lost_manual,
        }


# =============================================================================
# Cost Distribution Service
# =============================================================================

from django.db.models import DecimalField
from django.db.models.functions import Coalesce
from apps.proyeccion.models import CostLineType


class CostDistributionService:
    """Business logic for CostDistribution — rollups, autofill, bulk edits."""

    @staticmethod
    def compute_rollups(project) -> dict:
        """Compute SUMPRODUCT(amount, fraction) across all lines for each period.

        Returns dict with per-period arrays (length = periodcount) and totals.
        All numeric values are Decimal.
        """
        N = project.periodcount or 0
        zeros = [Decimal("0")] * N

        # Direct: SUMPRODUCT via ORM annotation — join CostDistribution with breakdown.amount
        direct_by_period = list(zeros)
        direct_qs = CostDistribution.objects.filter(
            projectid=project, linetype=CostLineType.BREAKDOWN,
        ).annotate(
            contribution=F('breakdownid__amount') * F('fraction'),
        ).values('periodnumber').annotate(
            total=Coalesce(Sum('contribution'), Decimal("0"), output_field=DecimalField(max_digits=19, decimal_places=4)),
        )
        for row in direct_qs:
            p = row['periodnumber']
            if 1 <= p <= N:
                direct_by_period[p - 1] = Decimal(row['total'] or 0)

        # Indirect: SUMPRODUCT via IndirectCostDetail.amount
        indirect_by_period = list(zeros)
        indirect_qs = CostDistribution.objects.filter(
            projectid=project, linetype=CostLineType.INDIRECT,
        ).annotate(
            contribution=F('indirectcostid__amount') * F('fraction'),
        ).values('periodnumber').annotate(
            total=Coalesce(Sum('contribution'), Decimal("0"), output_field=DecimalField(max_digits=19, decimal_places=4)),
        )
        for row in indirect_qs:
            p = row['periodnumber']
            if 1 <= p <= N:
                indirect_by_period[p - 1] = Decimal(row['total'] or 0)

        # Retiros via chosen alternative
        chosen = OfferAlternative.objects.filter(projectid=project, ischosen=True).first()
        trans_pct = chosen.transversalpercent if chosen else Decimal("0")
        prof_pct = chosen.profitpercent if chosen else Decimal("0")

        base_cost = [d + i for d, i in zip(direct_by_period, indirect_by_period)]
        retiro_by_period = [_round2(c * trans_pct) for c in base_cost]
        utility_by_period = [_round2(c * prof_pct) for c in base_cost]
        total_cost_by_period = [b + r + u for b, r, u in zip(base_cost, retiro_by_period, utility_by_period)]

        # Sale from WorkPlanEntry (PLANNED)
        sale_by_period = list(zeros)
        sale_qs = WorkPlanEntry.objects.filter(
            projectid=project, entrytype=WorkPlanEntryType.PLANNED,
        ).values('periodnumber').annotate(total=Coalesce(Sum('distributedamount'), Decimal("0")))
        for row in sale_qs:
            p = row['periodnumber']
            if 1 <= p <= N:
                sale_by_period[p - 1] = Decimal(row['total'] or 0)

        return {
            'direct_by_period': direct_by_period,
            'indirect_by_period': indirect_by_period,
            'retiro_by_period': retiro_by_period,
            'utility_by_period': utility_by_period,
            'total_cost_by_period': total_cost_by_period,
            'sale_by_period': sale_by_period,
            'direct_total': sum(direct_by_period, Decimal("0")),
            'indirect_total': sum(indirect_by_period, Decimal("0")),
            'retiro_total': sum(retiro_by_period, Decimal("0")),
            'utility_total': sum(utility_by_period, Decimal("0")),
            'cost_total': sum(total_cost_by_period, Decimal("0")),
            'sale_total': sum(sale_by_period, Decimal("0")),
            'chosen_alternative_id': chosen.alternativeid if chosen else None,
            'transversalpercent': trans_pct,
            'profitpercent': prof_pct,
        }

    @staticmethod
    @transaction.atomic
    def autofill(project, *, strategy: str, only_empty: bool, scope: str) -> dict:
        """Populate CostDistribution according to strategy/scope.

        strategy: 'proportional_workplan' | 'uniform'
        only_empty: if True, don't overwrite existing rows (even derived)
        scope: 'all' | 'direct_only' | 'indirect_only' | 'family:<CODE>'
        """
        if strategy not in ('proportional_workplan', 'uniform'):
            raise ValueError(f"Unknown strategy: {strategy}")

        N = project.periodcount
        if N == 0:
            raise ValueError("Project has no periods — generate them first.")

        lines_affected = 0
        warnings = []

        # Gather lines to process
        breakdowns = []
        indirects = []
        if scope in ('all', 'direct_only') or scope.startswith('family:'):
            bq = UnitCostBreakdown.objects.filter(conceptid__projectid=project).select_related('conceptid')
            if scope.startswith('family:'):
                fam_code = scope.split(':', 1)[1]
                bq = bq.filter(conceptid__subfamilyid__familyid__code=fam_code)
            breakdowns = list(bq)
        if scope in ('all', 'indirect_only'):
            indirects = list(IndirectCostDetail.objects.filter(projectid=project))

        # Process breakdowns
        for bd in breakdowns:
            fractions = CostDistributionService._compute_line_fractions_breakdown(
                bd, project, strategy, N, warnings,
            )
            lines_affected += CostDistributionService._upsert_line_distribution(
                project=project, linetype=CostLineType.BREAKDOWN,
                breakdownid=bd.breakdownid, indirectcostid=None,
                fractions=fractions, only_empty=only_empty,
            )

        # Process indirects (always uniform within startmonth-endmonth range)
        for ind in indirects:
            fractions = CostDistributionService._compute_line_fractions_indirect(ind, N)
            lines_affected += CostDistributionService._upsert_line_distribution(
                project=project, linetype=CostLineType.INDIRECT,
                breakdownid=None, indirectcostid=ind.indirectcostid,
                fractions=fractions, only_empty=only_empty,
            )

        return {
            'lines_affected': lines_affected,
            'warnings': warnings,
        }

    @staticmethod
    def _compute_line_fractions_breakdown(bd, project, strategy, N, warnings):
        """Return list of N Decimals summing to 1.0."""
        if strategy == 'uniform':
            return [Decimal(1) / Decimal(N)] * N
        # proportional_workplan
        wp = WorkPlanEntry.objects.filter(
            conceptid=bd.conceptid, projectid=project, entrytype=WorkPlanEntryType.PLANNED,
        ).values('periodnumber', 'distributedamount')
        total = sum((Decimal(e['distributedamount']) for e in wp), Decimal("0"))
        if total <= 0:
            warnings.append(f"breakdown {bd.breakdownid}: no workplan — fallback uniform")
            return [Decimal(1) / Decimal(N)] * N
        buckets = [Decimal("0")] * N
        for e in wp:
            p = e['periodnumber']
            if 1 <= p <= N:
                buckets[p - 1] = Decimal(e['distributedamount']) / total
        return buckets

    @staticmethod
    def _compute_line_fractions_indirect(ind, N):
        start = ind.startmonth or 1
        end = ind.endmonth or N
        start = max(1, min(start, N))
        end = max(start, min(end, N))
        span = end - start + 1
        each = Decimal(1) / Decimal(span)
        buckets = [Decimal("0")] * N
        for p in range(start, end + 1):
            buckets[p - 1] = each
        return buckets

    @staticmethod
    def _upsert_line_distribution(*, project, linetype, breakdownid, indirectcostid, fractions, only_empty) -> int:
        """Return number of rows written/modified."""
        affected = 0
        for idx, frac in enumerate(fractions):
            period = idx + 1
            lookup = {'projectid': project, 'linetype': linetype, 'periodnumber': period}
            if breakdownid:
                lookup['breakdownid_id'] = breakdownid
            else:
                lookup['indirectcostid_id'] = indirectcostid
            existing = CostDistribution.objects.filter(**lookup).first()
            if only_empty and existing is not None:
                continue  # preserve
            defaults = {'fraction': frac.quantize(Decimal("0.00000001")), 'isderived': True}
            if existing:
                for k, v in defaults.items():
                    setattr(existing, k, v)
                existing.version = F('version') + 1
                existing.save(update_fields=['fraction', 'isderived', 'version', 'modifiedon'])
            else:
                CostDistribution.objects.create(**lookup, **defaults)
            affected += 1
        return affected

    @staticmethod
    @transaction.atomic
    def apply_bulk_edits(project, *, user, edits: list) -> dict:
        """Apply multiple edits atomically with optimistic locking per cell.

        Each edit: {lineid, linetype, periodnumber, fraction, expected_version}
        Raises VersionConflict(list[{lineid, periodnumber, your_version, server_version,
                                      your_value, server_value, server_modifiedby,
                                      server_modifiedon}]) on any version mismatch.

        Note: SQLite (used in development) does not support row-level locking, so
        select_for_update() is a no-op at the SQL level in dev. The all-or-nothing
        atomicity via transaction.atomic() still holds. PostgreSQL in production
        enforces proper row-level locking.
        """
        conflicts = []
        # SELECT FOR UPDATE on the affected rows to serialize with other writers
        for edit in edits:
            lt = CostLineType.BREAKDOWN if edit['linetype'] == 'BREAKDOWN' else CostLineType.INDIRECT
            lookup = {'projectid': project, 'linetype': lt, 'periodnumber': edit['periodnumber']}
            if lt == CostLineType.BREAKDOWN:
                lookup['breakdownid_id'] = edit['lineid']
            else:
                lookup['indirectcostid_id'] = edit['lineid']
            existing = CostDistribution.objects.select_for_update().filter(**lookup).first()
            if existing is None:
                # Create with version=0; expected must also be 0
                if edit.get('expected_version', 0) != 0:
                    conflicts.append({
                        'lineid': edit['lineid'], 'periodnumber': edit['periodnumber'],
                        'your_version': edit.get('expected_version'),
                        'server_version': 0,
                        'your_value': float(edit['fraction']),
                        'server_value': None,
                        'server_modifiedby': None,
                        'server_modifiedon': None,
                    })
                continue
            if existing.version != edit['expected_version']:
                conflicts.append({
                    'lineid': edit['lineid'], 'periodnumber': edit['periodnumber'],
                    'your_version': edit['expected_version'],
                    'server_version': existing.version,
                    'your_value': float(edit['fraction']),
                    'server_value': float(existing.fraction),
                    'server_modifiedby': str(existing.modifiedby) if existing.modifiedby else None,
                    'server_modifiedon': existing.modifiedon.isoformat(),
                })

        if conflicts:
            raise VersionConflict(conflicts)

        # No conflicts — apply all
        new_versions = {}
        for edit in edits:
            lt = CostLineType.BREAKDOWN if edit['linetype'] == 'BREAKDOWN' else CostLineType.INDIRECT
            lookup = {'projectid': project, 'linetype': lt, 'periodnumber': edit['periodnumber']}
            if lt == CostLineType.BREAKDOWN:
                lookup['breakdownid_id'] = edit['lineid']
            else:
                lookup['indirectcostid_id'] = edit['lineid']
            existing = CostDistribution.objects.filter(**lookup).first()
            if existing is None:
                new = CostDistribution.objects.create(
                    **lookup,
                    fraction=Decimal(str(edit['fraction'])).quantize(Decimal("0.00000001")),
                    isderived=False, version=1, modifiedby=user,
                )
                new_versions[f"{edit['lineid']}:{edit['periodnumber']}"] = 1
            else:
                existing.fraction = Decimal(str(edit['fraction'])).quantize(Decimal("0.00000001"))
                existing.isderived = False
                existing.version += 1
                existing.modifiedby = user
                existing.save(update_fields=['fraction', 'isderived', 'version', 'modifiedby', 'modifiedon'])
                new_versions[f"{edit['lineid']}:{edit['periodnumber']}"] = existing.version

        return {'updated': len(edits), 'new_versions': new_versions}

    @staticmethod
    @transaction.atomic
    def reset_line(project, *, lineid: str, linetype: str) -> dict:
        lt = CostLineType.BREAKDOWN if linetype == 'BREAKDOWN' else CostLineType.INDIRECT
        filt = {'projectid': project, 'linetype': lt}
        if lt == CostLineType.BREAKDOWN:
            filt['breakdownid_id'] = lineid
        else:
            filt['indirectcostid_id'] = lineid
        CostDistribution.objects.filter(**filt).delete()

        # Regenerate via autofill (default: proportional_workplan falls back to uniform)
        N = project.periodcount
        warnings = []
        if lt == CostLineType.BREAKDOWN:
            bd = UnitCostBreakdown.objects.get(breakdownid=lineid)
            fractions = CostDistributionService._compute_line_fractions_breakdown(
                bd, project, 'proportional_workplan', N, warnings,
            )
            CostDistributionService._upsert_line_distribution(
                project=project, linetype=lt,
                breakdownid=lineid, indirectcostid=None,
                fractions=fractions, only_empty=False,
            )
        else:
            ind = IndirectCostDetail.objects.get(indirectcostid=lineid)
            fractions = CostDistributionService._compute_line_fractions_indirect(ind, N)
            CostDistributionService._upsert_line_distribution(
                project=project, linetype=lt,
                breakdownid=None, indirectcostid=lineid,
                fractions=fractions, only_empty=False,
            )
        return {'reset': True, 'warnings': warnings}

    @staticmethod
    def build_payload(project) -> dict:
        """Assemble the full GET /cost-distribution response."""
        rollups = CostDistributionService.compute_rollups(project)
        periods = list(ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'))

        families = CostDistributionService._build_families_hierarchy(project, rollups)

        # Frontend-friendly flattening
        rollups_payload = {
            'direct_by_period': [float(x) for x in rollups['direct_by_period']],
            'indirect_by_period': [float(x) for x in rollups['indirect_by_period']],
            'retiro_by_period': [float(x) for x in rollups['retiro_by_period']],
            'utility_by_period': [float(x) for x in rollups['utility_by_period']],
            'total_cost_by_period': [float(x) for x in rollups['total_cost_by_period']],
            'sale_by_period': [float(x) for x in rollups['sale_by_period']],
            'margin_by_period': [
                float(s - c) for s, c in zip(rollups['sale_by_period'], rollups['total_cost_by_period'])
            ],
        }
        sale_total = rollups['sale_total']
        cost_total = rollups['cost_total']
        totals = {
            'direct_total': float(rollups['direct_total']),
            'indirect_total': float(rollups['indirect_total']),
            'retiro_total': float(rollups['retiro_total']),
            'utility_total': float(rollups['utility_total']),
            'cost_total': float(cost_total),
            'sale_total': float(sale_total),
            'margin_total': float(sale_total - cost_total),
            'margin_pct': float((sale_total - cost_total) / sale_total) if sale_total else 0.0,
        }
        if rollups['chosen_alternative_id']:
            alt = OfferAlternative.objects.get(alternativeid=rollups['chosen_alternative_id'])
            chosen = {
                'alternativeid': str(alt.alternativeid),
                'name': alt.name,
                'transversalpercent': float(alt.transversalpercent),
                'profitpercent': float(alt.profitpercent),
            }
        else:
            chosen = {
                'alternativeid': None, 'name': None,
                'transversalpercent': 0.0, 'profitpercent': 0.0,
            }

        return {
            'periods': [_period_dto(p) for p in periods],
            'families': families,
            'rollups': rollups_payload,
            'totals': totals,
            'chosen_alternative': chosen,
        }

    # Canonical direct-cost categories, in the order the Excel reference uses them.
    # Maps BreakdownCategoryCode values → display name.
    _DIRECT_CATEGORIES = [
        (1, 'MATERIALS',    'MATERIALES'),
        (2, 'HAULING',      'ACARREOS'),
        (3, 'MACHINERY',    'MAQUINARIA'),
        (4, 'LABOR',        'MANO DE OBRA'),
        (5, 'SUBCONTRACTS', 'SUBCONTRATOS'),
        (6, 'MINOR_TOOLS',  'HERRAMIENTA MENOR'),
        (7, 'PPE',          'EPP'),
    ]

    @staticmethod
    def _build_families_hierarchy(project, rollups) -> list:
        """Build families array: directs grouped by breakdown category (MATERIALES,
        MAQUINARIA, ...), indirects grouped by IndirectCostDetail.categorycode using
        the `area` field for the display name.
        """
        N = project.periodcount
        families = []

        # DIRECT: group UnitCostBreakdown by categorycode (not by concept family)
        bds_by_cat = defaultdict(list)
        bds = UnitCostBreakdown.objects.filter(
            conceptid__projectid=project,
        ).select_related('conceptid')
        for bd in bds:
            bds_by_cat[bd.categorycode].append(bd)

        for cat_value, cat_code, cat_name in CostDistributionService._DIRECT_CATEGORIES:
            bd_list = bds_by_cat.get(cat_value, [])
            if not bd_list:
                continue  # omit empty categories so the UI stays tight
            rollups_by_period = CostDistributionService._family_rollup(
                bd_list, N, linetype='BREAKDOWN',
            )
            total_amount = sum((bd.amount for bd in bd_list), Decimal("0"))
            families.append({
                'code': cat_code,
                'name': cat_name,
                'categorytype': 'DIRECT',
                'totalamount': float(total_amount),
                'rollups_by_period': [float(x) for x in rollups_by_period],
                'lines': [
                    CostDistributionService._line_payload_breakdown(bd, N)
                    for bd in bd_list
                ],
            })

        # INDIRECT: group by categorycode; use `area` field for the family name
        ind_by_cat = defaultdict(list)
        for ind in IndirectCostDetail.objects.filter(projectid=project):
            ind_by_cat[ind.categorycode or 'OTHER'].append(ind)
        for cat in sorted(ind_by_cat.keys()):
            inds = ind_by_cat[cat]
            rollups_by_period = CostDistributionService._family_rollup(
                inds, N, linetype='INDIRECT',
            )
            total_amount = sum((ind.amount for ind in inds), Decimal("0"))
            name = (inds[0].area or '').strip() or f'Indirecto {cat}'
            families.append({
                'code': cat,
                'name': name,
                'categorytype': 'INDIRECT',
                'totalamount': float(total_amount),
                'rollups_by_period': [float(x) for x in rollups_by_period],
                'lines': [
                    CostDistributionService._line_payload_indirect(ind, N)
                    for ind in inds
                ],
            })
        return families

    @staticmethod
    def _family_rollup(lines, N, *, linetype):
        """SUMPRODUCT of given lines x fractions per period."""
        buckets = [Decimal("0")] * N
        if not lines:
            return buckets
        if linetype == 'BREAKDOWN':
            line_ids = [l.breakdownid for l in lines]
            amounts = {l.breakdownid: l.amount for l in lines}
            qs = CostDistribution.objects.filter(breakdownid_id__in=line_ids)
            for d in qs:
                amt = amounts.get(d.breakdownid_id, Decimal("0"))
                if 1 <= d.periodnumber <= N:
                    buckets[d.periodnumber - 1] += amt * d.fraction
        else:
            line_ids = [l.indirectcostid for l in lines]
            amounts = {l.indirectcostid: l.amount for l in lines}
            qs = CostDistribution.objects.filter(indirectcostid_id__in=line_ids)
            for d in qs:
                amt = amounts.get(d.indirectcostid_id, Decimal("0"))
                if 1 <= d.periodnumber <= N:
                    buckets[d.periodnumber - 1] += amt * d.fraction
        return buckets

    @staticmethod
    def _line_payload_breakdown(bd, N):
        dists = list(CostDistribution.objects.filter(breakdownid=bd).order_by('periodnumber'))
        cells = [
            {'periodnumber': d.periodnumber, 'fraction': float(d.fraction),
             'isderived': d.isderived, 'version': d.version}
            for d in dists
        ]
        checksum = sum((d.fraction for d in dists), Decimal("0"))
        return {
            'lineid': str(bd.breakdownid),
            'linetype': 'BREAKDOWN',
            'description': bd.description,
            'unit': bd.unit,
            'totalamount': float(bd.amount),
            'distribution': cells,
            'checksum': float(checksum),
        }

    @staticmethod
    def _line_payload_indirect(ind, N):
        dists = list(CostDistribution.objects.filter(indirectcostid=ind).order_by('periodnumber'))
        cells = [
            {'periodnumber': d.periodnumber, 'fraction': float(d.fraction),
             'isderived': d.isderived, 'version': d.version}
            for d in dists
        ]
        checksum = sum((d.fraction for d in dists), Decimal("0"))
        return {
            'lineid': str(ind.indirectcostid),
            'linetype': 'INDIRECT',
            'description': ind.description,
            'unit': '',
            'totalamount': float(ind.amount),
            'distribution': cells,
            'checksum': float(checksum),
        }


class VersionConflict(Exception):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        super().__init__(f"{len(conflicts)} version conflicts")


def _round2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"))


def _period_dto(p):
    return {
        'periodid': str(p.periodid),
        'periodnumber': p.periodnumber,
        'periodlabel': p.periodlabel,
        'startdate': p.startdate.isoformat(),
        'enddate': p.enddate.isoformat(),
        'periodtype': p.periodtype,
    }


# =============================================================================
# Presence Service
# =============================================================================

from apps.proyeccion.models import DistributionPresence


class PresenceService:
    STALE_THRESHOLD_MINUTES = 2

    @staticmethod
    def heartbeat(project, user, *, mode: str):
        obj, _ = DistributionPresence.objects.update_or_create(
            projectid=project, userid=user,
            defaults={'mode': mode},
        )
        return obj

    @staticmethod
    def list_active(project):
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(minutes=PresenceService.STALE_THRESHOLD_MINUTES)
        return list(
            DistributionPresence.objects
            .filter(projectid=project, last_seen__gte=cutoff)
            .select_related('userid')
            .order_by('-last_seen')
        )


# =============================================================================
# Estimation Financial Settings Service
# =============================================================================


class EstimationFinancialSettingsService:
    """Manage 1:1 financial settings for an EstimationProject."""

    _WHITELIST = frozenset({
        'advanceamountnotax', 'advanceentryperiod', 'advanceamortizationrate',
        'imssretentionrate', 'otherretentionrate', 'retentionreturnperiod',
        'directpaymentlag', 'indirectpaymentlag',
        'financecostrate',
    })

    @staticmethod
    def get_or_create(project_id):
        """Idempotent. Materializes defaults on first call."""
        project = EstimationProject.objects.get(pk=project_id)
        settings, _created = EstimationFinancialSettings.objects.get_or_create(projectid=project)
        return settings

    @classmethod
    def update(cls, project_id, dto, user=None):
        """Apply only whitelisted fields. Ignore unknown keys silently."""
        settings = cls.get_or_create(project_id)
        for key, value in (dto or {}).items():
            if key in cls._WHITELIST:
                setattr(settings, key, value)
        if user is not None:
            settings.modifiedby = user
        settings.save()
        return settings


# =============================================================================
# Estimation Billing Rule Service
# =============================================================================


class EstimationBillingRuleService:
    """Manage N billing tranches per estimation project."""

    _SUM_TOLERANCE = Decimal('0.0001')
    _MAX_RULES = 10

    @staticmethod
    def list(project_id):
        return list(
            EstimationBillingRule.objects.filter(projectid=project_id).order_by('sequence')
        )

    @classmethod
    @transaction.atomic
    def replace(cls, project_id, rules, user=None):
        """All-or-nothing replacement. Validates count, sum, sequences."""
        if not rules:
            raise ValueError('Debe proporcionar al menos 1 regla de facturación.')
        if len(rules) > cls._MAX_RULES:
            raise ValueError(f'Máximo {cls._MAX_RULES} reglas permitidas.')

        sequences = [r['sequence'] for r in rules]
        if len(set(sequences)) != len(sequences):
            raise ValueError('Las secuencias deben ser únicas.')

        total = sum((Decimal(str(r['percent'])) for r in rules), Decimal('0'))
        if abs(total - Decimal('1')) > cls._SUM_TOLERANCE:
            raise ValueError(
                f'La suma de porcentajes debe ser 100% (±0.01%). Suma actual: {total * 100:.4f}%.'
            )

        project = EstimationProject.objects.get(pk=project_id)
        EstimationBillingRule.objects.filter(projectid=project).delete()
        created = []
        for r in rules:
            instance = EstimationBillingRule.objects.create(
                projectid=project,
                sequence=r['sequence'],
                percent=Decimal(str(r['percent'])),
                lagperiods=int(r['lagperiods']),
            )
            if user is not None:
                instance.createdby = user
                instance.modifiedby = user
                instance.save(update_fields=['createdby', 'modifiedby'])
            created.append(instance)
        return sorted(created, key=lambda x: x.sequence)


# =============================================================================
# Estimation PNT (Proyección de Necesidad de Tesorería) Calculator
# =============================================================================

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from django.utils import timezone

ZERO = Decimal('0')


@dataclass
class _PNTRow:
    code: str
    label: str
    section: str  # 'RESULTADO' | 'COBROS' | 'PAGOS' | 'CAJA'
    values: list
    emphasis: bool = False


@dataclass
class _PNTReport:
    projectid: object
    granularity: str
    periods: list
    rows: list
    stats: dict
    generated_at: datetime


@dataclass
class _InlineBillingRule:
    sequence: int
    percent: Decimal
    lagperiods: int


class EstimationPNTCalculator:
    """Derive PNT from CostDistribution rollups + financial settings + billing rules."""

    _OVERRIDE_ALLOWLIST = frozenset({
        'imssretentionrate', 'otherretentionrate', 'retentionreturnperiod',
        'advanceamountnotax', 'advanceentryperiod', 'advanceamortizationrate',
        'directpaymentlag', 'indirectpaymentlag', 'financecostrate',
    })

    def __init__(self, project_id):
        self.project = EstimationProject.objects.get(pk=project_id)
        self.periods = list(
            ProjectionPeriod.objects.filter(projectid=project_id).order_by('periodnumber')
        )
        self.N = len(self.periods)
        if self.N == 0:
            raise ValueError(
                'No hay periodos. Inicializa el Plan de Obra (Paso 9) antes de consultar el PNT.'
            )
        self.settings = EstimationFinancialSettingsService.get_or_create(project_id)
        self.billing_rules = self._load_billing_rules()
        self.rollups = CostDistributionService.compute_rollups(self.project)

    def _load_billing_rules(self):
        persisted = EstimationBillingRuleService.list(self.project.estimationprojectid)
        if persisted:
            return [
                _InlineBillingRule(sequence=r.sequence, percent=r.percent, lagperiods=r.lagperiods)
                for r in persisted
            ]
        # Default implícito: 100%/lag 0
        return [_InlineBillingRule(sequence=1, percent=Decimal('1'), lagperiods=0)]

    def _apply_overrides(self, overrides):
        """Mutate self.settings / self.billing_rules in-memory only."""
        for key, value in (overrides or {}).items():
            if key in self._OVERRIDE_ALLOWLIST:
                if isinstance(value, (int, float, str)):
                    value = Decimal(str(value)) if key not in {
                        'retentionreturnperiod', 'advanceentryperiod',
                        'directpaymentlag', 'indirectpaymentlag',
                    } else int(value)
                setattr(self.settings, key, value)
        if 'billing_rules' in (overrides or {}):
            self.billing_rules = [
                _InlineBillingRule(
                    sequence=int(r['sequence']),
                    percent=Decimal(str(r['percent'])),
                    lagperiods=int(r['lagperiods']),
                )
                for r in overrides['billing_rules']
            ]

    def compute(self, overrides=None, granularity='period'):
        if granularity not in ('period', 'month'):
            raise ValueError(f"granularity must be 'period' or 'month', got {granularity!r}")
        if overrides:
            self._apply_overrides(overrides)

        # Base vectors from rollups
        produccion = list(self.rollups['sale_by_period'])
        costo_directo_neg = [-x for x in self.rollups['direct_by_period']]
        costo_indirecto_neg = [-x for x in self.rollups['indirect_by_period']]
        retiro_transv_neg = [-x for x in self.rollups['retiro_by_period']]
        retiro_util_neg = [-x for x in self.rollups['utility_by_period']]

        # ---- COBROS ----
        cobro_facturacion, cobros_fuera = self._compute_cobro_facturacion(produccion)
        anticipo_concedido = self._single_period_vector(
            self.settings.advanceamountnotax, self.settings.advanceentryperiod,
        )
        anticipo_amortizado = [
            -self.settings.advanceamortizationrate * cf for cf in cobro_facturacion
        ]
        retencion_imss = [-self.settings.imssretentionrate * cf for cf in cobro_facturacion]
        otras_retencion = [-self.settings.otherretentionrate * cf for cf in cobro_facturacion]
        devolucion = self._compute_devolucion(retencion_imss, otras_retencion)
        saldo_anticipo = self._cumsum(anticipo_amortizado)

        cobro_total = [
            anticipo_concedido[i] + cobro_facturacion[i] + anticipo_amortizado[i]
            + retencion_imss[i] + otras_retencion[i] + devolucion[i]
            for i in range(self.N)
        ]
        # NOTE: saldo_anticipo intentionally excluded (avoids double-count of amortización).

        rows = [
            _PNTRow('COBRO_TOTAL', 'Cobro Total sin IVA', 'COBROS', cobro_total, emphasis=True),
            _PNTRow('COBRO_FACTURACION', 'Cobro Facturación', 'COBROS', cobro_facturacion),
            _PNTRow('ANTICIPO_CONCEDIDO', 'Anticipo Concedido', 'COBROS', anticipo_concedido),
            _PNTRow('ANTICIPO_AMORT', 'Anticipo Amortizado', 'COBROS', anticipo_amortizado),
            _PNTRow('RET_IMSS', 'Retenciones IMSS', 'COBROS', retencion_imss),
            _PNTRow('OTRAS_RET', 'Otras Retenciones', 'COBROS', otras_retencion),
            _PNTRow('DEVOLUCION', 'Devolución Retenciones', 'COBROS', devolucion),
            _PNTRow('SALDO_ANTICIPO', 'Saldo Anticipo', 'COBROS', saldo_anticipo),
        ]

        # PAGOS, CAJA, RESULTADO will be added in subsequent tasks.

        periods_out = [
            {'label': p.periodlabel, 'startdate': p.startdate, 'enddate': p.enddate}
            for p in self.periods
        ]
        return _PNTReport(
            projectid=self.project.estimationprojectid,
            granularity=granularity,
            periods=periods_out,
            rows=rows,
            stats={
                'cobros_fuera_horizonte': cobros_fuera,
            },
            generated_at=timezone.now(),
        )

    # --- internals ---

    def _compute_cobro_facturacion(self, produccion):
        out = [ZERO] * self.N
        fuera = ZERO
        for i in range(self.N):
            if produccion[i] == ZERO:
                continue
            for rule in self.billing_rules:
                target = i + rule.lagperiods
                amount = produccion[i] * rule.percent
                if 0 <= target < self.N:
                    out[target] += amount
                else:
                    fuera += amount
        return out, fuera

    def _single_period_vector(self, amount, period_1indexed):
        out = [ZERO] * self.N
        if not amount:
            return out
        p = (period_1indexed or 1) - 1
        if 0 <= p < self.N:
            out[p] = Decimal(amount)
        return out

    def _compute_devolucion(self, imss, otras):
        out = [ZERO] * self.N
        if self.settings.retentionreturnperiod is None:
            return out
        p = self.settings.retentionreturnperiod - 1
        if 0 <= p < self.N:
            out[p] = -sum(imss) - sum(otras)
        return out

    @staticmethod
    def _cumsum(values):
        out = []
        acc = ZERO
        for v in values:
            acc += v
            out.append(acc)
        return out
