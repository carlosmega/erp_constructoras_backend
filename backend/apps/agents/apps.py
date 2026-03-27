from django.apps import AppConfig


class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agents'
    verbose_name = 'AI Agents'

    def ready(self):
        # Import all engines to trigger @register_agent decorators
        import apps.agents.engines.lead_scoring  # noqa: F401
        import apps.agents.engines.duplicate_detection  # noqa: F401
        import apps.agents.engines.expense_classification  # noqa: F401
        import apps.agents.engines.budget_alert  # noqa: F401
        import apps.agents.engines.pipeline_forecast  # noqa: F401
        import apps.agents.engines.next_best_action  # noqa: F401
        import apps.agents.engines.quote_optimization  # noqa: F401
        import apps.agents.engines.opportunity_stage_advisor  # noqa: F401
        import apps.agents.engines.lead_qualification_assistant  # noqa: F401
        import apps.agents.engines.cost_variance_analyzer  # noqa: F401
        import apps.agents.engines.provision_reconciliation  # noqa: F401
        import apps.agents.engines.client_estimate_generator  # noqa: F401
        import apps.agents.engines.payroll_validation  # noqa: F401
        import apps.agents.engines.attendance_anomaly  # noqa: F401
        import apps.agents.engines.project_staffing  # noqa: F401
        import apps.agents.engines.invoice_collection  # noqa: F401
        import apps.agents.engines.corporate_allocation_optimizer  # noqa: F401
        import apps.agents.engines.cash_flow_projector  # noqa: F401
        import apps.agents.engines.activity_summarizer  # noqa: F401
        import apps.agents.engines.email_crm_linker  # noqa: F401
        import apps.agents.engines.meeting_prep  # noqa: F401
        import apps.agents.engines.data_quality  # noqa: F401
        import apps.agents.engines.audit_compliance  # noqa: F401
        import apps.agents.engines.permission_anomaly  # noqa: F401
        import apps.agents.engines.proyeccion_estimator  # noqa: F401
        import apps.agents.engines.bid_analysis  # noqa: F401
        import apps.agents.engines.smart_notification  # noqa: F401
        import apps.agents.engines.escalation  # noqa: F401
        import apps.agents.engines.invoice_inbox_processor  # noqa: F401
