import pytest
from apps.users.tests.factories import SystemAdminFactory, SalespersonFactory


@pytest.fixture
def system_admin(db):
    return SystemAdminFactory()


@pytest.fixture
def salesperson(db):
    return SalespersonFactory()
