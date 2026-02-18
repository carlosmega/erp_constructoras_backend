"""
Script to create a Django superuser programmatically.

Usage:
    python create_superuser.py

Default credentials:
    Email: admin@crm.com
    Fullname: System Administrator
    Password: admin123
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
django.setup()

from apps.users.models import SystemUser, SecurityRole

def create_superuser():
    """Create a superuser with default credentials."""
    email = 'admin@crm.com'
    fullname = 'System Administrator'
    password = 'admin123'

    # Check if user already exists
    if SystemUser.objects.filter(emailaddress1=email).exists():
        print(f"[ERROR] User with email '{email}' already exists!")
        user = SystemUser.objects.get(emailaddress1=email)
        print(f"[OK] Existing user: {user.fullname} ({user.emailaddress1})")
        return

    try:
        # Create superuser
        user = SystemUser.objects.create_superuser(
            emailaddress1=email,
            fullname=fullname,
            password=password
        )

        print("[SUCCESS] Superuser created successfully!")
        print(f"  Email: {email}")
        print(f"  Full Name: {fullname}")
        print(f"  Password: {password}")
        print(f"  Role: {user.role_name}")
        print()
        print("[WARNING] IMPORTANT: Change the password after first login!")
        print(f"  You can access the admin at: http://localhost:8000/admin")

    except Exception as e:
        print(f"[ERROR] Error creating superuser: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    create_superuser()
