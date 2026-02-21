"""
Microsoft Graph integration schemas (Django Ninja DTOs).
"""

from ninja import Schema
from typing import Optional
from datetime import datetime


class ConnectUrlResponse(Schema):
    """Response with Microsoft OAuth2 authorization URL."""
    authorization_url: str


class ConnectionStatusResponse(Schema):
    """Response with current Microsoft Graph connection status."""
    connected: bool
    microsoft_email: Optional[str] = None
    connected_on: Optional[datetime] = None
    last_sync_on: Optional[datetime] = None
    last_sync_count: int = 0


class SyncResultResponse(Schema):
    """Response with email sync results."""
    success: bool
    total_fetched: int = 0
    new_emails: int = 0
    duplicates_skipped: int = 0
    matched_emails: int = 0
    unmatched_emails: int = 0
    errors: list[str] = []


class DisconnectResponse(Schema):
    """Response after disconnecting Microsoft account."""
    success: bool
    message: str


class SSOInitResponse(Schema):
    """Response with Microsoft SSO authorization URL."""
    authorization_url: str


class SSOExchangeDto(Schema):
    """Request body for SSO token exchange."""
    token: str
