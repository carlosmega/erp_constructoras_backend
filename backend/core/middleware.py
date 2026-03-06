"""
Custom middleware for CRM Backend Foundation.

Provides audit trail support and API URL normalization.
"""

import threading
from typing import Optional
from django.urls import resolve, Resolver404

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


class ApiTrailingSlashMiddleware:
    """
    Rewrites API mutation URLs to include trailing slash when needed.

    Django's CommonMiddleware with APPEND_SLASH=True redirects GET requests
    to trailing-slash URLs, but raises RuntimeError for POST/PATCH/PUT/DELETE.
    This middleware intercepts mutation requests and rewrites the URL path
    (not redirect) to include the trailing slash if a matching route exists.

    Must be placed BEFORE django.middleware.common.CommonMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method in ('POST', 'PATCH', 'PUT', 'DELETE')
            and not request.path.endswith('/')
            and request.path.startswith('/api/')
        ):
            try:
                resolve(request.path + '/')
                # Route exists with trailing slash — rewrite in-place
                request.path_info = request.path_info + '/'
                request.path = request.path + '/'
            except Resolver404:
                pass  # No match with trailing slash either; leave as-is
        return self.get_response(request)


class DevAutoLoginMiddleware:
    """
    Auto-authenticate requests with the first SystemUser (admin) in DEBUG mode.

    This enables frontend development without a real login flow.
    Only active when settings.DEBUG is True and the request is not already
    authenticated.

    Must be placed AFTER AuthenticationMiddleware in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._admin_user = None

    def __call__(self, request):
        from django.conf import settings

        if settings.DEBUG and hasattr(request, 'user') and not request.user.is_authenticated:
            if self._admin_user is None:
                from apps.users.models import SystemUser
                self._admin_user = (
                    SystemUser.objects
                    .select_related('securityroleid')
                    .filter(isdisabled=False)
                    .first()
                )
            if self._admin_user:
                request.user = self._admin_user

        return self.get_response(request)


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
