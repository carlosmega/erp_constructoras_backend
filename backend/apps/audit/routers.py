"""
Audit log API endpoints.
"""

from typing import Optional
from uuid import UUID

from django.http import HttpRequest
from ninja import Router, Query

from apps.audit.models import AuditActionCode
from apps.audit.schemas import AuditLogSchema, AuditLogListResponse
from apps.audit.services import AuditLogService
from core.permissions import require_authenticated

audit_router = Router(tags=['Audit'])


@audit_router.get('/', response=AuditLogListResponse)
@require_authenticated
def list_audit_logs(
    request: HttpRequest,
    entity: Optional[str] = None,
    recordid: Optional[UUID] = None,
    userid: Optional[UUID] = None,
    action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List audit logs with optional filters.

    Only System Administrator and Sales Manager can view all logs.
    Regular users can only see logs for their own actions.
    """
    user = request.user

    # Non-admin users can only see their own actions
    if user.role_name not in ['System Administrator', 'Sales Manager']:
        userid = user.systemuserid

    items = list(AuditLogService.query_logs(
        entity=entity,
        record_id=recordid,
        user_id=userid,
        action=action,
        start_date=start_date,
        end_date=end_date,
        search=search,
        limit=min(limit, 200),
        offset=offset,
    ))

    total = AuditLogService.count_logs(
        entity=entity,
        record_id=recordid,
        user_id=userid,
        action=action,
    )

    return {'items': items, 'total': total}


@audit_router.get('/entity/{entity}/{record_id}/', response=list[AuditLogSchema])
@require_authenticated
def get_record_audit_trail(
    request: HttpRequest,
    entity: str,
    record_id: UUID,
    limit: int = 50,
    offset: int = 0,
):
    """Get audit trail for a specific record.

    All authenticated users can view the audit trail of records
    they have read access to.
    """
    return list(AuditLogService.get_record_trail(
        entity=entity,
        record_id=record_id,
        limit=min(limit, 200),
        offset=offset,
    ))
