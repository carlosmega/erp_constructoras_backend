"""
Custom authentication backend for SystemUser model.

Ensures that the securityroleid relationship is always loaded
when retrieving users from the session, which is critical for
role-based permission checks.
"""

from django.contrib.auth.backends import ModelBackend
from apps.users.models import SystemUser


class SystemUserBackend(ModelBackend):
    """
    Custom authentication backend that properly loads SystemUser with related fields.

    This backend extends Django's ModelBackend to ensure that when a user is
    loaded from the session, the securityroleid foreign key is always
    select_related to avoid N+1 queries and ensure role_name property works.
    """

    def get_user(self, user_id):
        """
        Get user by ID with securityroleid relationship pre-loaded.

        This method is called by Django's authentication middleware when
        loading a user from the session.

        Args:
            user_id: Primary key of the user (systemuserid UUID)

        Returns:
            SystemUser instance with securityroleid loaded, or None if not found
        """
        try:
            # Always select_related securityroleid to ensure role_name works
            user = SystemUser.objects.select_related('securityroleid').get(pk=user_id)
            return user
        except SystemUser.DoesNotExist:
            return None

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user by email and password.

        Args:
            request: HttpRequest object
            username: Email address (emailaddress1)
            password: User password

        Returns:
            SystemUser instance if authentication succeeds, None otherwise
        """
        if username is None or password is None:
            return None

        try:
            # Get user by email with securityroleid pre-loaded
            user = SystemUser.objects.select_related('securityroleid').get(emailaddress1=username)
        except SystemUser.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user
            SystemUser().set_password(password)
            return None

        # Check password
        if user.check_password(password):
            return user

        return None
