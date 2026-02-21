"""
Microsoft Graph integration API endpoints.

OAuth2 flow + email sync endpoints.
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from ninja import Router

from apps.graph.schemas import (
    ConnectUrlResponse,
    ConnectionStatusResponse,
    DisconnectResponse,
    SyncResultResponse,
)
from apps.graph.services import GraphEmailSyncService, MicrosoftAuthService, MicrosoftSSOService
from core.exceptions import ValidationError
from core.permissions import require_authenticated

logger = logging.getLogger(__name__)

graph_router = Router(tags=['Microsoft Graph'])


@graph_router.get('/connect', response=ConnectUrlResponse)
@require_authenticated
def get_connect_url(request: HttpRequest):
    """Get Microsoft OAuth2 authorization URL.

    Returns a URL that the frontend should redirect the user to
    for Microsoft login and consent.
    """
    url = MicrosoftAuthService.get_authorization_url(request.user)
    return {'authorization_url': url}


@graph_router.get('/callback', auth=None, include_in_schema=False)
def oauth_callback(request: HttpRequest, code: str = '', state: str = '', error: str = '', error_description: str = ''):
    """OAuth2 callback from Microsoft.

    Public endpoint (no auth required) — validation is done via signed state parameter.
    Redirects to frontend with success or error query params.
    """
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    redirect_base = f'{frontend_url}/activities'

    # Handle error from Microsoft
    if error:
        logger.warning('Microsoft OAuth error: %s — %s', error, error_description)
        params = urlencode({'graph_error': error_description or error})
        return HttpResponseRedirect(f'{redirect_base}?{params}')

    if not code or not state:
        params = urlencode({'graph_error': 'Missing authorization code or state'})
        return HttpResponseRedirect(f'{redirect_base}?{params}')

    # Determine flow type by state prefix
    is_sso = state.startswith('sso|')

    try:
        if is_sso:
            # SSO flow → create SSOToken and redirect to login page
            sso_token = MicrosoftSSOService.handle_sso_callback(code=code, state=state)
            return HttpResponseRedirect(f'{frontend_url}/login?sso_token={sso_token.token}')
        else:
            # Email sync flow (existing behavior)
            MicrosoftAuthService.handle_callback(code=code, state=state)
            return HttpResponseRedirect(f'{redirect_base}?graph_connected=true')
    except ValidationError as e:
        logger.error('OAuth callback failed: %s', e)
        error_redirect = f'{frontend_url}/login' if is_sso else redirect_base
        params = urlencode({'graph_error' if not is_sso else 'sso_error': str(e)})
        return HttpResponseRedirect(f'{error_redirect}?{params}')
    except Exception as e:
        logger.exception('Unexpected error in OAuth callback: %s', e)
        error_redirect = f'{frontend_url}/login' if is_sso else redirect_base
        error_key = 'sso_error' if is_sso else 'graph_error'
        error_msg = f'{type(e).__name__}: {e}' if settings.DEBUG else 'An unexpected error occurred during authentication'
        params = urlencode({error_key: error_msg})
        return HttpResponseRedirect(f'{error_redirect}?{params}')


@graph_router.get('/status', response=ConnectionStatusResponse)
@require_authenticated
def get_connection_status(request: HttpRequest):
    """Get Microsoft Graph connection status for the current user."""
    return MicrosoftAuthService.get_connection_status(request.user)


@graph_router.post('/sync', response=SyncResultResponse)
@require_authenticated
def sync_emails(request: HttpRequest):
    """Trigger on-demand email sync from Microsoft Graph.

    Fetches the last 30 days of emails from the user's mailbox
    and processes them through the CRM email matching pipeline.
    """
    return GraphEmailSyncService.sync_emails(request.user)


@graph_router.post('/disconnect', response=DisconnectResponse)
@require_authenticated
def disconnect(request: HttpRequest):
    """Disconnect Microsoft account from CRM."""
    MicrosoftAuthService.disconnect(request.user)
    return {'success': True, 'message': 'Microsoft account disconnected successfully'}
