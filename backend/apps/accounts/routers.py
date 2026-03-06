"""API routers for Account Management. Phase 7 Implementation"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest
from apps.accounts.schemas import AccountSchema, AccountLookupSchema, CreateAccountDto, UpdateAccountDto
from apps.accounts.services import AccountService
from core.permissions import require_permission, require_authenticated, Permission

accounts_router = Router(tags=["Accounts"])


@accounts_router.get('/supplier-lookup/', response=List[AccountLookupSchema])
@require_authenticated
def supplier_lookup(request, search: str = ''):
    """List active accounts for supplier selection. Requires: authenticated user"""
    accounts = AccountService.list_accounts_for_supplier_lookup(search or None)
    return list(accounts)


@accounts_router.get("/", response=List[AccountSchema])
@require_permission(Permission.ACCOUNT_READ)
def list_accounts(request: HttpRequest, statecode: Optional[int] = None, search: Optional[str] = None, ownerid: Optional[str] = None):
    """List accounts with filtering. Requires: ACCOUNT_READ permission"""
    owner_uuid = UUID(ownerid) if ownerid else None
    accounts = AccountService.list_accounts(user=request.user, statecode=statecode, search=search, ownerid=owner_uuid)
    return list(accounts)


@accounts_router.post("/", response={201: AccountSchema})
@require_permission(Permission.ACCOUNT_CREATE)
def create_account(request: HttpRequest, payload: CreateAccountDto):
    """Create new account. Requires: ACCOUNT_CREATE permission"""
    account = AccountService.create_account(payload, request.user)
    return 201, account


@accounts_router.get("/{account_id}", response=AccountSchema)
@require_permission(Permission.ACCOUNT_READ)
def get_account(request: HttpRequest, account_id: UUID):
    """Get account by ID. Requires: ACCOUNT_READ permission"""
    account = AccountService.get_account_by_id(account_id, request.user)
    return account


@accounts_router.patch("/{account_id}", response=AccountSchema)
@require_permission(Permission.ACCOUNT_UPDATE)
def update_account(request: HttpRequest, account_id: UUID, payload: UpdateAccountDto):
    """Update account. Requires: ACCOUNT_UPDATE permission"""
    account = AccountService.update_account(account_id, payload, request.user)
    return account


@accounts_router.delete("/{account_id}", response={204: None})
@require_permission(Permission.ACCOUNT_DELETE)
def delete_account(request: HttpRequest, account_id: UUID):
    """Deactivate account. Requires: ACCOUNT_DELETE permission"""
    AccountService.deactivate_account(account_id, request.user)
    return 204, None
