"""
Case business logic service layer.

Handles case operations, state transitions, and resolution workflow.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.cases.models import (
    Case,
    CaseStateCode,
    CaseStatusCode,
    CasePriorityCode,
)
from apps.cases.schemas import (
    CreateCaseDto,
    UpdateCaseDto,
    ResolveCaseDto,
    CancelCaseDto,
)
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import filter_by_ownership


class CaseService:
    """
    Service class for Case entity business logic.
    """

    @staticmethod
    def generate_ticket_number() -> str:
        """
        Generate a unique ticket number in the format CAS-YYYY-NNNN.

        Returns:
            Ticket number string (e.g., CAS-2026-0001)
        """
        current_year = timezone.now().year
        prefix = f"CAS-{current_year}-"

        # Find the last ticket number for the current year
        last_case = (
            Case.objects
            .filter(ticketnumber__startswith=prefix)
            .order_by('-ticketnumber')
            .first()
        )

        if last_case:
            # Extract the sequence number and increment
            last_number = int(last_case.ticketnumber.split('-')[-1])
            next_number = last_number + 1
        else:
            next_number = 1

        return f"{prefix}{next_number:04d}"

    @staticmethod
    def list_cases(
        user: SystemUser,
        search: Optional[str] = None,
        statecode: Optional[int] = None,
    ) -> QuerySet[Case]:
        """
        List cases with filtering and ownership rules.

        Args:
            user: Current user (for ownership filtering)
            search: Search in title, ticketnumber, description
            statecode: Filter by state code

        Returns:
            QuerySet of Case objects
        """
        queryset = Case.objects.all()

        # Apply ownership filtering based on user role
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        # Apply filters
        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(ticketnumber__icontains=search) |
                Q(description__icontains=search)
            )

        # Optimize query with select_related
        queryset = queryset.select_related(
            'ownerid', 'accountid', 'contactid',
            'primarycontactid', 'productid',
            'createdby', 'modifiedby'
        )

        return queryset

    @staticmethod
    def create_case(dto: CreateCaseDto, user: SystemUser) -> Case:
        """
        Create a new case.

        Args:
            dto: Case creation data
            user: Current user (will be set as createdby and modifiedby)

        Returns:
            Created Case instance

        Raises:
            ValidationError: If validation fails
        """
        # Validate owner exists
        try:
            owner = SystemUser.objects.get(systemuserid=dto.ownerid)
        except SystemUser.DoesNotExist:
            raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        # Resolve polymorphic customer
        from core.customers import resolve_customer
        account, contact = resolve_customer(dto.customerid, dto.customerid_type)

        # Resolve primary contact
        primary_contact = None
        if dto.primarycontactid:
            from apps.contacts.models import Contact
            try:
                primary_contact = Contact.objects.get(contactid=dto.primarycontactid)
            except Contact.DoesNotExist:
                raise ValidationError(f"Primary contact with ID {dto.primarycontactid} not found")

        # Resolve product
        product = None
        if dto.productid:
            from apps.products.models import Product
            try:
                product = Product.objects.get(productid=dto.productid)
            except Product.DoesNotExist:
                raise ValidationError(f"Product with ID {dto.productid} not found")

        # Generate ticket number
        ticket_number = CaseService.generate_ticket_number()

        # Create case
        case = Case(
            title=dto.title,
            description=dto.description,
            ticketnumber=ticket_number,
            casetypecode=dto.casetypecode,
            prioritycode=dto.prioritycode,
            caseorigincode=dto.caseorigincode,
            accountid=account,
            contactid=contact,
            primarycontactid=primary_contact,
            productid=product,
            ownerid=owner,
            statecode=CaseStateCode.ACTIVE,
            statuscode=CaseStatusCode.IN_PROGRESS,
            createdby=user,
            modifiedby=user,
        )

        case.save()
        return case

    @staticmethod
    def get_case_by_id(case_id: UUID, user: SystemUser) -> Case:
        """
        Get case by ID with ownership check.

        Args:
            case_id: Case UUID
            user: Current user

        Returns:
            Case instance

        Raises:
            NotFound: If case doesn't exist
            PermissionDenied: If user doesn't have access
        """
        try:
            case = Case.objects.select_related(
                'ownerid', 'accountid', 'contactid',
                'primarycontactid', 'productid',
                'createdby', 'modifiedby'
            ).get(incidentid=case_id)
        except Case.DoesNotExist:
            raise NotFound(f"Case with ID {case_id} not found")

        # Check ownership (System Administrator and Sales Manager can see all)
        if user.role_name not in ["System Administrator", "Sales Manager"]:
            if case.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this case")

        return case

    @staticmethod
    def update_case(case_id: UUID, dto: UpdateCaseDto, user: SystemUser) -> Case:
        """
        Update an existing case.

        Args:
            case_id: Case UUID
            dto: Update data (partial)
            user: Current user

        Returns:
            Updated Case instance

        Raises:
            NotFound: If case doesn't exist
            PermissionDenied: If user doesn't have access
            ValidationError: If validation fails or case is not Active
        """
        case = CaseService.get_case_by_id(case_id, user)

        # Check if case is still active (can't update resolved/cancelled cases)
        if case.statecode != CaseStateCode.ACTIVE:
            raise ValidationError(
                f"Cannot update case in '{case.state_name}' state. "
                "Only active cases can be updated."
            )

        # Update simple fields (only if provided)
        update_fields = [
            'title', 'description', 'casetypecode', 'prioritycode',
        ]

        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(case, field, value)

        # Handle primary contact change
        if dto.primarycontactid is not None:
            from apps.contacts.models import Contact
            try:
                primary_contact = Contact.objects.get(contactid=dto.primarycontactid)
                case.primarycontactid = primary_contact
            except Contact.DoesNotExist:
                raise ValidationError(f"Primary contact with ID {dto.primarycontactid} not found")

        # Handle product change
        if dto.productid is not None:
            from apps.products.models import Product
            try:
                product = Product.objects.get(productid=dto.productid)
                case.productid = product
            except Product.DoesNotExist:
                raise ValidationError(f"Product with ID {dto.productid} not found")

        # Handle owner change
        if dto.ownerid is not None:
            try:
                new_owner = SystemUser.objects.get(systemuserid=dto.ownerid)
                case.ownerid = new_owner
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        case.modifiedby = user
        case.save()

        return case

    @staticmethod
    def delete_case(case_id: UUID, user: SystemUser) -> None:
        """
        Delete (cancel) a case.

        Soft delete by marking as cancelled.

        Args:
            case_id: Case UUID
            user: Current user

        Raises:
            NotFound: If case doesn't exist
            PermissionDenied: If user doesn't have access
        """
        cancel_dto = CancelCaseDto(reason="Deleted by user")
        CaseService.cancel_case(case_id, cancel_dto, user)

    @staticmethod
    def resolve_case(case_id: UUID, dto: ResolveCaseDto, user: SystemUser) -> Case:
        """
        Resolve a case.

        Sets statecode to RESOLVED, statuscode to PROBLEM_SOLVED,
        and records resolution details.

        Args:
            case_id: Case UUID
            dto: Resolution data
            user: Current user

        Returns:
            Resolved Case instance

        Raises:
            NotFound: If case doesn't exist
            PermissionDenied: If user doesn't have access
            ValidationError: If case is not Active
        """
        case = CaseService.get_case_by_id(case_id, user)

        if case.statecode != CaseStateCode.ACTIVE:
            raise ValidationError(
                f"Cannot resolve case in '{case.state_name}' state. "
                "Only active cases can be resolved."
            )

        case.statecode = CaseStateCode.RESOLVED
        case.statuscode = CaseStatusCode.PROBLEM_SOLVED
        case.resolutiontype = dto.resolutiontype
        case.resolutionsummary = dto.resolutionsummary
        case.resolvedon = timezone.now()
        case.modifiedby = user
        case.save()

        return case

    @staticmethod
    def cancel_case(case_id: UUID, dto: CancelCaseDto, user: SystemUser) -> Case:
        """
        Cancel a case.

        Sets statecode to CANCELLED and statuscode to CANCELLED.
        Optionally appends cancellation reason to description.

        Args:
            case_id: Case UUID
            dto: Cancellation data
            user: Current user

        Returns:
            Cancelled Case instance

        Raises:
            NotFound: If case doesn't exist
            PermissionDenied: If user doesn't have access
            ValidationError: If case is already cancelled
        """
        case = CaseService.get_case_by_id(case_id, user)

        if case.statecode == CaseStateCode.CANCELLED:
            raise ValidationError("Case is already cancelled.")

        case.statecode = CaseStateCode.CANCELLED
        case.statuscode = CaseStatusCode.CANCELLED

        # Add reason to description if provided
        if dto.reason:
            case.description = (case.description or '') + f"\n\nCancellation reason: {dto.reason}"

        case.modifiedby = user
        case.save()

        return case

    @staticmethod
    def reopen_case(case_id: UUID, user: SystemUser) -> Case:
        """
        Reopen a resolved or cancelled case.

        Sets statecode back to ACTIVE and statuscode to IN_PROGRESS.
        Clears resolution fields.

        Args:
            case_id: Case UUID
            user: Current user

        Returns:
            Reopened Case instance

        Raises:
            NotFound: If case doesn't exist
            PermissionDenied: If user doesn't have access
            ValidationError: If case is already active
        """
        case = CaseService.get_case_by_id(case_id, user)

        if case.statecode == CaseStateCode.ACTIVE:
            raise ValidationError("Case is already active.")

        case.statecode = CaseStateCode.ACTIVE
        case.statuscode = CaseStatusCode.IN_PROGRESS
        case.resolvedon = None
        case.resolutiontype = None
        case.resolutionsummary = None
        case.modifiedby = user
        case.save()

        return case
