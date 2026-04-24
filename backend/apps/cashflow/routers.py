"""Cashflow / PNT API routers."""
import base64
import json
from typing import List, Optional
from uuid import UUID
from ninja import Router
from django.http import HttpRequest, JsonResponse

from apps.cashflow.models import ProjectBillingRule, ProjectFinancialSettings
from apps.cashflow.schemas import (
    BillingRuleDto,
    FinancialSettingsDto,
    PNTReportDto,
    ReplaceBillingRulesDto,
    UpdateFinancialSettingsDto,
)
from apps.cashflow.services.billing_rule import BillingRuleService
from apps.cashflow.services.financial_settings import FinancialSettingsService
from apps.cashflow.services.pnt_calculator import PNTCalculator
from core.exceptions import ValidationError
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


def _serialize_rule(rule: ProjectBillingRule) -> dict:
    """Flatten a billing rule to match BillingRuleDto (no projectid field)."""
    return {
        'ruleid': rule.ruleid,
        'sequence': rule.sequence,
        'percent': rule.percent,
        'lagperiods': rule.lagperiods,
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


@cashflow_router.get(
    "/projects/{project_id}/billing-rules/",
    response=List[BillingRuleDto],
)
@require_permission(Permission.CASHFLOW_READ)
def list_billing_rules(request: HttpRequest, project_id: UUID):
    """Return the project's billing rules sorted by sequence."""
    return [_serialize_rule(r) for r in BillingRuleService.list_rules(project_id)]


@cashflow_router.put(
    "/projects/{project_id}/billing-rules/",
    response=List[BillingRuleDto],
)
@require_permission(Permission.CASHFLOW_UPDATE_BILLING_RULES)
def replace_billing_rules(
    request: HttpRequest,
    project_id: UUID,
    payload: ReplaceBillingRulesDto,
):
    """Atomically replace the project's billing rules. Validates Σ=100%±0.0001."""
    rules_data = [r.dict(exclude={'ruleid'}) for r in payload.rules]
    rules = BillingRuleService.replace(project_id, rules_data)
    return [_serialize_rule(r) for r in rules]


@cashflow_router.get(
    "/projects/{project_id}/pnt/",
    response=PNTReportDto,
)
@require_permission(Permission.CASHFLOW_READ)
def get_pnt(
    request: HttpRequest,
    project_id: UUID,
    granularity: str = 'period',
    overrides: Optional[str] = None,
):
    """Return the full PNT report for a project.

    Query params:
    - granularity: 'period' (default) or 'month'
    - overrides: base64-encoded JSON with override dict (simulation, no DB writes)
    """
    if granularity not in ('period', 'month'):
        raise ValidationError("granularity must be 'period' or 'month'")

    overrides_dict = None
    if overrides:
        try:
            overrides_dict = json.loads(base64.b64decode(overrides).decode())
        except Exception as exc:
            raise ValidationError(f'overrides must be base64-encoded JSON: {exc}')

    try:
        calc = PNTCalculator(project_id)
    except ValueError as exc:
        # No periods initialized → 409 Conflict
        return JsonResponse(
            {'success': False, 'error': {'code': 'CONFLICT', 'message': str(exc)}},
            status=409,
        )

    report = calc.compute(overrides=overrides_dict, granularity=granularity)
    # Map dataclass _Report → PNTReportDto-compatible dict
    return {
        'projectid': report.projectid,
        'granularity': report.granularity,
        'periods': report.periods,
        'rows': [
            {
                'code': r.code, 'label': r.label, 'section': r.section,
                'values': r.values, 'emphasis': r.emphasis,
            }
            for r in report.rows
        ],
        'stats': report.stats,
        'generated_at': report.generated_at,
    }
