"""
Next Best Action Engine.

Suggests the most relevant next action for sales entities:
- Leads: call if no recent activity, qualify if score > 70
- Opportunities: send_quote if in Propose without quote, follow_up if stale
- Quotes: activate if draft with items, follow_up if active > 7 days
"""

import logging
from datetime import timedelta
from typing import Any, Optional

from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.leads.models import Lead, LeadStateCode
except ImportError:
    Lead = None
    LeadStateCode = None

try:
    from apps.opportunities.models import Opportunity, OpportunityStateCode, SalesStage
except ImportError:
    Opportunity = None
    OpportunityStateCode = None
    SalesStage = None

try:
    from apps.quotes.models import Quote, QuoteStateCode
except ImportError:
    Quote = None
    QuoteStateCode = None

try:
    from apps.activities.models import Activity
except ImportError:
    Activity = None

logger = logging.getLogger(__name__)


def _last_activity_date(entity_id, entity_type: str):
    """Get the most recent activity date for an entity."""
    if Activity is None:
        return None
    act = Activity.objects.filter(
        regardingobjectid=entity_id,
        regardingobjectidtype=entity_type,
    ).order_by('-createdon').first()
    return act.createdon if act else None


@register_agent
class NextBestActionAgent(BaseAgent):
    """Suggests next best actions for sales entities based on current state."""

    AGENT_TYPE = AgentTypeCode.NEXT_BEST_ACTION

    def execute(
        self,
        owner_id: Optional[str] = None,
        entity_types: Optional[list] = None,
        **kwargs,
    ) -> Any:
        now = timezone.now()
        results = []

        if entity_types is None:
            entity_types = ['lead', 'opportunity', 'quote']

        # --- Leads ---
        if 'lead' in entity_types and Lead is not None:
            qs = Lead.objects.filter(statecode=LeadStateCode.OPEN).select_related('ownerid')
            if owner_id:
                qs = qs.filter(ownerid=owner_id)

            for lead in qs:
                last_act = _last_activity_date(lead.leadid, 'lead')
                days_since = (now - last_act).days if last_act else None

                # Qualify if high score inferred (has company, has budget, has email)
                score_proxy = 0
                if lead.companyname:
                    score_proxy += 25
                if lead.estimatedvalue and lead.estimatedvalue > 0:
                    score_proxy += 25
                if lead.emailaddress1:
                    score_proxy += 10
                if lead.jobtitle:
                    score_proxy += 10

                if score_proxy >= 70:
                    results.append({
                        'entityid': str(lead.leadid),
                        'entitytype': 'lead',
                        'entity_name': lead.fullname or str(lead.leadid),
                        'action': 'qualify',
                        'priority': 'high',
                        'reason': f"Lead has strong indicators (score proxy: {score_proxy}). Ready to qualify.",
                        'due_date': now.date().isoformat(),
                    })
                elif days_since is None or days_since >= 3:
                    results.append({
                        'entityid': str(lead.leadid),
                        'entitytype': 'lead',
                        'entity_name': lead.fullname or str(lead.leadid),
                        'action': 'call',
                        'priority': 'medium' if (days_since or 99) < 7 else 'high',
                        'reason': (
                            f"No activity in {days_since} days."
                            if days_since else "No activities logged yet."
                        ),
                        'due_date': now.date().isoformat(),
                    })

        # --- Opportunities ---
        if 'opportunity' in entity_types and Opportunity is not None:
            qs = Opportunity.objects.filter(
                statecode=OpportunityStateCode.OPEN,
            ).select_related('ownerid')
            if owner_id:
                qs = qs.filter(ownerid=owner_id)

            for opp in qs:
                last_act = _last_activity_date(opp.opportunityid, 'opportunity')
                days_since = (now - last_act).days if last_act else None

                # In Propose stage without a quote -> send_quote
                if opp.salesstage == SalesStage.PROPOSE:
                    has_quote = Quote and Quote.objects.filter(
                        opportunityid=opp.opportunityid,
                    ).exists()
                    if not has_quote:
                        results.append({
                            'entityid': str(opp.opportunityid),
                            'entitytype': 'opportunity',
                            'entity_name': opp.name,
                            'action': 'send_quote',
                            'priority': 'high',
                            'reason': "Opportunity is in Propose stage but has no quote.",
                            'due_date': now.date().isoformat(),
                        })
                        continue

                # Stale follow-up (no activity in 5+ days)
                if days_since is None or days_since >= 5:
                    results.append({
                        'entityid': str(opp.opportunityid),
                        'entitytype': 'opportunity',
                        'entity_name': opp.name,
                        'action': 'follow_up',
                        'priority': 'medium' if (days_since or 99) < 10 else 'high',
                        'reason': (
                            f"No activity in {days_since} days."
                            if days_since else "No activities logged."
                        ),
                        'due_date': (now + timedelta(days=1)).date().isoformat(),
                    })

        # --- Quotes ---
        if 'quote' in entity_types and Quote is not None:
            qs = Quote.objects.filter(
                statecode__in=[QuoteStateCode.DRAFT, QuoteStateCode.ACTIVE],
            ).select_related('ownerid')
            if owner_id:
                qs = qs.filter(ownerid=owner_id)

            for quote in qs:
                # Draft with items -> activate
                if quote.statecode == QuoteStateCode.DRAFT:
                    has_items = quote.quote_details.exists()
                    if has_items:
                        results.append({
                            'entityid': str(quote.quoteid),
                            'entitytype': 'quote',
                            'entity_name': f"{quote.quotenumber} - {quote.name}",
                            'action': 'activate',
                            'priority': 'medium',
                            'reason': "Draft quote has line items. Ready to activate and send.",
                            'due_date': now.date().isoformat(),
                        })

                # Active for >7 days -> follow up
                elif quote.statecode == QuoteStateCode.ACTIVE:
                    days_active = (now - quote.createdon).days if quote.createdon else 0
                    if days_active > 7:
                        results.append({
                            'entityid': str(quote.quoteid),
                            'entitytype': 'quote',
                            'entity_name': f"{quote.quotenumber} - {quote.name}",
                            'action': 'follow_up',
                            'priority': 'high' if days_active > 14 else 'medium',
                            'reason': f"Quote has been active for {days_active} days without resolution.",
                            'due_date': now.date().isoformat(),
                        })

        # Create suggestions for high-priority actions
        for item in results:
            if item['priority'] == 'high':
                self._create_suggestion(
                    title=f"Action: {item['action']} for {item['entitytype']}",
                    description=item['reason'],
                    confidence=0.75,
                    severity=SuggestionSeverity.WARNING,
                    suggested_action=item['action'],
                    suggested_data={
                        'entityid': item['entityid'],
                        'entitytype': item['entitytype'],
                    },
                    relatedentitytype=item['entitytype'],
                )

        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        results.sort(key=lambda r: priority_order.get(r['priority'], 3))

        return results
