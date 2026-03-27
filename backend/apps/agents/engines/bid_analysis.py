"""
Bid Analysis Engine.

Compares a proyeccion (estimation project) against historical construction projects:
- Find similar projects by type, size
- Calculate average margin
- Risk factors (below-average pricing, missing categories)
"""

import logging
from decimal import Decimal
from typing import Any

from django.db.models import Sum

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.proyeccion.models import EstimationProject, BudgetConcept
    _PROYECCION_AVAILABLE = True
except ImportError:
    _PROYECCION_AVAILABLE = False
    EstimationProject = None
    BudgetConcept = None

try:
    from apps.projects.models import ConstructionProject
except ImportError:
    ConstructionProject = None

try:
    from apps.expenses.models import ProjectExpense
except ImportError:
    ProjectExpense = None

logger = logging.getLogger(__name__)


@register_agent
class BidAnalysisAgent(BaseAgent):
    """Compares a proyeccion against historical projects for bid risk analysis."""

    AGENT_TYPE = AgentTypeCode.BID_ANALYSIS

    def execute(self, proyeccion_id: str = None, **kwargs) -> Any:
        if not proyeccion_id:
            raise ValueError("proyeccion_id is required")

        if not _PROYECCION_AVAILABLE:
            raise RuntimeError("Proyeccion models not available")
        if ConstructionProject is None:
            raise RuntimeError("ConstructionProject model not available")

        # ---- Fetch proyeccion ----
        try:
            proyeccion = EstimationProject.objects.get(
                estimationprojectid=proyeccion_id
            )
        except EstimationProject.DoesNotExist:
            raise ValueError(f"Proyeccion {proyeccion_id} not found")

        # Calculate total estimated amount from budget concepts
        total_estimated = float(
            BudgetConcept.objects.filter(
                projectid=proyeccion
            ).aggregate(total=Sum('totalamount'))['total'] or Decimal('0')
        )

        # If no concepts, fall back to estimatedcontractamount
        if total_estimated == 0:
            total_estimated = float(proyeccion.estimatedcontractamount or 0)

        # ---- Find comparable projects ----
        comparable_qs = ConstructionProject.objects.all()

        # Filter by same project type if available
        if hasattr(proyeccion, 'projecttype') and proyeccion.projecttype is not None:
            comparable_qs = comparable_qs.filter(
                projecttype=proyeccion.projecttype
            )

        # Also try to find projects in similar size range (50%-200% of estimated)
        if total_estimated > 0:
            lower = Decimal(str(total_estimated * 0.5))
            upper = Decimal(str(total_estimated * 2.0))
            size_filtered = comparable_qs.filter(
                contractamount_notax__gte=lower,
                contractamount_notax__lte=upper,
            )
            # If we find at least 2, use the size filter
            if size_filtered.count() >= 2:
                comparable_qs = size_filtered

        comparable_projects = []
        margins = []

        for project in comparable_qs.order_by('-createdon')[:20]:
            contract_amount = float(project.contractamount_notax or 0)
            if contract_amount == 0:
                continue

            # Calculate actual cost from expenses
            actual_cost = 0.0
            if ProjectExpense is not None:
                expense_total = ProjectExpense.objects.filter(
                    projectid=project
                ).aggregate(total=Sum('totalamount'))['total']
                actual_cost = float(expense_total or 0)

            if actual_cost > 0:
                margin_pct = round(
                    (contract_amount - actual_cost) / contract_amount * 100, 2
                )
            else:
                margin_pct = None  # No expense data

            comp = {
                'project_id': str(project.projectid),
                'name': project.name,
                'contract_amount': contract_amount,
                'actual_cost': actual_cost,
                'margin_pct': margin_pct,
            }
            comparable_projects.append(comp)
            if margin_pct is not None:
                margins.append(margin_pct)

        # ---- Margin analysis ----
        margin_analysis = {}
        if margins:
            avg_margin = round(sum(margins) / len(margins), 2)
            min_margin = min(margins)
            max_margin = max(margins)
            margin_analysis = {
                'avg_margin_pct': avg_margin,
                'min_margin_pct': min_margin,
                'max_margin_pct': max_margin,
                'sample_size': len(margins),
            }
        else:
            avg_margin = None
            margin_analysis = {
                'avg_margin_pct': None,
                'min_margin_pct': None,
                'max_margin_pct': None,
                'sample_size': 0,
            }

        # ---- Risk factors ----
        risk_factors = []
        risk_score = 0  # 0-100, higher = riskier

        # Below-average pricing
        if avg_margin is not None and total_estimated > 0:
            # Compare estimated margin implied by pricing vs historical
            if avg_margin < 10:
                risk_factors.append(
                    "Historical margins are below 10% for similar projects."
                )
                risk_score += 20

        # No comparable projects
        if len(comparable_projects) == 0:
            risk_factors.append("No comparable projects found for benchmarking.")
            risk_score += 30

        # Low concept count check
        concept_count = BudgetConcept.objects.filter(projectid=proyeccion).count()
        if concept_count < 5:
            risk_factors.append(
                f"Only {concept_count} budget concept(s) defined. May be incomplete."
            )
            risk_score += 15

        # Missing estimated contract amount
        if total_estimated == 0:
            risk_factors.append("Total estimated amount is zero. Budget not yet defined.")
            risk_score += 25

        # Check for zero-price concepts
        zero_price_count = BudgetConcept.objects.filter(
            projectid=proyeccion,
            unitprice=0,
        ).count()
        if zero_price_count > 0:
            risk_factors.append(
                f"{zero_price_count} concept(s) have zero unit price."
            )
            risk_score += 10

        risk_score = min(100, risk_score)

        # ---- Recommendation ----
        if risk_score >= 60:
            recommendation = "High risk bid. Thoroughly review pricing and add missing data."
        elif risk_score >= 30:
            recommendation = "Moderate risk. Review flagged items before submission."
        else:
            recommendation = "Low risk. Bid appears well-supported by historical data."

        # Create suggestion
        if risk_score >= 30:
            severity = (
                SuggestionSeverity.CRITICAL if risk_score >= 60
                else SuggestionSeverity.WARNING
            )
            self._create_suggestion(
                title=f"Bid risk score: {risk_score}/100 for {proyeccion.name}",
                description=(
                    f"{len(risk_factors)} risk factor(s) identified. "
                    f"{recommendation}"
                ),
                confidence=0.75,
                severity=severity,
                suggested_action='review_bid',
                suggested_data={
                    'proyeccion_id': str(proyeccion_id),
                    'risk_score': risk_score,
                    'risk_factors': risk_factors,
                },
                relatedentityid=proyeccion.estimationprojectid,
                relatedentitytype='estimationproject',
            )

        return {
            'proyeccion_id': str(proyeccion_id),
            'total_estimated': total_estimated,
            'comparable_projects': comparable_projects,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'margin_analysis': margin_analysis,
            'recommendation': recommendation,
        }
