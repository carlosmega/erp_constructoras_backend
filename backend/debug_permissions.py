"""
Debug script to check user permissions.
Run with: python debug_permissions.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
django.setup()

from apps.users.models import SystemUser
from core.permissions import has_permission, Permission, ROLE_PERMISSIONS

# Get the first user (salesperson)
user = SystemUser.objects.select_related('securityroleid').first()

if user:
    print(f"\n{'='*60}")
    print(f"USER INFORMATION")
    print(f"{'='*60}")
    print(f"Email: {user.emailaddress1}")
    print(f"Full Name: {user.fullname}")
    print(f"Is Authenticated: {user.is_authenticated}")
    print(f"Role ID: {user.securityroleid}")
    print(f"Role Name: {user.role_name}")
    print(f"\n{'='*60}")
    print(f"PERMISSION CHECKS")
    print(f"{'='*60}")

    # Check specific permissions
    permissions_to_check = [
        Permission.ACCOUNT_READ,
        Permission.ACCOUNT_CREATE,
        Permission.CONTACT_READ,
        Permission.CONTACT_CREATE,
        Permission.LEAD_READ,
    ]

    for perm in permissions_to_check:
        result = has_permission(user, perm)
        print(f"{perm.value:30s} : {result}")

    print(f"\n{'='*60}")
    print(f"ALL PERMISSIONS FOR ROLE: {user.role_name}")
    print(f"{'='*60}")
    role_perms = ROLE_PERMISSIONS.get(user.role_name, [])
    for perm in role_perms:
        print(f"  - {perm.value}")

    print(f"\n{'='*60}")
else:
    print("No users found in database!")
