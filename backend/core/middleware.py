"""
Custom middleware for CRM Backend Foundation.

Provides audit trail support by capturing current user context.
"""

import threading
from typing import Optional

# Thread-local storage for current user
_thread_locals = threading.local()


def get_current_user():
    """
    Get the currently authenticated user from thread-local storage.

    Returns:
        SystemUser instance or None if no user is authenticated

    Usage in services:
        from core.middleware import get_current_user

        current_user = get_current_user()
        entity.createdby = current_user
    """
    return getattr(_thread_locals, 'user', None)


def set_current_user(user):
    """
    Set the current user in thread-local storage.

    Args:
        user: SystemUser instance or None
    """
    _thread_locals.user = user


class AuditMiddleware:
    """
    Middleware to capture the current authenticated user for audit trail.

    This middleware stores the authenticated user in thread-local storage,
    making it available to service layer methods for populating audit fields
    (createdby, modifiedby).

    The middleware:
    1. Captures request.user if authenticated
    2. Stores in thread-local storage
    3. Processes the request
    4. Clears thread-local storage

    Note:
        - Must be placed after AuthenticationMiddleware in MIDDLEWARE
        - Thread-local storage ensures thread safety
        - Automatically cleared after each request
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Store authenticated user in thread-local storage
        if hasattr(request, 'user') and request.user.is_authenticated:
            set_current_user(request.user)
        else:
            set_current_user(None)

        # Process request
        response = self.get_response(request)

        # Clear thread-local storage
        set_current_user(None)

        return response
