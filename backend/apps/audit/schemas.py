"""
Audit log schemas (Django Ninja DTOs).
"""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from ninja import Schema


class AuditFieldChangeSchema(Schema):
    """A single field-level change."""
    field: str
    old: Any = None
    new: Any = None


class AuditLogSchema(Schema):
    """Full audit log entry response."""
    auditid: UUID
    action: str
    entity: str
    recordid: UUID
    recordname: str = ''
    userid: Optional[UUID] = None
    username: str = ''
    changes: Optional[List[AuditFieldChangeSchema]] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    message: str = ''
    ipaddress: Optional[str] = None
    timestamp: datetime

    @staticmethod
    def resolve_userid(obj):
        return obj.userid_id


class AuditLogListResponse(Schema):
    """Paginated audit log list."""
    items: List[AuditLogSchema]
    total: int
