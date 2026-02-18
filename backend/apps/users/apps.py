"""
Django app configuration for Users application.
"""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = 'User Management'

    def ready(self):
        """
        Import signal handlers and perform app initialization.
        """
        # Import signals here if needed
        pass
