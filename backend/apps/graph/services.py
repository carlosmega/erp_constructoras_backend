"""
Microsoft Graph integration services.

MicrosoftAuthService — OAuth2 flow (connect, callback, disconnect)
GraphEmailSyncService — Sync emails from Graph API into CRM
"""

import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

import msal
import requests
from django.conf import settings
from django.utils import timezone as dj_timezone

from apps.activities.models import (
    Activity,
    ActivityStateCode,
    ActivityTypeCode,
    Email,
)
from apps.graph.models import MicrosoftToken, SSOToken
from apps.users.models import SystemUser
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_BASE_URL = 'https://graph.microsoft.com/v1.0'

# Scopes needed for email sync
SCOPES = ['User.Read', 'Mail.Read', 'Mail.Read.Shared']

# Fields to request from Graph API /me/messages
MESSAGE_SELECT_FIELDS = (
    'id,subject,body,from,toRecipients,ccRecipients,'
    'internetMessageId,internetMessageHeaders,'
    'receivedDateTime,sentDateTime,isDraft'
)


class MicrosoftAuthService:
    """Handles OAuth2 flow with Azure AD via MSAL."""

    @staticmethod
    def _get_msal_app(cache=None):
        """Create MSAL ConfidentialClientApplication."""
        authority = f'https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}'
        return msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=authority,
            token_cache=cache,
        )

    @staticmethod
    def _sign_state(data: str) -> str:
        """Sign state parameter with HMAC-SHA256."""
        return hmac.new(
            settings.SECRET_KEY.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def get_authorization_url(user: SystemUser) -> str:
        """Generate Microsoft OAuth2 authorization URL.

        State contains user ID + timestamp, signed with HMAC.
        """
        app = MicrosoftAuthService._get_msal_app()

        # Build signed state: userId|timestamp|signature
        timestamp = str(int(time.time()))
        state_data = f'{user.systemuserid}|{timestamp}'
        signature = MicrosoftAuthService._sign_state(state_data)
        state = f'{state_data}|{signature}'

        result = app.get_authorization_request_url(
            scopes=SCOPES,
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
            state=state,
        )
        return result

    @staticmethod
    def validate_state(state: str) -> SystemUser:
        """Validate OAuth2 state parameter and return the user.

        Raises ValidationError if state is invalid or expired.
        """
        try:
            parts = state.split('|')
            if len(parts) != 3:
                raise ValidationError('Invalid OAuth state format')

            user_id, timestamp, signature = parts

            # Verify signature
            state_data = f'{user_id}|{timestamp}'
            expected_sig = MicrosoftAuthService._sign_state(state_data)
            if not hmac.compare_digest(signature, expected_sig):
                raise ValidationError('Invalid OAuth state signature')

            # Check expiry (10 minutes)
            state_time = int(timestamp)
            if time.time() - state_time > 600:
                raise ValidationError('OAuth state expired')

            user = SystemUser.objects.get(systemuserid=user_id)
            return user

        except SystemUser.DoesNotExist:
            raise ValidationError('User not found in OAuth state')
        except (ValueError, IndexError):
            raise ValidationError('Malformed OAuth state')

    @staticmethod
    def handle_callback(code: str, state: str) -> MicrosoftToken:
        """Exchange authorization code for tokens and save to DB.

        Returns the created/updated MicrosoftToken.
        """
        user = MicrosoftAuthService.validate_state(state)

        # Create MSAL app with fresh cache
        cache = msal.SerializableTokenCache()
        app = MicrosoftAuthService._get_msal_app(cache=cache)

        # Exchange code for tokens
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPES,
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
        )

        if 'error' in result:
            error_desc = result.get('error_description', result.get('error', 'Unknown error'))
            logger.error('MSAL token acquisition failed: %s', error_desc)
            raise ValidationError(f'Microsoft authentication failed: {error_desc}')

        # Get user profile from Graph API
        access_token = result['access_token']
        headers = {'Authorization': f'Bearer {access_token}'}
        profile_resp = requests.get(f'{GRAPH_BASE_URL}/me', headers=headers, timeout=10)
        profile_resp.raise_for_status()
        profile = profile_resp.json()

        microsoft_user_id = profile.get('id', '')
        microsoft_email = profile.get('mail') or profile.get('userPrincipalName', '')

        # Save or update token
        token, _created = MicrosoftToken.objects.update_or_create(
            userid=user,
            defaults={
                'microsoft_user_id': microsoft_user_id,
                'microsoft_email': microsoft_email,
                'token_cache': cache.serialize(),
            },
        )

        logger.info('Microsoft account connected for user %s (%s)', user.systemuserid, microsoft_email)
        return token

    @staticmethod
    def get_authenticated_session(user: SystemUser) -> requests.Session:
        """Get a requests.Session with valid Bearer token for Graph API.

        Uses MSAL's acquire_token_silent to refresh if needed.
        Raises ValidationError if no token or refresh fails.
        """
        try:
            token_record = MicrosoftToken.objects.get(userid=user)
        except MicrosoftToken.DoesNotExist:
            raise ValidationError('Microsoft account not connected. Please connect first.')

        # Load cache from DB
        cache = msal.SerializableTokenCache()
        cache.deserialize(token_record.token_cache)

        app = MicrosoftAuthService._get_msal_app(cache=cache)

        # Get accounts from cache
        accounts = app.get_accounts()
        if not accounts:
            # Cache has no accounts — token expired completely
            token_record.delete()
            raise ValidationError('Microsoft session expired. Please reconnect your account.')

        # Try silent token acquisition (uses refresh token if access token expired)
        result = app.acquire_token_silent(
            scopes=SCOPES,
            account=accounts[0],
        )

        if not result or 'access_token' not in result:
            token_record.delete()
            raise ValidationError('Microsoft token refresh failed. Please reconnect your account.')

        # Save updated cache (refresh token may have been rotated)
        if cache.has_state_changed:
            token_record.token_cache = cache.serialize()
            token_record.save(update_fields=['token_cache'])

        # Build authenticated session
        session = requests.Session()
        session.headers['Authorization'] = f'Bearer {result["access_token"]}'
        return session

    @staticmethod
    def get_connection_status(user: SystemUser) -> dict:
        """Get connection status for a user."""
        try:
            token = MicrosoftToken.objects.get(userid=user)
            return {
                'connected': True,
                'microsoft_email': token.microsoft_email,
                'connected_on': token.connected_on,
                'last_sync_on': token.last_sync_on,
                'last_sync_count': token.last_sync_count,
            }
        except MicrosoftToken.DoesNotExist:
            return {
                'connected': False,
                'microsoft_email': None,
                'connected_on': None,
                'last_sync_on': None,
                'last_sync_count': 0,
            }

    @staticmethod
    def disconnect(user: SystemUser) -> None:
        """Remove Microsoft connection for a user."""
        deleted_count, _ = MicrosoftToken.objects.filter(userid=user).delete()
        if deleted_count == 0:
            raise ValidationError('No Microsoft account connected.')
        logger.info('Microsoft account disconnected for user %s', user.systemuserid)


class MicrosoftSSOService:
    """Handles Microsoft SSO login flow.

    Reuses MicrosoftAuthService MSAL app. Creates temporary SSOToken
    that both the browser and NextAuth server use to authenticate.
    """

    # Request full scopes at SSO login so email sync is auto-connected
    SSO_SCOPES = SCOPES  # ['User.Read', 'Mail.Read', 'Mail.Read.Shared']
    SSO_TOKEN_TTL_SECONDS = 300  # 5 minutes

    @staticmethod
    def get_sso_authorization_url() -> str:
        """Generate Microsoft OAuth2 authorization URL for SSO login.

        State uses 'sso|' prefix to distinguish from email-sync flow.
        No user ID in state because user is not logged in yet.
        """
        app = MicrosoftAuthService._get_msal_app()

        # Build signed state: sso|nonce|timestamp|signature
        nonce = secrets.token_urlsafe(16)
        timestamp = str(int(time.time()))
        state_data = f'sso|{nonce}|{timestamp}'
        signature = MicrosoftAuthService._sign_state(state_data)
        state = f'{state_data}|{signature}'

        result = app.get_authorization_request_url(
            scopes=MicrosoftSSOService.SSO_SCOPES,
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
            state=state,
        )
        return result

    @staticmethod
    def validate_sso_state(state: str) -> None:
        """Validate SSO OAuth2 state parameter.

        Raises ValidationError if state is invalid or expired.
        """
        try:
            parts = state.split('|')
            if len(parts) != 4:
                raise ValidationError('Invalid SSO state format')

            prefix, nonce, timestamp, signature = parts

            if prefix != 'sso':
                raise ValidationError('Invalid SSO state prefix')

            # Verify signature
            state_data = f'{prefix}|{nonce}|{timestamp}'
            expected_sig = MicrosoftAuthService._sign_state(state_data)
            if not hmac.compare_digest(signature, expected_sig):
                raise ValidationError('Invalid SSO state signature')

            # Check expiry (10 minutes)
            state_time = int(timestamp)
            if time.time() - state_time > 600:
                raise ValidationError('SSO state expired')

        except (ValueError, IndexError):
            raise ValidationError('Malformed SSO state')

    @staticmethod
    def handle_sso_callback(code: str, state: str) -> SSOToken:
        """Handle SSO OAuth2 callback.

        Validates state, exchanges code for token, fetches user profile,
        looks up SystemUser by email, creates SSOToken.
        Also saves MicrosoftToken so Graph API email access is auto-connected.

        Returns SSOToken instance.
        Raises ValidationError if user not found or auth fails.
        """
        MicrosoftSSOService.validate_sso_state(state)

        # Exchange code for tokens — use a serializable cache so we can
        # persist the refresh token for Graph API email access
        cache = msal.SerializableTokenCache()
        app = MicrosoftAuthService._get_msal_app(cache=cache)
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=MicrosoftSSOService.SSO_SCOPES,
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
        )

        if 'error' in result:
            error_desc = result.get('error_description', result.get('error', 'Unknown error'))
            logger.error('MSAL SSO token acquisition failed: %s', error_desc)
            raise ValidationError(f'Microsoft authentication failed: {error_desc}')

        # Get user profile from Graph API
        access_token = result.get('access_token')
        if not access_token:
            logger.error('MSAL SSO: no access_token in result. Keys: %s', list(result.keys()))
            raise ValidationError('Microsoft authentication failed: no access token received')

        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            profile_resp = requests.get(f'{GRAPH_BASE_URL}/me', headers=headers, timeout=10)
            profile_resp.raise_for_status()
        except requests.RequestException as e:
            logger.error('Graph API /me request failed during SSO: %s', e)
            raise ValidationError(f'Failed to fetch Microsoft profile: {e}')
        profile = profile_resp.json()

        microsoft_email = profile.get('mail') or profile.get('userPrincipalName', '')
        if not microsoft_email:
            raise ValidationError('Could not retrieve email from Microsoft account')

        # Find SystemUser by email
        try:
            user = SystemUser.objects.get(emailaddress1__iexact=microsoft_email)
        except SystemUser.DoesNotExist:
            raise ValidationError(
                f'No CRM account found for this Microsoft email ({microsoft_email}). '
                'Contact your administrator to create an account.'
            )

        # Check if user is disabled
        if user.isdisabled:
            raise ValidationError('This account is disabled. Contact your administrator.')

        # Check if account is locked
        if user.is_locked:
            raise ValidationError('This account is locked. Contact your administrator.')

        # Auto-connect Graph API email access (saves MicrosoftToken with refresh token)
        microsoft_user_id = profile.get('id', '')
        try:
            MicrosoftToken.objects.update_or_create(
                userid=user,
                defaults={
                    'microsoft_user_id': microsoft_user_id,
                    'microsoft_email': microsoft_email,
                    'token_cache': cache.serialize(),
                },
            )
            logger.info('Graph API auto-connected for user %s (%s)', user.systemuserid, microsoft_email)
        except Exception as e:
            # Non-fatal: SSO login should still work even if Graph token save fails
            logger.warning('Failed to auto-connect Graph API for user %s: %s', user.systemuserid, e)

        # Create SSO token
        token_value = secrets.token_urlsafe(48)
        sso_token = SSOToken.objects.create(
            userid=user,
            token=token_value,
        )

        logger.info('SSO token created for user %s (%s)', user.systemuserid, microsoft_email)
        return sso_token

    @staticmethod
    def exchange_sso_token(token_value: str, request) -> SystemUser:
        """Exchange SSO token for Django session.

        Validates token exists and is not expired (<5 min).
        Creates Django session via django.contrib.auth.login().
        Returns the authenticated SystemUser.

        Called twice in quick succession (browser + NextAuth server),
        so we avoid unnecessary DB writes to prevent SQLite locking.

        Raises ValidationError if token invalid/expired.
        """
        try:
            sso_token = SSOToken.objects.select_related('userid', 'userid__securityroleid').get(
                token=token_value
            )
        except SSOToken.DoesNotExist:
            raise ValidationError('Invalid SSO token')

        # Check expiry
        age = (dj_timezone.now() - sso_token.created_on).total_seconds()
        if age > MicrosoftSSOService.SSO_TOKEN_TTL_SECONDS:
            sso_token.delete()
            raise ValidationError('SSO token expired')

        user = sso_token.userid

        # Verify user is still active
        if user.isdisabled:
            raise ValidationError('This account is disabled')
        if user.is_locked:
            raise ValidationError('This account is locked')

        # Create Django session — disconnect update_last_login signal
        # to prevent concurrent DB writes (browser + NextAuth call simultaneously)
        from django.contrib.auth import login as django_login, user_logged_in
        from django.contrib.auth.models import update_last_login

        user_logged_in.disconnect(update_last_login)
        try:
            django_login(request, user)
        finally:
            user_logged_in.connect(update_last_login)

        logger.info('SSO token exchanged for user %s', user.systemuserid)
        return user


class GraphProjectEmailService:
    """Proxy fetch emails from project shared mailboxes via Graph API."""

    # Fields to request for project mailbox listing
    PROJECT_MESSAGE_FIELDS = (
        'id,subject,from,toRecipients,receivedDateTime,'
        'bodyPreview,hasAttachments,isRead,importance,webLink'
    )

    @staticmethod
    def fetch_project_emails(
        user,
        project_email: str,
        top: int = 50,
        skip: int = 0,
        search: str | None = None,
    ) -> tuple[list[dict], int, str | None]:
        """Fetch emails from a project's shared mailbox via Graph API.

        Returns (emails_list, total_count, next_link).
        """
        session = MicrosoftAuthService.get_authenticated_session(user)
        url = f'{GRAPH_BASE_URL}/users/{project_email}/messages'
        params = {
            '$top': str(top),
            '$skip': str(skip),
            '$select': GraphProjectEmailService.PROJECT_MESSAGE_FIELDS,
            '$orderby': 'receivedDateTime desc',
        }
        if search:
            params['$search'] = f'"{search}"'
            params['$orderby'] = ''  # $search and $orderby conflict in Graph API

        # Remove empty params
        params = {k: v for k, v in params.items() if v}

        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        return (
            data.get('value', []),
            data.get('@odata.count', 0),
            data.get('@odata.nextLink'),
        )

    @staticmethod
    def map_graph_email(msg: dict) -> dict:
        """Map a Graph API message to ProjectEmailSchema format."""
        from_data = msg.get('from', {}).get('emailAddress', {})
        to_list = [
            r.get('emailAddress', {}).get('address', '')
            for r in msg.get('toRecipients', [])
            if r.get('emailAddress', {}).get('address')
        ]

        return {
            'messageid': msg.get('id', ''),
            'subject': msg.get('subject', '(Sin asunto)'),
            'sender': from_data.get('address', ''),
            'senderName': from_data.get('name'),
            'toRecipients': ', '.join(to_list),
            'receivedDateTime': msg.get('receivedDateTime', ''),
            'bodyPreview': msg.get('bodyPreview', ''),
            'hasAttachments': msg.get('hasAttachments', False),
            'isRead': msg.get('isRead', False),
            'importance': msg.get('importance', 'normal'),
            'webLink': msg.get('webLink', ''),
        }


class GraphEmailSyncService:
    """Syncs emails from Microsoft Graph API into CRM activities."""

    @staticmethod
    def sync_emails(user: SystemUser, max_results: int = 50) -> dict:
        """Sync emails from Microsoft Graph into CRM.

        1. Get authenticated session
        2. Fetch messages from Graph API (last 30 days, non-draft)
        3. For each message: dedup by messageid → create Activity+Email → run matching
        4. Update sync stats
        5. Return counts

        Returns dict matching SyncResultResponse schema.
        """
        result = {
            'success': True,
            'total_fetched': 0,
            'new_emails': 0,
            'duplicates_skipped': 0,
            'matched_emails': 0,
            'unmatched_emails': 0,
            'errors': [],
        }

        # Step 1: Get authenticated session
        session = MicrosoftAuthService.get_authenticated_session(user)

        # Step 2: Fetch messages from Graph API
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')

        url = (
            f'{GRAPH_BASE_URL}/me/messages'
            f'?$select={MESSAGE_SELECT_FIELDS}'
            f'&$top={max_results}'
            f'&$orderby=receivedDateTime desc'
            f'&$filter=isDraft eq false and receivedDateTime ge {thirty_days_ago}'
        )

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error('Graph API request failed: %s', e)
            result['success'] = False
            result['errors'].append(f'Graph API request failed: {e}')
            return result

        messages = data.get('value', [])
        result['total_fetched'] = len(messages)

        # Step 3: Process each message
        for msg in messages:
            try:
                created = GraphEmailSyncService._process_message(msg, user)
                if created is None:
                    result['duplicates_skipped'] += 1
                elif created.activity.regardingobjectid:
                    result['new_emails'] += 1
                    result['matched_emails'] += 1
                else:
                    result['new_emails'] += 1
                    result['unmatched_emails'] += 1
            except Exception as e:
                error_msg = f'Error processing email "{msg.get("subject", "?")[:50]}": {e}'
                logger.warning(error_msg)
                result['errors'].append(error_msg)

        # Step 4: Update sync stats
        try:
            token = MicrosoftToken.objects.get(userid=user)
            token.last_sync_on = dj_timezone.now()
            token.last_sync_count = result['new_emails']
            token.save(update_fields=['last_sync_on', 'last_sync_count'])
        except MicrosoftToken.DoesNotExist:
            pass

        logger.info(
            'Email sync for user %s: fetched=%d, new=%d, duplicates=%d, matched=%d',
            user.systemuserid, result['total_fetched'], result['new_emails'],
            result['duplicates_skipped'], result['matched_emails'],
        )

        return result

    @staticmethod
    def _process_message(msg: dict, user: SystemUser):
        """Process a single Graph API message.

        Returns Email if created, None if duplicate.
        """
        # Extract internet message ID for dedup
        internet_message_id = msg.get('internetMessageId', '')

        # Check for duplicate
        if internet_message_id and Email.objects.filter(messageid=internet_message_id).exists():
            return None

        # Extract fields
        subject = msg.get('subject', '(No Subject)')[:200]
        body_content = msg.get('body', {}).get('content', '')
        body_type = msg.get('body', {}).get('contentType', 'text')

        # Strip HTML if needed
        if body_type.lower() == 'html':
            body_content = GraphEmailSyncService._strip_html(body_content)

        # Extract email addresses
        from_addr = ''
        from_data = msg.get('from', {}).get('emailAddress', {})
        if from_data:
            from_addr = from_data.get('address', '')

        to_addrs = ';'.join(
            r.get('emailAddress', {}).get('address', '')
            for r in msg.get('toRecipients', [])
            if r.get('emailAddress', {}).get('address')
        )

        cc_addrs = ';'.join(
            r.get('emailAddress', {}).get('address', '')
            for r in msg.get('ccRecipients', [])
            if r.get('emailAddress', {}).get('address')
        )

        # Extract In-Reply-To from internet message headers
        in_reply_to = ''
        for header in msg.get('internetMessageHeaders', []):
            if header.get('name', '').lower() == 'in-reply-to':
                in_reply_to = header.get('value', '')
                break

        # Parse dates
        received_dt = GraphEmailSyncService._parse_datetime(msg.get('receivedDateTime'))
        sent_dt = GraphEmailSyncService._parse_datetime(msg.get('sentDateTime'))

        # Create Activity (base record)
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.EMAIL,
            subject=subject,
            description=body_content[:500] if body_content else None,
            statecode=ActivityStateCode.COMPLETED,
            actualstart=sent_dt,
            actualend=received_dt,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        # Create Email (child record)
        email = Email.objects.create(
            activity=activity,
            to=to_addrs or None,
            sender=from_addr or None,
            cc=cc_addrs or None,
            body=body_content or None,
            directioncode=False,  # Incoming
            messageid=internet_message_id or None,
            inreplyto=in_reply_to or None,
        )

        # Run matching pipeline
        try:
            from apps.activities.matching_service import EmailMatchingService
            match_result = EmailMatchingService.match_email(email)
            if match_result.get('matched'):
                activity.regardingobjectid = match_result['regardingobjectid']
                activity.regardingobjectidtype = match_result['regardingobjectidtype']
                activity.save(update_fields=['regardingobjectid', 'regardingobjectidtype'])
                email.matchmethod = match_result['matchmethod']
                email.matchconfidence = match_result['matchconfidence']
                email.save(update_fields=['matchmethod', 'matchconfidence'])
        except Exception as e:
            logger.warning('Email matching failed for %s: %s', activity.activityid, e)

        return email

    @staticmethod
    def _strip_html(html: str) -> str:
        """Simple HTML tag stripping."""
        # Remove style and script blocks
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Replace <br> and block elements with newlines
        text = re.sub(r'<br\s*/?>|</p>|</div>|</tr>|</li>', '\n', text, flags=re.IGNORECASE)
        # Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&nbsp;', ' ').replace('&quot;', '"')
        # Collapse multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _parse_datetime(iso_str):
        """Parse ISO 8601 datetime from Graph API."""
        if not iso_str:
            return None
        try:
            # Graph API returns ISO format like 2024-01-15T10:30:00Z
            return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
