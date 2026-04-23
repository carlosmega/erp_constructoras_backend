"""
Generic read-side service base.

Eliminates the ~30 copies of `list_X`/`get_X_by_id` that every feature has
(ownership filter + select_related + NotFound/PermissionDenied handling).

Write-side (`create_*`, `update_*`, state transitions, notifications) stays
in the concrete service because it's entity-specific. The goal here is to
remove the boilerplate, not force every feature into the same shape.

Usage:

    from core.services import BaseReadService
    from apps.leads.models import Lead

    class LeadService(BaseReadService):
        model = Lead
        pk_field = 'leadid'
        select_related_fields = ('ownerid', 'createdby', 'modifiedby')
        not_found_message = "Lead not found"

        # ... entity-specific create/update/delete ...
"""

from typing import Generic, TypeVar
from uuid import UUID

from django.db.models import Model, QuerySet

from core.exceptions import NotFound, PermissionDenied
from core.permissions import filter_by_ownership
from core.roles import ADMIN_ROLES

T = TypeVar('T', bound=Model)


class BaseReadService(Generic[T]):
    """Generic read-side base class.

    Subclasses must set `model` and `pk_field`. `select_related_fields` and
    messages can be customized; they default to the common shape.
    """

    model: type[T]
    pk_field: str
    select_related_fields: tuple[str, ...] = ('ownerid', 'createdby', 'modifiedby')
    owner_field: str = 'ownerid'
    not_found_message: str = "Record not found"
    access_denied_message: str = "You don't have access to this record"

    @classmethod
    def base_queryset(cls, user) -> QuerySet[T]:
        """
        Returns the base queryset visible to `user`, with ownership filter and
        `select_related` for common FKs applied.

        Concrete services should start from this queryset and layer their own
        filters on top (e.g. statecode, search).
        """
        qs = cls.model.objects.all()
        qs = filter_by_ownership(qs, user, owner_field=cls.owner_field)
        return qs.select_related(*cls.select_related_fields)

    @classmethod
    def get_by_id(cls, record_id: UUID, user) -> T:
        """
        Fetch one record by PK, enforcing ownership unless the user is admin.

        Raises:
            NotFound: if the PK doesn't exist.
            PermissionDenied: if the record belongs to another user and the
                current user is not in `ADMIN_ROLES`.
        """
        lookup = {cls.pk_field: record_id}
        try:
            record = cls.model.objects.select_related(
                *cls.select_related_fields
            ).get(**lookup)
        except cls.model.DoesNotExist:
            raise NotFound(f"{cls.not_found_message}: {record_id}")

        if user.role_name not in ADMIN_ROLES:
            owner_id = getattr(record, f'{cls.owner_field}_id', None)
            if owner_id != user.systemuserid:
                raise PermissionDenied(cls.access_denied_message)

        return record
