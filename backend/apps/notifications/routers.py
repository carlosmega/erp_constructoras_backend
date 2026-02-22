"""
Notification API endpoints.

All endpoints require authentication. No specific permission checks needed -
every user can manage their own notifications.
"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from apps.notifications.schemas import NotificationSchema, UnreadCountSchema, BulkIdsDto
from apps.notifications.services import NotificationService
from core.permissions import require_authenticated

notifications_router = Router(tags=["Notifications"])


@notifications_router.get("/", response=List[NotificationSchema])
@require_authenticated
def list_notifications(
    request: HttpRequest,
    is_read: Optional[bool] = None,
    typecode: Optional[str] = None,
    search: Optional[str] = None,
):
    """List notifications for the current user."""
    notifications = NotificationService.list_notifications(
        user=request.user,
        is_read=is_read,
        typecode=typecode,
        search=search,
    )
    return list(notifications)


@notifications_router.get("/unread-count", response=UnreadCountSchema)
@require_authenticated
def get_unread_count(request: HttpRequest):
    """Get unread notification count (lightweight, for bell badge polling)."""
    count = NotificationService.get_unread_count(request.user)
    return {"count": count}


@notifications_router.post("/{notification_id}/read", response=NotificationSchema)
@require_authenticated
def mark_as_read(request: HttpRequest, notification_id: UUID):
    """Mark a single notification as read."""
    notification = NotificationService.mark_as_read(notification_id, request.user)
    return notification


@notifications_router.post("/read-all", response={200: dict})
@require_authenticated
def mark_all_as_read(request: HttpRequest):
    """Mark all unread notifications as read."""
    count = NotificationService.mark_all_as_read(request.user)
    return {"count": count}


@notifications_router.post("/bulk-archive", response={200: dict})
@require_authenticated
def bulk_archive(request: HttpRequest, payload: BulkIdsDto):
    """Archive selected notifications."""
    count = NotificationService.archive_notifications(payload.ids, request.user)
    return {"count": count}


@notifications_router.delete("/bulk-delete", response={200: dict})
@require_authenticated
def bulk_delete(request: HttpRequest, payload: BulkIdsDto):
    """Delete selected notifications."""
    count = NotificationService.delete_notifications(payload.ids, request.user)
    return {"count": count}
