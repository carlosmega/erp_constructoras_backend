"""
Audit service layer.

Provides:
- AuditLogService: CRUD and query for audit logs
- audit_action: Decorator for automatic audit logging on service methods
- log_action: Simple function for manual audit logging
"""

import json
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from django.db.models import QuerySet

from apps.audit.models import AuditLog, AuditActionCode
from apps.users.models import SystemUser
from core.middleware import get_current_user

logger = logging.getLogger(__name__)


# ============================================================================
# Serialization helpers
# ============================================================================

def _serialize_value(value: Any) -> Any:
    """Convert a model field value to JSON-safe representation."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float, bool, str)):
        return value
    # Decimal, date, etc.
    return str(value)


def _get_model_snapshot(instance, fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """Take a JSON-serializable snapshot of a model instance's fields.

    Args:
        instance: Django model instance
        fields: Specific fields to capture. If None, captures all concrete fields
                 except large text/binary blobs.
    """
    if instance is None:
        return {}

    skip_fields = {'token_cache', 'password'}  # Never audit sensitive fields
    result = {}

    if fields:
        for f in fields:
            if f in skip_fields:
                continue
            val = getattr(instance, f, None)
            # For FK fields, try to get the raw DB column value
            if hasattr(instance, f'{f}_id'):
                val = getattr(instance, f'{f}_id', val)
            result[f] = _serialize_value(val)
    else:
        for field in instance._meta.concrete_fields:
            name = field.attname  # Use attname for FK → gets the _id column
            if name in skip_fields:
                continue
            result[name] = _serialize_value(getattr(instance, name, None))

    return result


def _compute_changes(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compute field-level diff between two snapshots.

    Returns list of {field, old, new} dicts for changed fields only.
    Ignores modifiedon/modifiedby (noise).
    """
    ignore = {'modifiedon', 'modifiedby'}
    changes = []
    all_keys = set(old.keys()) | set(new.keys())
    for key in sorted(all_keys):
        if key in ignore:
            continue
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes.append({'field': key, 'old': old_val, 'new': new_val})
    return changes


def _get_ip_address(request=None) -> Optional[str]:
    """Extract client IP from request if available."""
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_record_name(instance) -> str:
    """Try to extract a human-readable name from a model instance."""
    for attr in ('name', 'fullname', 'subject', 'projectnumber', 'rmanumber', 'folio'):
        val = getattr(instance, attr, None)
        if val:
            return str(val)[:255]
    return str(getattr(instance, 'pk', ''))


# ============================================================================
# Core logging function
# ============================================================================

def log_action(
    action: str,
    entity: str,
    record_id,
    user: Optional[SystemUser] = None,
    record_name: str = '',
    changes: Optional[List[Dict]] = None,
    old_values: Optional[Dict] = None,
    new_values: Optional[Dict] = None,
    message: str = '',
    request=None,
) -> AuditLog:
    """Create an audit log entry.

    This is the low-level function. Prefer @audit_action decorator for services.

    Args:
        action: AuditActionCode value (e.g. 'create', 'update', 'delete')
        entity: Entity type string (e.g. 'lead', 'opportunity')
        record_id: UUID of the affected record
        user: User who performed the action (falls back to thread-local)
        record_name: Human-readable name of the record
        changes: List of {field, old, new} dicts
        old_values: Full snapshot before the action
        new_values: Full snapshot after the action
        message: Optional human-readable description
        request: Optional HttpRequest for IP extraction
    """
    if user is None:
        user = get_current_user()

    username = ''
    if user:
        username = getattr(user, 'fullname', '') or str(user)

    try:
        entry = AuditLog.objects.create(
            action=action,
            entity=entity,
            recordid=record_id,
            recordname=record_name[:255] if record_name else '',
            userid=user,
            username=username[:200],
            changes=changes,
            old_values=old_values,
            new_values=new_values,
            message=message[:500] if message else '',
            ipaddress=_get_ip_address(request),
        )
        return entry
    except Exception:
        logger.exception('Failed to create audit log entry for %s %s:%s', action, entity, record_id)
        return None


# ============================================================================
# @audit_action decorator
# ============================================================================

def audit_action(action: str, entity: str, record_arg: str = None, id_field: str = None):
    """Decorator for automatic audit logging on service methods.

    Captures old state (for updates/deletes), runs the method, captures new state,
    computes diff, and writes an AuditLog entry. Never blocks the main operation —
    if audit logging fails, the exception is logged but the result is returned.

    Args:
        action: AuditActionCode value (e.g. 'create', 'update', 'delete', 'qualify')
        entity: Entity type (e.g. 'lead', 'opportunity')
        record_arg: Name of the kwarg or positional arg that holds the record ID
                     (e.g. 'lead_id'). If None, tries to infer from entity + '_id'.
        id_field: Name of the PK field on the model (e.g. 'leadid'). If None, inferred
                  as entity + 'id' (no underscore, CDS style).

    Usage:
        class LeadService:
            @staticmethod
            @audit_action(action='update', entity='lead', record_arg='lead_id')
            def update_lead(lead_id, dto, user):
                ...
                return lead

            @staticmethod
            @audit_action(action='create', entity='lead')
            def create_lead(dto, user):
                ...
                return lead  # PK extracted from returned instance
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Resolve the record ID from arguments
            _record_arg = record_arg or f'{entity}_id'
            _id_field = id_field or f'{entity}id'
            record_id = None
            old_snapshot = None
            model_class = None

            # Try to get record_id from kwargs or positional args
            if _record_arg in kwargs:
                record_id = kwargs[_record_arg]
            else:
                # Try positional: for @staticmethod, first arg after self/cls
                # Service methods are @staticmethod, so args[0] is typically the id or dto
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if _record_arg in params:
                    idx = params.index(_record_arg)
                    if idx < len(args):
                        record_id = args[idx]

            # For update/delete: capture old state before the method runs
            needs_old = action in ('update', 'delete', 'assign', 'qualify', 'close',
                                   'win', 'lose', 'cancel', 'activate', 'deactivate',
                                   'approve', 'reject', 'convert', 'classify', 'verify')
            if needs_old and record_id:
                try:
                    from django.apps import apps
                    # Find the model class by looking for entity+'id' as PK
                    for model in apps.get_models():
                        if hasattr(model, _id_field) and model._meta.pk and model._meta.pk.name == _id_field:
                            model_class = model
                            break
                    if model_class:
                        instance = model_class.objects.get(**{_id_field: record_id})
                        old_snapshot = _get_model_snapshot(instance)
                except Exception:
                    logger.debug('Could not capture old state for audit: %s %s', entity, record_id)

            # Execute the actual service method
            result = func(*args, **kwargs)

            # After execution: capture new state and write audit log
            try:
                new_snapshot = None
                record_name = ''

                if action == 'delete':
                    # For delete, result might be None or the deleted instance
                    _write_audit(action, entity, record_id, old_snapshot, None, None)
                    return result

                # The result should be the model instance
                if result and hasattr(result, 'pk'):
                    if record_id is None:
                        record_id = result.pk
                    new_snapshot = _get_model_snapshot(result)
                    record_name = _get_record_name(result)

                    if needs_old and old_snapshot:
                        changes = _compute_changes(old_snapshot, new_snapshot)
                        if changes:  # Only log if something actually changed
                            _write_audit(action, entity, record_id, old_snapshot, new_snapshot, changes, record_name)
                    elif action == 'create':
                        _write_audit('create', entity, record_id, None, new_snapshot, None, record_name)
                    else:
                        # State transition without old snapshot
                        _write_audit(action, entity, record_id, old_snapshot, new_snapshot, None, record_name)
                elif record_id:
                    # Result is not a model (e.g. dict or tuple) — log what we can
                    _write_audit(action, entity, record_id, old_snapshot, None, None)
            except Exception:
                logger.exception('Audit logging failed for %s %s', action, entity)

            return result
        return wrapper
    return decorator


def _write_audit(action, entity, record_id, old_snapshot, new_snapshot, changes, record_name=''):
    """Helper to write an audit entry using log_action."""
    user = get_current_user()
    msg_parts = [action.capitalize(), entity]
    if record_name:
        msg_parts.append(f'"{record_name}"')
    message = ' '.join(msg_parts)

    log_action(
        action=action,
        entity=entity,
        record_id=record_id,
        user=user,
        record_name=record_name,
        changes=changes,
        old_values=old_snapshot if action in ('delete', 'update') else None,
        new_values=new_snapshot if action in ('create',) else None,
        message=message,
    )


# ============================================================================
# Query service
# ============================================================================

class AuditLogService:
    """Query and manage audit logs."""

    @staticmethod
    def get_record_trail(
        entity: str,
        record_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> QuerySet[AuditLog]:
        """Get audit trail for a specific record."""
        return (
            AuditLog.objects
            .filter(entity=entity, recordid=record_id)
            .select_related('userid')
            .order_by('-timestamp')[offset:offset + limit]
        )

    @staticmethod
    def query_logs(
        entity: Optional[str] = None,
        record_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> QuerySet[AuditLog]:
        """Query audit logs with filters."""
        qs = AuditLog.objects.select_related('userid')

        if entity:
            qs = qs.filter(entity=entity)
        if record_id:
            qs = qs.filter(recordid=record_id)
        if user_id:
            qs = qs.filter(userid_id=user_id)
        if action:
            qs = qs.filter(action=action)
        if start_date:
            qs = qs.filter(timestamp__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__lte=end_date)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(recordname__icontains=search) |
                Q(username__icontains=search) |
                Q(message__icontains=search)
            )

        return qs.order_by('-timestamp')[offset:offset + limit]

    @staticmethod
    def count_logs(
        entity: Optional[str] = None,
        record_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        action: Optional[str] = None,
    ) -> int:
        """Count audit logs matching filters."""
        qs = AuditLog.objects.all()
        if entity:
            qs = qs.filter(entity=entity)
        if record_id:
            qs = qs.filter(recordid=record_id)
        if user_id:
            qs = qs.filter(userid_id=user_id)
        if action:
            qs = qs.filter(action=action)
        return qs.count()
