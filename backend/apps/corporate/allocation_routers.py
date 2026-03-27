"""Corporate allocation, portfolio, timeline, and simulation API routers."""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from core.permissions import require_permission, Permission

from apps.corporate.schemas import (
    CorporateAllocationSchema,
    CalculateAllocationDto,
    ApplyAllocationDto,
    PortfolioSummarySchema,
    CapacityBreakevenSchema,
    TimelineDataSchema,
    WhatIfSimulationSchema,
    CreateSimulationDto,
    SimulationResultSchema,
)
from apps.corporate.allocation_services import (
    CorporateAllocationService,
    PortfolioService,
    SimulationService,
)


# =============================================================================
# Allocation Router
# =============================================================================

allocations_router = Router(tags=["Corporate Allocations"])


@allocations_router.get("/allocations/", response=List[CorporateAllocationSchema])
@require_permission(Permission.CORPORATE_READ)
def list_allocations(
    request: HttpRequest,
    budget_id: UUID,
    year: Optional[int] = None,
):
    """List allocations for a budget."""
    return list(CorporateAllocationService.list_allocations(budget_id, request.user, year))


@allocations_router.get("/allocations/{allocation_id}/", response=CorporateAllocationSchema)
@require_permission(Permission.CORPORATE_READ)
def get_allocation(request: HttpRequest, allocation_id: UUID):
    """Get allocation detail with lines."""
    return CorporateAllocationService.get_allocation(allocation_id, request.user)


@allocations_router.post("/budgets/{budget_id}/allocations/calculate/", response={201: CorporateAllocationSchema})
@require_permission(Permission.CORPORATE_ALLOCATE)
def calculate_allocation(request: HttpRequest, budget_id: UUID, payload: CalculateAllocationDto):
    """Calculate allocation preview (creates DRAFT)."""
    allocation = CorporateAllocationService.calculate_allocation(budget_id, payload, request.user)
    return 201, CorporateAllocationService.get_allocation(allocation.allocationid, request.user)


@allocations_router.post("/allocations/{allocation_id}/apply/", response=CorporateAllocationSchema)
@require_permission(Permission.CORPORATE_ALLOCATE)
def apply_allocation(request: HttpRequest, allocation_id: UUID):
    """Apply allocation - injects amounts into C4 ImputationCodes."""
    CorporateAllocationService.apply_allocation(allocation_id, request.user)
    return CorporateAllocationService.get_allocation(allocation_id, request.user)


@allocations_router.post("/allocations/{allocation_id}/reverse/", response=CorporateAllocationSchema)
@require_permission(Permission.CORPORATE_ALLOCATE)
def reverse_allocation(request: HttpRequest, allocation_id: UUID):
    """Reverse an applied allocation."""
    CorporateAllocationService.reverse_allocation(allocation_id, request.user)
    return CorporateAllocationService.get_allocation(allocation_id, request.user)


# =============================================================================
# Portfolio Router
# =============================================================================

portfolio_router = Router(tags=["Corporate Portfolio"])


@portfolio_router.get("/portfolio/", response=PortfolioSummarySchema)
@require_permission(Permission.CORPORATE_READ)
def get_portfolio(request: HttpRequest, fiscal_year: Optional[int] = None):
    """Get multi-project portfolio with real profitability after overhead."""
    from datetime import date
    year = fiscal_year or date.today().year
    return PortfolioService.get_portfolio_summary(request.user, year)


@portfolio_router.get("/capacity/", response=CapacityBreakevenSchema)
@require_permission(Permission.CORPORATE_READ)
def get_capacity(request: HttpRequest, fiscal_year: Optional[int] = None):
    """Get capacity and break-even analysis."""
    from datetime import date
    year = fiscal_year or date.today().year
    return PortfolioService.get_capacity_breakeven(request.user, year)


@portfolio_router.get("/timeline/", response=TimelineDataSchema)
@require_permission(Permission.CORPORATE_READ)
def get_timeline(request: HttpRequest, fiscal_year: Optional[int] = None):
    """Get timeline/Gantt data for project occupation and overhead coverage."""
    from datetime import date
    year = fiscal_year or date.today().year
    return PortfolioService.get_timeline_data(request.user, year)


# =============================================================================
# Simulation Router
# =============================================================================

simulations_router = Router(tags=["Corporate Simulations"])


@simulations_router.get("/simulations/", response=List[WhatIfSimulationSchema])
@require_permission(Permission.CORPORATE_SIMULATE)
def list_simulations(request: HttpRequest):
    """List what-if simulations."""
    return list(SimulationService.list_simulations(request.user))


@simulations_router.post("/simulations/", response={201: WhatIfSimulationSchema})
@require_permission(Permission.CORPORATE_SIMULATE)
def create_simulation(request: HttpRequest, payload: CreateSimulationDto):
    """Create a new what-if simulation."""
    simulation = SimulationService.create_simulation(payload, request.user)
    return 201, simulation


@simulations_router.get("/simulations/{simulation_id}/", response=WhatIfSimulationSchema)
@require_permission(Permission.CORPORATE_SIMULATE)
def get_simulation(request: HttpRequest, simulation_id: UUID):
    """Get simulation details."""
    return SimulationService.get_simulation(simulation_id, request.user)


@simulations_router.post("/simulations/{simulation_id}/run/", response=WhatIfSimulationSchema)
@require_permission(Permission.CORPORATE_SIMULATE)
def run_simulation(request: HttpRequest, simulation_id: UUID):
    """Execute simulation and compute results."""
    return SimulationService.run_simulation(simulation_id, request.user)


@simulations_router.delete("/simulations/{simulation_id}/", response={204: None})
@require_permission(Permission.CORPORATE_SIMULATE)
def delete_simulation(request: HttpRequest, simulation_id: UUID):
    """Delete a simulation."""
    SimulationService.delete_simulation(simulation_id, request.user)
    return 204, None
