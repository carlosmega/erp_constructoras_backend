"""API routers for Contact Management. Phase 7 Implementation"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest
from apps.contacts.schemas import ContactSchema, CreateContactDto, UpdateContactDto
from apps.contacts.services import ContactService
from core.permissions import require_permission, Permission

contacts_router = Router(tags=["Contacts"])


@contacts_router.get("/", response=List[ContactSchema])
@require_permission(Permission.CONTACT_READ)
def list_contacts(
    request: HttpRequest,
    statecode: Optional[int] = None,
    parentcustomerid: Optional[str] = None,
    search: Optional[str] = None,
    ownerid: Optional[str] = None
):
    """List contacts with filtering. Requires: CONTACT_READ permission"""
    parent_uuid = UUID(parentcustomerid) if parentcustomerid else None
    owner_uuid = UUID(ownerid) if ownerid else None
    contacts = ContactService.list_contacts(
        user=request.user, statecode=statecode, parentcustomerid=parent_uuid,
        search=search, ownerid=owner_uuid
    )
    return list(contacts)


@contacts_router.post("/", response={201: ContactSchema})
@require_permission(Permission.CONTACT_CREATE)
def create_contact(request: HttpRequest, payload: CreateContactDto):
    """Create new contact. Requires: CONTACT_CREATE permission"""
    contact = ContactService.create_contact(payload, request.user)
    return 201, contact


@contacts_router.get("/{contact_id}", response=ContactSchema)
@require_permission(Permission.CONTACT_READ)
def get_contact(request: HttpRequest, contact_id: UUID):
    """Get contact by ID. Requires: CONTACT_READ permission"""
    contact = ContactService.get_contact_by_id(contact_id, request.user)
    return contact


@contacts_router.patch("/{contact_id}", response=ContactSchema)
@require_permission(Permission.CONTACT_UPDATE)
def update_contact(request: HttpRequest, contact_id: UUID, payload: UpdateContactDto):
    """Update contact. Requires: CONTACT_UPDATE permission"""
    contact = ContactService.update_contact(contact_id, payload, request.user)
    return contact


@contacts_router.delete("/{contact_id}", response={204: None})
@require_permission(Permission.CONTACT_DELETE)
def delete_contact(request: HttpRequest, contact_id: UUID):
    """Deactivate contact. Requires: CONTACT_DELETE permission"""
    ContactService.deactivate_contact(contact_id, request.user)
    return 204, None
