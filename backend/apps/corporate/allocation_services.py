"""Corporate allocation, portfolio, and simulation services."""

from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from typing import Optional, List
from collections import defaultdict

from django.db import transaction, models
from django.utils import timezone

from apps.corporate.models import (
    CorporateBudget,
    CorporateBudgetLine,
    CorporateAllocation,
    CorporateAllocationLine,
    WhatIfSimulation,
    BudgetStateCode,
    BudgetVersionStateCode,
    ProrationMethodCode,
    AllocationStateCode,
    SimulationStateCode,
    CorporateExpenseCategoryCode,
)
from apps.projects.models import ConstructionProject
from apps.budgets.models import CostCategory, ImputationCode, CostTypeCode
from core.exceptions import ValidationError, NotFound
from core.permissions import filter_by_ownership


MONTH_FIELDS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
MONTH_LABELS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


class CorporateAllocationService:
    """Core proration engine for distributing corporate costs to projects."""

    @staticmethod
    def get_active_projects(year: int, month: int):
        """Get projects active during a given month."""
        from datetime import date as dt_date
        month_start = dt_date(year, month, 1)
        if month == 12:
            month_end = dt_date(year + 1, 1, 1)
        else:
            month_end = dt_date(year, month + 1, 1)

        return ConstructionProject.objects.filter(
            statecode=1,  # Active
            startdate__lt=month_end,
            contractenddate__gte=month_start,
        ).select_related('ownerid')

    @staticmethod
    def _get_monthly_budget(budget, month: int):
        """Get the total budgeted amount for a specific month from active version."""
        active_version = budget.versions.filter(statecode=BudgetVersionStateCode.ACTIVE).first()
        if not active_version:
            return Decimal('0')

        field_name = MONTH_FIELDS[month - 1]
        total = active_version.lines.aggregate(
            total=models.Sum(field_name)
        )['total'] or Decimal('0')
        return total

    @staticmethod
    def _calculate_weights(projects, method: int, manual_weights: dict = None):
        """Calculate weight for each project based on proration method."""
        weights = []

        if method == ProrationMethodCode.DIRECT_COST:
            # Sum P1-P10 (direct cost) totalbudget per project
            for project in projects:
                direct_total = ImputationCode.objects.filter(
                    projectid=project,
                    costtype=CostTypeCode.DIRECT,
                ).aggregate(total=models.Sum('totalbudget'))['total'] or Decimal('0')
                weights.append((project, direct_total))

        elif method == ProrationMethodCode.CONTRACT_AMOUNT:
            for project in projects:
                weights.append((project, project.contractamount_notax or Decimal('0')))

        elif method == ProrationMethodCode.DURATION:
            for project in projects:
                weights.append((project, Decimal(str(project.durationmonths or 1))))

        elif method == ProrationMethodCode.MANUAL:
            if not manual_weights:
                raise ValidationError("Manual weights are required for manual proration method")
            for project in projects:
                pct = manual_weights.get(str(project.projectid), Decimal('0'))
                weights.append((project, Decimal(str(pct))))

        elif method == ProrationMethodCode.HYBRID:
            # Each project can have its own method specified in manual_weights
            # Format: {project_id: {"method": int, "value": float}}
            if not manual_weights:
                raise ValidationError("Manual weights are required for hybrid proration method")
            for project in projects:
                config = manual_weights.get(str(project.projectid), {})
                value = Decimal(str(config.get('value', 0)))
                weights.append((project, value))

        total_weight = sum(w[1] for w in weights)
        return weights, total_weight

    @staticmethod
    @transaction.atomic
    def calculate_allocation(budget_id: UUID, dto, user):
        """Calculate allocation (preview). Creates DRAFT allocation."""
        try:
            budget = CorporateBudget.objects.prefetch_related('versions__lines').get(
                corporatebudgetid=budget_id
            )
        except CorporateBudget.DoesNotExist:
            raise NotFound(f"Corporate budget {budget_id} not found")

        if budget.statecode != BudgetStateCode.APPROVED:
            raise ValidationError("Budget must be approved before calculating allocations")

        # Check if allocation already exists for this month
        existing = CorporateAllocation.objects.filter(
            corporatebudgetid=budget,
            year=dto.year,
            month=dto.month,
            statecode__in=[AllocationStateCode.DRAFT, AllocationStateCode.APPLIED],
        ).first()
        if existing:
            raise ValidationError(
                f"An allocation for {dto.year}/{dto.month} already exists (state: {existing.get_statecode_display()}). "
                f"Reverse it first before creating a new one."
            )

        # Get active projects for the month
        projects = list(CorporateAllocationService.get_active_projects(dto.year, dto.month))
        if not projects:
            raise ValidationError(f"No active projects found for {dto.year}/{dto.month}")

        # Get monthly budget amount
        monthly_budget = CorporateAllocationService._get_monthly_budget(budget, dto.month)

        # Calculate weights
        weights, total_weight = CorporateAllocationService._calculate_weights(
            projects, dto.prorationmethod, dto.manualweights
        )

        # Create allocation
        allocation = CorporateAllocation(
            corporatebudgetid=budget,
            year=dto.year,
            month=dto.month,
            prorationmethod=dto.prorationmethod,
            totalamountallocated=Decimal('0'),
            unallocatedamount=monthly_budget,
            statecode=AllocationStateCode.DRAFT,
            createdby=user,
            modifiedby=user,
        )
        allocation.save()

        # Create allocation lines
        total_allocated = Decimal('0')
        for project, weight_value in weights:
            if total_weight > 0:
                pct = (weight_value / total_weight) * 100
                amount = (weight_value / total_weight) * monthly_budget
            else:
                pct = Decimal('0')
                amount = Decimal('0')

            amount = amount.quantize(Decimal('0.01'))
            total_allocated += amount

            CorporateAllocationLine(
                allocationid=allocation,
                projectid=project,
                prorationmethod=dto.prorationmethod,
                weightvalue=weight_value,
                weightpercent=pct,
                allocatedamount=amount,
                createdby=user,
                modifiedby=user,
            ).save()

        allocation.totalamountallocated = total_allocated
        allocation.unallocatedamount = monthly_budget - total_allocated
        allocation.save()

        return allocation

    @staticmethod
    def list_allocations(budget_id: UUID, user, year: Optional[int] = None):
        qs = CorporateAllocation.objects.filter(corporatebudgetid=budget_id)
        if year is not None:
            qs = qs.filter(year=year)
        return qs.prefetch_related(
            models.Prefetch('lines', queryset=CorporateAllocationLine.objects.select_related('projectid'))
        )

    @staticmethod
    def get_allocation(allocation_id: UUID, user):
        try:
            return CorporateAllocation.objects.prefetch_related(
                models.Prefetch('lines', queryset=CorporateAllocationLine.objects.select_related('projectid'))
            ).get(allocationid=allocation_id)
        except CorporateAllocation.DoesNotExist:
            raise NotFound(f"Allocation {allocation_id} not found")

    @staticmethod
    @transaction.atomic
    def apply_allocation(allocation_id: UUID, user):
        """Apply allocation: inject amounts into C4 ImputationCodes."""
        allocation = CorporateAllocationService.get_allocation(allocation_id, user)

        if allocation.statecode != AllocationStateCode.DRAFT:
            raise ValidationError("Only DRAFT allocations can be applied")

        for line in allocation.lines.all():
            project = line.projectid

            # Find C4 cost category for this project
            c4_category = CostCategory.objects.filter(
                projectid=project,
                code='C4',
            ).first()

            if not c4_category:
                # Create C4 category if it doesn't exist
                c4_category = CostCategory(
                    projectid=project,
                    costtype=CostTypeCode.INDIRECT,
                    code='C4',
                    name='Gastos de Oficina Central',
                    description='Prorrateo automático de gastos corporativos',
                    sortorder=14,
                    createdby=user,
                    modifiedby=user,
                )
                c4_category.save()

            # Find or create ImputationCode for this month
            code_label = f"C4-CORP-{allocation.month}"
            imputation_code, created = ImputationCode.objects.get_or_create(
                projectid=project,
                code=code_label,
                defaults={
                    'categoryid': c4_category,
                    'costtype': CostTypeCode.INDIRECT,
                    'sequencenumber': allocation.month,
                    'name': f"Gastos Corporativos - {MONTH_LABELS[allocation.month - 1]} {allocation.year}",
                    'totalbudget': line.allocatedamount,
                    'createdby': user,
                    'modifiedby': user,
                }
            )

            if not created:
                imputation_code.totalbudget = line.allocatedamount
                imputation_code.modifiedby = user
                imputation_code.save()

            # Link allocation line to imputation code
            line.imputationcodeid = imputation_code
            line.save()

        allocation.statecode = AllocationStateCode.APPLIED
        allocation.appliedon = timezone.now()
        allocation.modifiedby = user
        allocation.save()
        return allocation

    @staticmethod
    @transaction.atomic
    def reverse_allocation(allocation_id: UUID, user):
        """Reverse an applied allocation: remove amounts from C4 ImputationCodes."""
        allocation = CorporateAllocationService.get_allocation(allocation_id, user)

        if allocation.statecode != AllocationStateCode.APPLIED:
            raise ValidationError("Only APPLIED allocations can be reversed")

        for line in allocation.lines.all():
            if line.imputationcodeid:
                imputation_code = line.imputationcodeid
                imputation_code.totalbudget = max(
                    Decimal('0'),
                    imputation_code.totalbudget - line.allocatedamount
                )
                imputation_code.modifiedby = user
                imputation_code.save()

                line.imputationcodeid = None
                line.save()

        allocation.statecode = AllocationStateCode.REVERSED
        allocation.modifiedby = user
        allocation.save()
        return allocation


class PortfolioService:
    """Portfolio analytics: multi-project profitability, capacity, timeline."""

    @staticmethod
    def get_portfolio_summary(user, fiscal_year: int):
        """HU-C05: Multi-project profitability including corporate overhead."""
        projects = ConstructionProject.objects.filter(
            statecode=1,  # Active
        ).select_related('ownerid')
        projects = filter_by_ownership(projects, user)

        # Get corporate budget for the year
        budget = CorporateBudget.objects.filter(
            fiscalyear=fiscal_year,
            statecode=BudgetStateCode.APPROVED,
        ).first()
        corporate_annual = float(budget.totalbudget) if budget else 0

        project_data = []
        total_contract = Decimal('0')
        total_direct = Decimal('0')
        total_indirect_campo = Decimal('0')
        total_overhead = Decimal('0')

        for project in projects:
            contract = project.contractamount_notax or Decimal('0')

            # Sum direct costs (P1-P10)
            direct = ImputationCode.objects.filter(
                projectid=project,
                costtype=CostTypeCode.DIRECT,
            ).aggregate(total=models.Sum('totalbudget'))['total'] or Decimal('0')

            # Sum indirect costs excluding C4 (C1-C3, C5-C8)
            indirect_campo = ImputationCode.objects.filter(
                projectid=project,
                costtype=CostTypeCode.INDIRECT,
            ).exclude(
                categoryid__code='C4'
            ).aggregate(total=models.Sum('totalbudget'))['total'] or Decimal('0')

            # Sum C4 (corporate overhead allocated)
            overhead = ImputationCode.objects.filter(
                projectid=project,
                costtype=CostTypeCode.INDIRECT,
                categoryid__code='C4',
            ).aggregate(total=models.Sum('totalbudget'))['total'] or Decimal('0')

            margin_before = contract - direct - indirect_campo
            margin_after = margin_before - overhead
            margin_pct = (margin_after / contract * 100) if contract else Decimal('0')

            project_data.append({
                'projectid': str(project.projectid),
                'projectnumber': project.projectnumber,
                'name': project.name,
                'statecode': project.statecode,
                'startdate': str(project.startdate) if project.startdate else None,
                'contractenddate': str(project.contractenddate) if project.contractenddate else None,
                'durationmonths': project.durationmonths or 0,
                'contractamount': contract,
                'directcosts': direct,
                'indirectcostscampo': indirect_campo,
                'corporateoverhead': overhead,
                'marginbeforeoverhead': margin_before,
                'marginafteroverhead': margin_after,
                'marginpercent': margin_pct,
            })

            total_contract += contract
            total_direct += direct
            total_indirect_campo += indirect_campo
            total_overhead += overhead

        total_margin = total_contract - total_direct - total_indirect_campo - total_overhead
        total_margin_pct = (total_margin / total_contract * 100) if total_contract else Decimal('0')

        return {
            'projects': project_data,
            'totalcontractamount': total_contract,
            'totaldirectcosts': total_direct,
            'totalindirectcostscampo': total_indirect_campo,
            'totalcorporateoverhead': total_overhead,
            'totalmargin': total_margin,
            'totalmarginpercent': total_margin_pct,
            'corporatebudgetannual': Decimal(str(corporate_annual)),
            'unallocatedoverhead': Decimal(str(corporate_annual)) - total_overhead,
        }

    @staticmethod
    def get_capacity_breakeven(user, fiscal_year: int):
        """HU-C04: Capacity and break-even analysis."""
        budget = CorporateBudget.objects.filter(
            fiscalyear=fiscal_year,
            statecode=BudgetStateCode.APPROVED,
        ).prefetch_related('versions__lines').first()

        corporate_annual = Decimal('0')
        if budget:
            corporate_annual = budget.totalbudget

        projects = ConstructionProject.objects.filter(statecode=1)
        projects = filter_by_ownership(projects, user)

        total_cd = Decimal('0')
        for project in projects:
            direct = ImputationCode.objects.filter(
                projectid=project,
                costtype=CostTypeCode.DIRECT,
            ).aggregate(total=models.Sum('totalbudget'))['total'] or Decimal('0')
            total_cd += direct

        # Estimate capacity based on historical data or a multiplier
        # Rule: capacity = corporate_budget / avg_overhead_pct (assume ~12% overhead)
        avg_overhead_pct = Decimal('0.12')
        estimated_capacity = (corporate_annual / avg_overhead_pct) if avg_overhead_pct else Decimal('0')

        # Break-even: minimum CD to cover corporate costs
        breakeven = (corporate_annual / avg_overhead_pct) if avg_overhead_pct else Decimal('0')

        coverage_pct = (total_cd / estimated_capacity * 100) if estimated_capacity else Decimal('0')
        available = estimated_capacity - total_cd
        idle_pct = Decimal('100') - coverage_pct if coverage_pct <= 100 else Decimal('0')

        # Monthly coverage
        months_coverage = []
        for m in range(1, 13):
            active_projects = CorporateAllocationService.get_active_projects(fiscal_year, m)
            active_count = active_projects.count()

            monthly_budgeted = Decimal('0')
            if budget:
                monthly_budgeted = CorporateAllocationService._get_monthly_budget(budget, m)

            # Sum allocated for this month
            allocated = CorporateAllocationLine.objects.filter(
                allocationid__corporatebudgetid=budget,
                allocationid__year=fiscal_year,
                allocationid__month=m,
                allocationid__statecode=AllocationStateCode.APPLIED,
            ).aggregate(total=models.Sum('allocatedamount'))['total'] or Decimal('0')

            month_coverage_pct = (allocated / monthly_budgeted * 100) if monthly_budgeted else Decimal('0')

            months_coverage.append({
                'month': m,
                'year': fiscal_year,
                'label': MONTH_LABELS[m - 1],
                'activeprojects': active_count,
                'coveragepercent': month_coverage_pct,
                'overheadbudgeted': monthly_budgeted,
                'overheadallocated': allocated,
            })

        return {
            'corporatebudgetannual': corporate_annual,
            'totalcontractedcd': total_cd,
            'estimatedcapacity': estimated_capacity,
            'breakevenpointcd': breakeven,
            'currentcoveragepercent': coverage_pct,
            'availablecapacity': available,
            'idlecapacitypercent': idle_pct,
            'activeprojectcount': projects.count(),
            'monthscoverage': months_coverage,
        }

    @staticmethod
    def get_timeline_data(user, fiscal_year: int):
        """HU-C06: Timeline/Gantt data for project occupation and overhead coverage."""
        projects = ConstructionProject.objects.filter(
            statecode=1,
        ).select_related('ownerid')
        projects = filter_by_ownership(projects, user)

        budget = CorporateBudget.objects.filter(
            fiscalyear=fiscal_year,
            statecode=BudgetStateCode.APPROVED,
        ).prefetch_related('versions__lines').first()

        timeline_projects = []
        for project in projects:
            overhead = CorporateAllocationLine.objects.filter(
                projectid=project,
                allocationid__year=fiscal_year,
                allocationid__statecode=AllocationStateCode.APPLIED,
            ).aggregate(total=models.Sum('allocatedamount'))['total'] or Decimal('0')

            timeline_projects.append({
                'projectid': str(project.projectid),
                'projectnumber': project.projectnumber,
                'name': project.name,
                'startdate': str(project.startdate) if project.startdate else '',
                'contractenddate': str(project.contractenddate) if project.contractenddate else '',
                'allocatedoverhead': overhead,
            })

        months = []
        for m in range(1, 13):
            from datetime import date as dt_date
            month_start = dt_date(fiscal_year, m, 1)
            if m == 12:
                month_end = dt_date(fiscal_year + 1, 1, 1)
            else:
                month_end = dt_date(fiscal_year, m + 1, 1)

            active_in_month = [
                p for p in timeline_projects
                if p['startdate'] and p['contractenddate']
                and p['startdate'] < str(month_end)
                and p['contractenddate'] >= str(month_start)
            ]

            monthly_budgeted = Decimal('0')
            if budget:
                monthly_budgeted = CorporateAllocationService._get_monthly_budget(budget, m)

            allocated = Decimal('0')
            if budget:
                allocated = CorporateAllocationLine.objects.filter(
                    allocationid__corporatebudgetid=budget,
                    allocationid__year=fiscal_year,
                    allocationid__month=m,
                    allocationid__statecode=AllocationStateCode.APPLIED,
                ).aggregate(total=models.Sum('allocatedamount'))['total'] or Decimal('0')

            coverage = (allocated / monthly_budgeted * 100) if monthly_budgeted else Decimal('0')

            months.append({
                'month': m,
                'year': fiscal_year,
                'label': MONTH_LABELS[m - 1],
                'projects': active_in_month,
                'overheadbudgeted': monthly_budgeted,
                'overheadallocated': allocated,
                'coveragepercent': coverage,
            })

        return {
            'months': months,
            'projects': timeline_projects,
        }


class SimulationService:
    """What-if simulation for evaluating new project impact on corporate overhead."""

    @staticmethod
    def list_simulations(user):
        qs = WhatIfSimulation.objects.all()
        qs = filter_by_ownership(qs, user)
        return qs.select_related('ownerid')

    @staticmethod
    def get_simulation(simulation_id: UUID, user):
        try:
            return WhatIfSimulation.objects.select_related('ownerid').get(
                simulationid=simulation_id
            )
        except WhatIfSimulation.DoesNotExist:
            raise NotFound(f"Simulation {simulation_id} not found")

    @staticmethod
    def create_simulation(dto, user):
        simulation = WhatIfSimulation(
            name=dto.name,
            description=dto.description,
            fiscalyear=dto.fiscalyear,
            corporatebudgetid_id=dto.corporatebudgetid if dto.corporatebudgetid else None,
            parameters=dto.parameters,
            results={},
            statecode=SimulationStateCode.ACTIVE,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        simulation.save()
        return simulation

    @staticmethod
    def run_simulation(simulation_id: UUID, user):
        """Execute the what-if simulation and store results."""
        simulation = SimulationService.get_simulation(simulation_id, user)
        params = simulation.parameters

        proration_method = params.get('prorationmethod', ProrationMethodCode.DIRECT_COST)
        hypothetical_projects = params.get('hypotheticalprojects', [])
        base_project_ids = params.get('baseprojects', [])

        # Get current active projects
        if base_project_ids:
            current_projects = ConstructionProject.objects.filter(
                projectid__in=base_project_ids, statecode=1
            )
        else:
            current_projects = ConstructionProject.objects.filter(statecode=1)

        # Get corporate budget
        budget = CorporateBudget.objects.filter(
            fiscalyear=simulation.fiscalyear,
            statecode=BudgetStateCode.APPROVED,
        ).first()
        monthly_budget = budget.monthlypromedio if budget else Decimal('0')

        # --- CURRENT SCENARIO ---
        current_weights = []
        for project in current_projects:
            if proration_method == ProrationMethodCode.DIRECT_COST:
                weight = ImputationCode.objects.filter(
                    projectid=project, costtype=CostTypeCode.DIRECT,
                ).aggregate(total=models.Sum('totalbudget'))['total'] or Decimal('0')
            elif proration_method == ProrationMethodCode.CONTRACT_AMOUNT:
                weight = project.contractamount_notax or Decimal('0')
            else:
                weight = Decimal(str(project.durationmonths or 1))
            current_weights.append({
                'projectid': str(project.projectid),
                'name': project.name,
                'ishypothetical': False,
                'weight': float(weight),
            })

        current_total_weight = sum(w['weight'] for w in current_weights)

        current_results = []
        for w in current_weights:
            pct = (w['weight'] / current_total_weight * 100) if current_total_weight else 0
            allocated = float(monthly_budget) * pct / 100
            current_results.append({
                'projectid': w['projectid'],
                'name': w['name'],
                'ishypothetical': False,
                'weightpercent': round(pct, 2),
                'allocatedamount': round(allocated, 2),
                'marginimpact': 0,
            })

        current_coverage = (sum(r['allocatedamount'] for r in current_results) / float(monthly_budget) * 100) if monthly_budget else 0

        # --- NEW SCENARIO (with hypothetical projects) ---
        new_weights = list(current_weights)
        for hp in hypothetical_projects:
            if proration_method == ProrationMethodCode.DIRECT_COST:
                weight = hp.get('directcost', 0)
            elif proration_method == ProrationMethodCode.CONTRACT_AMOUNT:
                weight = hp.get('contractamount', 0)
            else:
                weight = hp.get('durationmonths', 1)
            new_weights.append({
                'projectid': None,
                'name': hp.get('name', 'New Project'),
                'ishypothetical': True,
                'weight': float(weight),
            })

        new_total_weight = sum(w['weight'] for w in new_weights)

        new_results = []
        for w in new_weights:
            pct = (w['weight'] / new_total_weight * 100) if new_total_weight else 0
            allocated = float(monthly_budget) * pct / 100

            # Calculate margin impact for existing projects
            margin_impact = 0
            if not w['ishypothetical'] and current_total_weight:
                old_pct = (w['weight'] / current_total_weight * 100)
                old_allocated = float(monthly_budget) * old_pct / 100
                margin_impact = round(old_allocated - allocated, 2)  # positive = saves money

            new_results.append({
                'projectid': w['projectid'],
                'name': w['name'],
                'ishypothetical': w['ishypothetical'],
                'weightpercent': round(pct, 2),
                'allocatedamount': round(allocated, 2),
                'marginimpact': margin_impact,
            })

        new_coverage = (sum(r['allocatedamount'] for r in new_results) / float(monthly_budget) * 100) if monthly_budget else 0

        results = {
            'currentscenario': {
                'projects': current_results,
                'totaloverhead': float(monthly_budget),
                'coveragepercent': round(current_coverage, 2),
                'unallocated': round(float(monthly_budget) - sum(r['allocatedamount'] for r in current_results), 2),
            },
            'newscenario': {
                'projects': new_results,
                'totaloverhead': float(monthly_budget),
                'coveragepercent': round(new_coverage, 2),
                'unallocated': round(float(monthly_budget) - sum(r['allocatedamount'] for r in new_results), 2),
            },
        }

        simulation.results = results
        simulation.modifiedby = user
        simulation.save()
        return simulation

    @staticmethod
    def delete_simulation(simulation_id: UUID, user):
        simulation = SimulationService.get_simulation(simulation_id, user)
        simulation.delete()
