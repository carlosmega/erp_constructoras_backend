"""
Expense Classification Engine.

Suggests ImputationCode for unclassified expenses based on:
- Factor 1: Same supplier RFC -> same code historically (weight 10 per occurrence)
- Factor 2: Document type mapping (PAYROLL->C1, INVOICE->P4/P1/P3)
- Factor 3: Amount range similarity
Returns top 3 suggestions with confidence scores.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional

from django.db.models import Count, Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.expenses.models import (
        ProjectExpense,
        ClassificationLog,
        ClassificationStatusCode,
        DocumentTypeCode,
        ExpenseStateCode,
    )
except ImportError:
    ProjectExpense = None
    ClassificationLog = None
    ClassificationStatusCode = None
    DocumentTypeCode = None
    ExpenseStateCode = None

try:
    from apps.budgets.models import ImputationCode, CostCategory
except ImportError:
    ImputationCode = None
    CostCategory = None

logger = logging.getLogger(__name__)

# Document type to category code prefix mapping
DOCTYPE_CATEGORY_MAP = {
    3: ['C1'],           # PAYROLL -> C1 (Personnel)
    0: ['P4', 'P1', 'P3'],  # INVOICE -> Materials, Subcontracts, Equipment
    1: ['P4', 'P1'],     # CREDIT_NOTE -> same as invoice
    2: ['P4', 'P1'],     # NO_INVOICE_EXPENSE
    4: ['P4', 'P1'],     # PROVISION
}


@register_agent
class ExpenseClassificationAgent(BaseAgent):
    """Suggests imputation codes for unclassified project expenses."""

    AGENT_TYPE = AgentTypeCode.EXPENSE_CLASSIFICATION

    def execute(
        self,
        project_id: str = '',
        expense_ids: Optional[list] = None,
        **kwargs,
    ) -> Any:
        if not project_id:
            raise ValueError("project_id is required")
        if ProjectExpense is None or ImputationCode is None:
            raise RuntimeError("Required models not available")

        # Load unclassified expenses
        qs = ProjectExpense.objects.filter(
            projectid=project_id,
            statecode=ExpenseStateCode.ACTIVE,
            classificationstatus=ClassificationStatusCode.PENDING,
        ).select_related('imputationcodeid', 'periodid')

        if expense_ids:
            qs = qs.filter(expenseid__in=expense_ids)

        # Load all imputation codes for the project
        all_codes = list(
            ImputationCode.objects.filter(
                projectid=project_id,
            ).select_related('categoryid', 'zoneid')
        )
        code_map = {str(c.imputationcodeid): c for c in all_codes}

        # Build historical classification index (supplier RFC -> code frequency)
        historical_expenses = ProjectExpense.objects.filter(
            projectid=project_id,
            statecode=ExpenseStateCode.ACTIVE,
            classificationstatus=ClassificationStatusCode.CLASSIFIED,
            imputationcodeid__isnull=False,
        ).values('supplierrfc', 'imputationcodeid').annotate(
            freq=Count('expenseid')
        )

        rfc_code_freq = defaultdict(lambda: defaultdict(int))
        for row in historical_expenses:
            if row['supplierrfc']:
                rfc_code_freq[row['supplierrfc']][str(row['imputationcodeid'])] += row['freq']

        # Auto-classify confidence threshold
        auto_threshold = self.config.get('auto_classify_threshold', 0.85)

        results = []
        for expense in qs:
            scores = defaultdict(float)
            reasons = defaultdict(list)

            # Factor 1: Same supplier RFC historical match
            if expense.supplierrfc and expense.supplierrfc in rfc_code_freq:
                rfc_freqs = rfc_code_freq[expense.supplierrfc]
                weight_per_occurrence = 10
                for code_id, freq in rfc_freqs.items():
                    scores[code_id] += freq * weight_per_occurrence
                    reasons[code_id].append(
                        f"Same RFC '{expense.supplierrfc}' classified here {freq}x"
                    )

            # Factor 2: Document type mapping
            doctype = expense.documenttype
            preferred_prefixes = DOCTYPE_CATEGORY_MAP.get(doctype, [])
            for code in all_codes:
                cat_code = code.categoryid.code if code.categoryid else ''
                if cat_code in preferred_prefixes:
                    scores[str(code.imputationcodeid)] += 5
                    reasons[str(code.imputationcodeid)].append(
                        f"Document type matches category {cat_code}"
                    )

            # Factor 3: Amount range similarity
            expense_amount = float(expense.subtotal or 0)
            if expense_amount > 0:
                classified_in_range = ProjectExpense.objects.filter(
                    projectid=project_id,
                    statecode=ExpenseStateCode.ACTIVE,
                    classificationstatus=ClassificationStatusCode.CLASSIFIED,
                    imputationcodeid__isnull=False,
                    subtotal__gte=Decimal(str(expense_amount * 0.5)),
                    subtotal__lte=Decimal(str(expense_amount * 2.0)),
                ).values('imputationcodeid').annotate(cnt=Count('expenseid'))

                for row in classified_in_range:
                    code_id = str(row['imputationcodeid'])
                    scores[code_id] += row['cnt'] * 2
                    reasons[code_id].append(
                        f"Similar amount range ({row['cnt']} matches)"
                    )

            # Rank and pick top 3
            if not scores:
                results.append({
                    'expenseid': str(expense.expenseid),
                    'suggestions': [],
                    'auto_classify': False,
                })
                continue

            max_score = max(scores.values()) if scores else 1
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]

            suggestions = []
            for code_id, raw_score in ranked:
                confidence = round(min(raw_score / max(max_score * 1.2, 1), 1.0), 3)
                code_obj = code_map.get(code_id)
                if code_obj:
                    suggestions.append({
                        'imputationcodeid': code_id,
                        'code': code_obj.code,
                        'name': code_obj.name,
                        'confidence': confidence,
                        'reason': '; '.join(reasons.get(code_id, [])),
                    })

            # Determine auto-classify eligibility
            auto_classify = (
                len(suggestions) > 0
                and suggestions[0]['confidence'] >= auto_threshold
            )

            # Create suggestion for the top pick
            if suggestions:
                top = suggestions[0]
                self._create_suggestion(
                    title=f"Classify expense as {top['code']}",
                    description=(
                        f"Expense from '{expense.suppliername or expense.supplierrfc}' "
                        f"matches '{top['name']}' with {top['confidence']:.0%} confidence."
                    ),
                    confidence=top['confidence'],
                    severity=SuggestionSeverity.INFO,
                    suggested_action='classify_expense',
                    suggested_data={
                        'expenseid': str(expense.expenseid),
                        'imputationcodeid': top['imputationcodeid'],
                        'code': top['code'],
                    },
                    relatedentityid=expense.expenseid,
                    relatedentitytype='expense',
                )

            results.append({
                'expenseid': str(expense.expenseid),
                'suggestions': suggestions,
                'auto_classify': auto_classify,
            })

        return results
