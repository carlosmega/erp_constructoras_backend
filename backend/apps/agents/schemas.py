"""
Agent schemas (DTOs) for Django Ninja API.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from ninja import Schema, ModelSchema

from apps.agents.models import AgentConfig, AgentRun, AgentSuggestion


# ============================================================================
# AgentConfig Schemas
# ============================================================================

class AgentConfigSchema(ModelSchema):
    class Meta:
        model = AgentConfig
        fields = [
            'agentconfigid', 'agenttype', 'enabled', 'config',
            'schedule_cron', 'projectid', 'createdon', 'modifiedon',
        ]

    agenttype_display: str = ''

    @staticmethod
    def resolve_agenttype_display(obj):
        return obj.get_agenttype_display()


class UpdateAgentConfigDto(Schema):
    enabled: Optional[bool] = None
    config: Optional[dict] = None
    schedule_cron: Optional[str] = None


# ============================================================================
# AgentRun Schemas
# ============================================================================

class AgentRunSchema(ModelSchema):
    class Meta:
        model = AgentRun
        fields = [
            'agentrunid', 'agenttype', 'statecode', 'input_params',
            'output_summary', 'suggestions_count', 'accepted_count',
            'rejected_count', 'duration_ms', 'error_message',
            'triggered_by', 'createdon',
        ]

    agenttype_display: str = ''
    statecode_display: str = ''

    @staticmethod
    def resolve_agenttype_display(obj):
        return obj.get_agenttype_display()

    @staticmethod
    def resolve_statecode_display(obj):
        return obj.get_statecode_display()


class RunAgentDto(Schema):
    agenttype: int
    params: Optional[dict] = None
    project_id: Optional[str] = None


class RunAgentInlineDto(Schema):
    params: Optional[dict] = None
    project_id: Optional[str] = None


class AgentRunResultSchema(Schema):
    run_id: Optional[str] = None
    status: str
    output_summary: Optional[dict] = None
    error: Optional[str] = None
    suggestions_count: int = 0
    duration_ms: int = 0


# ============================================================================
# AgentSuggestion Schemas
# ============================================================================

class AgentSuggestionSchema(ModelSchema):
    class Meta:
        model = AgentSuggestion
        fields = [
            'suggestionid', 'agenttype', 'statecode',
            'relatedentityid', 'relatedentitytype',
            'title', 'description', 'confidence', 'severity',
            'suggested_action', 'suggested_data',
            'resolved_on', 'resolution_notes', 'createdon',
        ]

    agenttype_display: str = ''
    statecode_display: str = ''
    agentrunid: Optional[str] = None
    resolved_by_name: Optional[str] = None

    @staticmethod
    def resolve_agenttype_display(obj):
        return obj.get_agenttype_display()

    @staticmethod
    def resolve_statecode_display(obj):
        return obj.get_statecode_display()

    @staticmethod
    def resolve_agentrunid(obj):
        return str(obj.agentrun_id) if obj.agentrun_id else None

    @staticmethod
    def resolve_resolved_by_name(obj):
        return obj.resolved_by.fullname if obj.resolved_by else None


class ResolveSuggestionDto(Schema):
    action: str  # "accept" | "reject"
    notes: Optional[str] = ''


class SuggestionStatsSchema(Schema):
    total: int = 0
    pending: int = 0
    accepted: int = 0
    rejected: int = 0
    acceptance_rate: float = 0.0
    by_agent: Optional[list] = None
