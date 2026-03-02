"""Factory Boy factories for Notification model."""

import factory
from factory.django import DjangoModelFactory
from apps.notifications.models import Notification, NotificationTypeCode, NotificationPriorityCode


def _get_or_create_user():
    from apps.users.models import SystemUser, SecurityRole
    role = SecurityRole.objects.get(name='Salesperson')
    user, _ = SystemUser.objects.get_or_create(
        emailaddress1='notif-factory@crm.test',
        defaults={
            'fullname': 'Notification Factory User',
            'securityroleid': role,
        },
    )
    if not user.has_usable_password():
        user.set_password('test123')
        user.save()
    return user


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    ownerid = factory.LazyFunction(_get_or_create_user)
    typecode = NotificationTypeCode.SYSTEM
    prioritycode = NotificationPriorityCode.MEDIUM
    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('paragraph')
    isread = False
    isarchived = False
