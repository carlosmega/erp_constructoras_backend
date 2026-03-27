"""
Agent service layer.

Handles agent orchestration, configuration, suggestion management,
and delegates to specific engine implementations.
"""

import logging
from typing import Optional, List
from uuid import UUID

from django.db.models import QuerySet, Count, Q
from django.utils import timezone

from apps.agents.models import (
    AgentConfig,
    AgentRun,
    AgentSuggestion,
    AgentTypeCode,
    AgentStatusCode,
    SuggestionStatusCode,
)
from apps.users.models import SystemUser
from core.exceptions import NotFound, ValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# Agent Registry
# ============================================================================

_AGENT_REGISTRY = {}


def register_agent(agent_class):
    """Decorator to register an agent engine."""
    _AGENT_REGISTRY[agent_class.AGENT_TYPE] = agent_class
    return agent_class


def get_agent_class(agent_type: int):
    """Get agent class by type code."""
    cls = _AGENT_REGISTRY.get(agent_type)
    if not cls:
        raise ValidationError(f"Unknown agent type: {agent_type}")
    return cls


# ============================================================================
# AgentConfigService
# ============================================================================

class AgentConfigService:

    @staticmethod
    def list_configs(project_id: Optional[str] = None) -> QuerySet[AgentConfig]:
        qs = AgentConfig.objects.all()
        if project_id:
            qs = qs.filter(Q(projectid=project_id) | Q(projectid__isnull=True))
        return qs.order_by('agenttype')

    @staticmethod
    def get_config(agent_type: int, project_id: Optional[str] = None) -> AgentConfig:
        try:
            return AgentConfig.objects.get(agenttype=agent_type, projectid=project_id)
        except AgentConfig.DoesNotExist:
            try:
                return AgentConfig.objects.get(agenttype=agent_type, projectid=None)
            except AgentConfig.DoesNotExist:
                raise NotFound(f"Config for agent type {agent_type} not found")

    @staticmethod
    def upsert_config(
        agent_type: int,
        user: SystemUser,
        project_id: Optional[str] = None,
        enabled: Optional[bool] = None,
        config: Optional[dict] = None,
        schedule_cron: Optional[str] = None,
    ) -> AgentConfig:
        obj, created = AgentConfig.objects.get_or_create(
            agenttype=agent_type,
            projectid=project_id,
            defaults={
                'enabled': enabled if enabled is not None else True,
                'config': config or {},
                'schedule_cron': schedule_cron or '',
                'createdby': user,
                'modifiedby': user,
            }
        )
        if not created:
            if enabled is not None:
                obj.enabled = enabled
            if config is not None:
                obj.config = config
            if schedule_cron is not None:
                obj.schedule_cron = schedule_cron
            obj.modifiedby = user
            obj.save()
        return obj

    @staticmethod
    def toggle_agent(agent_type: int, user: SystemUser, project_id: Optional[str] = None) -> AgentConfig:
        config = AgentConfigService.get_config(agent_type, project_id)
        config.enabled = not config.enabled
        config.modifiedby = user
        config.save(update_fields=['enabled', 'modifiedby', 'modifiedon'])
        return config


# ============================================================================
# AgentRunService
# ============================================================================

class AgentRunService:

    @staticmethod
    def run_agent(
        agent_type: int,
        user: SystemUser,
        params: Optional[dict] = None,
        project_id: Optional[str] = None,
        triggered_by: str = "manual",
    ) -> dict:
        agent_class = get_agent_class(agent_type)
        agent = agent_class(project_id=project_id, user=user)
        return agent.run(params=params, triggered_by=triggered_by)

    @staticmethod
    def run_inline(
        agent_type: int,
        user: SystemUser,
        params: Optional[dict] = None,
        project_id: Optional[str] = None,
    ) -> dict:
        agent_class = get_agent_class(agent_type)
        agent = agent_class(project_id=project_id, user=user)
        return agent.run_inline(params=params)

    @staticmethod
    def list_runs(
        agent_type: Optional[int] = None,
        statecode: Optional[int] = None,
        limit: int = 50,
    ) -> QuerySet[AgentRun]:
        qs = AgentRun.objects.all()
        if agent_type is not None:
            qs = qs.filter(agenttype=agent_type)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs[:limit]

    @staticmethod
    def get_run(run_id: UUID) -> AgentRun:
        try:
            return AgentRun.objects.get(agentrunid=run_id)
        except AgentRun.DoesNotExist:
            raise NotFound(f"Agent run {run_id} not found")


# ============================================================================
# AgentSuggestionService
# ============================================================================

class AgentSuggestionService:

    @staticmethod
    def list_suggestions(
        agent_type: Optional[int] = None,
        statecode: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> QuerySet[AgentSuggestion]:
        qs = AgentSuggestion.objects.select_related('resolved_by', 'agentrun')
        if agent_type is not None:
            qs = qs.filter(agenttype=agent_type)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        if entity_type:
            qs = qs.filter(relatedentitytype=entity_type)
        if entity_id:
            qs = qs.filter(relatedentityid=entity_id)
        if severity:
            qs = qs.filter(severity=severity)
        return qs[:limit]

    @staticmethod
    def resolve_suggestion(
        suggestion_id: UUID,
        user: SystemUser,
        action: str,
        notes: str = '',
    ) -> AgentSuggestion:
        try:
            suggestion = AgentSuggestion.objects.select_related('agentrun').get(
                suggestionid=suggestion_id
            )
        except AgentSuggestion.DoesNotExist:
            raise NotFound(f"Suggestion {suggestion_id} not found")

        if suggestion.statecode != SuggestionStatusCode.PENDING:
            raise ValidationError(
                f"Suggestion already resolved as {suggestion.get_statecode_display()}"
            )

        if action == 'accept':
            suggestion.statecode = SuggestionStatusCode.ACCEPTED
        elif action == 'reject':
            suggestion.statecode = SuggestionStatusCode.REJECTED
        else:
            raise ValidationError(f"Invalid action: {action}. Use 'accept' or 'reject'.")

        suggestion.resolved_by = user
        suggestion.resolved_on = timezone.now()
        suggestion.resolution_notes = notes
        suggestion.modifiedby = user
        suggestion.save(update_fields=[
            'statecode', 'resolved_by', 'resolved_on',
            'resolution_notes', 'modifiedby', 'modifiedon',
        ])

        # Update parent run counters
        run = suggestion.agentrun
        if action == 'accept':
            run.accepted_count = (run.accepted_count or 0) + 1
        else:
            run.rejected_count = (run.rejected_count or 0) + 1
        run.save(update_fields=['accepted_count', 'rejected_count'])

        return suggestion

    @staticmethod
    def get_stats(agent_type: Optional[int] = None) -> dict:
        qs = AgentSuggestion.objects.all()
        if agent_type is not None:
            qs = qs.filter(agenttype=agent_type)

        total = qs.count()
        pending = qs.filter(statecode=SuggestionStatusCode.PENDING).count()
        accepted = qs.filter(statecode=SuggestionStatusCode.ACCEPTED).count()
        rejected = qs.filter(statecode=SuggestionStatusCode.REJECTED).count()
        resolved = accepted + rejected

        by_agent = list(
            qs.values('agenttype').annotate(
                total=Count('suggestionid'),
                accepted=Count('suggestionid', filter=Q(statecode=SuggestionStatusCode.ACCEPTED)),
                rejected=Count('suggestionid', filter=Q(statecode=SuggestionStatusCode.REJECTED)),
            ).order_by('agenttype')
        )

        return {
            "total": total,
            "pending": pending,
            "accepted": accepted,
            "rejected": rejected,
            "acceptance_rate": round(accepted / resolved * 100, 1) if resolved > 0 else 0.0,
            "by_agent": by_agent,
        }
