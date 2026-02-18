"""
Custom exception classes for CRM Backend Foundation.

Provides standardized exception handling across the application.
"""

from typing import Any, Dict, Optional


class CRMBaseException(Exception):
    """Base exception for all CRM-specific exceptions."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class PermissionDenied(CRMBaseException):
    """
    Raised when a user attempts an operation they don't have permission for.

    HTTP Status: 403 Forbidden
    """

    def __init__(self, message: str = "You do not have permission to perform this action", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class ValidationError(CRMBaseException):
    """
    Raised when input data fails validation.

    HTTP Status: 400 Bad Request
    """

    def __init__(self, message: str = "Invalid input data", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class NotFound(CRMBaseException):
    """
    Raised when a requested resource cannot be found.

    HTTP Status: 404 Not Found
    """

    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class AuthenticationFailed(CRMBaseException):
    """
    Raised when authentication credentials are invalid.

    HTTP Status: 401 Unauthorized
    """

    def __init__(self, message: str = "Invalid credentials", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class AccountLocked(CRMBaseException):
    """
    Raised when a user account is locked due to failed login attempts.

    HTTP Status: 401 Unauthorized
    """

    def __init__(self, message: str = "Account has been locked due to multiple failed login attempts", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class AccountDisabled(CRMBaseException):
    """
    Raised when attempting to authenticate with a disabled account.

    HTTP Status: 401 Unauthorized
    """

    def __init__(self, message: str = "This account has been disabled", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
