"""Contact business logic service layer. Phase 7 Implementation"""

from typing import Optional
from uuid import UUID
from django.db.models import Q, QuerySet
from apps.contacts.models import Contact, ContactStateCode
from apps.contacts.schemas import CreateContactDto, UpdateContactDto
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.roles import ADMIN_ROLES
from core.permissions import filter_by_ownership
from core.services import BaseReadService
from apps.audit.services import audit_action


class ContactService(BaseReadService[Contact]):
    """Service class for Contact entity business logic."""

    model = Contact
    pk_field = 'contactid'
    select_related_fields = ('ownerid', 'parentcustomerid', 'createdby', 'modifiedby')
    not_found_message = "Contact not found"
    access_denied_message = "You don't have access to this contact"

    @staticmethod
    def list_contacts(
        user: SystemUser,
        statecode: Optional[int] = None,
        parentcustomerid: Optional[UUID] = None,
        search: Optional[str] = None,
        ownerid: Optional[UUID] = None,
    ) -> QuerySet[Contact]:
        """List contacts with filtering."""
        queryset = Contact.objects.all()
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        if parentcustomerid:
            queryset = queryset.filter(parentcustomerid=parentcustomerid)
        if ownerid:
            if user.role_name not in ADMIN_ROLES:
                raise PermissionDenied("You cannot view other users' contacts")
            queryset = queryset.filter(ownerid=ownerid)
        if search:
            queryset = queryset.filter(
                Q(fullname__icontains=search) |
                Q(emailaddress1__icontains=search) |
                Q(jobtitle__icontains=search)
            )

        return queryset.select_related('ownerid', 'parentcustomerid', 'createdby', 'modifiedby')

    @staticmethod
    @audit_action(action='create', entity='contact')
    def create_contact(dto: CreateContactDto, user: SystemUser) -> Contact:
        """Create a new contact."""
        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        contact = Contact(
            firstname=dto.firstname,
            lastname=dto.lastname,
            emailaddress1=dto.emailaddress1,
            telephone1=dto.telephone1,
            mobilephone=dto.mobilephone,
            jobtitle=dto.jobtitle,
            parentcustomerid_id=dto.parentcustomerid,
            address1_line1=dto.address1_line1,
            address1_city=dto.address1_city,
            address1_stateorprovince=dto.address1_stateorprovince,
            address1_postalcode=dto.address1_postalcode,
            address1_country=dto.address1_country,
            description=dto.description,
            ownerid=owner,
            createdby=user,
            modifiedby=user,
        )
        contact.save()
        return contact

    @classmethod
    def get_contact_by_id(cls, contact_id: UUID, user: SystemUser) -> Contact:
        """Get contact by ID with ownership check (delegates to BaseReadService)."""
        return cls.get_by_id(contact_id, user)

    @staticmethod
    @audit_action(action='update', entity='contact', record_arg='contact_id')
    def update_contact(contact_id: UUID, dto: UpdateContactDto, user: SystemUser) -> Contact:
        """Update an existing contact."""
        contact = ContactService.get_contact_by_id(contact_id, user)

        update_fields = ['firstname', 'lastname', 'emailaddress1', 'telephone1', 'mobilephone',
                        'jobtitle', 'parentcustomerid', 'address1_line1', 'address1_city',
                        'address1_stateorprovince', 'address1_postalcode', 'address1_country',
                        'description', 'statuscode']

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                if field == 'parentcustomerid':
                    setattr(contact, f'{field}_id', value)
                else:
                    setattr(contact, field, value)

        contact.modifiedby = user
        contact.save()
        return contact

    @staticmethod
    @audit_action(action='delete', entity='contact', record_arg='contact_id')
    def deactivate_contact(contact_id: UUID, user: SystemUser) -> Contact:
        """Deactivate a contact."""
        contact = ContactService.get_contact_by_id(contact_id, user)
        contact.statecode = ContactStateCode.INACTIVE
        contact.modifiedby = user
        contact.save()
        return contact
