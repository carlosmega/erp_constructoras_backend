"""Cashflow / PNT API routers."""
from uuid import UUID
from ninja import Router
from django.http import HttpRequest

from apps.cashflow.models import ProjectFinancialSettings
from apps.cashflow.schemas import (
    FinancialSettingsDto,
    UpdateFinancialSettingsDto,
)
from apps.cashflow.services.financial_settings import FinancialSettingsService
from core.permissions import require_permission, Permission


cashflow_router = Router(tags=["Cashflow / PNT"])


def _serialize_settings(settings: ProjectFinancialSettings) -> dict:
    """Flatten the model into a dict matching FinancialSettingsDto.

    FinancialSettingsDto is a plain Schema (not ModelSchema) that declares
    ``projectid: UUID``, so we must resolve the FK to its primary key before
    pydantic validates the response.
    """
    return {
        'settingsid': settings.settingsid,
        'projectid': settings.projectid_id,
        'imssretentionrate': settings.imssretentionrate,
        'otherretentionrate': settings.otherretentionrate,
        'retentionreturnperiod': settings.retentionreturnperiod,
        'advanceamortizationrate': settings.advanceamortizationrate,
        'anticipoentryperiod': settings.anticipoentryperiod,
        'transversalcost': settings.transversalcost,
        'transversalwithdrawalperiod': settings.transversalwithdrawalperiod,
        'utilitycost': settings.utilitycost,
        'utilitywithdrawalperiod': settings.utilitywithdrawalperiod,
        'financecostrate': settings.financecostrate,
    }


@cashflow_router.get(
    "/projects/{project_id}/financial-settings/",
    response=FinancialSettingsDto,
)
@require_permission(Permission.CASHFLOW_READ)
def get_financial_settings(request: HttpRequest, project_id: UUID):
    """Return the project's financial settings, materializing defaults on first read."""
    settings = FinancialSettingsService.get_or_create(project_id)
    return _serialize_settings(settings)


@cashflow_router.patch(
    "/projects/{project_id}/financial-settings/",
    response=FinancialSettingsDto,
)
@require_permission(Permission.CASHFLOW_UPDATE_SETTINGS)
def update_financial_settings(
    request: HttpRequest,
    project_id: UUID,
    payload: UpdateFinancialSettingsDto,
):
    """Partially update the project's financial settings."""
    data = payload.dict(exclude_unset=True)
    settings = FinancialSettingsService.update(project_id, data)
    return _serialize_settings(settings)
