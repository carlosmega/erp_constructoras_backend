"""Smoke tests for Agents module."""

import uuid

import pytest

from apps.agents.models import (
    AgentConfig,
    AgentRun,
    AgentSuggestion,
    AgentTypeCode,
    AgentStatusCode,
    SuggestionStatusCode,
)
from apps.agents.tests.factories import (
    AgentConfigFactory,
    AgentRunFactory,
    AgentSuggestionFactory,
    PendingAgentRunFactory,
    FailedAgentRunFactory,
    AcceptedSuggestionFactory,
)


# ============================================================================
# Model creation smoke tests
# ============================================================================

@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAgentConfig:
    """Quick sanity checks for AgentConfig model."""

    def test_model_creation(self, salesperson):
        config = AgentConfigFactory(ownerid=salesperson)
        assert config.pk is not None
        assert config.agenttype == AgentTypeCode.LEAD_SCORING
        assert config.enabled is True

    def test_str_representation(self, salesperson):
        config = AgentConfigFactory(ownerid=salesperson)
        assert 'Lead Scoring' in str(config)

    def test_different_agent_types(self, salesperson):
        c1 = AgentConfigFactory(ownerid=salesperson, agenttype=AgentTypeCode.LEAD_SCORING)
        c2 = AgentConfigFactory(ownerid=salesperson, agenttype=AgentTypeCode.DUPLICATE_DETECTION)
        assert c1.agenttype != c2.agenttype


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAgentRun:
    """Quick sanity checks for AgentRun model."""

    def test_model_creation(self, salesperson):
        run = AgentRunFactory(createdby=salesperson)
        assert run.pk is not None
        assert run.statecode == AgentStatusCode.COMPLETED

    def test_pending_run(self, salesperson):
        run = PendingAgentRunFactory(createdby=salesperson)
        assert run.statecode == AgentStatusCode.PENDING
        assert run.duration_ms is None

    def test_failed_run(self, salesperson):
        run = FailedAgentRunFactory(createdby=salesperson)
        assert run.statecode == AgentStatusCode.FAILED
        assert run.error_message != ''

    def test_str_representation(self, salesperson):
        run = AgentRunFactory(createdby=salesperson)
        assert 'Lead Scoring' in str(run)


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAgentSuggestion:
    """Quick sanity checks for AgentSuggestion model."""

    def test_model_creation(self, salesperson):
        suggestion = AgentSuggestionFactory(
            agentrun=AgentRunFactory(createdby=salesperson),
        )
        assert suggestion.pk is not None
        assert suggestion.statecode == SuggestionStatusCode.PENDING

    def test_accepted_suggestion(self, salesperson):
        suggestion = AcceptedSuggestionFactory(
            agentrun=AgentRunFactory(createdby=salesperson),
        )
        assert suggestion.statecode == SuggestionStatusCode.ACCEPTED
        assert suggestion.resolved_by is not None

    def test_str_representation(self, salesperson):
        suggestion = AgentSuggestionFactory(
            agentrun=AgentRunFactory(createdby=salesperson),
            title='Check lead quality score',
        )
        assert 'Check lead quality' in str(suggestion)

    def test_suggestion_linked_to_run(self, salesperson):
        run = AgentRunFactory(createdby=salesperson)
        s1 = AgentSuggestionFactory(agentrun=run)
        s2 = AgentSuggestionFactory(agentrun=run)
        assert run.suggestions.count() == 2


# ============================================================================
# Service smoke tests
# ============================================================================

@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAgentConfigService:
    """Quick sanity checks for AgentConfigService."""

    def test_list_configs(self, salesperson):
        from apps.agents.services import AgentConfigService
        AgentConfigFactory(ownerid=salesperson, agenttype=AgentTypeCode.LEAD_SCORING)
        AgentConfigFactory(ownerid=salesperson, agenttype=AgentTypeCode.DUPLICATE_DETECTION)
        configs = AgentConfigService.list_configs()
        assert configs.count() >= 2

    def test_get_config(self, salesperson):
        from apps.agents.services import AgentConfigService
        AgentConfigFactory(ownerid=salesperson, agenttype=AgentTypeCode.LEAD_SCORING)
        config = AgentConfigService.get_config(AgentTypeCode.LEAD_SCORING)
        assert config.agenttype == AgentTypeCode.LEAD_SCORING

    def test_upsert_config_creates(self, salesperson):
        from apps.agents.services import AgentConfigService
        config = AgentConfigService.upsert_config(
            agent_type=AgentTypeCode.BUDGET_ALERT,
            user=salesperson,
            enabled=True,
            config={"threshold": 90},
        )
        assert config.agenttype == AgentTypeCode.BUDGET_ALERT
        assert config.config == {"threshold": 90}

    def test_toggle_agent(self, salesperson):
        from apps.agents.services import AgentConfigService
        AgentConfigFactory(
            ownerid=salesperson, agenttype=AgentTypeCode.LEAD_SCORING, enabled=True,
        )
        config = AgentConfigService.toggle_agent(AgentTypeCode.LEAD_SCORING, salesperson)
        assert config.enabled is False


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAgentRunService:
    """Quick sanity checks for AgentRunService."""

    def test_list_runs(self, salesperson):
        from apps.agents.services import AgentRunService
        AgentRunFactory(createdby=salesperson)
        runs = AgentRunService.list_runs()
        assert runs.count() >= 1

    def test_list_runs_filter_by_type(self, salesperson):
        from apps.agents.services import AgentRunService
        AgentRunFactory(createdby=salesperson, agenttype=AgentTypeCode.LEAD_SCORING)
        AgentRunFactory(createdby=salesperson, agenttype=AgentTypeCode.DUPLICATE_DETECTION)
        runs = AgentRunService.list_runs(agent_type=AgentTypeCode.LEAD_SCORING)
        assert all(r.agenttype == AgentTypeCode.LEAD_SCORING for r in runs)

    def test_get_run(self, salesperson):
        from apps.agents.services import AgentRunService
        run = AgentRunFactory(createdby=salesperson)
        fetched = AgentRunService.get_run(run.agentrunid)
        assert fetched.agentrunid == run.agentrunid

    def test_get_run_not_found(self, salesperson):
        from apps.agents.services import AgentRunService
        from core.exceptions import NotFound
        with pytest.raises(NotFound):
            AgentRunService.get_run(uuid.uuid4())


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAgentSuggestionService:
    """Quick sanity checks for AgentSuggestionService."""

    def test_list_suggestions(self, salesperson):
        from apps.agents.services import AgentSuggestionService
        run = AgentRunFactory(createdby=salesperson)
        AgentSuggestionFactory(agentrun=run)
        suggestions = AgentSuggestionService.list_suggestions()
        assert suggestions.count() >= 1

    def test_resolve_suggestion_accept(self, salesperson):
        from apps.agents.services import AgentSuggestionService
        run = AgentRunFactory(createdby=salesperson)
        suggestion = AgentSuggestionFactory(agentrun=run)
        resolved = AgentSuggestionService.resolve_suggestion(
            suggestion_id=suggestion.suggestionid,
            user=salesperson,
            action='accept',
            notes='Looks good',
        )
        assert resolved.statecode == SuggestionStatusCode.ACCEPTED
        assert resolved.resolved_by == salesperson

    def test_resolve_suggestion_reject(self, salesperson):
        from apps.agents.services import AgentSuggestionService
        run = AgentRunFactory(createdby=salesperson)
        suggestion = AgentSuggestionFactory(agentrun=run)
        resolved = AgentSuggestionService.resolve_suggestion(
            suggestion_id=suggestion.suggestionid,
            user=salesperson,
            action='reject',
            notes='Not relevant',
        )
        assert resolved.statecode == SuggestionStatusCode.REJECTED

    def test_resolve_already_resolved_raises(self, salesperson):
        from apps.agents.services import AgentSuggestionService
        from core.exceptions import ValidationError
        run = AgentRunFactory(createdby=salesperson)
        suggestion = AcceptedSuggestionFactory(agentrun=run)
        with pytest.raises(ValidationError):
            AgentSuggestionService.resolve_suggestion(
                suggestion_id=suggestion.suggestionid,
                user=salesperson,
                action='accept',
            )

    def test_get_stats(self, salesperson):
        from apps.agents.services import AgentSuggestionService
        stats = AgentSuggestionService.get_stats()
        assert 'total' in stats
        assert 'pending' in stats
        assert 'acceptance_rate' in stats


# ============================================================================
# Router smoke tests
# ============================================================================

@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAgentRouters:
    """Quick sanity checks for Agent API endpoints.

    Note: salesperson has AGENT_VIEW, AGENT_RUN, AGENT_RESOLVE but not AGENT_CONFIG.
    Config write endpoints need admin_auth_client.
    """

    def test_config_list_200(self, admin_auth_client, system_admin):
        AgentConfigFactory(ownerid=system_admin, agenttype=AgentTypeCode.LEAD_SCORING)
        response = admin_auth_client.get('/api/agents/config/')
        assert response.status_code == 200

    def test_config_get_by_type_200(self, admin_auth_client, system_admin):
        AgentConfigFactory(ownerid=system_admin, agenttype=AgentTypeCode.LEAD_SCORING)
        response = admin_auth_client.get('/api/agents/config/1')
        assert response.status_code == 200

    def test_runs_list_200(self, auth_client, salesperson):
        AgentRunFactory(createdby=salesperson)
        response = auth_client.get('/api/agents/runs')
        assert response.status_code == 200

    def test_runs_get_200(self, auth_client, salesperson):
        run = AgentRunFactory(createdby=salesperson)
        response = auth_client.get(f'/api/agents/runs/{run.agentrunid}')
        assert response.status_code == 200

    def test_suggestions_list_200(self, auth_client, salesperson):
        run = AgentRunFactory(createdby=salesperson)
        AgentSuggestionFactory(agentrun=run)
        response = auth_client.get('/api/agents/suggestions/')
        assert response.status_code == 200

    def test_suggestions_stats_200(self, auth_client, salesperson):
        response = auth_client.get('/api/agents/suggestions/stats')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        client = Client()
        response = client.get('/api/agents/config/')
        assert response.status_code == 403
