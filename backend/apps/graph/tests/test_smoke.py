"""Smoke tests for Graph (Microsoft integration) module."""

import pytest

from apps.graph.models import MicrosoftToken, SSOToken
from apps.graph.tests.factories import MicrosoftTokenFactory, SSOTokenFactory


# ============================================================================
# Model creation smoke tests
# ============================================================================

@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeMicrosoftToken:
    """Quick sanity checks for MicrosoftToken model."""

    def test_model_creation(self, salesperson):
        token = MicrosoftTokenFactory(userid=salesperson)
        assert token.pk is not None
        assert token.userid == salesperson
        assert token.microsoft_user_id != ''
        assert token.microsoft_email != ''
        assert token.token_cache != ''

    def test_str_representation(self, salesperson):
        token = MicrosoftTokenFactory(userid=salesperson)
        text = str(token)
        assert 'Microsoft' in text

    def test_one_to_one_constraint(self, salesperson):
        """Only one MicrosoftToken per user."""
        MicrosoftTokenFactory(userid=salesperson)
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            MicrosoftTokenFactory(userid=salesperson)

    def test_connected_on_auto_set(self, salesperson):
        token = MicrosoftTokenFactory(userid=salesperson)
        assert token.connected_on is not None

    def test_defaults(self, salesperson):
        token = MicrosoftTokenFactory(userid=salesperson)
        assert token.last_sync_on is None
        assert token.last_sync_count == 0


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeSSOToken:
    """Quick sanity checks for SSOToken model."""

    def test_model_creation(self, salesperson):
        sso = SSOTokenFactory(userid=salesperson)
        assert sso.pk is not None
        assert sso.userid == salesperson
        assert len(sso.token) > 0

    def test_str_representation(self, salesperson):
        sso = SSOTokenFactory(userid=salesperson)
        text = str(sso)
        assert 'SSOToken' in text

    def test_token_unique(self, salesperson, salesperson2):
        sso1 = SSOTokenFactory(userid=salesperson)
        sso2 = SSOTokenFactory(userid=salesperson2)
        assert sso1.token != sso2.token

    def test_created_on_auto_set(self, salesperson):
        sso = SSOTokenFactory(userid=salesperson)
        assert sso.created_on is not None

    def test_multiple_sso_tokens_per_user(self, salesperson):
        """A user can have multiple SSO tokens (ForeignKey, not OneToOne)."""
        sso1 = SSOTokenFactory(userid=salesperson)
        sso2 = SSOTokenFactory(userid=salesperson)
        assert sso1.pk != sso2.pk


# ============================================================================
# Service smoke tests
# ============================================================================

@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeMicrosoftAuthService:
    """Quick sanity checks for MicrosoftAuthService (non-external methods)."""

    def test_get_connection_status_not_connected(self, salesperson):
        from apps.graph.services import MicrosoftAuthService
        status = MicrosoftAuthService.get_connection_status(salesperson)
        assert status['connected'] is False
        assert status['microsoft_email'] is None

    def test_get_connection_status_connected(self, salesperson):
        from apps.graph.services import MicrosoftAuthService
        MicrosoftTokenFactory(userid=salesperson)
        status = MicrosoftAuthService.get_connection_status(salesperson)
        assert status['connected'] is True
        assert status['microsoft_email'] is not None
        assert status['connected_on'] is not None

    def test_disconnect(self, salesperson):
        from apps.graph.services import MicrosoftAuthService
        MicrosoftTokenFactory(userid=salesperson)
        MicrosoftAuthService.disconnect(salesperson)
        assert not MicrosoftToken.objects.filter(userid=salesperson).exists()

    def test_disconnect_not_connected_raises(self, salesperson):
        from apps.graph.services import MicrosoftAuthService
        from core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            MicrosoftAuthService.disconnect(salesperson)


# ============================================================================
# Router smoke tests
# ============================================================================

@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeGraphRouters:
    """Quick sanity checks for Graph API endpoints.

    Note: Most graph endpoints require external Microsoft services,
    so we only test the status/disconnect endpoints and auth guards.
    """

    def test_status_200(self, auth_client, salesperson):
        response = auth_client.get('/api/graph/status')
        assert response.status_code == 200
        data = response.json()
        assert 'connected' in data

    def test_status_connected(self, auth_client, salesperson):
        MicrosoftTokenFactory(userid=salesperson)
        response = auth_client.get('/api/graph/status')
        assert response.status_code == 200
        data = response.json()
        assert data['connected'] is True

    def test_disconnect_no_connection_400(self, auth_client, salesperson):
        response = auth_client.post('/api/graph/disconnect')
        assert response.status_code == 400

    def test_disconnect_success(self, auth_client, salesperson):
        MicrosoftTokenFactory(userid=salesperson)
        response = auth_client.post('/api/graph/disconnect')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        client = Client()
        response = client.get('/api/graph/status')
        assert response.status_code == 403
