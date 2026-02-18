"""
Unit tests for Opportunity services.

Tests OpportunityService business logic including CRUD operations,
state management, ownership filtering, and statistics.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from apps.opportunities.models import (
    Opportunity,
    OpportunityStateCode,
    OpportunityStatusCode,
    SalesStage,
)
from apps.opportunities.services import OpportunityService
from apps.opportunities.schemas import (
    CreateOpportunityDto,
    UpdateOpportunityDto,
    CloseOpportunityDto,
)
from apps.opportunities.tests.factories import (
    OpportunityFactory,
    WonOpportunityFactory,
    LostOpportunityFactory,
)
from apps.users.tests.factories import (
    SalespersonFactory,
    SystemAdminFactory,
    SalesManagerFactory,
)
from apps.accounts.tests.factories import AccountFactory
from apps.leads.tests.factories import QualifiedLeadFactory
from core.exceptions import ValidationError, NotFound, PermissionDenied


@pytest.mark.unit
class TestListOpportunities:
    """Tests for OpportunityService.list_opportunities method."""

    def test_list_all_opportunities(self, db, salesperson):
        """Test listing all user's opportunities."""
        OpportunityFactory.create_batch(3, ownerid=salesperson)

        opps = OpportunityService.list_opportunities(salesperson)

        assert opps.count() == 3

    def test_list_opportunities_filter_by_state(self, db, salesperson):
        """Test filtering opportunities by statecode."""
        OpportunityFactory.create_batch(2, ownerid=salesperson, statecode=OpportunityStateCode.OPEN)
        WonOpportunityFactory(ownerid=salesperson)

        open_opps = OpportunityService.list_opportunities(salesperson, statecode=OpportunityStateCode.OPEN)
        won_opps = OpportunityService.list_opportunities(salesperson, statecode=OpportunityStateCode.WON)

        assert open_opps.count() == 2
        assert won_opps.count() == 1

    def test_list_opportunities_filter_by_sales_stage(self, db, salesperson):
        """Test filtering opportunities by salesstage."""
        OpportunityFactory(ownerid=salesperson, salesstage=SalesStage.QUALIFY)
        OpportunityFactory(ownerid=salesperson, salesstage=SalesStage.DEVELOP)
        OpportunityFactory(ownerid=salesperson, salesstage=SalesStage.PROPOSE)

        qualify_opps = OpportunityService.list_opportunities(salesperson, salesstage=SalesStage.QUALIFY)
        develop_opps = OpportunityService.list_opportunities(salesperson, salesstage=SalesStage.DEVELOP)

        assert qualify_opps.count() == 1
        assert develop_opps.count() == 1

    def test_list_opportunities_search(self, db, salesperson):
        """Test searching opportunities by name or description."""
        OpportunityFactory(ownerid=salesperson, name='Acme Corp Deal', customername='Acme')
        OpportunityFactory(ownerid=salesperson, name='Beta Inc Deal', customername='Beta')
        OpportunityFactory(ownerid=salesperson, name='Gamma LLC Deal', description='Important Acme partnership')

        # Search by name
        results = OpportunityService.list_opportunities(salesperson, search='Acme')
        assert results.count() >= 1

        # Search by customername
        results = OpportunityService.list_opportunities(salesperson, search='Beta')
        assert results.count() >= 1

    def test_list_opportunities_ownership_filter_salesperson(self, db, salesperson, salesperson2):
        """Test salesperson only sees their own opportunities."""
        OpportunityFactory.create_batch(2, ownerid=salesperson)
        OpportunityFactory(ownerid=salesperson2)

        opps = OpportunityService.list_opportunities(salesperson)

        assert opps.count() == 2

    def test_list_opportunities_ownership_filter_admin_sees_all(self, db, system_admin, salesperson):
        """Test system admin sees all opportunities."""
        OpportunityFactory.create_batch(2, ownerid=salesperson)
        OpportunityFactory(ownerid=system_admin)

        opps = OpportunityService.list_opportunities(system_admin)

        assert opps.count() == 3

    def test_list_opportunities_filter_by_owner(self, db, sales_manager, salesperson):
        """Test sales manager can filter by owner."""
        OpportunityFactory.create_batch(2, ownerid=salesperson)
        OpportunityFactory(ownerid=sales_manager)

        opps = OpportunityService.list_opportunities(sales_manager, ownerid=salesperson.systemuserid)

        assert opps.count() == 2

    def test_list_opportunities_filter_by_owner_permission_denied(self, db, salesperson, salesperson2):
        """Test salesperson cannot filter by other owner."""
        OpportunityFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="cannot view other users"):
            OpportunityService.list_opportunities(salesperson, ownerid=salesperson2.systemuserid)


@pytest.mark.unit
class TestCreateOpportunity:
    """Tests for OpportunityService.create_opportunity method."""

    def test_create_opportunity_success(self, db, salesperson):
        """Test successful opportunity creation."""
        dto = CreateOpportunityDto(
            name='New Deal',
            description='Test opportunity',
            customername='Test Corp',
            estimatedrevenue=Decimal('50000.00'),
            estimatedclosedate=date.today() + timedelta(days=30),
            salesstage=SalesStage.QUALIFY,
            probability=25,
        )

        opp = OpportunityService.create_opportunity(dto, salesperson)

        assert opp.opportunityid is not None
        assert opp.name == 'New Deal'
        assert opp.estimatedrevenue == Decimal('50000.00')
        assert opp.statecode == OpportunityStateCode.OPEN
        assert opp.statuscode == OpportunityStatusCode.IN_PROGRESS
        assert opp.ownerid == salesperson
        assert opp.createdby == salesperson

    def test_create_opportunity_with_originating_lead(self, db, salesperson):
        """Test creating opportunity from qualified lead."""
        lead = QualifiedLeadFactory(ownerid=salesperson)

        dto = CreateOpportunityDto(
            name='Deal from Lead',
            originatingleadid=lead.leadid,
        )

        opp = OpportunityService.create_opportunity(dto, salesperson)

        assert opp.originatingleadid == lead

    def test_create_opportunity_with_custom_owner(self, db, salesperson, salesperson2):
        """Test creating opportunity with different owner."""
        dto = CreateOpportunityDto(
            name='Assigned Deal',
            ownerid=salesperson2.systemuserid,
        )

        opp = OpportunityService.create_opportunity(dto, salesperson)

        assert opp.ownerid == salesperson2
        assert opp.createdby == salesperson

    def test_create_opportunity_invalid_owner(self, db, salesperson):
        """Test creating opportunity with invalid owner."""
        dto = CreateOpportunityDto(
            name='Invalid Owner Deal',
            ownerid=uuid4(),
        )

        with pytest.raises(ValidationError, match='Owner with ID'):
            OpportunityService.create_opportunity(dto, salesperson)

    def test_create_opportunity_invalid_probability(self, db, salesperson):
        """Test creating opportunity with invalid probability."""
        dto = CreateOpportunityDto(
            name='Invalid Probability',
            probability=150,
        )

        with pytest.raises(ValidationError, match='Probability must be between 0 and 100'):
            OpportunityService.create_opportunity(dto, salesperson)


@pytest.mark.unit
class TestGetOpportunityById:
    """Tests for OpportunityService.get_opportunity_by_id method."""

    def test_get_opportunity_by_id_success(self, db, salesperson):
        """Test getting opportunity by ID."""
        opp = OpportunityFactory(ownerid=salesperson)

        retrieved_opp = OpportunityService.get_opportunity_by_id(opp.opportunityid, salesperson)

        assert retrieved_opp.opportunityid == opp.opportunityid
        assert retrieved_opp.name == opp.name

    def test_get_opportunity_by_id_not_found(self, db, salesperson):
        """Test getting non-existent opportunity."""
        invalid_id = uuid4()

        with pytest.raises(NotFound, match='not found'):
            OpportunityService.get_opportunity_by_id(invalid_id, salesperson)

    def test_get_opportunity_by_id_permission_denied(self, db, salesperson, salesperson2):
        """Test salesperson cannot access other's opportunity."""
        opp = OpportunityFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="don't have access"):
            OpportunityService.get_opportunity_by_id(opp.opportunityid, salesperson)

    def test_get_opportunity_by_id_admin_access_all(self, db, system_admin, salesperson):
        """Test admin can access any opportunity."""
        opp = OpportunityFactory(ownerid=salesperson)

        retrieved_opp = OpportunityService.get_opportunity_by_id(opp.opportunityid, system_admin)

        assert retrieved_opp.opportunityid == opp.opportunityid


@pytest.mark.unit
class TestUpdateOpportunity:
    """Tests for OpportunityService.update_opportunity method."""

    def test_update_opportunity_name(self, db, salesperson):
        """Test updating opportunity name."""
        opp = OpportunityFactory(ownerid=salesperson, name='Old Name')

        dto = UpdateOpportunityDto(name='New Name')
        updated_opp = OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

        assert updated_opp.name == 'New Name'

    def test_update_opportunity_revenue(self, db, salesperson):
        """Test updating estimated revenue."""
        opp = OpportunityFactory(ownerid=salesperson, estimatedrevenue=Decimal('10000.00'))

        dto = UpdateOpportunityDto(estimatedrevenue=Decimal('20000.00'))
        updated_opp = OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

        assert updated_opp.estimatedrevenue == Decimal('20000.00')

    def test_update_opportunity_sales_stage(self, db, salesperson):
        """Test updating sales stage."""
        opp = OpportunityFactory(ownerid=salesperson, salesstage=SalesStage.QUALIFY)

        dto = UpdateOpportunityDto(salesstage=SalesStage.DEVELOP)
        updated_opp = OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

        assert updated_opp.salesstage == SalesStage.DEVELOP

    def test_update_opportunity_probability(self, db, salesperson):
        """Test updating probability."""
        opp = OpportunityFactory(ownerid=salesperson, probability=25)

        dto = UpdateOpportunityDto(probability=75)
        updated_opp = OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

        assert updated_opp.probability == 75

    def test_update_opportunity_invalid_probability(self, db, salesperson):
        """Test updating with invalid probability."""
        opp = OpportunityFactory(ownerid=salesperson)

        dto = UpdateOpportunityDto(probability=150)

        with pytest.raises(ValidationError, match='Probability must be between 0 and 100'):
            OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

    def test_update_opportunity_account_reference(self, db, salesperson):
        """Test updating account reference."""
        owner = salesperson
        account = AccountFactory(ownerid=owner, createdby=owner, modifiedby=owner)
        opp = OpportunityFactory(ownerid=salesperson, accountid=None)

        dto = UpdateOpportunityDto(accountid=account.accountid)
        updated_opp = OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

        assert updated_opp.accountid == account

    def test_update_opportunity_invalid_account(self, db, salesperson):
        """Test updating with invalid account."""
        opp = OpportunityFactory(ownerid=salesperson)

        dto = UpdateOpportunityDto(accountid=uuid4())

        with pytest.raises(ValidationError, match='Account with ID'):
            OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

    def test_update_opportunity_cannot_update_closed(self, db, salesperson):
        """Test cannot update closed opportunity."""
        opp = WonOpportunityFactory(ownerid=salesperson)

        dto = UpdateOpportunityDto(name='New Name')

        with pytest.raises(ValidationError, match='Cannot update opportunity'):
            OpportunityService.update_opportunity(opp.opportunityid, dto, salesperson)

    def test_update_opportunity_not_found(self, db, salesperson):
        """Test updating non-existent opportunity."""
        dto = UpdateOpportunityDto(name='New Name')

        with pytest.raises(NotFound):
            OpportunityService.update_opportunity(uuid4(), dto, salesperson)


@pytest.mark.unit
@pytest.mark.workflow
class TestCloseOpportunity:
    """Tests for OpportunityService.close_opportunity method."""

    def test_close_opportunity_as_won(self, db, salesperson):
        """Test closing opportunity as won."""
        opp = OpportunityFactory(
            ownerid=salesperson,
            estimatedrevenue=Decimal('100000.00')
        )

        dto = CloseOpportunityDto(
            status=OpportunityStatusCode.WON,
            actualrevenue=Decimal('95000.00'),
            closingnotes='Customer signed contract'
        )

        closed_opp = OpportunityService.close_opportunity(opp.opportunityid, dto, salesperson)

        assert closed_opp.statecode == OpportunityStateCode.WON
        assert closed_opp.statuscode == OpportunityStatusCode.WON
        assert closed_opp.actualrevenue == Decimal('95000.00')
        assert closed_opp.probability == 100
        assert closed_opp.actualclosedate is not None
        assert 'Customer signed contract' in closed_opp.description

    def test_close_opportunity_as_won_default_revenue(self, db, salesperson):
        """Test closing as won uses estimated revenue if not provided."""
        opp = OpportunityFactory(
            ownerid=salesperson,
            estimatedrevenue=Decimal('100000.00')
        )

        dto = CloseOpportunityDto(status=OpportunityStatusCode.WON)
        closed_opp = OpportunityService.close_opportunity(opp.opportunityid, dto, salesperson)

        assert closed_opp.actualrevenue == Decimal('100000.00')

    def test_close_opportunity_as_lost_canceled(self, db, salesperson):
        """Test closing opportunity as lost/canceled."""
        opp = OpportunityFactory(ownerid=salesperson)

        dto = CloseOpportunityDto(
            status=OpportunityStatusCode.CANCELED,
            closingnotes='Customer went with competitor'
        )

        closed_opp = OpportunityService.close_opportunity(opp.opportunityid, dto, salesperson)

        assert closed_opp.statecode == OpportunityStateCode.LOST
        assert closed_opp.statuscode == OpportunityStatusCode.CANCELED
        assert closed_opp.actualrevenue == Decimal('0.00')
        assert closed_opp.probability == 0

    def test_close_opportunity_as_lost_outsold(self, db, salesperson):
        """Test closing opportunity as lost/out-sold."""
        opp = OpportunityFactory(ownerid=salesperson)

        dto = CloseOpportunityDto(status=OpportunityStatusCode.OUT_SOLD)
        closed_opp = OpportunityService.close_opportunity(opp.opportunityid, dto, salesperson)

        assert closed_opp.statecode == OpportunityStateCode.LOST
        assert closed_opp.statuscode == OpportunityStatusCode.OUT_SOLD

    def test_close_opportunity_already_closed(self, db, salesperson):
        """Test cannot close already closed opportunity."""
        opp = WonOpportunityFactory(ownerid=salesperson)

        dto = CloseOpportunityDto(status=OpportunityStatusCode.WON)

        with pytest.raises(ValidationError, match='already closed'):
            OpportunityService.close_opportunity(opp.opportunityid, dto, salesperson)

    def test_close_opportunity_invalid_status(self, db, salesperson):
        """Test closing with invalid status."""
        opp = OpportunityFactory(ownerid=salesperson)

        dto = CloseOpportunityDto(status=OpportunityStatusCode.IN_PROGRESS)

        with pytest.raises(ValidationError, match='Invalid closing status'):
            OpportunityService.close_opportunity(opp.opportunityid, dto, salesperson)


@pytest.mark.unit
class TestDeleteOpportunity:
    """Tests for OpportunityService.delete_opportunity method."""

    def test_delete_opportunity_success(self, db, salesperson):
        """Test successful opportunity deletion (soft close as canceled)."""
        opp = OpportunityFactory(ownerid=salesperson)

        deleted_opp = OpportunityService.delete_opportunity(opp.opportunityid, salesperson)

        assert deleted_opp.statecode == OpportunityStateCode.LOST
        assert deleted_opp.statuscode == OpportunityStatusCode.CANCELED
        assert 'Deleted by user' in deleted_opp.description


@pytest.mark.unit
class TestGetOpportunityStats:
    """Tests for OpportunityService.get_opportunity_stats method."""

    def test_get_opportunity_stats_basic(self, db, salesperson):
        """Test basic opportunity statistics."""
        OpportunityFactory.create_batch(2, ownerid=salesperson, statecode=OpportunityStateCode.OPEN)
        WonOpportunityFactory(ownerid=salesperson)
        LostOpportunityFactory(ownerid=salesperson)

        stats = OpportunityService.get_opportunity_stats(salesperson)

        assert stats.total_opportunities == 4
        assert stats.open_opportunities == 2
        assert stats.won_opportunities == 1
        assert stats.lost_opportunities == 1

    def test_get_opportunity_stats_revenue(self, db, salesperson):
        """Test revenue statistics."""
        OpportunityFactory(
            ownerid=salesperson,
            estimatedrevenue=Decimal('50000.00'),
            statecode=OpportunityStateCode.OPEN
        )
        WonOpportunityFactory(
            ownerid=salesperson,
            estimatedrevenue=Decimal('100000.00'),
            actualrevenue=Decimal('95000.00')
        )

        stats = OpportunityService.get_opportunity_stats(salesperson)

        assert stats.total_estimated_revenue >= Decimal('50000.00')
        assert stats.total_actual_revenue >= Decimal('95000.00')

    def test_get_opportunity_stats_win_rate(self, db, salesperson):
        """Test win rate calculation."""
        WonOpportunityFactory.create_batch(3, ownerid=salesperson)
        LostOpportunityFactory(ownerid=salesperson)

        stats = OpportunityService.get_opportunity_stats(salesperson)

        # 3 won / 4 total closed = 75%
        assert stats.win_rate == 75.0

    def test_get_opportunity_stats_weighted_revenue(self, db, salesperson):
        """Test weighted revenue calculation."""
        OpportunityFactory(
            ownerid=salesperson,
            estimatedrevenue=Decimal('100000.00'),
            probability=50,
            statecode=OpportunityStateCode.OPEN
        )

        stats = OpportunityService.get_opportunity_stats(salesperson)

        # 100,000 * 50% = 50,000
        assert stats.total_weighted_revenue == Decimal('50000.00')
