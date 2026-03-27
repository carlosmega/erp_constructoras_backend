"""
Proyeccion Cost Estimator Engine.

Suggests concept prices based on historical data:
- Lookup similar concepts from past projects
- Calculate price statistics (min, max, avg, median)
- Adjust for time (simple inflation factor if configured)
"""

import logging
import statistics
from decimal import Decimal
from typing import Any, Optional

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.proyeccion.models import (
        BudgetConcept,
        EstimationProject,
        ConceptPriceCatalogItem,
        ConceptPriceReference,
    )
    _PROYECCION_AVAILABLE = True
except ImportError:
    _PROYECCION_AVAILABLE = False
    BudgetConcept = None
    EstimationProject = None
    ConceptPriceCatalogItem = None
    ConceptPriceReference = None

logger = logging.getLogger(__name__)


@register_agent
class ProyeccionEstimatorAgent(BaseAgent):
    """Suggests concept prices based on historical project data."""

    AGENT_TYPE = AgentTypeCode.PROYECCION_ESTIMATOR

    def execute(
        self,
        concept_ids: Optional[list] = None,
        project_type: Optional[int] = None,
        **kwargs,
    ) -> Any:
        if not _PROYECCION_AVAILABLE:
            return [{
                'concept_id': cid,
                'concept_name': '',
                'suggested_unit_price': 0,
                'price_range': {'min': 0, 'max': 0, 'avg': 0, 'median': 0},
                'source_count': 0,
                'confidence': 0,
                'notes': 'Proyeccion models not accessible.',
            } for cid in (concept_ids or [])]

        if not concept_ids:
            raise ValueError("concept_ids list is required")

        inflation_factor = Decimal(str(self.config.get('inflation_factor', 0.0)))
        min_sources = self.config.get('min_sources_for_confidence', 3)

        concepts = BudgetConcept.objects.filter(
            conceptid__in=concept_ids
        ).select_related('projectid', 'subfamilyid')

        results = []

        for concept in concepts:
            # Strategy 1: Look for similar concepts by description in other projects
            similar = BudgetConcept.objects.filter(
                description__iexact=concept.description,
                unit=concept.unit,
            ).exclude(
                projectid=concept.projectid,
            )

            # Optionally filter by project type
            if project_type is not None:
                similar = similar.filter(projectid__projecttype=project_type)

            prices = [
                float(c.unitprice) for c in similar
                if c.unitprice and float(c.unitprice) > 0
            ]

            # Strategy 2: Also check ConceptPriceCatalogItem + references
            if ConceptPriceCatalogItem is not None and ConceptPriceReference is not None:
                catalog_items = ConceptPriceCatalogItem.objects.filter(
                    description__icontains=concept.description[:50],
                    unit=concept.unit,
                )
                for item in catalog_items[:5]:
                    refs = ConceptPriceReference.objects.filter(
                        catalogitemid=item
                    )
                    for ref in refs:
                        if ref.unitprice and float(ref.unitprice) > 0:
                            prices.append(float(ref.unitprice))

            if prices:
                price_min = min(prices)
                price_max = max(prices)
                price_avg = round(statistics.mean(prices), 4)
                price_median = round(statistics.median(prices), 4)

                # Apply inflation adjustment
                if inflation_factor > 0:
                    adjustment = 1 + float(inflation_factor)
                    suggested = round(price_median * adjustment, 4)
                else:
                    suggested = price_median

                source_count = len(prices)
                # Confidence: higher with more sources
                if source_count >= min_sources * 2:
                    confidence = 0.9
                elif source_count >= min_sources:
                    confidence = 0.7
                elif source_count >= 2:
                    confidence = 0.5
                else:
                    confidence = 0.3

                notes = f"Based on {source_count} historical reference(s)."
                if inflation_factor > 0:
                    notes += f" Inflation-adjusted by {float(inflation_factor)*100:.1f}%."
            else:
                price_min = 0
                price_max = 0
                price_avg = 0
                price_median = 0
                suggested = 0
                source_count = 0
                confidence = 0
                notes = "No historical data found for this concept."

            result = {
                'concept_id': str(concept.conceptid),
                'concept_name': concept.description,
                'suggested_unit_price': suggested,
                'price_range': {
                    'min': price_min,
                    'max': price_max,
                    'avg': price_avg,
                    'median': price_median,
                },
                'source_count': source_count,
                'confidence': confidence,
                'notes': notes,
            }
            results.append(result)

            # Create suggestion if we have a good price estimate
            if confidence >= 0.5 and suggested > 0:
                current_price = float(concept.unitprice or 0)
                if current_price == 0 or abs(current_price - suggested) / max(current_price, 1) > 0.1:
                    self._create_suggestion(
                        title=f"Price suggestion for '{concept.description[:80]}'",
                        description=(
                            f"Suggested unit price: ${suggested:,.4f} "
                            f"(range: ${price_min:,.4f} - ${price_max:,.4f}, "
                            f"{source_count} source(s))"
                        ),
                        confidence=confidence,
                        severity=SuggestionSeverity.INFO,
                        suggested_action='update_unit_price',
                        suggested_data={
                            'concept_id': str(concept.conceptid),
                            'suggested_price': suggested,
                            'current_price': current_price,
                        },
                        relatedentityid=concept.conceptid,
                        relatedentitytype='budgetconcept',
                    )

        # Handle concept_ids not found in database
        found_ids = {str(c.conceptid) for c in concepts}
        for cid in concept_ids:
            if str(cid) not in found_ids:
                results.append({
                    'concept_id': str(cid),
                    'concept_name': '',
                    'suggested_unit_price': 0,
                    'price_range': {'min': 0, 'max': 0, 'avg': 0, 'median': 0},
                    'source_count': 0,
                    'confidence': 0,
                    'notes': f'Concept {cid} not found.',
                })

        return results
