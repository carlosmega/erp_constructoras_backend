"""
Base agent class providing common infrastructure for all AI agents.

All agent engines inherit from BaseAgent and implement the execute() method.
The base class handles:
- Config loading from AgentConfig
- AgentRun lifecycle (create, start, complete, fail)
- Suggestion creation with consistent schema
- Timing and error handling
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID

from django.utils import timezone

from apps.agents.models import (
    AgentConfig,
    AgentRun,
    AgentSuggestion,
    AgentTypeCode,
    AgentStatusCode,
    SuggestionSeverity,
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all ERP agents."""

    AGENT_TYPE: int = None  # Must be set by subclass

    def __init__(self, project_id: Optional[str] = None, user=None):
        self.project_id = project_id
        self.user = user
        self.config = self._load_config()
        self._run: Optional[AgentRun] = None
        self._suggestions: list[AgentSuggestion] = []

    def _load_config(self) -> dict:
        """Load agent-specific config from AgentConfig, or return defaults."""
        try:
            agent_config = AgentConfig.objects.get(
                agenttype=self.AGENT_TYPE,
                projectid=self.project_id,
            )
            if not agent_config.enabled:
                return {"_disabled": True}
            return agent_config.config or {}
        except AgentConfig.DoesNotExist:
            # Try global config (projectid=None)
            try:
                agent_config = AgentConfig.objects.get(
                    agenttype=self.AGENT_TYPE,
                    projectid=None,
                )
                if not agent_config.enabled:
                    return {"_disabled": True}
                return agent_config.config or {}
            except AgentConfig.DoesNotExist:
                return {}

    def run(self, params: Optional[dict] = None, triggered_by: str = "manual") -> dict:
        """Execute agent with full lifecycle management.

        Returns:
            dict with keys: run_id, status, output_summary, suggestions_count, duration_ms
        """
        if self.config.get("_disabled"):
            return {
                "run_id": None,
                "status": "disabled",
                "output_summary": {},
                "suggestions_count": 0,
                "duration_ms": 0,
            }

        params = params or {}
        self._run = AgentRun.objects.create(
            agenttype=self.AGENT_TYPE,
            statecode=AgentStatusCode.RUNNING,
            input_params=params,
            triggered_by=triggered_by,
            createdby=self.user,
            modifiedby=self.user,
        )
        self._suggestions = []

        start = time.monotonic()
        try:
            result = self.execute(**params)
            duration_ms = int((time.monotonic() - start) * 1000)

            self._run.statecode = AgentStatusCode.COMPLETED
            self._run.output_summary = result if isinstance(result, dict) else {"result": result}
            self._run.suggestions_count = len(self._suggestions)
            self._run.duration_ms = duration_ms
            self._run.modifiedby = self.user
            self._run.save(update_fields=[
                'statecode', 'output_summary', 'suggestions_count',
                'duration_ms', 'modifiedby', 'modifiedon',
            ])

            return {
                "run_id": str(self._run.agentrunid),
                "status": "completed",
                "output_summary": self._run.output_summary,
                "suggestions_count": len(self._suggestions),
                "duration_ms": duration_ms,
            }

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception("Agent %s failed: %s", self.AGENT_TYPE, e)

            self._run.statecode = AgentStatusCode.FAILED
            self._run.error_message = str(e)
            self._run.duration_ms = duration_ms
            self._run.modifiedby = self.user
            self._run.save(update_fields=[
                'statecode', 'error_message', 'duration_ms',
                'modifiedby', 'modifiedon',
            ])

            return {
                "run_id": str(self._run.agentrunid),
                "status": "failed",
                "error": str(e),
                "suggestions_count": 0,
                "duration_ms": duration_ms,
            }

    def run_inline(self, params: Optional[dict] = None) -> dict:
        """Execute agent without persisting AgentRun (for synchronous UI calls)."""
        if self.config.get("_disabled"):
            return {"status": "disabled", "results": []}

        params = params or {}
        try:
            result = self.execute(**params)
            return {"status": "completed", "results": result}
        except Exception as e:
            logger.exception("Agent %s inline failed: %s", self.AGENT_TYPE, e)
            return {"status": "failed", "error": str(e), "results": []}

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Core agent logic. Must be implemented by subclasses.

        Returns:
            Agent-specific result (dict or list).
        """
        raise NotImplementedError

    def _create_suggestion(
        self,
        title: str,
        description: str = '',
        confidence: float = 0.5,
        severity: str = SuggestionSeverity.INFO,
        suggested_action: str = '',
        suggested_data: Optional[dict] = None,
        relatedentityid: Optional[UUID] = None,
        relatedentitytype: str = '',
    ) -> Optional[AgentSuggestion]:
        """Create a suggestion linked to the current run."""
        if not self._run:
            logger.warning("Cannot create suggestion without an active run")
            return None

        try:
            suggestion = AgentSuggestion.objects.create(
                agentrun=self._run,
                agenttype=self.AGENT_TYPE,
                title=title[:255],
                description=description,
                confidence=max(0.0, min(1.0, confidence)),
                severity=severity,
                suggested_action=suggested_action,
                suggested_data=suggested_data or {},
                relatedentityid=relatedentityid,
                relatedentitytype=relatedentitytype,
                createdby=self.user,
                modifiedby=self.user,
            )
            self._suggestions.append(suggestion)
            return suggestion
        except Exception as e:
            logger.error("Failed to create suggestion: %s", e, exc_info=True)
            return None
