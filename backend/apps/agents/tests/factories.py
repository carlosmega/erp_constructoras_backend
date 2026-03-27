"""
Factory Boy factories for Agent models.

Provides test data generation for AgentConfig, AgentRun, and AgentSuggestion.
"""

import factory
from factory.django import DjangoModelFactory

from apps.agents.models import (
    AgentConfig,
    AgentRun,
    AgentSuggestion,
    AgentTypeCode,
    AgentStatusCode,
    SuggestionStatusCode,
    SuggestionSeverity,
)
from apps.users.tests.factories import SalespersonFactory


class AgentConfigFactory(DjangoModelFactory):
    """Factory for creating AgentConfig instances."""

    class Meta:
        model = AgentConfig

    agenttype = AgentTypeCode.LEAD_SCORING
    enabled = True
    config = factory.LazyFunction(dict)
    schedule_cron = ''
    projectid = None
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class AgentRunFactory(DjangoModelFactory):
    """Factory for creating AgentRun instances."""

    class Meta:
        model = AgentRun

    agenttype = AgentTypeCode.LEAD_SCORING
    statecode = AgentStatusCode.COMPLETED
    input_params = factory.LazyFunction(dict)
    output_summary = factory.LazyFunction(lambda: {"total": 0})
    suggestions_count = 0
    accepted_count = 0
    rejected_count = 0
    duration_ms = 150
    error_message = ''
    triggered_by = 'manual'
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


class PendingAgentRunFactory(AgentRunFactory):
    """Factory for creating a pending AgentRun."""

    statecode = AgentStatusCode.PENDING
    duration_ms = None


class FailedAgentRunFactory(AgentRunFactory):
    """Factory for creating a failed AgentRun."""

    statecode = AgentStatusCode.FAILED
    error_message = 'Test error: something went wrong'


class AgentSuggestionFactory(DjangoModelFactory):
    """Factory for creating AgentSuggestion instances."""

    class Meta:
        model = AgentSuggestion

    agentrun = factory.SubFactory(AgentRunFactory)
    agenttype = factory.SelfAttribute('agentrun.agenttype')
    statecode = SuggestionStatusCode.PENDING
    relatedentityid = None
    relatedentitytype = ''
    title = factory.Sequence(lambda n: f'Suggestion #{n}')
    description = factory.Faker('sentence')
    confidence = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    severity = SuggestionSeverity.INFO
    suggested_action = ''
    suggested_data = factory.LazyFunction(dict)
    resolved_by = None
    resolved_on = None
    resolution_notes = ''
    createdby = factory.SelfAttribute('agentrun.createdby')
    modifiedby = factory.SelfAttribute('createdby')


class AcceptedSuggestionFactory(AgentSuggestionFactory):
    """Factory for creating an accepted AgentSuggestion."""

    statecode = SuggestionStatusCode.ACCEPTED
    resolved_by = factory.SelfAttribute('agentrun.createdby')
    resolved_on = factory.Faker('date_time_this_year')
    resolution_notes = 'Accepted by test user'
