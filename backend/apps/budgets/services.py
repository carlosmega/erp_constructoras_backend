"""Budget business logic service layer."""

import calendar
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import QuerySet, Max

from apps.budgets.models import (
    CostCategory,
    CostTypeCode,
    ImputationCode,
    ImputationPeriod,
    PeriodTypeCode,
)
from apps.budgets.schemas import (
    CreateCostCategoryDto,
    UpdateCostCategoryDto,
    CreateImputationCodeDto,
    UpdateImputationCodeDto,
)
from core.exceptions import ValidationError, NotFound

# Spanish month abbreviations
MONTH_LABELS = {
    1: 'ENE', 2: 'FEB', 3: 'MAR', 4: 'ABR',
    5: 'MAY', 6: 'JUN', 7: 'JUL', 8: 'AGO',
    9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DIC',
}

# Standard categories: (code, name, costtype, sortorder)
DEFAULT_DIRECT_CATEGORIES = [
    ('P1', 'Subcontratos', CostTypeCode.DIRECT, 1),
    ('P2', 'Maquinaria', CostTypeCode.DIRECT, 2),
    ('P3', 'Mano de Obra', CostTypeCode.DIRECT, 3),
    ('P4', 'Materiales', CostTypeCode.DIRECT, 4),
    ('P5', 'Acarreos', CostTypeCode.DIRECT, 5),
    ('P6', 'Fletes', CostTypeCode.DIRECT, 6),
    ('P7', 'Combustibles', CostTypeCode.DIRECT, 7),
    ('P8', 'Madera/Ferretería/Herramienta', CostTypeCode.DIRECT, 8),
    ('P9', 'Herramienta Menor y EPP', CostTypeCode.DIRECT, 9),
    ('P10', 'Mangueras y Reparaciones', CostTypeCode.DIRECT, 10),
]

DEFAULT_INDIRECT_CATEGORIES = [
    ('C1', 'Personal', CostTypeCode.INDIRECT, 11),
    ('C2', 'Equipamiento para Personal', CostTypeCode.INDIRECT, 12),
    ('C3', 'Traslados y Hospedajes', CostTypeCode.INDIRECT, 13),
    ('C4', 'Gastos de Oficina Central', CostTypeCode.INDIRECT, 14),
    ('C5', 'Implantación en Sitio', CostTypeCode.INDIRECT, 15),
    ('C6', 'Otros Costos Operativos', CostTypeCode.INDIRECT, 16),
    ('C7', 'Fianzas/Seguros/Otros Previos', CostTypeCode.INDIRECT, 17),
    ('C8', 'Proyectos/Gestiones/Impuestos', CostTypeCode.INDIRECT, 18),
]


class CostCategoryService:
    """Service class for CostCategory business logic."""

    @staticmethod
    def list_categories(project_id: UUID, user) -> QuerySet[CostCategory]:
        """List all cost categories for a project."""
        return CostCategory.objects.filter(
            projectid=project_id
        ).select_related('createdby', 'modifiedby')

    @staticmethod
    def create_category(dto: CreateCostCategoryDto, user) -> CostCategory:
        """Create a new cost category."""
        # Validate costtype
        if dto.costtype not in [c.value for c in CostTypeCode]:
            raise ValidationError(f"Invalid cost type: {dto.costtype}")

        category = CostCategory(
            projectid_id=dto.projectid,
            costtype=dto.costtype,
            code=dto.code,
            name=dto.name,
            description=dto.description,
            sortorder=dto.sortorder or 0,
            createdby=user,
            modifiedby=user,
        )
        category.save()
        return category

    @staticmethod
    @transaction.atomic
    def seed_default_categories(project_id: UUID, user) -> list[CostCategory]:
        """Create all 18 standard categories (P1-P10 + C1-C8) for a project."""
        categories = []

        all_defaults = DEFAULT_DIRECT_CATEGORIES + DEFAULT_INDIRECT_CATEGORIES

        for code, name, costtype, sortorder in all_defaults:
            category = CostCategory(
                projectid_id=project_id,
                costtype=costtype,
                code=code,
                name=name,
                sortorder=sortorder,
                createdby=user,
                modifiedby=user,
            )
            categories.append(category)

        CostCategory.objects.bulk_create(categories)
        return categories


class ImputationCodeService:
    """Service class for ImputationCode business logic."""

    @staticmethod
    def list_codes(
        project_id: UUID,
        user,
        costtype: Optional[int] = None,
        categoryid: Optional[UUID] = None,
    ) -> QuerySet[ImputationCode]:
        """List imputation codes for a project with optional filtering."""
        queryset = ImputationCode.objects.filter(projectid=project_id)

        if costtype is not None:
            queryset = queryset.filter(costtype=costtype)
        if categoryid is not None:
            queryset = queryset.filter(categoryid=categoryid)

        return queryset.select_related(
            'categoryid', 'zoneid', 'createdby', 'modifiedby'
        )

    @staticmethod
    def get_code_by_id(code_id: UUID, user) -> ImputationCode:
        """Get an imputation code by ID."""
        try:
            return ImputationCode.objects.select_related(
                'categoryid', 'zoneid', 'createdby', 'modifiedby'
            ).get(imputationcodeid=code_id)
        except ImputationCode.DoesNotExist:
            raise NotFound(f"Imputation code with ID {code_id} not found")

    @staticmethod
    def create_code(dto: CreateImputationCodeDto, user) -> ImputationCode:
        """Create an imputation code with auto-generated code string and sequence number."""
        # Validate costtype
        if dto.costtype not in [c.value for c in CostTypeCode]:
            raise ValidationError(f"Invalid cost type: {dto.costtype}")

        # Fetch the category
        try:
            category = CostCategory.objects.get(categoryid=dto.categoryid)
        except CostCategory.DoesNotExist:
            raise ValidationError(f"Category with ID {dto.categoryid} not found")

        # Validate zone requirement
        if dto.costtype == CostTypeCode.DIRECT:
            if not dto.zoneid:
                raise ValidationError("Zone is required for direct cost imputation codes")
        else:
            if dto.zoneid:
                raise ValidationError("Zone must not be set for indirect cost imputation codes")

        # Calculate next sequence number
        if dto.costtype == CostTypeCode.DIRECT:
            # Sequence per (project, category, zone)
            max_seq = ImputationCode.objects.filter(
                projectid=dto.projectid,
                categoryid=dto.categoryid,
                zoneid=dto.zoneid,
            ).aggregate(max_seq=Max('sequencenumber'))['max_seq'] or 0
        else:
            # Sequence per (project, category)
            max_seq = ImputationCode.objects.filter(
                projectid=dto.projectid,
                categoryid=dto.categoryid,
            ).aggregate(max_seq=Max('sequencenumber'))['max_seq'] or 0

        next_seq = max_seq + 1

        # Auto-generate code string
        if dto.costtype == CostTypeCode.DIRECT:
            # Fetch zone for prefix
            from apps.projects.models import ProjectZone
            try:
                zone = ProjectZone.objects.get(zoneid=dto.zoneid)
            except ProjectZone.DoesNotExist:
                raise ValidationError(f"Zone with ID {dto.zoneid} not found")
            code_str = f"{zone.prefix}-{category.code}-{next_seq}"
        else:
            code_str = f"{category.code}-{next_seq}"

        # Compute remaining budget
        remaining = dto.totalbudget

        imputation_code = ImputationCode(
            projectid_id=dto.projectid,
            categoryid=category,
            zoneid_id=dto.zoneid,
            costtype=dto.costtype,
            code=code_str,
            sequencenumber=next_seq,
            name=dto.name,
            description=dto.description,
            estimatedsupplier=dto.estimatedsupplier,
            unitcost=dto.unitcost,
            quantity=dto.quantity,
            executionmonths=dto.executionmonths,
            totalbudget=dto.totalbudget,
            personnelname=dto.personnelname,
            personnelrole=dto.personnelrole,
            personneltype=dto.personneltype,
            monthlycost=dto.monthlycost,
            units=dto.units,
            totalspent=Decimal('0'),
            remainingbudget=remaining,
            percentused=Decimal('0'),
            createdby=user,
            modifiedby=user,
        )
        imputation_code.save()
        return imputation_code

    @staticmethod
    def update_code(code_id: UUID, dto: UpdateImputationCodeDto, user) -> ImputationCode:
        """Update an existing imputation code."""
        imputation_code = ImputationCodeService.get_code_by_id(code_id, user)

        update_fields = [
            'name', 'description', 'estimatedsupplier', 'unitcost', 'quantity',
            'executionmonths', 'totalbudget', 'personnelname', 'personnelrole',
            'personneltype', 'monthlycost', 'units', 'statecode',
        ]

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(imputation_code, field, value)

        # Recalculate remaining budget if totalbudget changed
        if dto.totalbudget is not None:
            imputation_code.remainingbudget = imputation_code.totalbudget - imputation_code.totalspent
            if imputation_code.totalbudget > 0:
                imputation_code.percentused = (
                    imputation_code.totalspent / imputation_code.totalbudget * 100
                )
            else:
                imputation_code.percentused = Decimal('0')

        imputation_code.modifiedby = user
        imputation_code.save()
        return imputation_code


class PeriodService:
    """Service class for ImputationPeriod business logic."""

    @staticmethod
    def list_periods(project_id: UUID, user) -> QuerySet[ImputationPeriod]:
        """List all periods for a project, ordered by sortorder."""
        return ImputationPeriod.objects.filter(
            projectid=project_id
        ).select_related('createdby', 'modifiedby')

    @staticmethod
    @transaction.atomic
    def initialize_periods(project_id: UUID, user) -> list[ImputationPeriod]:
        """Generate all periods from project start to contract end date."""
        from apps.projects.models import ConstructionProject

        try:
            project = ConstructionProject.objects.get(projectid=project_id)
        except ConstructionProject.DoesNotExist:
            raise NotFound(f"Project with ID {project_id} not found")

        if not project.startdate or not project.contractenddate:
            raise ValidationError("Project must have start date and contract end date to initialize periods")

        # Check if periods already exist
        existing = ImputationPeriod.objects.filter(projectid=project_id).exists()
        if existing:
            raise ValidationError("Periods already initialized for this project. Use extend instead.")

        periodtype = project.periodtype
        periods = PeriodService._generate_periods(
            project_id=project_id,
            periodtype=periodtype,
            start_date=project.startdate,
            end_date=project.contractenddate,
            start_sortorder=1,
            user=user,
        )

        ImputationPeriod.objects.bulk_create(periods)
        return periods

    @staticmethod
    @transaction.atomic
    def extend_periods(project_id: UUID, months: int, user) -> list[ImputationPeriod]:
        """Extend periods by N months beyond the current last period."""
        from apps.projects.models import ConstructionProject

        try:
            project = ConstructionProject.objects.get(projectid=project_id)
        except ConstructionProject.DoesNotExist:
            raise NotFound(f"Project with ID {project_id} not found")

        if months <= 0:
            raise ValidationError("Months must be a positive integer")

        # Get the last existing period
        last_period = ImputationPeriod.objects.filter(
            projectid=project_id
        ).order_by('-sortorder').first()

        if not last_period:
            raise ValidationError("No existing periods found. Use initialize first.")

        # Calculate new start date (day after last period end)
        new_start = last_period.enddate + relativedelta(days=1)
        new_end = new_start + relativedelta(months=months) - relativedelta(days=1)
        next_sortorder = last_period.sortorder + 1

        periods = PeriodService._generate_periods(
            project_id=project_id,
            periodtype=last_period.periodtype,
            start_date=new_start,
            end_date=new_end,
            start_sortorder=next_sortorder,
            user=user,
        )

        ImputationPeriod.objects.bulk_create(periods)
        return periods

    @staticmethod
    def close_period(period_id: UUID, user) -> ImputationPeriod:
        """Close a period (set statecode=1)."""
        try:
            period = ImputationPeriod.objects.get(periodid=period_id)
        except ImputationPeriod.DoesNotExist:
            raise NotFound(f"Period with ID {period_id} not found")

        if period.statecode == 1:
            raise ValidationError("Period is already closed")

        period.statecode = 1
        period.modifiedby = user
        period.save()
        return period

    @staticmethod
    def reopen_period(period_id: UUID, user) -> ImputationPeriod:
        """Reopen a closed period (set statecode=0)."""
        try:
            period = ImputationPeriod.objects.get(periodid=period_id)
        except ImputationPeriod.DoesNotExist:
            raise NotFound(f"Period with ID {period_id} not found")

        if period.statecode == 0:
            raise ValidationError("Period is already open")

        period.statecode = 0
        period.modifiedby = user
        period.save()
        return period

    @staticmethod
    def _generate_periods(
        project_id: UUID,
        periodtype: int,
        start_date: date,
        end_date: date,
        start_sortorder: int,
        user,
    ) -> list[ImputationPeriod]:
        """Generate period records between start_date and end_date."""
        periods = []
        sortorder = start_sortorder

        current = date(start_date.year, start_date.month, 1)
        end_month = date(end_date.year, end_date.month, 1)

        while current <= end_month:
            year = current.year
            month = current.month
            month_label = MONTH_LABELS[month]
            last_day = calendar.monthrange(year, month)[1]

            if periodtype == PeriodTypeCode.FORTNIGHTLY:
                # Q1: 1st to 15th
                periods.append(ImputationPeriod(
                    projectid_id=project_id,
                    periodtype=periodtype,
                    year=year,
                    month=month,
                    periodnumber=1,
                    label=f"{month_label} {year} Q1",
                    startdate=date(year, month, 1),
                    enddate=date(year, month, 15),
                    sortorder=sortorder,
                    createdby=user,
                    modifiedby=user,
                ))
                sortorder += 1

                # Q2: 16th to last day
                periods.append(ImputationPeriod(
                    projectid_id=project_id,
                    periodtype=periodtype,
                    year=year,
                    month=month,
                    periodnumber=2,
                    label=f"{month_label} {year} Q2",
                    startdate=date(year, month, 16),
                    enddate=date(year, month, last_day),
                    sortorder=sortorder,
                    createdby=user,
                    modifiedby=user,
                ))
                sortorder += 1

            elif periodtype == PeriodTypeCode.WEEKLY:
                # S1: 1st to 7th
                periods.append(ImputationPeriod(
                    projectid_id=project_id,
                    periodtype=periodtype,
                    year=year,
                    month=month,
                    periodnumber=1,
                    label=f"{month_label} {year} S1",
                    startdate=date(year, month, 1),
                    enddate=date(year, month, 7),
                    sortorder=sortorder,
                    createdby=user,
                    modifiedby=user,
                ))
                sortorder += 1

                # S2: 8th to 14th
                periods.append(ImputationPeriod(
                    projectid_id=project_id,
                    periodtype=periodtype,
                    year=year,
                    month=month,
                    periodnumber=2,
                    label=f"{month_label} {year} S2",
                    startdate=date(year, month, 8),
                    enddate=date(year, month, 14),
                    sortorder=sortorder,
                    createdby=user,
                    modifiedby=user,
                ))
                sortorder += 1

                # S3: 15th to 21st
                periods.append(ImputationPeriod(
                    projectid_id=project_id,
                    periodtype=periodtype,
                    year=year,
                    month=month,
                    periodnumber=3,
                    label=f"{month_label} {year} S3",
                    startdate=date(year, month, 15),
                    enddate=date(year, month, 21),
                    sortorder=sortorder,
                    createdby=user,
                    modifiedby=user,
                ))
                sortorder += 1

                # S4: 22nd to last day
                periods.append(ImputationPeriod(
                    projectid_id=project_id,
                    periodtype=periodtype,
                    year=year,
                    month=month,
                    periodnumber=4,
                    label=f"{month_label} {year} S4",
                    startdate=date(year, month, 22),
                    enddate=date(year, month, last_day),
                    sortorder=sortorder,
                    createdby=user,
                    modifiedby=user,
                ))
                sortorder += 1

            # Move to next month
            current = current + relativedelta(months=1)

        return periods
