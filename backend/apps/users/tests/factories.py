"""
Factory Boy factories for User models.

Provides test data generation for SystemUser and SecurityRole models.
"""

import factory
from factory.django import DjangoModelFactory
from apps.users.models import SecurityRole, SystemUser


class SecurityRoleFactory(DjangoModelFactory):
    """Factory for creating SecurityRole instances."""

    class Meta:
        model = SecurityRole
        django_get_or_create = ('name',)

    name = factory.Iterator([
        'System Administrator',
        'Sales Manager',
        'Salesperson',
        'Marketing User',
        'Read-Only User',
    ])
    description = factory.LazyAttribute(
        lambda obj: f'Role description for {obj.name}'
    )


class SystemUserFactory(DjangoModelFactory):
    """Factory for creating SystemUser instances."""

    class Meta:
        model = SystemUser

    emailaddress1 = factory.Sequence(lambda n: f'user{n}@crm.test')
    fullname = factory.Faker('name')
    securityroleid = factory.SubFactory(
        SecurityRoleFactory,
        name='Salesperson'
    )
    isdisabled = False
    failedloginattempts = 0

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password after user creation."""
        if not create:
            return

        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password('testpass123')
        obj.save()


class SystemAdminFactory(SystemUserFactory):
    """Factory for creating System Administrator users."""

    securityroleid = factory.SubFactory(
        SecurityRoleFactory,
        name='System Administrator'
    )
    fullname = 'System Administrator'
    emailaddress1 = factory.Sequence(lambda n: f'admin{n}@crm.test')


class SalesManagerFactory(SystemUserFactory):
    """Factory for creating Sales Manager users."""

    securityroleid = factory.SubFactory(
        SecurityRoleFactory,
        name='Sales Manager'
    )
    fullname = factory.Faker('name')
    emailaddress1 = factory.Sequence(lambda n: f'manager{n}@crm.test')


class SalespersonFactory(SystemUserFactory):
    """Factory for creating Salesperson users."""

    securityroleid = factory.SubFactory(
        SecurityRoleFactory,
        name='Salesperson'
    )
    fullname = factory.Faker('name')
    emailaddress1 = factory.Sequence(lambda n: f'sales{n}@crm.test')


class MarketingUserFactory(SystemUserFactory):
    """Factory for creating Marketing User accounts."""

    securityroleid = factory.SubFactory(
        SecurityRoleFactory,
        name='Marketing User'
    )
    fullname = factory.Faker('name')
    emailaddress1 = factory.Sequence(lambda n: f'marketing{n}@crm.test')


class ReadOnlyUserFactory(SystemUserFactory):
    """Factory for creating Read-Only User accounts."""

    securityroleid = factory.SubFactory(
        SecurityRoleFactory,
        name='Read-Only User'
    )
    fullname = factory.Faker('name')
    emailaddress1 = factory.Sequence(lambda n: f'readonly{n}@crm.test')
