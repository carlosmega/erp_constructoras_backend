"""
Canonical role names used throughout the codebase for comparisons.

These MUST match the values stored in `securityrole.name` (seeded by
`core/management/commands/seed_test_data.py` and related fixtures).

Prefer this enum over raw strings whenever comparing `user.role_name`,
so typos cause import errors instead of silently granting/denying access.

Usage:
    from core.roles import Role

    if user.role_name == Role.SYSTEM_ADMINISTRATOR:
        ...

    if user.role_name in {Role.SYSTEM_ADMINISTRATOR, Role.SALES_MANAGER}:
        ...

Because `Role` is a `str` subclass, string equality still works — existing
tests that compare against literals like `"Sales Manager"` don't break.
"""

from enum import Enum


class Role(str, Enum):
    SYSTEM_ADMINISTRATOR = "System Administrator"
    SALES_MANAGER = "Sales Manager"
    SALESPERSON = "Salesperson"
    MARKETING_USER = "Marketing User"
    READ_ONLY_USER = "Read-Only User"

    def __str__(self) -> str:  # so f-strings render "Sales Manager", not "Role.SALES_MANAGER"
        return self.value


# Common groupings used across services/permissions
ADMIN_ROLES: frozenset[str] = frozenset({
    Role.SYSTEM_ADMINISTRATOR,
    Role.SALES_MANAGER,
})
"""Users in these roles bypass ownership filters (see every services.py)."""
