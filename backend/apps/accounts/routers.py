"""API routers for Account Management. Phase 7 Implementation"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest
from apps.accounts.schemas import AccountSchema, CreateAccountDto, UpdateAccountDto
from apps.accounts.services import AccountService
from core.permissions import require_permission, Permission


accounts_router = Router(tags=["Accounts"])


@accounts_router.get("/debug")
def debug_accounts_auth(request: HttpRequest):
    """Debug endpoint to check authentication status"""
    import logging
    logger = logging.getLogger(__name__)

    user = request.user
    logger.info(f"DEBUG - User object: {user}")
    logger.info(f"DEBUG - Is authenticated: {user.is_authenticated if user else 'No user'}")

    if user and user.is_authenticated:
        logger.info(f"DEBUG - User email: {user.emailaddress1}")
        logger.info(f"DEBUG - User role_name: {user.role_name}")
        logger.info(f"DEBUG - SecurityRole ID: {user.securityroleid}")

        from core.permissions import has_permission, Permission
        has_perm = has_permission(user, Permission.ACCOUNT_READ)
        logger.info(f"DEBUG - Has ACCOUNT_READ permission: {has_perm}")

        return {
            "authenticated": True,
            "user": user.emailaddress1,
            "role": user.role_name,
            "has_account_read": has_perm,
            "session_key": request.session.session_key,
        }
    else:
        return {
            "authenticated": False,
            "user": str(user),
            "session_key": request.session.session_key if hasattr(request, 'session') else None,
        }


@accounts_router.get("/", response=List[AccountSchema])
@require_permission(Permission.ACCOUNT_READ)
def list_accounts(request: HttpRequest, statecode: Optional[int] = None, search: Optional[str] = None, ownerid: Optional[str] = None):
    """List accounts with filtering. Requires: ACCOUNT_READ permission"""
    owner_uuid = UUID(ownerid) if ownerid else None
    accounts = AccountService.list_accounts(user=request.user, statecode=statecode, search=search, ownerid=owner_uuid)
    return accounts


@accounts_router.post("/", response=AccountSchema)
@require_permission(Permission.ACCOUNT_CREATE)
def create_account(request: HttpRequest, payload: CreateAccountDto):
    """Create new account. Requires: ACCOUNT_CREATE permission"""
    account = AccountService.create_account(payload, request.user)
    return account


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


@accounts_router.delete("/{account_id}")
@require_permission(Permission.ACCOUNT_DELETE)
def delete_account(request: HttpRequest, account_id: UUID):
    """Deactivate account. Requires: ACCOUNT_DELETE permission"""
    account = AccountService.deactivate_account(account_id, request.user)
    return {"success": True, "message": f"Account {account.name} deactivated successfully"}
