"""Factory Boy factories for Activity models."""

import factory
from factory.django import DjangoModelFactory
from apps.activities.models import Activity, ActivityTypeCode, ActivityStateCode
from apps.users.tests.factories import SalespersonFactory


class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity

    activitytypecode = ActivityTypeCode.TASK
    subject = factory.Sequence(lambda n: f'Activity {n}')
    statecode = ActivityStateCode.OPEN
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class EmailActivityFactory(ActivityFactory):
    activitytypecode = ActivityTypeCode.EMAIL
    subject = factory.Sequence(lambda n: f'Email {n}')


class TaskActivityFactory(ActivityFactory):
    activitytypecode = ActivityTypeCode.TASK
    subject = factory.Sequence(lambda n: f'Task {n}')
