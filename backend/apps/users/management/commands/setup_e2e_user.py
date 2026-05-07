"""
Crea (idempotentemente) el usuario que usan los tests E2E de Playwright.

Las credenciales coinciden con `erp_frontend/e2e/fixtures/auth.setup.ts`.
NO usar este comando en producción — es exclusivo para entornos de prueba.

Uso:
    python manage.py setup_e2e_user
    python manage.py setup_e2e_user --reset-password
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.users.models import SecurityRole, SystemUser


E2E_EMAIL = 'admin@crm.com'
E2E_FULLNAME = 'E2E Test Admin'
E2E_PASSWORD = 'admin123'


class Command(BaseCommand):
    help = 'Crea o resetea el usuario admin para los tests E2E de Playwright.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='Si el usuario ya existe, resetea su contraseña al valor por defecto.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'setup_e2e_user está deshabilitado cuando DEBUG=False. '
                'Este comando es exclusivo para entornos de desarrollo y CI. '
                'En producción usa `python manage.py createsuperuser` con un '
                'email real y una contraseña fuerte.'
            )

        admin_role, _ = SecurityRole.objects.get_or_create(
            name='System Administrator',
            defaults={'description': 'Full access to all entities and operations'},
        )

        user = SystemUser.objects.filter(emailaddress1=E2E_EMAIL).first()

        if user is None:
            user = SystemUser.objects.create_superuser(
                emailaddress1=E2E_EMAIL,
                fullname=E2E_FULLNAME,
                password=E2E_PASSWORD,
            )
            self.stdout.write(self.style.SUCCESS(
                f'Usuario E2E creado: {E2E_EMAIL} / {E2E_PASSWORD}'
            ))
            return

        if options['reset_password']:
            user.set_password(E2E_PASSWORD)
            user.isdisabled = False
            user.failedloginattempts = 0
            if user.securityroleid_id != admin_role.pk:
                user.securityroleid = admin_role
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'Contraseña reseteada para {E2E_EMAIL}: {E2E_PASSWORD}'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'Usuario {E2E_EMAIL} ya existe. Usa --reset-password para forzar reset.'
        ))
