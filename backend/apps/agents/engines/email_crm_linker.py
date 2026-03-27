"""
Email-to-CRM Linker Agent (Type 20).

Suggests CRM entity matches for unlinked email activities
using email address, domain, and subject keyword matching.
"""

import logging
import re

from django.db.models import Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.activities.models import Activity, Email, ActivityTypeCode, ActivityStateCode
from apps.leads.models import Lead
from apps.contacts.models import Contact
from apps.accounts.models import Account
from apps.opportunities.models import Opportunity

logger = logging.getLogger(__name__)


@register_agent
class EmailCrmLinkerAgent(BaseAgent):
    """Suggests CRM entity links for unlinked email activities."""

    AGENT_TYPE = AgentTypeCode.EMAIL_CRM_LINKER

    def execute(self, *, activity_ids: list = None, **kwargs) -> list:
        auto_link_threshold = self.config.get('auto_link_threshold', 0.90)
        max_suggestions = self.config.get('max_suggestions', 3)

        # Get unlinked emails
        email_filter = Q(
            activitytypecode=ActivityTypeCode.EMAIL,
        )
        if activity_ids:
            email_filter &= Q(activityid__in=activity_ids)
        else:
            # Default: unlinked emails (no regarding object)
            email_filter &= Q(regardingobjectid__isnull=True)

        activities = (
            Activity.objects
            .filter(email_filter)
            .select_related('email_details')
            .order_by('-createdon')[:100]
        )

        results = []

        for activity in activities:
            try:
                email_detail = activity.email_details
            except Email.DoesNotExist:
                continue

            email_from = email_detail.sender or ''
            email_subject = activity.subject or ''

            suggestions = []

            # Extract email address and domain
            email_address = self._extract_email(email_from)
            domain = self._extract_domain(email_address)

            # ============================================================
            # Match 1: Exact email address match
            # ============================================================
            if email_address:
                # Check leads
                matching_leads = Lead.objects.filter(
                    emailaddress1__iexact=email_address
                )[:3]
                for lead in matching_leads:
                    suggestions.append({
                        'entityid': str(lead.leadid),
                        'entitytype': 'lead',
                        'entity_name': lead.fullname or f"{lead.firstname or ''} {lead.lastname}".strip(),
                        'confidence': 0.95,
                        'match_reason': f'Email match: {email_address}',
                    })

                # Check contacts
                matching_contacts = Contact.objects.filter(
                    emailaddress1__iexact=email_address
                )[:3]
                for contact in matching_contacts:
                    suggestions.append({
                        'entityid': str(contact.contactid),
                        'entitytype': 'contact',
                        'entity_name': contact.fullname or '',
                        'confidence': 0.95,
                        'match_reason': f'Email match: {email_address}',
                    })

            # ============================================================
            # Match 2: Domain match to account
            # ============================================================
            if domain and domain not in (
                'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com',
                'live.com', 'icloud.com', 'protonmail.com',
            ):
                matching_accounts = Account.objects.filter(
                    Q(websiteurl__icontains=domain) |
                    Q(emailaddress1__icontains=f'@{domain}')
                )[:3]
                for account in matching_accounts:
                    # Avoid duplicates if contact already matched from same account
                    suggestions.append({
                        'entityid': str(account.accountid),
                        'entitytype': 'account',
                        'entity_name': account.name,
                        'confidence': 0.75,
                        'match_reason': f'Domain match: {domain}',
                    })

            # ============================================================
            # Match 3: Subject keyword match
            # ============================================================
            if email_subject:
                subject_lower = email_subject.lower()

                # Match opportunity names
                opportunities = Opportunity.objects.filter(
                    statecode=0,  # Open
                ).values('opportunityid', 'name')[:50]

                for opp in opportunities:
                    opp_name = (opp['name'] or '').lower()
                    if opp_name and len(opp_name) > 3 and opp_name in subject_lower:
                        suggestions.append({
                            'entityid': str(opp['opportunityid']),
                            'entitytype': 'opportunity',
                            'entity_name': opp['name'],
                            'confidence': 0.65,
                            'match_reason': f'Subject contains opportunity name: {opp["name"]}',
                        })

                # Match quote numbers (pattern: QUO-YYYY-NNN or COT-YYYY-NNN)
                quote_patterns = re.findall(
                    r'((?:QUO|COT|QUOTE)-\d{4}-\d{3})',
                    email_subject,
                    re.IGNORECASE,
                )
                if quote_patterns:
                    from apps.quotes.models import Quote
                    for pattern in quote_patterns:
                        matching_quotes = Quote.objects.filter(
                            quotenumber__iexact=pattern,
                        )[:1]
                        for quote in matching_quotes:
                            suggestions.append({
                                'entityid': str(quote.quoteid),
                                'entitytype': 'quote',
                                'entity_name': f"{quote.quotenumber} - {quote.name}",
                                'confidence': 0.85,
                                'match_reason': f'Quote number in subject: {pattern}',
                            })

            # Deduplicate and sort by confidence
            seen = set()
            unique_suggestions = []
            for s in sorted(suggestions, key=lambda x: x['confidence'], reverse=True):
                key = (s['entityid'], s['entitytype'])
                if key not in seen:
                    seen.add(key)
                    unique_suggestions.append(s)

            top_suggestions = unique_suggestions[:max_suggestions]

            # Determine if auto-link is appropriate
            auto_link = (
                len(top_suggestions) == 1
                and top_suggestions[0]['confidence'] >= auto_link_threshold
            )

            result = {
                'activity_id': str(activity.activityid),
                'email_subject': email_subject,
                'email_from': email_from,
                'suggestions': top_suggestions,
                'auto_link': auto_link,
            }
            results.append(result)

            # Create suggestion
            if top_suggestions:
                best = top_suggestions[0]
                self._create_suggestion(
                    title=(
                        f"Link email '{email_subject[:50]}' -> "
                        f"{best['entitytype']}: {best['entity_name'][:50]}"
                    ),
                    description=(
                        f"Email from {email_from}. "
                        f"Best match: {best['entity_name']} ({best['entitytype']}) "
                        f"with {best['confidence']*100:.0f}% confidence. "
                        f"Reason: {best['match_reason']}."
                        + (" Auto-link recommended." if auto_link else "")
                    ),
                    confidence=best['confidence'],
                    severity=SuggestionSeverity.INFO,
                    suggested_action='auto_link' if auto_link else 'manual_link',
                    suggested_data=result,
                    relatedentityid=activity.activityid,
                    relatedentitytype='activity',
                )

        return results

    @staticmethod
    def _extract_email(from_field: str) -> str:
        """Extract email address from a From field like 'Name <email@domain.com>'."""
        if not from_field:
            return ''
        match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', from_field)
        return match.group(0).lower() if match else from_field.strip().lower()

    @staticmethod
    def _extract_domain(email: str) -> str:
        """Extract domain from email address."""
        if '@' in email:
            return email.split('@')[1].lower()
        return ''
