"""
Corporate Allocation Optimizer Agent (Type 17).

Simulates different allocation methods for distributing corporate costs
to projects and recommends the fairest approach.
"""

import logging
from decimal import Decimal

from django.db.models import Sum, Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.corporate.models import CorporateBudget, CorporateBudgetLine, BudgetVersionStateCode
from apps.projects.models import ConstructionProject, ProjectStateCode
from apps.expenses.models import ProjectExpense, ExpenseStateCode

logger = logging.getLogger(__name__)


@register_agent
class CorporateAllocationOptimizerAgent(BaseAgent):
    """Simulates allocation methods and recommends the best one."""

    AGENT_TYPE = AgentTypeCode.CORPORATE_ALLOCATION

    def execute(self, *, budget_id: str, **kwargs) -> dict:
        budget = CorporateBudget.objects.get(corporatebudgetid=budget_id)

        # Get total corporate cost to allocate
        active_version = budget.versions.filter(
            statecode=BudgetVersionStateCode.ACTIVE
        ).first()

        total_to_allocate = Decimal('0')
        if active_version:
            total_to_allocate = (
                CorporateBudgetLine.objects
                .filter(versionid=active_version.versionid)
                .aggregate(total=Sum('annualamount'))['total']
                or Decimal('0')
            )

        if total_to_allocate == 0:
            return {
                'methods': [],
                'recommended_method': None,
                'recommendation_reason': 'No budget amount to allocate',
            }

        # Get active projects
        projects = ConstructionProject.objects.filter(
            statecode=ProjectStateCode.ACTIVE,
        )

        if not projects.exists():
            return {
                'methods': [],
                'recommended_method': None,
                'recommendation_reason': 'No active projects found',
            }

        project_data = []
        for p in projects:
            direct_cost = (
                ProjectExpense.objects
                .filter(
                    projectid=p.projectid,
                    statecode=ExpenseStateCode.ACTIVE,
                )
                .aggregate(total=Sum('netamount'))['total']
                or Decimal('0')
            )
            contract_amount = p.contractamount_notax or Decimal('0')
            duration = p.durationmonths or 1

            project_data.append({
                'project_id': str(p.projectid),
                'name': p.name,
                'direct_cost': direct_cost,
                'contract_amount': contract_amount,
                'duration_months': duration,
            })

        methods = []

        # Method 1: Direct cost proportion
        total_direct = sum(p['direct_cost'] for p in project_data) or Decimal('1')
        direct_results = []
        for p in project_data:
            pct = float(p['direct_cost'] / total_direct * 100) if total_direct else 0
            allocated = float(total_to_allocate * p['direct_cost'] / total_direct) if total_direct else 0
            direct_results.append({
                'project_id': p['project_id'],
                'name': p['name'],
                'allocated': round(allocated, 2),
                'pct': round(pct, 2),
            })
        fairness_direct = self._calculate_fairness(direct_results)
        methods.append({
            'method': 'direct_cost',
            'results': direct_results,
            'fairness_score': fairness_direct,
        })

        # Method 2: Contract amount proportion
        total_contract = sum(p['contract_amount'] for p in project_data) or Decimal('1')
        contract_results = []
        for p in project_data:
            pct = float(p['contract_amount'] / total_contract * 100) if total_contract else 0
            allocated = float(total_to_allocate * p['contract_amount'] / total_contract) if total_contract else 0
            contract_results.append({
                'project_id': p['project_id'],
                'name': p['name'],
                'allocated': round(allocated, 2),
                'pct': round(pct, 2),
            })
        fairness_contract = self._calculate_fairness(contract_results)
        methods.append({
            'method': 'contract_amount',
            'results': contract_results,
            'fairness_score': fairness_contract,
        })

        # Method 3: Duration proportion
        total_duration = sum(p['duration_months'] for p in project_data) or 1
        duration_results = []
        for p in project_data:
            pct = p['duration_months'] / total_duration * 100
            allocated = float(total_to_allocate) * p['duration_months'] / total_duration
            duration_results.append({
                'project_id': p['project_id'],
                'name': p['name'],
                'allocated': round(allocated, 2),
                'pct': round(pct, 2),
            })
        fairness_duration = self._calculate_fairness(duration_results)
        methods.append({
            'method': 'duration',
            'results': duration_results,
            'fairness_score': fairness_duration,
        })

        # Recommend best method (highest fairness score)
        best = max(methods, key=lambda m: m['fairness_score'])
        method_labels = {
            'direct_cost': 'Direct Cost %',
            'contract_amount': 'Contract Amount %',
            'duration': 'Duration %',
        }

        reasons = {
            'direct_cost': (
                'Direct cost allocation reflects actual project activity and '
                'proportionally distributes overhead to projects consuming more resources.'
            ),
            'contract_amount': (
                'Contract amount allocation distributes costs proportionally to '
                'project economic value, suitable when costs correlate with revenue.'
            ),
            'duration': (
                'Duration-based allocation is simplest and fairest when projects '
                'have similar resource consumption rates over time.'
            ),
        }

        result = {
            'methods': methods,
            'recommended_method': best['method'],
            'recommendation_reason': (
                f"{method_labels[best['method']]} has the highest fairness score "
                f"({best['fairness_score']:.3f}). {reasons[best['method']]}"
            ),
        }

        self._create_suggestion(
            title=f"Recommended allocation: {method_labels[best['method']]} (fairness: {best['fairness_score']:.3f})",
            description=(
                f"Analyzed {len(project_data)} active projects. "
                f"Total to allocate: ${float(total_to_allocate):,.2f}. "
                f"Best method: {method_labels[best['method']]}."
            ),
            confidence=best['fairness_score'],
            severity=SuggestionSeverity.INFO,
            suggested_action='apply_allocation',
            suggested_data=result,
        )

        return result

    @staticmethod
    def _calculate_fairness(results: list) -> float:
        """Calculate fairness score using normalized Gini coefficient.

        Returns a value between 0 and 1, where 1 is perfectly equal distribution.
        """
        n = len(results)
        if n <= 1:
            return 1.0

        percentages = sorted([r['pct'] for r in results])
        mean_pct = sum(percentages) / n
        if mean_pct == 0:
            return 1.0

        # Gini coefficient calculation
        numerator = sum(
            abs(percentages[i] - percentages[j])
            for i in range(n)
            for j in range(n)
        )
        gini = numerator / (2 * n * n * mean_pct)

        # Convert to fairness (1 - gini), where 1 = perfectly fair
        return round(1.0 - gini, 3)
