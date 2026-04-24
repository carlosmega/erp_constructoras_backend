"""FinancialSettingsService — CRUD with lazy materialization."""
from __future__ import annotations
from uuid import UUID
from django.db import transaction
from apps.cashflow.models import ProjectFinancialSettings


class FinancialSettingsService:

    @staticmethod
    def get_or_create(project_id: UUID) -> ProjectFinancialSettings:
        """Return the settings for a project, creating with defaults if missing."""
        settings, _ = ProjectFinancialSettings.objects.get_or_create(
            projectid_id=project_id,
        )
        return settings

    @staticmethod
    @transaction.atomic
    def update(project_id: UUID, data: dict) -> ProjectFinancialSettings:
        """Apply partial updates. Expected keys match model fields."""
        settings = FinancialSettingsService.get_or_create(project_id)
        allowed = {
            'imssretentionrate', 'otherretentionrate', 'retentionreturnperiod',
            'advanceamortizationrate', 'anticipoentryperiod',
            'transversalcost', 'transversalwithdrawalperiod',
            'utilitycost', 'utilitywithdrawalperiod',
            'financecostrate',
        }
        for field, value in data.items():
            if field in allowed:
                setattr(settings, field, value)
        settings.save()
        return settings
