"""
Lead Scoring Engine.

Scores leads 0-100 based on multiple factors including company info,
contact quality, budget, activities, and engagement recency.
Maps score to quality: hot(>=70), warm(>=40), cold(<40).
"""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.leads.models import Lead, LeadStateCode, LeadQualityCode
except ImportError:
    Lead = None
    LeadStateCode = None
    LeadQualityCode = None

try:
    from apps.activities.models import Activity
except ImportError:
    Activity = None

logger = logging.getLogger(__name__)

SENIOR_TITLES = [
    'director', 'gerente', 'ceo', 'cfo', 'cto', 'coo', 'vp',
    'vice president', 'president', 'owner', 'founder', 'partner',
    'jefe', 'superintendente', 'manager',
]

REFERRAL_SOURCES = [2, 3, 4, 9]  # Employee Referral, External Referral, Partner, Word of Mouth
PHONE_SOURCES = []  # No specific phone source in enum
WEB_SOURCES = [8]  # Web


@register_agent
class LeadScoringAgent(BaseAgent):
    """Scores leads 0-100 based on multiple engagement and qualification factors."""

    AGENT_TYPE = AgentTypeCode.LEAD_SCORING

    def execute(self, lead_ids: Optional[list] = None, **kwargs) -> Any:
        if Lead is None:
            raise RuntimeError("Lead model not available")

        # Build queryset
        qs = Lead.objects.filter(statecode=LeadStateCode.OPEN)
        if lead_ids:
            qs = qs.filter(leadid__in=lead_ids)
        qs = qs.select_related('ownerid')

        # Compute pipeline average estimated value for comparison
        pipeline_avg = qs.aggregate(avg=Avg('estimatedvalue'))['avg'] or Decimal('0')

        # Stale threshold from config (days)
        stale_days = self.config.get('stale_days', 30)
        stale_cutoff = timezone.now() - timedelta(days=stale_days)

        results = []
        for lead in qs:
            score = 0
            breakdown = {}
            recommendations = []

            # --- has_company (+15) ---
            if lead.companyname:
                score += 15
                breakdown['has_company'] = 15
            else:
                recommendations.append("Add company name to improve score.")

            # --- senior_job_title (+10) ---
            if lead.jobtitle and any(t in lead.jobtitle.lower() for t in SENIOR_TITLES):
                score += 10
                breakdown['senior_job_title'] = 10

            # --- source score: referral(+20), phone(+15), web(+10) ---
            if lead.leadsourcecode:
                if lead.leadsourcecode in REFERRAL_SOURCES:
                    score += 20
                    breakdown['source_referral'] = 20
                elif lead.leadsourcecode in PHONE_SOURCES:
                    score += 15
                    breakdown['source_phone'] = 15
                elif lead.leadsourcecode in WEB_SOURCES:
                    score += 10
                    breakdown['source_web'] = 10

            # --- high_value vs pipeline avg (+20) ---
            if lead.estimatedvalue and pipeline_avg > 0:
                if lead.estimatedvalue > pipeline_avg:
                    score += 20
                    breakdown['high_value'] = 20

            # --- corporate_email (+5) ---
            if lead.emailaddress1:
                domain = lead.emailaddress1.split('@')[-1].lower() if '@' in lead.emailaddress1 else ''
                free_domains = ['gmail.com', 'hotmail.com', 'yahoo.com', 'outlook.com', 'live.com']
                if domain and domain not in free_domains:
                    score += 5
                    breakdown['corporate_email'] = 5
            else:
                recommendations.append("Add email address.")

            # --- has_budget (+10) ---
            if lead.estimatedvalue and lead.estimatedvalue > 0:
                score += 10
                breakdown['has_budget'] = 10
            else:
                recommendations.append("Set estimated value / budget amount.")

            # --- budget_approved (+5) ---
            # No explicit budget_approved field; use estimatedclosedate as proxy
            if lead.estimatedclosedate:
                score += 5
                breakdown['budget_approved'] = 5

            # --- decision_maker (+10) ---
            if lead.jobtitle and any(
                t in lead.jobtitle.lower()
                for t in ['director', 'ceo', 'owner', 'founder', 'gerente general', 'president']
            ):
                score += 10
                breakdown['decision_maker'] = 10

            # --- activities count (+5 each, max 15) ---
            activity_count = 0
            if Activity is not None:
                activity_count = Activity.objects.filter(
                    regardingobjectid=lead.leadid,
                    regardingobjectidtype='lead',
                ).count()
            activity_score = min(activity_count * 5, 15)
            if activity_score > 0:
                score += activity_score
                breakdown['activities'] = activity_score
            else:
                recommendations.append("Log at least one activity (call, email, meeting).")

            # --- stale penalty (-5 if >30 days with no activity) ---
            last_activity = None
            if Activity is not None and activity_count > 0:
                last_obj = Activity.objects.filter(
                    regardingobjectid=lead.leadid,
                    regardingobjectidtype='lead',
                ).order_by('-createdon').first()
                if last_obj:
                    last_activity = last_obj.createdon

            reference_date = last_activity or lead.createdon
            if reference_date and reference_date < stale_cutoff:
                score -= 5
                breakdown['stale_penalty'] = -5
                recommendations.append("Lead is stale. Follow up immediately.")

            # Clamp score 0-100
            score = max(0, min(100, score))

            # Map score to quality
            if score >= 70:
                quality_suggestion = 'hot'
                quality_code = LeadQualityCode.HOT
            elif score >= 40:
                quality_suggestion = 'warm'
                quality_code = LeadQualityCode.WARM
            else:
                quality_suggestion = 'cold'
                quality_code = LeadQualityCode.COLD

            # Create suggestion if quality differs from current
            if lead.leadqualitycode != quality_code:
                self._create_suggestion(
                    title=f"Update lead quality to {quality_suggestion.upper()}",
                    description=(
                        f"Lead '{lead.fullname}' scored {score}/100. "
                        f"Suggested quality: {quality_suggestion}."
                    ),
                    confidence=round(score / 100, 2),
                    severity=SuggestionSeverity.INFO,
                    suggested_action='update_quality',
                    suggested_data={
                        'leadid': str(lead.leadid),
                        'new_quality': quality_code,
                        'score': score,
                    },
                    relatedentityid=lead.leadid,
                    relatedentitytype='lead',
                )

            results.append({
                'leadid': str(lead.leadid),
                'score': score,
                'quality_suggestion': quality_suggestion,
                'breakdown': breakdown,
                'recommendations': recommendations,
            })

        return results
