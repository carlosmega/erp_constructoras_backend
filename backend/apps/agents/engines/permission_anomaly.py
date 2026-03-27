"""
Permission Anomaly Engine.

Detects permission anomalies:
- Users with admin role that haven't logged in >30 days
- Multiple admin accounts (warn if >3)
- Users with roles that don't match their activity patterns
- Disabled users still in active role
"""

import logging
from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.users.models import SystemUser, SecurityRole
except ImportError:
    SystemUser = None
    SecurityRole = None

try:
    from core.permissions import ROLE_PERMISSIONS
except ImportError:
    ROLE_PERMISSIONS = {}

logger = logging.getLogger(__name__)

ADMIN_ROLE_NAME = 'System Administrator'


@register_agent
class PermissionAnomalyAgent(BaseAgent):
    """Detects permission anomalies across user accounts and roles."""

    AGENT_TYPE = AgentTypeCode.PERMISSION_ANOMALY

    def execute(self, **kwargs) -> Any:
        if SystemUser is None or SecurityRole is None:
            raise RuntimeError("User models not available")

        now = timezone.now()
        inactive_threshold_days = self.config.get('inactive_threshold_days', 30)
        max_admins = self.config.get('max_admins', 3)

        users = SystemUser.objects.select_related('securityroleid').all()
        users_audited = users.count()

        findings = []
        recommendations = []

        # ================================================================
        # Role distribution
        # ================================================================
        role_dist = {}
        role_counts = (
            users.values('securityroleid__name')
            .annotate(count=Count('systemuserid'))
            .order_by('-count')
        )
        for entry in role_counts:
            role_name = entry['securityroleid__name'] or 'No Role'
            role_dist[role_name] = entry['count']

        admin_count = role_dist.get(ADMIN_ROLE_NAME, 0)

        # ================================================================
        # 1. Admin users that haven't logged in >N days
        # ================================================================
        inactive_cutoff = now - timedelta(days=inactive_threshold_days)
        inactive_admins = users.filter(
            securityroleid__name=ADMIN_ROLE_NAME,
            isdisabled=False,
        ).filter(
            # Either never logged in or last login is stale
            lastlogindate__isnull=True,
        ) | users.filter(
            securityroleid__name=ADMIN_ROLE_NAME,
            isdisabled=False,
            lastlogindate__lt=inactive_cutoff,
        )
        inactive_admins = inactive_admins.distinct()

        for user in inactive_admins:
            last_login = (
                user.lastlogindate.isoformat() if user.lastlogindate else 'never'
            )
            findings.append({
                'type': 'inactive_admin',
                'user_id': str(user.systemuserid),
                'user_name': user.fullname,
                'role': ADMIN_ROLE_NAME,
                'details': (
                    f"Admin user last logged in: {last_login}. "
                    f"Inactive for >{inactive_threshold_days} days."
                ),
                'recommendation': 'Review if admin access is still needed. Consider downgrading role.',
            })

        # ================================================================
        # 2. Multiple admin accounts
        # ================================================================
        if admin_count > max_admins:
            findings.append({
                'type': 'excessive_admins',
                'user_id': None,
                'user_name': None,
                'role': ADMIN_ROLE_NAME,
                'details': (
                    f"{admin_count} admin accounts detected (threshold: {max_admins}). "
                    f"Excessive admin accounts increase security risk."
                ),
                'recommendation': (
                    f"Reduce admin accounts to {max_admins} or fewer. "
                    f"Use least-privilege roles where possible."
                ),
            })
            recommendations.append(
                f"Reduce admin accounts from {admin_count} to <= {max_admins}."
            )

        # ================================================================
        # 3. Users with roles that don't match activity patterns
        # ================================================================
        # Check for sales-related roles with zero activities
        try:
            from apps.activities.models import Activity

            sales_roles = ['Salesperson', 'Sales Manager']
            sales_users = users.filter(
                securityroleid__name__in=sales_roles,
                isdisabled=False,
            )
            activity_cutoff = now - timedelta(days=60)

            for user in sales_users:
                activity_count = Activity.objects.filter(
                    ownerid=user,
                    createdon__gte=activity_cutoff,
                ).count()
                if activity_count == 0:
                    findings.append({
                        'type': 'role_activity_mismatch',
                        'user_id': str(user.systemuserid),
                        'user_name': user.fullname,
                        'role': user.securityroleid.name if user.securityroleid else 'Unknown',
                        'details': (
                            f"Sales role user has 0 activities in the last 60 days."
                        ),
                        'recommendation': (
                            'Verify user is still active in sales. '
                            'Consider reassigning or updating role.'
                        ),
                    })
        except ImportError:
            pass

        # ================================================================
        # 4. Disabled users still in active role
        # ================================================================
        disabled_active_role = users.filter(
            isdisabled=True,
        ).exclude(
            securityroleid__name='Read-Only User',
        )

        for user in disabled_active_role:
            role_name = user.securityroleid.name if user.securityroleid else 'Unknown'
            findings.append({
                'type': 'disabled_user_active_role',
                'user_id': str(user.systemuserid),
                'user_name': user.fullname,
                'role': role_name,
                'details': (
                    f"Disabled user still assigned role '{role_name}'. "
                    f"Should be downgraded to Read-Only or removed."
                ),
                'recommendation': 'Downgrade disabled user to Read-Only role or remove entirely.',
            })

        # ================================================================
        # Recommendations & suggestions
        # ================================================================
        if findings:
            critical_count = sum(
                1 for f in findings
                if f['type'] in ('inactive_admin', 'excessive_admins')
            )
            warning_count = len(findings) - critical_count

            if critical_count > 0:
                recommendations.append(
                    f"{critical_count} critical permission anomaly(ies) require immediate review."
                )
            if warning_count > 0:
                recommendations.append(
                    f"{warning_count} warning-level finding(s) should be reviewed."
                )

            # Create suggestions
            for finding in findings:
                severity = (
                    SuggestionSeverity.CRITICAL
                    if finding['type'] in ('inactive_admin', 'excessive_admins')
                    else SuggestionSeverity.WARNING
                )
                self._create_suggestion(
                    title=f"Permission anomaly: {finding['type']}",
                    description=finding['details'],
                    confidence=0.8,
                    severity=severity,
                    suggested_action='review_permission',
                    suggested_data=finding,
                    relatedentityid=finding['user_id'] if finding['user_id'] else None,
                    relatedentitytype='systemuser' if finding['user_id'] else '',
                )
        else:
            recommendations.append("No permission anomalies detected. All clear.")

        return {
            'users_audited': users_audited,
            'findings': findings,
            'role_distribution': role_dist,
            'admin_count': admin_count,
            'recommendations': recommendations,
        }
