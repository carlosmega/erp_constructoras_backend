"""
Data Quality Engine.

Audits data quality across CRM entities (Leads, Contacts, Accounts, Opportunities).
Identifies missing fields, stale records, invalid formats, and orphan records.
Produces an overall score 0-100 based on percentage of clean records.
"""

import logging
import re
from typing import Any

from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.leads.models import Lead, LeadStateCode
except ImportError:
    Lead = None
    LeadStateCode = None

try:
    from apps.contacts.models import Contact
except ImportError:
    Contact = None

try:
    from apps.accounts.models import Account
except ImportError:
    Account = None

try:
    from apps.opportunities.models import Opportunity, OpportunityStateCode
except ImportError:
    Opportunity = None
    OpportunityStateCode = None

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def _sample_ids(qs, field='pk', limit=5):
    """Return a list of string IDs from the first N records."""
    return [str(getattr(obj, field)) for obj in qs[:limit]]


@register_agent
class DataQualityAgent(BaseAgent):
    """Audits data quality across CRM entities and produces a score 0-100."""

    AGENT_TYPE = AgentTypeCode.DATA_QUALITY

    def execute(self, **kwargs) -> Any:
        now = timezone.now()
        stale_lead_days = self.config.get('stale_lead_days', 30)
        stale_opp_days = self.config.get('stale_opp_days', 90)

        by_entity = {}
        total_records = 0
        total_issues = 0
        recommendations = []

        # ================================================================
        # Leads
        # ================================================================
        if Lead is not None:
            leads = Lead.objects.filter(statecode=LeadStateCode.OPEN)
            lead_total = leads.count()
            lead_issues_count = 0
            top_issues = []

            # Missing email
            no_email = leads.filter(
                Q(emailaddress1__isnull=True) | Q(emailaddress1='')
            )
            if no_email.exists():
                count = no_email.count()
                lead_issues_count += count
                top_issues.append({
                    'type': 'missing_email',
                    'count': count,
                    'sample_ids': _sample_ids(no_email, 'leadid'),
                })

            # Missing phone
            no_phone = leads.filter(
                Q(telephone1__isnull=True) | Q(telephone1=''),
                Q(mobilephone__isnull=True) | Q(mobilephone=''),
            )
            if no_phone.exists():
                count = no_phone.count()
                lead_issues_count += count
                top_issues.append({
                    'type': 'missing_phone',
                    'count': count,
                    'sample_ids': _sample_ids(no_phone, 'leadid'),
                })

            # Stale > N days
            stale_cutoff = now - timedelta(days=stale_lead_days)
            stale = leads.filter(modifiedon__lt=stale_cutoff)
            if stale.exists():
                count = stale.count()
                lead_issues_count += count
                top_issues.append({
                    'type': 'stale',
                    'count': count,
                    'sample_ids': _sample_ids(stale, 'leadid'),
                })

            # Invalid email format
            has_email = leads.exclude(
                Q(emailaddress1__isnull=True) | Q(emailaddress1='')
            )
            invalid_email_ids = []
            for lead in has_email.only('leadid', 'emailaddress1'):
                if not EMAIL_REGEX.match(lead.emailaddress1 or ''):
                    invalid_email_ids.append(str(lead.leadid))
            if invalid_email_ids:
                count = len(invalid_email_ids)
                lead_issues_count += count
                top_issues.append({
                    'type': 'invalid_email_format',
                    'count': count,
                    'sample_ids': invalid_email_ids[:5],
                })

            lead_score = round((1 - lead_issues_count / max(lead_total, 1)) * 100)
            lead_score = max(0, min(100, lead_score))
            by_entity['leads'] = {
                'total': lead_total,
                'issues': lead_issues_count,
                'score': lead_score,
                'top_issues': top_issues,
            }
            total_records += lead_total
            total_issues += lead_issues_count
        else:
            by_entity['leads'] = {'total': 0, 'issues': 0, 'score': 100, 'top_issues': []}

        # ================================================================
        # Contacts
        # ================================================================
        if Contact is not None:
            contacts = Contact.objects.all()
            contact_total = contacts.count()
            contact_issues_count = 0
            top_issues = []

            # Missing email
            no_email = contacts.filter(
                Q(emailaddress1__isnull=True) | Q(emailaddress1='')
            )
            if no_email.exists():
                count = no_email.count()
                contact_issues_count += count
                top_issues.append({
                    'type': 'missing_email',
                    'count': count,
                    'sample_ids': _sample_ids(no_email, 'contactid'),
                })

            # Orphan contacts (no account)
            orphans = contacts.filter(
                Q(parentcustomerid__isnull=True)
            )
            if orphans.exists():
                count = orphans.count()
                contact_issues_count += count
                top_issues.append({
                    'type': 'orphan_no_account',
                    'count': count,
                    'sample_ids': _sample_ids(orphans, 'contactid'),
                })

            # Missing phone
            no_phone = contacts.filter(
                Q(telephone1__isnull=True) | Q(telephone1=''),
            )
            if no_phone.exists():
                count = no_phone.count()
                contact_issues_count += count
                top_issues.append({
                    'type': 'missing_phone',
                    'count': count,
                    'sample_ids': _sample_ids(no_phone, 'contactid'),
                })

            contact_score = round((1 - contact_issues_count / max(contact_total, 1)) * 100)
            contact_score = max(0, min(100, contact_score))
            by_entity['contacts'] = {
                'total': contact_total,
                'issues': contact_issues_count,
                'score': contact_score,
                'top_issues': top_issues,
            }
            total_records += contact_total
            total_issues += contact_issues_count
        else:
            by_entity['contacts'] = {'total': 0, 'issues': 0, 'score': 100, 'top_issues': []}

        # ================================================================
        # Accounts
        # ================================================================
        if Account is not None:
            accounts = Account.objects.all()
            account_total = accounts.count()
            account_issues_count = 0
            top_issues = []

            # Missing email
            no_email = accounts.filter(
                Q(emailaddress1__isnull=True) | Q(emailaddress1='')
            )
            if no_email.exists():
                count = no_email.count()
                account_issues_count += count
                top_issues.append({
                    'type': 'missing_email',
                    'count': count,
                    'sample_ids': _sample_ids(no_email, 'accountid'),
                })

            # Missing category
            no_category = accounts.filter(
                Q(accountcategorycode__isnull=True)
            )
            if no_category.exists():
                count = no_category.count()
                account_issues_count += count
                top_issues.append({
                    'type': 'missing_category',
                    'count': count,
                    'sample_ids': _sample_ids(no_category, 'accountid'),
                })

            account_score = round((1 - account_issues_count / max(account_total, 1)) * 100)
            account_score = max(0, min(100, account_score))
            by_entity['accounts'] = {
                'total': account_total,
                'issues': account_issues_count,
                'score': account_score,
                'top_issues': top_issues,
            }
            total_records += account_total
            total_issues += account_issues_count
        else:
            by_entity['accounts'] = {'total': 0, 'issues': 0, 'score': 100, 'top_issues': []}

        # ================================================================
        # Opportunities
        # ================================================================
        if Opportunity is not None:
            opps = Opportunity.objects.filter(statecode=OpportunityStateCode.OPEN)
            opp_total = opps.count()
            opp_issues_count = 0
            top_issues = []

            # Stale > N days
            stale_cutoff = now - timedelta(days=stale_opp_days)
            stale = opps.filter(modifiedon__lt=stale_cutoff)
            if stale.exists():
                count = stale.count()
                opp_issues_count += count
                top_issues.append({
                    'type': 'stale',
                    'count': count,
                    'sample_ids': _sample_ids(stale, 'opportunityid'),
                })

            # No owner
            no_owner = opps.filter(ownerid__isnull=True)
            if no_owner.exists():
                count = no_owner.count()
                opp_issues_count += count
                top_issues.append({
                    'type': 'no_owner',
                    'count': count,
                    'sample_ids': _sample_ids(no_owner, 'opportunityid'),
                })

            # Missing close date
            no_close_date = opps.filter(estimatedclosedate__isnull=True)
            if no_close_date.exists():
                count = no_close_date.count()
                opp_issues_count += count
                top_issues.append({
                    'type': 'missing_close_date',
                    'count': count,
                    'sample_ids': _sample_ids(no_close_date, 'opportunityid'),
                })

            opp_score = round((1 - opp_issues_count / max(opp_total, 1)) * 100)
            opp_score = max(0, min(100, opp_score))
            by_entity['opportunities'] = {
                'total': opp_total,
                'issues': opp_issues_count,
                'score': opp_score,
                'top_issues': top_issues,
            }
            total_records += opp_total
            total_issues += opp_issues_count
        else:
            by_entity['opportunities'] = {'total': 0, 'issues': 0, 'score': 100, 'top_issues': []}

        # ================================================================
        # Overall score & recommendations
        # ================================================================
        if total_records > 0:
            overall_score = round((1 - total_issues / total_records) * 100)
            overall_score = max(0, min(100, overall_score))
        else:
            overall_score = 100

        # Generate recommendations
        for entity_name, data in by_entity.items():
            if data['score'] < 50:
                recommendations.append(
                    f"{entity_name.capitalize()}: Score {data['score']}/100 -- "
                    f"address {data['issues']} issue(s) urgently."
                )
            elif data['score'] < 80:
                recommendations.append(
                    f"{entity_name.capitalize()}: Score {data['score']}/100 -- "
                    f"review {data['issues']} issue(s) for improvement."
                )

        if overall_score < 60:
            recommendations.append(
                "Overall data quality is below 60%. Schedule a data cleanup sprint."
            )

        # Create suggestion based on overall score
        if overall_score < 80:
            severity = (
                SuggestionSeverity.CRITICAL if overall_score < 50
                else SuggestionSeverity.WARNING
            )
            self._create_suggestion(
                title=f"Data quality score: {overall_score}/100",
                description=(
                    f"{total_issues} issues found across {total_records} records. "
                    f"Top areas: {', '.join(recommendations[:3])}"
                ),
                confidence=0.9,
                severity=severity,
                suggested_action='data_cleanup',
                suggested_data={
                    'overall_score': overall_score,
                    'total_issues': total_issues,
                },
            )

        return {
            'scan_date': now.isoformat(),
            'overall_score': overall_score,
            'by_entity': by_entity,
            'total_records': total_records,
            'total_issues': total_issues,
            'recommendations': recommendations,
        }
