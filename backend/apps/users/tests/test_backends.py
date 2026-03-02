"""Tests for the custom SystemUser authentication backend."""

import pytest
from apps.users.backends import SystemUserBackend


@pytest.mark.django_db
class TestSystemUserBackend:
    def setup_method(self):
        self.backend = SystemUserBackend()

    def test_get_user_returns_user(self, salesperson):
        user = self.backend.get_user(salesperson.pk)
        assert user == salesperson

    def test_get_user_returns_none_for_nonexistent(self):
        import uuid
        user = self.backend.get_user(uuid.uuid4())
        assert user is None

    def test_authenticate_success(self, salesperson):
        user = self.backend.authenticate(None, username='sales@crm.test', password='sales123')
        assert user == salesperson

    def test_authenticate_wrong_password(self, salesperson):
        user = self.backend.authenticate(None, username='sales@crm.test', password='wrong')
        assert user is None

    def test_authenticate_nonexistent_email(self, db):
        user = self.backend.authenticate(None, username='nonexistent@crm.test', password='pass')
        assert user is None

    def test_authenticate_none_username(self, db):
        user = self.backend.authenticate(None, username=None, password='pass')
        assert user is None

    def test_authenticate_none_password(self, db):
        user = self.backend.authenticate(None, username='test@crm.test', password=None)
        assert user is None
