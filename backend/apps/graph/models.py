"""
Microsoft Graph integration models.

Stores OAuth2 token cache for Microsoft Graph API access per user.
"""

import uuid
from django.db import models


class MicrosoftToken(models.Model):
    """
    Stores MSAL token cache for a user's Microsoft Graph connection.

    OneToOne with SystemUser. The token_cache field contains the full
    MSAL serialized cache (access + refresh tokens). MSAL handles
    refresh internally via acquire_token_silent().
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    userid = models.OneToOneField(
        'users.SystemUser',
        on_delete=models.CASCADE,
        related_name='microsoft_token',
        db_column='userid',
    )
    microsoft_user_id = models.CharField(
        max_length=255,
        help_text='Azure AD Object ID',
    )
    microsoft_email = models.EmailField(
        help_text='Microsoft account email (display only)',
    )
    token_cache = models.TextField(
        help_text='MSAL serialized token cache (contains access + refresh tokens)',
    )
    connected_on = models.DateTimeField(auto_now_add=True)
    last_sync_on = models.DateTimeField(null=True, blank=True)
    last_sync_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'microsoft_token'
        verbose_name = 'Microsoft Token'
        verbose_name_plural = 'Microsoft Tokens'

    def __str__(self):
        return f"Microsoft: {self.microsoft_email} (User: {self.userid_id})"


class SSOToken(models.Model):
    """
    Temporary SSO token for Microsoft SSO login flow.

    Created after successful Microsoft OAuth callback. Used by both the browser
    (to create Django session) and NextAuth server (to get user info for JWT).
    Expires after 5 minutes (validated in code).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    userid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.CASCADE,
        related_name='sso_tokens',
        db_column='userid',
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sso_token'
        verbose_name = 'SSO Token'
        verbose_name_plural = 'SSO Tokens'

    def __str__(self):
        return f"SSOToken for user {self.userid_id}"
