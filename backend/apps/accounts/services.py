"""Account business logic service layer. Phase 7 Implementation"""

from typing import Optional
from uuid import UUID
from django.db.models import Q, QuerySet
from apps.accounts.models import Account, AccountStateCode, CustomerTypeCode
from apps.accounts.schemas import CreateAccountDto, UpdateAccountDto
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import filter_by_ownership


class AccountService:
    """Service class for Account entity business logic."""

    @staticmethod
    def list_accounts(
        user: SystemUser,
        statecode: Optional[int] = None,
        search: Optional[str] = None,
        ownerid: Optional[UUID] = None,
    ) -> QuerySet[Account]:
        """List accounts with filtering."""
        queryset = Account.objects.all()
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        if ownerid:
            if user.role_name not in ["System Administrator", "Sales Manager"]:
                raise PermissionDenied("You cannot view other users' accounts")
            queryset = queryset.filter(ownerid=ownerid)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(accountnumber__icontains=search) |
                Q(emailaddress1__icontains=search)
            )

        return queryset.select_related('ownerid', 'createdby', 'modifiedby')

    @staticmethod
    def create_account(dto: CreateAccountDto, user: SystemUser) -> Account:
        """Create a new account."""
        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        account = Account(
            name=dto.name,
            accountnumber=dto.accountnumber,
            emailaddress1=dto.emailaddress1,
            telephone1=dto.telephone1,
            websiteurl=dto.websiteurl,
            address1_line1=dto.address1_line1,
            address1_city=dto.address1_city,
            address1_stateorprovince=dto.address1_stateorprovince,
            address1_postalcode=dto.address1_postalcode,
            address1_country=dto.address1_country,
            description=dto.description,
            revenue=dto.revenue,
            numberofemployees=dto.numberofemployees,
            customertypecode=dto.customertypecode if dto.customertypecode is not None else CustomerTypeCode.CUSTOMER,
            ownerid=owner,
            createdby=user,
            modifiedby=user,
        )
        account.save()
        return account

    @staticmethod
    def get_account_by_id(account_id: UUID, user: SystemUser) -> Account:
        """Get account by ID with ownership check."""
        try:
            account = Account.objects.select_related('ownerid', 'createdby', 'modifiedby').get(accountid=account_id)
        except Account.DoesNotExist:
            raise NotFound(f"Account with ID {account_id} not found")

        if user.role_name not in ["System Administrator", "Sales Manager"]:
            if account.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this account")

        return account

    @staticmethod
    def update_account(account_id: UUID, dto: UpdateAccountDto, user: SystemUser) -> Account:
        """Update an existing account."""
        account = AccountService.get_account_by_id(account_id, user)

        update_fields = ['name', 'accountnumber', 'emailaddress1', 'telephone1', 'websiteurl',
                        'address1_line1', 'address1_city', 'address1_stateorprovince',
                        'address1_postalcode', 'address1_country', 'description',
                        'revenue', 'numberofemployees', 'customertypecode', 'statuscode']

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(account, field, value)

        account.modifiedby = user
        account.save()
        return account

    @staticmethod
    def list_accounts_for_supplier_lookup(search: Optional[str] = None) -> QuerySet[Account]:
        """List active accounts for supplier selection."""
        queryset = Account.objects.filter(statecode=AccountStateCode.ACTIVE)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(emailaddress1__icontains=search) |
                Q(accountnumber__icontains=search)
            )
        return queryset.order_by('name')[:50]

    @staticmethod
    def deactivate_account(account_id: UUID, user: SystemUser) -> Account:
        """Deactivate an account."""
        account = AccountService.get_account_by_id(account_id, user)
        account.statecode = AccountStateCode.INACTIVE
        account.modifiedby = user
        account.save()
        return account
