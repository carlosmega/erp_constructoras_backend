"""
Quote Optimization Engine.

Analyzes quotes for pricing insights:
- Margin analysis: compare priceperunit vs product.currentcost
- Win probability based on historical win rate for similar total amounts
- Cross-sell: find products frequently quoted together but missing
- Discount warning if discount > 20% of base
"""

import logging
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.quotes.models import Quote, QuoteDetail, QuoteStateCode
except ImportError:
    Quote = None
    QuoteDetail = None
    QuoteStateCode = None

try:
    from apps.products.models import Product
except ImportError:
    Product = None

logger = logging.getLogger(__name__)


@register_agent
class QuoteOptimizationAgent(BaseAgent):
    """Analyzes quotes for margin, win probability, cross-sell, and discount insights."""

    AGENT_TYPE = AgentTypeCode.QUOTE_OPTIMIZATION

    def execute(self, quote_id: str = '', **kwargs) -> Any:
        if not quote_id:
            raise ValueError("quote_id is required")
        if Quote is None or QuoteDetail is None:
            raise RuntimeError("Required models not available")

        try:
            quote = Quote.objects.get(quoteid=quote_id)
        except Quote.DoesNotExist:
            raise ValueError(f"Quote {quote_id} not found")

        details = list(quote.quote_details.all().order_by('sequencenumber'))

        # --- Margin Analysis ---
        margin_analysis = self._analyze_margins(details)

        # --- Win Probability ---
        win_probability = self._estimate_win_probability(quote)

        # --- Cross-sell Products ---
        cross_sell = self._find_cross_sell(details)

        # --- Discount Analysis ---
        discount_analysis = self._analyze_discounts(quote, details)

        # --- Pricing Warnings ---
        pricing_warnings = []
        if margin_analysis['total_margin_pct'] < 10:
            pricing_warnings.append(
                f"Overall margin is very low ({margin_analysis['total_margin_pct']:.1f}%). "
                "Consider adjusting pricing."
            )
        for item in margin_analysis.get('low_margin_items', []):
            pricing_warnings.append(
                f"'{item['product']}' has {item['margin_pct']:.1f}% margin."
            )
        if discount_analysis.get('excessive_discounts'):
            pricing_warnings.append(
                f"Quote has {len(discount_analysis['excessive_discounts'])} items "
                "with discounts exceeding 20% of base price."
            )

        # Create suggestion if there are warnings
        if pricing_warnings:
            self._create_suggestion(
                title=f"Quote optimization for {quote.quotenumber}",
                description='; '.join(pricing_warnings[:3]),
                confidence=0.7,
                severity=SuggestionSeverity.WARNING,
                suggested_action='review_pricing',
                suggested_data={
                    'quoteid': str(quote_id),
                    'warnings_count': len(pricing_warnings),
                },
                relatedentityid=quote.quoteid,
                relatedentitytype='quote',
            )

        return {
            'quoteid': str(quote_id),
            'margin_analysis': margin_analysis,
            'win_probability': win_probability,
            'cross_sell_products': cross_sell,
            'pricing_warnings': pricing_warnings,
            'discount_analysis': discount_analysis,
        }

    def _analyze_margins(self, details: list) -> dict:
        """Analyze margins per line item and overall."""
        total_revenue = Decimal('0')
        total_cost = Decimal('0')
        low_margin_items = []

        if Product is None:
            return {
                'total_margin_pct': 0.0,
                'low_margin_items': [],
                'note': 'Product model not available for cost comparison',
            }

        # Build product cost lookup by name
        product_names = [d.productname for d in details]
        products = {
            p.name.lower(): p
            for p in Product.objects.filter(name__in=product_names)
        }

        for detail in details:
            revenue = detail.extendedamount or Decimal('0')
            total_revenue += revenue

            product = products.get(detail.productname.lower()) if detail.productname else None
            if product and product.currentcost:
                cost = product.currentcost * detail.quantity
                total_cost += cost
                margin_pct = float(
                    (revenue - cost) / revenue * 100
                ) if revenue > 0 else 0.0

                if margin_pct < 15:
                    low_margin_items.append({
                        'product': detail.productname,
                        'priceperunit': float(detail.priceperunit),
                        'currentcost': float(product.currentcost),
                        'margin_pct': round(margin_pct, 1),
                    })

        total_margin_pct = float(
            (total_revenue - total_cost) / total_revenue * 100
        ) if total_revenue > 0 else 0.0

        return {
            'total_margin_pct': round(total_margin_pct, 1),
            'low_margin_items': low_margin_items,
        }

    def _estimate_win_probability(self, quote: 'Quote') -> float:
        """Estimate win probability based on historical quotes with similar amounts."""
        total = float(quote.totalamount or 0)
        if total <= 0:
            return 0.0

        # Find quotes in similar range (0.5x to 2x)
        low = Decimal(str(total * 0.5))
        high = Decimal(str(total * 2.0))

        similar_quotes = Quote.objects.filter(
            totalamount__gte=low,
            totalamount__lte=high,
            statecode__in=[QuoteStateCode.WON, QuoteStateCode.CLOSED],
        )

        total_count = similar_quotes.count()
        if total_count == 0:
            return 0.5  # Default if no historical data

        won_count = similar_quotes.filter(statecode=QuoteStateCode.WON).count()
        return round(won_count / total_count, 3)

    def _find_cross_sell(self, details: list) -> list:
        """Find products frequently quoted together but missing from this quote."""
        current_products = {d.productname.lower() for d in details if d.productname}
        if not current_products:
            return []

        # Find other quotes that contain any of the same products
        related_quotes = QuoteDetail.objects.filter(
            productname__in=[d.productname for d in details],
        ).values_list('quoteid', flat=True).distinct()[:100]

        # Count co-occurrence of products in those quotes
        co_products = (
            QuoteDetail.objects.filter(quoteid__in=related_quotes)
            .values_list('productname', flat=True)
        )

        product_freq = Counter(
            name.lower() for name in co_products if name
        )

        # Remove products already in the current quote
        suggestions = []
        for product_name, freq in product_freq.most_common(10):
            if product_name not in current_products and freq >= 2:
                suggestions.append({
                    'product_name': product_name,
                    'co_occurrence_count': freq,
                    'reason': f"Found in {freq} similar quotes",
                })
            if len(suggestions) >= 5:
                break

        return suggestions

    def _analyze_discounts(self, quote: 'Quote', details: list) -> dict:
        """Analyze discounts for potential issues."""
        discount_threshold = self.config.get('discount_warning_pct', 20)
        excessive_discounts = []

        for detail in details:
            base = detail.baseamount or Decimal('0')
            discount = detail.manualdiscountamount or Decimal('0')
            if base > 0 and discount > 0:
                discount_pct = float(discount / base * 100)
                if discount_pct > discount_threshold:
                    excessive_discounts.append({
                        'product': detail.productname,
                        'base_amount': float(base),
                        'discount_amount': float(discount),
                        'discount_pct': round(discount_pct, 1),
                    })

        quote_level_discount_pct = float(quote.discountpercentage or 0)

        return {
            'quote_discount_pct': quote_level_discount_pct,
            'excessive_discounts': excessive_discounts,
            'total_discount': float(quote.totaldiscountamount or 0),
        }
