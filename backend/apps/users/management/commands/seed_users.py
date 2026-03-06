"""
Django management command to seed dummy users for the ERP system.

Creates users with different security roles for development and testing.
All passwords default to 'Password1' unless --password is specified.

Usage:
    python manage.py seed_users
    python manage.py seed_users --password mypass123
    python manage.py seed_users --clear   # Remove seeded users first
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import SystemUser, SecurityRole


# Dummy users organized by role
USERS_DATA = [
    # ── System Administrators ──
    {
        'email': 'director@construpro.mx',
        'fullname': 'Ing. Fernando Reyes Garza',
        'role': 'System Administrator',
    },

    # ── Sales Managers ──
    {
        'email': 'gerente.comercial@construpro.mx',
        'fullname': 'Lic. Patricia Salazar Mendoza',
        'role': 'Sales Manager',
    },
    {
        'email': 'gerente.operaciones@construpro.mx',
        'fullname': 'Ing. Ricardo Treviño Leal',
        'role': 'Sales Manager',
    },

    # ── Salespersons (Project Managers, Site Engineers, etc.) ──
    {
        'email': 'carlos.mendoza@construpro.mx',
        'fullname': 'Ing. Carlos Mendoza Ríos',
        'role': 'Salesperson',
    },
    {
        'email': 'laura.ramirez@construpro.mx',
        'fullname': 'Arq. Laura Ramírez Vega',
        'role': 'Salesperson',
    },
    {
        'email': 'roberto.garza@construpro.mx',
        'fullname': 'Ing. Roberto Garza Flores',
        'role': 'Salesperson',
    },
    {
        'email': 'sofia.martinez@construpro.mx',
        'fullname': 'Ing. Sofía Martínez Cantú',
        'role': 'Salesperson',
    },
    {
        'email': 'miguel.hernandez@construpro.mx',
        'fullname': 'Ing. Miguel Hernández Luna',
        'role': 'Salesperson',
    },
    {
        'email': 'diana.lopez@construpro.mx',
        'fullname': 'Arq. Diana López Torres',
        'role': 'Salesperson',
    },
    {
        'email': 'alejandro.ruiz@construpro.mx',
        'fullname': 'Ing. Alejandro Ruiz Peña',
        'role': 'Salesperson',
    },
    {
        'email': 'gabriela.castro@construpro.mx',
        'fullname': 'Ing. Gabriela Castro Morales',
        'role': 'Salesperson',
    },

    # ── Marketing Users ──
    {
        'email': 'marketing@construpro.mx',
        'fullname': 'Lic. Andrea Villarreal Nava',
        'role': 'Marketing User',
    },

    # ── Read-Only Users ──
    {
        'email': 'auditor@construpro.mx',
        'fullname': 'C.P. Jorge Sánchez Valdez',
        'role': 'Read-Only User',
    },
    {
        'email': 'contralor@construpro.mx',
        'fullname': 'C.P. Mariana Ochoa Lira',
        'role': 'Read-Only User',
    },
]

# Emails created by this command (used by --clear)
SEEDED_EMAILS = [u['email'] for u in USERS_DATA]


class Command(BaseCommand):
    help = 'Seed dummy users with security roles for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='Password1',
            help='Password for all seeded users (default: Password1)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Remove previously seeded users before creating new ones',
        )

    def handle(self, *args, **options):
        password = options['password']

        if options['clear']:
            deleted, _ = SystemUser.objects.filter(
                emailaddress1__in=SEEDED_EMAILS
            ).delete()
            self.stdout.write(self.style.WARNING(
                f'Deleted {deleted} previously seeded users'
            ))

        # Ensure roles exist
        self._ensure_roles()

        # Get or create an admin for audit fields
        admin = SystemUser.objects.filter(
            securityroleid__name='System Administrator',
            isdisabled=False,
        ).first()

        if not admin:
            self.stdout.write(self.style.ERROR(
                'No admin user found. Run: python manage.py createsuperuser'
            ))
            return

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for user_data in USERS_DATA:
                email = user_data['email']

                if SystemUser.objects.filter(emailaddress1=email).exists():
                    skipped_count += 1
                    continue

                role = SecurityRole.objects.get(name=user_data['role'])
                user = SystemUser.objects.create_user(
                    emailaddress1=email,
                    fullname=user_data['fullname'],
                    password=password,
                    securityroleid=role,
                    createdby=admin,
                    modifiedby=admin,
                )
                created_count += 1
                self.stdout.write(
                    f'  + {user.fullname:<40} | {email:<40} | {role.name}'
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done: {created_count} created, {skipped_count} skipped (already exist)'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'All seeded users have password: {password}'
        ))

    def _ensure_roles(self):
        """Create security roles if they don't exist."""
        roles = [
            ('System Administrator', 'Full access to all entities and operations'),
            ('Sales Manager', 'Manage sales team and view all opportunities'),
            ('Salesperson', 'Manage own leads and opportunities'),
            ('Marketing User', 'Manage campaigns and leads'),
            ('Read-Only User', 'View-only access to entities'),
        ]
        for name, description in roles:
            SecurityRole.objects.get_or_create(
                name=name,
                defaults={'description': description},
            )
