"""
Lead Qualification Assistant Engine.

Evaluates lead readiness for qualification:
- Required fields: budgetamount (estimatedvalue), needanalysis (description),
  estimatedvalue, budgetstatus (estimatedclosedate as proxy)
- Recommended: purchasetimeframe (estimatedclosedate), decisionmaker (jobtitle),
  emailaddress1
- Activity check: at least 1 call/meeting
- B2B detection (has companyname)
- Duplicate account/contact detection
- Pre-fills QualifyLeadDto if ready
"""

import logging
from typing import Any

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.leads.models import Lead, LeadStateCode
except ImportError:
    Lead = None
    LeadStateCode = None

try:
    from apps.accounts.models import Account
except ImportError:
    Account = None

try:
    from apps.contacts.models import Contact
except ImportError:
    Contact = None

try:
    from apps.activities.models import Activity
except ImportError:
    Activity = None

logger = logging.getLogger(__name__)


@register_agent
class LeadQualificationAssistantAgent(BaseAgent):
    """Evaluates lead readiness for qualification and pre-fills the qualify DTO."""

    AGENT_TYPE = AgentTypeCode.LEAD_QUALIFICATION_ASSISTANT

    def execute(self, lead_id: str = '', **kwargs) -> Any:
        if not lead_id:
            raise ValueError("lead_id is required")
        if Lead is None:
            raise RuntimeError("Lead model not available")

        try:
            lead = Lead.objects.select_related('ownerid').get(leadid=lead_id)
        except Lead.DoesNotExist:
            raise ValueError(f"Lead {lead_id} not found")

        if lead.statecode != LeadStateCode.OPEN:
            raise ValueError(f"Lead is not open (state: {lead.statecode})")

        missing_fields = []
        warnings = []
        readiness_score = 0
        max_score = 100

        # --- Required fields (40 points total) ---
        # budgetamount -> estimatedvalue
        if lead.estimatedvalue and lead.estimatedvalue > 0:
            readiness_score += 10
        else:
            missing_fields.append('estimatedvalue (budget amount)')

        # budgetstatus -> estimatedclosedate as proxy
        if lead.estimatedclosedate:
            readiness_score += 10
        else:
            missing_fields.append('estimatedclosedate (budget status / timeline)')

        # needanalysis -> description
        if lead.description:
            readiness_score += 10
        else:
            missing_fields.append('description (need analysis)')

        # estimatedvalue (separate check for non-zero)
        if lead.estimatedvalue and lead.estimatedvalue > 0:
            readiness_score += 10
        # Already counted above; add extra check for high value
        elif lead.estimatedvalue is None:
            pass  # Already in missing_fields

        # --- Recommended fields (30 points total) ---
        # purchasetimeframe -> estimatedclosedate (already checked)
        if lead.estimatedclosedate:
            readiness_score += 10

        # decisionmaker -> jobtitle
        if lead.jobtitle:
            readiness_score += 10
        else:
            warnings.append("No job title set. Unable to confirm decision-maker status.")

        # emailaddress1
        if lead.emailaddress1:
            readiness_score += 10
        else:
            warnings.append("No email address. Contact quality is reduced.")

        # --- Activity check (15 points) ---
        activity_count = 0
        has_call_or_meeting = False
        if Activity is not None:
            activities = Activity.objects.filter(
                regardingobjectid=lead.leadid,
                regardingobjectidtype='lead',
            )
            activity_count = activities.count()
            has_call_or_meeting = activities.filter(
                activitytypecode__in=['phonecall', 'appointment', 'meeting'],
            ).exists()

        if has_call_or_meeting:
            readiness_score += 15
        elif activity_count > 0:
            readiness_score += 5
            warnings.append(
                "Has activities but no call/meeting. Consider scheduling one before qualifying."
            )
        else:
            missing_fields.append('activities (at least 1 call or meeting)')

        # --- B2B detection (5 points) ---
        is_b2b = bool(lead.companyname)
        if is_b2b:
            readiness_score += 5

        # --- Duplicate detection ---
        existing_account = None
        existing_contact = None

        if is_b2b and Account is not None:
            match = Account.objects.filter(
                name__iexact=lead.companyname,
            ).first()
            if match:
                existing_account = {
                    'accountid': str(match.accountid),
                    'name': match.name,
                }
                warnings.append(
                    f"Existing account found: '{match.name}'. Consider linking instead of creating new."
                )

        if lead.emailaddress1 and Contact is not None:
            match = Contact.objects.filter(
                emailaddress1__iexact=lead.emailaddress1,
            ).first()
            if match:
                existing_contact = {
                    'contactid': str(match.contactid),
                    'fullname': match.fullname or '',
                }
                warnings.append(
                    f"Existing contact found: '{match.fullname}'. Consider linking instead of creating new."
                )

        # Clamp readiness score
        readiness_score = min(readiness_score, max_score)
        ready = readiness_score >= 70 and len(missing_fields) == 0

        # Pre-fill QualifyLeadDto if ready
        prefilled_dto = None
        if ready or readiness_score >= 50:
            prefilled_dto = {
                'createAccount': is_b2b and existing_account is None,
                'existingAccountId': (
                    existing_account['accountid'] if existing_account else None
                ),
                'createContact': existing_contact is None,
                'existingContactId': (
                    existing_contact['contactid'] if existing_contact else None
                ),
                'opportunityName': (
                    lead.subject or f"Opportunity - {lead.fullname}"
                ),
                'estimatedRevenue': float(lead.estimatedvalue) if lead.estimatedvalue else None,
                'estimatedCloseDate': (
                    lead.estimatedclosedate.isoformat() if lead.estimatedclosedate else None
                ),
                'description': lead.description or '',
            }

        # Create suggestion
        if ready:
            self._create_suggestion(
                title=f"Lead '{lead.fullname}' is ready to qualify",
                description=(
                    f"Readiness score: {readiness_score}/100. "
                    f"All required fields are present."
                ),
                confidence=readiness_score / 100,
                severity=SuggestionSeverity.INFO,
                suggested_action='qualify_lead',
                suggested_data={
                    'leadid': str(lead.leadid),
                    'prefilled_dto': prefilled_dto,
                },
                relatedentityid=lead.leadid,
                relatedentitytype='lead',
            )
        elif missing_fields:
            self._create_suggestion(
                title=f"Lead '{lead.fullname}' needs more data before qualifying",
                description=(
                    f"Readiness score: {readiness_score}/100. "
                    f"Missing: {', '.join(missing_fields)}."
                ),
                confidence=readiness_score / 100,
                severity=SuggestionSeverity.WARNING,
                suggested_action='complete_lead_data',
                suggested_data={
                    'leadid': str(lead.leadid),
                    'missing_fields': missing_fields,
                },
                relatedentityid=lead.leadid,
                relatedentitytype='lead',
            )

        return {
            'leadid': str(lead.leadid),
            'ready': ready,
            'readiness_score': readiness_score,
            'missing_fields': missing_fields,
            'warnings': warnings,
            'prefilled_dto': prefilled_dto,
            'is_b2b': is_b2b,
            'existing_account': existing_account,
            'existing_contact': existing_contact,
        }
