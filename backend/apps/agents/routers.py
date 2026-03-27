"""
Agent API endpoints.

Provides REST API for agent configuration, execution, and suggestion management.
"""

from typing import Optional, List
from uuid import UUID

from ninja import Router, Query

from apps.agents.schemas import (
    AgentConfigSchema,
    UpdateAgentConfigDto,
    AgentRunSchema,
    RunAgentDto,
    RunAgentInlineDto,
    AgentRunResultSchema,
    AgentSuggestionSchema,
    ResolveSuggestionDto,
    SuggestionStatsSchema,
)
from apps.agents.services import (
    AgentConfigService,
    AgentRunService,
    AgentSuggestionService,
)
from core.permissions import require_permission, Permission

# ============================================================================
# Router Registration
# ============================================================================

agents_config_router = Router(tags=["Agents - Config"])
agents_run_router = Router(tags=["Agents - Execution"])
agents_suggestion_router = Router(tags=["Agents - Suggestions"])


# ============================================================================
# Config Endpoints
# ============================================================================

@agents_config_router.get(
    "/",
    response=List[AgentConfigSchema],
    summary="List agent configurations",
)
@require_permission(Permission.AGENT_VIEW)
def list_configs(request, project_id: Optional[str] = None):
    return AgentConfigService.list_configs(project_id=project_id)


@agents_config_router.get(
    "/{agent_type}",
    response=AgentConfigSchema,
    summary="Get agent config by type",
)
@require_permission(Permission.AGENT_VIEW)
def get_config(request, agent_type: int, project_id: Optional[str] = None):
    return AgentConfigService.get_config(agent_type, project_id)


@agents_config_router.patch(
    "/{agent_type}",
    response=AgentConfigSchema,
    summary="Update agent config",
)
@require_permission(Permission.AGENT_CONFIG)
def update_config(request, agent_type: int, payload: UpdateAgentConfigDto, project_id: Optional[str] = None):
    return AgentConfigService.upsert_config(
        agent_type=agent_type,
        user=request.user,
        project_id=project_id,
        enabled=payload.enabled,
        config=payload.config,
        schedule_cron=payload.schedule_cron,
    )


@agents_config_router.post(
    "/{agent_type}/toggle",
    response=AgentConfigSchema,
    summary="Toggle agent enabled/disabled",
)
@require_permission(Permission.AGENT_CONFIG)
def toggle_agent(request, agent_type: int, project_id: Optional[str] = None):
    return AgentConfigService.toggle_agent(agent_type, request.user, project_id)


# ============================================================================
# Execution Endpoints
# ============================================================================

@agents_run_router.post(
    "/run",
    response=AgentRunResultSchema,
    summary="Execute an agent (async with persisted run)",
)
@require_permission(Permission.AGENT_RUN)
def run_agent(request, payload: RunAgentDto):
    return AgentRunService.run_agent(
        agent_type=payload.agenttype,
        user=request.user,
        params=payload.params,
        project_id=payload.project_id,
    )


@agents_run_router.post(
    "/inline/{agent_type}",
    summary="Execute agent inline (synchronous, no persistence)",
)
@require_permission(Permission.AGENT_RUN)
def run_agent_inline(request, agent_type: int, payload: RunAgentInlineDto):
    return AgentRunService.run_inline(
        agent_type=agent_type,
        user=request.user,
        params=payload.params,
        project_id=payload.project_id,
    )


@agents_run_router.get(
    "/runs",
    response=List[AgentRunSchema],
    summary="List agent run history",
)
@require_permission(Permission.AGENT_VIEW)
def list_runs(
    request,
    agent_type: Optional[int] = None,
    statecode: Optional[int] = None,
    limit: int = 50,
):
    return AgentRunService.list_runs(
        agent_type=agent_type,
        statecode=statecode,
        limit=min(limit, 200),
    )


@agents_run_router.get(
    "/runs/{run_id}",
    response=AgentRunSchema,
    summary="Get agent run detail",
)
@require_permission(Permission.AGENT_VIEW)
def get_run(request, run_id: UUID):
    return AgentRunService.get_run(run_id)


# ============================================================================
# Suggestion Endpoints
# ============================================================================

@agents_suggestion_router.get(
    "/",
    response=List[AgentSuggestionSchema],
    summary="List agent suggestions",
)
@require_permission(Permission.AGENT_VIEW)
def list_suggestions(
    request,
    agent_type: Optional[int] = None,
    statecode: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
):
    return AgentSuggestionService.list_suggestions(
        agent_type=agent_type,
        statecode=statecode,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
        limit=min(limit, 500),
    )


@agents_suggestion_router.post(
    "/{suggestion_id}/resolve",
    response=AgentSuggestionSchema,
    summary="Accept or reject a suggestion",
)
@require_permission(Permission.AGENT_RESOLVE)
def resolve_suggestion(request, suggestion_id: UUID, payload: ResolveSuggestionDto):
    return AgentSuggestionService.resolve_suggestion(
        suggestion_id=suggestion_id,
        user=request.user,
        action=payload.action,
        notes=payload.notes or '',
    )


@agents_suggestion_router.get(
    "/stats",
    response=SuggestionStatsSchema,
    summary="Get suggestion acceptance statistics",
)
@require_permission(Permission.AGENT_VIEW)
def suggestion_stats(request, agent_type: Optional[int] = None):
    return AgentSuggestionService.get_stats(agent_type=agent_type)
