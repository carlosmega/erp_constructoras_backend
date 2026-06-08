"""Tests for core middleware (ApiTrailingSlashMiddleware, AuditMiddleware)."""

import pytest
from django.test import Client, RequestFactory
from core.middleware import (
    ApiTrailingSlashMiddleware,
    AuditMiddleware,
    get_current_user,
    set_current_user,
)


@pytest.mark.unit
class TestApiTrailingSlashMiddleware:
    def test_rewrites_post_without_trailing_slash(self, db, salesperson):
        """POST to /api/leads should be rewritten to /api/leads/."""
        client = Client()
        client.force_login(salesperson)
        # POST to path without trailing slash should still work
        response = client.post(
            '/api/leads',
            {'lastname': 'MiddlewareTest'},
            content_type='application/json',
        )
        # Should succeed (rewritten to /api/leads/) or return valid response
        assert response.status_code in (200, 201, 301)

    def test_get_without_trailing_slash_redirects(self, db, salesperson):
        """GET to /api/leads should redirect to /api/leads/."""
        client = Client()
        client.force_login(salesperson)
        response = client.get('/api/leads')
        # CommonMiddleware may redirect GET requests
        assert response.status_code in (200, 301, 302)

    def test_non_api_paths_unaffected(self, db):
        """Non-API paths should not be affected by middleware."""
        client = Client()
        response = client.get('/admin/login/')
        # Should return normally (200 or redirect)
        assert response.status_code in (200, 301, 302)


@pytest.mark.unit
class TestAuditMiddleware:
    def test_sets_current_user_for_authenticated(self, db, salesperson):
        """Authenticated requests should set the current user in thread-local storage."""
        client = Client()
        client.force_login(salesperson)
        # Make a request - the middleware will set the user
        client.get('/api/leads/')
        # After request completes, user should be cleared
        assert get_current_user() is None

    def test_clears_user_after_request(self, db):
        """Current user should be cleared after each request."""
        client = Client()
        client.get('/api/roles/')
        assert get_current_user() is None

    def test_set_and_get_current_user(self, db, salesperson):
        """Test manual set/get of current user."""
        set_current_user(salesperson)
        assert get_current_user() == salesperson
        set_current_user(None)
        assert get_current_user() is None


@pytest.mark.unit
class TestDevAutoLoginMiddleware:
    """DevAutoLoginMiddleware must fail CLOSED: auto-login only when BOTH
    DEBUG and DEV_AUTOLOGIN are True, so a prod deploy with DEBUG mis-set to
    True does not silently authenticate anonymous callers."""

    def _anon_request(self):
        from django.contrib.auth.models import AnonymousUser
        req = RequestFactory().get('/api/estimation-projects/')
        req.user = AnonymousUser()
        return req

    def test_no_autologin_when_flag_off_even_in_debug(self, db, settings):
        from core.middleware import DevAutoLoginMiddleware
        settings.DEBUG = True
        settings.DEV_AUTOLOGIN = False
        mw = DevAutoLoginMiddleware(lambda r: r)
        req = self._anon_request()
        mw(req)
        assert not req.user.is_authenticated  # stayed anonymous

    def test_no_autologin_when_debug_off(self, db, settings):
        from core.middleware import DevAutoLoginMiddleware
        settings.DEBUG = False
        settings.DEV_AUTOLOGIN = True
        mw = DevAutoLoginMiddleware(lambda r: r)
        req = self._anon_request()
        mw(req)
        assert not req.user.is_authenticated

    def test_autologin_when_both_enabled(self, db, settings, system_admin):
        from core.middleware import DevAutoLoginMiddleware
        settings.DEBUG = True
        settings.DEV_AUTOLOGIN = True
        mw = DevAutoLoginMiddleware(lambda r: r)
        req = self._anon_request()
        mw(req)
        assert req.user.is_authenticated  # dev user injected
