"""
Email Matching Service.

4-layer pipeline for associating emails with CRM records:
1. Tracking Token (highest priority, 95% confidence)
2. Thread Correlation (90% confidence)
3. Email Address Auto-match (50-85% confidence)
4. Manual Association (100% confidence)
"""

import re
import logging
from uuid import UUID
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from apps.activities.models import Activity, Email, ActivityTypeCode, MatchMethod
from apps.users.models import SystemUser
from core.exceptions import ValidationError, PermissionDenied

logger = logging.getLogger(__name__)

# Regex for tracking token in email subject: [CRM:OPP-abc12345]
TRACKING_TOKEN_REGEX = re.compile(r'\[CRM:(?P<type>[A-Z]+)-(?P<id>[a-f0-9]{8})\]')

# Entity type mapping for tracking tokens
TOKEN_TYPE_MAP = {
    'OPP': 'opportunity',
    'ACC': 'account',
    'CON': 'contact',
    'LEAD': 'lead',
    'QUOTE': 'quote',
    'ORD': 'order',
    'INV': 'invoice',
}

REVERSE_TOKEN_TYPE_MAP = {v: k for k, v in TOKEN_TYPE_MAP.items()}


class EmailMatchingService:
    """Service for matching emails to CRM records."""

    @staticmethod
    def generate_tracking_token(entity_type: str, entity_id: str) -> str:
        """Generate a tracking token for insertion in email subjects.

        Args:
            entity_type: CRM entity type (opportunity, account, contact, lead)
            entity_id: UUID of the entity

        Returns:
            Tracking token string like [CRM:OPP-abc12345]
        """
        type_code = REVERSE_TOKEN_TYPE_MAP.get(entity_type, entity_type.upper()[:5])
        short_id = str(entity_id).replace('-', '')[:8]
        return f'[CRM:{type_code}-{short_id}]'

    @staticmethod
    def match_email(email: Email) -> dict:
        """Run the 4-layer matching pipeline on an email.

        Returns dict with:
            matched: bool
            regardingobjectid: UUID or None
            regardingobjectidtype: str or None
            matchmethod: str or None
            matchconfidence: int or None
            suggestions: list of candidate records
        """
        result = {
            'matched': False,
            'regardingobjectid': None,
            'regardingobjectidtype': None,
            'matchmethod': None,
            'matchconfidence': None,
            'suggestions': [],
            'matched_contacts': [],
            'matched_accounts': [],
            'candidate_opportunities': [],
        }

        # Layer 1: Tracking Token
        match = EmailMatchingService._match_by_tracking_token(email)
        if match:
            result.update(match)
            return result

        # Layer 2: Thread Correlation
        match = EmailMatchingService._match_by_thread(email)
        if match:
            result.update(match)
            return result

        # Layer 3: Email Address Auto-match
        match = EmailMatchingService._match_by_email_address(email)
        if match:
            result.update(match)
            return result

        return result

    @staticmethod
    def _match_by_tracking_token(email: Email) -> Optional[dict]:
        """Layer 1: Match by tracking token in subject (confidence 95%)."""
        subject = email.activity.subject or ''
        match = TRACKING_TOKEN_REGEX.search(subject)
        if not match:
            return None

        token_type = match.group('type')
        short_id = match.group('id')

        entity_type = TOKEN_TYPE_MAP.get(token_type)
        if not entity_type:
            return None

        # Find the entity by UUID prefix
        entity_id = EmailMatchingService._find_entity_by_short_id(entity_type, short_id)
        if not entity_id:
            return None

        return {
            'matched': True,
            'regardingobjectid': entity_id,
            'regardingobjectidtype': entity_type,
            'matchmethod': MatchMethod.TRACKING_TOKEN,
            'matchconfidence': 95,
        }

    @staticmethod
    def _find_entity_by_short_id(entity_type: str, short_id: str) -> Optional[UUID]:
        """Find an entity by matching the first 8 chars of its UUID."""
        model_map = EmailMatchingService._get_model_map()
        model_info = model_map.get(entity_type)
        if not model_info:
            return None

        model_class, pk_field = model_info
        try:
            # Filter by UUID starting with the short_id
            entities = model_class.objects.filter(
                **{f'{pk_field}__startswith': short_id}
            )
            # UUID fields are stored as UUIDs, so we need string comparison
            # Use raw queryset for prefix matching on UUID
            for entity in model_class.objects.all().iterator():
                entity_uuid = str(getattr(entity, pk_field)).replace('-', '')
                if entity_uuid.startswith(short_id):
                    return getattr(entity, pk_field)
        except Exception as e:
            logger.warning(f"Error finding entity by short_id: {e}")

        return None

    @staticmethod
    def _match_by_thread(email: Email) -> Optional[dict]:
        """Layer 2: Match by thread correlation (confidence 90%).

        If the email has an inreplyto header, find the parent email
        and use its regarding object.
        """
        if not email.inreplyto:
            return None

        try:
            parent_email = Email.objects.select_related('activity').get(
                messageid=email.inreplyto
            )
            if parent_email.activity.regardingobjectid:
                return {
                    'matched': True,
                    'regardingobjectid': parent_email.activity.regardingobjectid,
                    'regardingobjectidtype': parent_email.activity.regardingobjectidtype,
                    'matchmethod': MatchMethod.THREAD_CORRELATION,
                    'matchconfidence': 90,
                }
        except Email.DoesNotExist:
            pass

        return None

    @staticmethod
    def _match_by_email_address(email: Email) -> Optional[dict]:
        """Layer 3: Match by email address (confidence 50-85%).

        Extracts email addresses from to/sender/cc/bcc and searches
        Contacts, Accounts, and Leads.
        """
        addresses = EmailMatchingService._extract_email_addresses(email)
        if not addresses:
            return None

        from apps.contacts.models import Contact
        from apps.accounts.models import Account
        from apps.leads.models import Lead

        matched_contacts = []
        matched_accounts = []
        matched_leads = []

        # Search contacts
        for addr in addresses:
            contacts = Contact.objects.filter(
                Q(emailaddress1__iexact=addr) | Q(emailaddress2__iexact=addr)
            )
            for contact in contacts:
                matched_contacts.append({
                    'contactid': str(contact.contactid),
                    'fullname': contact.fullname,
                    'emailaddress1': contact.emailaddress1,
                    'parentcustomerid': str(contact.parentcustomerid_id) if hasattr(contact, 'parentcustomerid_id') and contact.parentcustomerid_id else None,
                })

        # Search accounts
        for addr in addresses:
            accounts = Account.objects.filter(emailaddress1__iexact=addr)
            for account in accounts:
                matched_accounts.append({
                    'accountid': str(account.accountid),
                    'name': account.name,
                    'emailaddress1': account.emailaddress1,
                })

        # Search leads
        for addr in addresses:
            leads = Lead.objects.filter(emailaddress1__iexact=addr)
            for lead in leads:
                matched_leads.append({
                    'leadid': str(lead.leadid),
                    'fullname': f'{lead.firstname or ""} {lead.lastname or ""}'.strip(),
                    'emailaddress1': lead.emailaddress1,
                })

        # Try to find open opportunities linked to matched contacts/accounts
        candidate_opportunities = []
        if matched_contacts or matched_accounts:
            from apps.opportunities.models import Opportunity
            contact_ids = [c['contactid'] for c in matched_contacts]
            account_ids = [a['accountid'] for a in matched_accounts]

            opp_filter = Q()
            if contact_ids:
                opp_filter |= Q(customerid__in=contact_ids, customeridtype='contact')
            if account_ids:
                opp_filter |= Q(customerid__in=account_ids, customeridtype='account')

            # Also check parentaccountid
            parent_account_ids = [
                c['parentcustomerid'] for c in matched_contacts
                if c.get('parentcustomerid')
            ]
            if parent_account_ids:
                opp_filter |= Q(parentaccountid__in=parent_account_ids)

            opportunities = Opportunity.objects.filter(
                opp_filter,
                statecode=0  # Open
            ).order_by('-modifiedon')[:10]

            for opp in opportunities:
                candidate_opportunities.append({
                    'opportunityid': str(opp.opportunityid),
                    'name': opp.name,
                    'estimatedvalue': float(opp.estimatedvalue) if opp.estimatedvalue else None,
                    'salesstage': opp.salesstage if hasattr(opp, 'salesstage') else None,
                    'statecode': opp.statecode,
                    'modifiedon': opp.modifiedon.isoformat() if opp.modifiedon else None,
                })

        # Determine best match
        if len(candidate_opportunities) == 1:
            opp = candidate_opportunities[0]
            return {
                'matched': True,
                'regardingobjectid': UUID(opp['opportunityid']),
                'regardingobjectidtype': 'opportunity',
                'matchmethod': MatchMethod.EMAIL_ADDRESS,
                'matchconfidence': 85,
                'matched_contacts': matched_contacts,
                'matched_accounts': matched_accounts,
                'candidate_opportunities': candidate_opportunities,
            }
        elif len(candidate_opportunities) > 1:
            # Multiple opportunities - pick the most recently modified
            best = candidate_opportunities[0]
            return {
                'matched': True,
                'regardingobjectid': UUID(best['opportunityid']),
                'regardingobjectidtype': 'opportunity',
                'matchmethod': MatchMethod.EMAIL_ADDRESS,
                'matchconfidence': 60,
                'matched_contacts': matched_contacts,
                'matched_accounts': matched_accounts,
                'candidate_opportunities': candidate_opportunities,
            }
        elif matched_contacts:
            contact = matched_contacts[0]
            return {
                'matched': True,
                'regardingobjectid': UUID(contact['contactid']),
                'regardingobjectidtype': 'contact',
                'matchmethod': MatchMethod.EMAIL_ADDRESS,
                'matchconfidence': 70,
                'matched_contacts': matched_contacts,
                'matched_accounts': matched_accounts,
                'candidate_opportunities': candidate_opportunities,
            }
        elif matched_accounts:
            account = matched_accounts[0]
            return {
                'matched': True,
                'regardingobjectid': UUID(account['accountid']),
                'regardingobjectidtype': 'account',
                'matchmethod': MatchMethod.EMAIL_ADDRESS,
                'matchconfidence': 65,
                'matched_contacts': matched_contacts,
                'matched_accounts': matched_accounts,
                'candidate_opportunities': candidate_opportunities,
            }
        elif matched_leads:
            lead = matched_leads[0]
            return {
                'matched': True,
                'regardingobjectid': UUID(lead['leadid']),
                'regardingobjectidtype': 'lead',
                'matchmethod': MatchMethod.EMAIL_ADDRESS,
                'matchconfidence': 50,
                'matched_contacts': matched_contacts,
                'matched_accounts': matched_accounts,
                'candidate_opportunities': candidate_opportunities,
            }

        return None

    @staticmethod
    def _extract_email_addresses(email: Email) -> list[str]:
        """Extract all email addresses from to, sender, cc, bcc fields."""
        addresses = set()
        email_regex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

        for field in [email.to, email.sender, email.cc, email.bcc]:
            if field:
                found = email_regex.findall(field)
                addresses.update(addr.lower() for addr in found)

        return list(addresses)

    @staticmethod
    def _get_model_map():
        """Get mapping of entity types to (Model, pk_field) tuples."""
        from apps.opportunities.models import Opportunity
        from apps.accounts.models import Account
        from apps.contacts.models import Contact
        from apps.leads.models import Lead
        from apps.quotes.models import Quote
        from apps.orders.models import Order
        from apps.invoices.models import Invoice

        return {
            'opportunity': (Opportunity, 'opportunityid'),
            'account': (Account, 'accountid'),
            'contact': (Contact, 'contactid'),
            'lead': (Lead, 'leadid'),
            'quote': (Quote, 'quoteid'),
            'order': (Order, 'salesorderid'),
            'invoice': (Invoice, 'invoiceid'),
        }

    # ========================================================================
    # Manual Association Methods
    # ========================================================================

    @staticmethod
    def link_email_to_record(
        activity_id: UUID,
        regarding_id: UUID,
        regarding_type: str,
        user: SystemUser
    ) -> Activity:
        """Manually link an email activity to a CRM record.

        Args:
            activity_id: ID of the email activity
            regarding_id: ID of the target record
            regarding_type: Type of the target record (opportunity, account, contact, lead)
            user: User performing the action

        Returns:
            Updated Activity
        """
        from core.permissions import check_ownership

        activity = Activity.objects.get(activityid=activity_id)

        if not check_ownership(user, activity):
            raise PermissionDenied("You don't have permission to modify this activity")

        activity.regardingobjectid = regarding_id
        activity.regardingobjectidtype = regarding_type
        activity.modifiedby = user
        activity.modifiedon = timezone.now()
        activity.save()

        # Update email matching metadata
        try:
            email = Email.objects.get(activity=activity)
            email.matchmethod = MatchMethod.MANUAL
            email.matchconfidence = 100
            email.save()
        except Email.DoesNotExist:
            pass

        return activity

    @staticmethod
    def unlink_email(activity_id: UUID, user: SystemUser) -> Activity:
        """Remove the regarding association from an email activity.

        Args:
            activity_id: ID of the email activity
            user: User performing the action

        Returns:
            Updated Activity
        """
        from core.permissions import check_ownership

        activity = Activity.objects.get(activityid=activity_id)

        if not check_ownership(user, activity):
            raise PermissionDenied("You don't have permission to modify this activity")

        activity.regardingobjectid = None
        activity.regardingobjectidtype = None
        activity.modifiedby = user
        activity.modifiedon = timezone.now()
        activity.save()

        # Clear email matching metadata
        try:
            email = Email.objects.get(activity=activity)
            email.matchmethod = None
            email.matchconfidence = None
            email.trackingtokenid = None
            email.save()
        except Email.DoesNotExist:
            pass

        return activity

    @staticmethod
    def get_unlinked_emails(user: SystemUser) -> list:
        """Get emails without a regarding object, filtered by ownership.

        Returns list of Activity objects for unlinked emails.
        """
        from core.permissions import filter_by_ownership

        queryset = filter_by_ownership(
            Activity.objects.filter(
                activitytypecode=ActivityTypeCode.EMAIL,
                regardingobjectid__isnull=True,
            ).select_related('ownerid'),
            user
        ).order_by('-createdon')

        # Prefetch email details
        activities = list(queryset)
        email_map = {}
        if activities:
            emails = Email.objects.filter(
                activity__in=[a.activityid for a in activities]
            )
            email_map = {e.activity_id: e for e in emails}

        result = []
        for activity in activities:
            email = email_map.get(activity.activityid)
            result.append({
                'activityid': activity.activityid,
                'subject': activity.subject,
                'statecode': activity.statecode,
                'createdon': activity.createdon,
                'ownerid': str(activity.ownerid_id),
                'to': email.to if email else None,
                'sender': email.sender if email else None,
                'cc': email.cc if email else None,
                'directioncode': email.directioncode if email else True,
            })

        return result

    @staticmethod
    def get_unlinked_email_count(user: SystemUser) -> int:
        """Get count of unlinked emails for badge display."""
        from core.permissions import filter_by_ownership

        return filter_by_ownership(
            Activity.objects.filter(
                activitytypecode=ActivityTypeCode.EMAIL,
                regardingobjectid__isnull=True,
            ),
            user
        ).count()

    @staticmethod
    def get_match_suggestions(activity_id: UUID, user: SystemUser) -> dict:
        """Run the matching pipeline and return suggestions for an email.

        Args:
            activity_id: ID of the email activity
            user: User requesting suggestions

        Returns:
            Dict with match results and suggestions
        """
        from core.permissions import check_ownership

        activity = Activity.objects.get(activityid=activity_id)

        if not check_ownership(user, activity):
            raise PermissionDenied("You don't have permission to view this activity")

        try:
            email = Email.objects.get(activity=activity)
        except Email.DoesNotExist:
            return {
                'activityid': str(activity_id),
                'matched': False,
                'suggestion': None,
                'matched_contacts': [],
                'matched_accounts': [],
                'candidate_opportunities': [],
            }

        match_result = EmailMatchingService.match_email(email)

        suggestion = None
        if match_result['matched']:
            suggestion = {
                'regardingobjectid': str(match_result['regardingobjectid']),
                'regardingobjectidtype': match_result['regardingobjectidtype'],
                'matchmethod': match_result['matchmethod'],
                'matchconfidence': match_result['matchconfidence'],
            }

        return {
            'activityid': str(activity_id),
            'matched': match_result['matched'],
            'suggestion': suggestion,
            'matched_contacts': match_result.get('matched_contacts', []),
            'matched_accounts': match_result.get('matched_accounts', []),
            'candidate_opportunities': match_result.get('candidate_opportunities', []),
        }
