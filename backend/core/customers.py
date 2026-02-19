"""
Polymorphic customer resolution utilities.

The frontend uses a single customerid + customeridtype ('account'|'contact')
pattern, while the backend stores separate accountid/contactid foreign keys.
These helpers bridge the two representations.
"""

from uuid import UUID
from typing import Optional, Tuple, Any

from core.exceptions import ValidationError, NotFound


def resolve_customer(customerid: Optional[UUID], customeridtype: Optional[str]) -> Tuple[Any, Any]:
    """
    Resolve customerid + customeridtype to (account, contact) tuple.

    Args:
        customerid: UUID of the customer (Account or Contact)
        customeridtype: 'account' or 'contact'

    Returns:
        Tuple of (account_instance_or_None, contact_instance_or_None)
    """
    if not customerid:
        return None, None

    if customeridtype == 'account':
        from apps.accounts.models import Account
        try:
            return Account.objects.get(accountid=customerid), None
        except Account.DoesNotExist:
            raise NotFound(f"Account with ID {customerid} not found")

    elif customeridtype == 'contact':
        from apps.contacts.models import Contact
        try:
            return None, Contact.objects.get(contactid=customerid)
        except Contact.DoesNotExist:
            raise NotFound(f"Contact with ID {customerid} not found")

    else:
        raise ValidationError(f"Invalid customeridtype: '{customeridtype}'. Must be 'account' or 'contact'.")


def get_customerid(obj) -> Optional[str]:
    """Extract customerid from a model instance with accountid/contactid FKs."""
    if obj.accountid_id:
        return str(obj.accountid_id)
    elif obj.contactid_id:
        return str(obj.contactid_id)
    return None


def get_customeridtype(obj) -> Optional[str]:
    """Extract customeridtype from a model instance with accountid/contactid FKs."""
    if obj.accountid_id:
        return 'account'
    elif obj.contactid_id:
        return 'contact'
    return None
