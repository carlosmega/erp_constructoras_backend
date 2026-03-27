"""
Duplicate Detection Engine.

Detects duplicate entities across leads, contacts, and accounts using:
- Exact email matching
- Normalized phone matching (last 10 digits)
- Fuzzy name matching via difflib.SequenceMatcher
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Optional
from uuid import UUID

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.leads.models import Lead
except ImportError:
    Lead = None

try:
    from apps.contacts.models import Contact
except ImportError:
    Contact = None

try:
    from apps.accounts.models import Account
except ImportError:
    Account = None

logger = logging.getLogger(__name__)


def _normalize_phone(phone: Optional[str]) -> str:
    """Extract last 10 digits from a phone number for comparison."""
    if not phone:
        return ''
    digits = re.sub(r'\D', '', phone)
    return digits[-10:] if len(digits) >= 10 else digits


def _get_name(obj, entity_type: str) -> str:
    """Get display name from an entity."""
    if entity_type in ('lead', 'contact'):
        return getattr(obj, 'fullname', '') or ''
    elif entity_type == 'account':
        return getattr(obj, 'name', '') or ''
    return ''


def _get_pk(obj, entity_type: str) -> str:
    """Get primary key from an entity."""
    if entity_type == 'lead':
        return str(obj.leadid)
    elif entity_type == 'contact':
        return str(obj.contactid)
    elif entity_type == 'account':
        return str(obj.accountid)
    return ''


def _get_email(obj) -> str:
    """Get primary email from an entity."""
    return getattr(obj, 'emailaddress1', '') or ''


def _get_phone(obj) -> str:
    """Get primary phone from an entity."""
    return getattr(obj, 'telephone1', '') or getattr(obj, 'mobilephone', '') or ''


@register_agent
class DuplicateDetectionAgent(BaseAgent):
    """Detects duplicate leads, contacts, and accounts."""

    AGENT_TYPE = AgentTypeCode.DUPLICATE_DETECTION

    def execute(self, entity_type: str = 'lead', entity_id: str = '', **kwargs) -> Any:
        if not entity_id:
            raise ValueError("entity_id is required")

        entity_type = entity_type.lower()
        threshold = self.config.get('name_match_threshold', 0.80)

        # Load source entity
        source = self._load_entity(entity_type, entity_id)
        if source is None:
            raise ValueError(f"{entity_type} with id {entity_id} not found")

        source_email = _get_email(source)
        source_phone = _normalize_phone(_get_phone(source))
        source_name = _get_name(source, entity_type)

        duplicates = []

        # Search across all entity types
        for target_type in ('lead', 'contact', 'account'):
            candidates = self._get_candidates(target_type, entity_type, entity_id)
            for candidate in candidates:
                cand_id = _get_pk(candidate, target_type)
                match_score = 0.0
                matched_fields = []
                match_details = {}

                # Exact email match
                cand_email = _get_email(candidate)
                if source_email and cand_email and source_email.lower() == cand_email.lower():
                    match_score = max(match_score, 1.0)
                    matched_fields.append('email')
                    match_details['email'] = cand_email

                # Normalized phone match
                cand_phone = _normalize_phone(_get_phone(candidate))
                if source_phone and cand_phone and source_phone == cand_phone:
                    match_score = max(match_score, 0.90)
                    matched_fields.append('phone')
                    match_details['phone'] = cand_phone

                # Fuzzy name match
                cand_name = _get_name(candidate, target_type)
                if source_name and cand_name:
                    name_ratio = SequenceMatcher(
                        None, source_name.lower(), cand_name.lower()
                    ).ratio()
                    if name_ratio >= threshold:
                        match_score = max(match_score, round(name_ratio, 3))
                        matched_fields.append('name')
                        match_details['name'] = cand_name
                        match_details['name_score'] = round(name_ratio, 3)

                if matched_fields:
                    duplicates.append({
                        'source_id': str(entity_id),
                        'source_type': entity_type,
                        'duplicate_id': cand_id,
                        'duplicate_type': target_type,
                        'match_score': round(match_score, 3),
                        'matched_fields': matched_fields,
                        'match_details': match_details,
                    })

                    # Create suggestion for high-confidence matches
                    if match_score >= 0.90:
                        self._create_suggestion(
                            title=f"Possible duplicate {target_type} detected",
                            description=(
                                f"'{source_name}' ({entity_type}) closely matches "
                                f"'{cand_name}' ({target_type}). "
                                f"Matched on: {', '.join(matched_fields)}."
                            ),
                            confidence=match_score,
                            severity=SuggestionSeverity.WARNING,
                            suggested_action='merge_or_dismiss',
                            suggested_data={
                                'source_id': str(entity_id),
                                'source_type': entity_type,
                                'duplicate_id': cand_id,
                                'duplicate_type': target_type,
                            },
                            relatedentityid=UUID(str(entity_id)),
                            relatedentitytype=entity_type,
                        )

        # Sort by match score descending
        duplicates.sort(key=lambda d: d['match_score'], reverse=True)
        return duplicates

    def _load_entity(self, entity_type: str, entity_id: str):
        """Load a single entity by type and ID."""
        try:
            if entity_type == 'lead' and Lead:
                return Lead.objects.get(leadid=entity_id)
            elif entity_type == 'contact' and Contact:
                return Contact.objects.get(contactid=entity_id)
            elif entity_type == 'account' and Account:
                return Account.objects.get(accountid=entity_id)
        except Exception:
            return None
        return None

    def _get_candidates(self, target_type: str, source_type: str, source_id: str):
        """Get candidate entities for comparison, excluding the source."""
        try:
            if target_type == 'lead' and Lead:
                qs = Lead.objects.all()
                if source_type == 'lead':
                    qs = qs.exclude(leadid=source_id)
                return qs[:500]
            elif target_type == 'contact' and Contact:
                qs = Contact.objects.all()
                if source_type == 'contact':
                    qs = qs.exclude(contactid=source_id)
                return qs[:500]
            elif target_type == 'account' and Account:
                qs = Account.objects.all()
                if source_type == 'account':
                    qs = qs.exclude(accountid=source_id)
                return qs[:500]
        except Exception:
            pass
        return []
