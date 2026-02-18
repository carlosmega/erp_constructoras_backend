"""
Unit tests for Opportunity models.

Tests Opportunity entity including state management, validation,
computed properties, and business rules.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.opportunities.models import (
    Opportunity,
    OpportunityStateCode,
    OpportunityStatusCode,
    SalesStage,
)
from apps.opportunities.tests.factories import (
    OpportunityFactory,
    HighValueOpportunityFactory,
    LowValueOpportunityFactory,
    WonOpportunityFactory,
    LostOpportunityFactory,
    DevelopStageOpportunityFactory,
    ProposeStageOpportunityFactory,
    CloseStageOpportunityFactory,
)
from apps.users.tests.factories import SalespersonFactory
from apps.accounts.tests.factories import AccountFactory


@pytest.mark.unit
class TestOpportunityEnums:
    """Tests for Opportunity enum definitions."""

    def test_opportunity_state_code_values(self):
        """Test OpportunityStateCode enum values."""
        assert OpportunityStateCode.OPEN.value == 0
        assert OpportunityStateCode.WON.value == 1
        assert OpportunityStateCode.LOST.value == 2

        assert OpportunityStateCode.OPEN.label == 'Open'
        assert OpportunityStateCode.WON.label == 'Won'
        assert OpportunityStateCode.LOST.label == 'Lost'

    def test_opportunity_status_code_values(self):
        """Test OpportunityStatusCode enum values."""
        assert OpportunityStatusCode.IN_PROGRESS.value == 1
        assert OpportunityStatusCode.ON_HOLD.value == 2
        assert OpportunityStatusCode.WON.value == 3
        assert OpportunityStatusCode.CANCELED.value == 4
        assert OpportunityStatusCode.OUT_SOLD.value == 5

    def test_sales_stage_values(self):
        """Test SalesStage enum values."""
        assert SalesStage.QUALIFY.value == 0
        assert SalesStage.DEVELOP.value == 1
        assert SalesStage.PROPOSE.value == 2
        assert SalesStage.CLOSE.value == 3


@pytest.mark.unit
class TestOpportunityModel:
    """Tests for Opportunity model creation and basic operations."""

    def test_create_opportunity_minimal(self, db):
        """Test creating opportunity with minimal required fields."""
        owner = SalespersonFactory()
        account = AccountFactory(ownerid=owner, createdby=owner, modifiedby=owner)

        opp = Opportunity.objects.create(
            name='Test Opportunity',
            ownerid=owner,
            accountid=account,
            createdby=owner,
            modifiedby=owner,
        )

        assert opp.opportunityid is not None
        assert opp.name == 'Test Opportunity'
        assert opp.statecode == OpportunityStateCode.OPEN
        assert opp.statuscode == OpportunityStatusCode.IN_PROGRESS
        assert opp.salesstage == SalesStage.QUALIFY
        assert opp.probability == 0

    def test_create_opportunity_full(self, db):
        """Test creating opportunity with all fields."""
        owner = SalespersonFactory()
        account = AccountFactory(ownerid=owner, createdby=owner, modifiedby=owner)
        today = date.today()

        opp = Opportunity.objects.create(
            name='Big Deal Corp Opportunity',
            description='High-value enterprise deal',
            customername='Big Deal Corp',
            accountid=account,
            estimatedrevenue=Decimal('250000.00'),
            estimatedclosedate=today + timedelta(days=60),
            salesstage=SalesStage.PROPOSE,
            probability=75,
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )

        assert opp.opportunityid is not None
        assert opp.name == 'Big Deal Corp Opportunity'
        assert opp.estimatedrevenue == Decimal('250000.00')
        assert opp.salesstage == SalesStage.PROPOSE
        assert opp.probability == 75

    def test_opportunity_factory(self, db):
        """Test OpportunityFactory creates valid opportunities."""
        opp = OpportunityFactory()

        assert opp.opportunityid is not None
        assert opp.name is not None
        assert opp.ownerid is not None
        assert opp.statecode == OpportunityStateCode.OPEN
        assert opp.statuscode == OpportunityStatusCode.IN_PROGRESS

    def test_opportunity_str_representation(self, db):
        """Test __str__ method."""
        opp = OpportunityFactory(name='Test Opportunity')
        assert str(opp) == 'Test Opportunity'


@pytest.mark.unit
class TestOpportunityProperties:
    """Tests for Opportunity computed properties."""

    def test_is_open_property(self, db):
        """Test is_open property."""
        open_opp = OpportunityFactory(statecode=OpportunityStateCode.OPEN)
        won_opp = WonOpportunityFactory()

        assert open_opp.is_open is True
        assert won_opp.is_open is False

    def test_is_won_property(self, db):
        """Test is_won property."""
        open_opp = OpportunityFactory(statecode=OpportunityStateCode.OPEN)
        won_opp = WonOpportunityFactory()

        assert open_opp.is_won is False
        assert won_opp.is_won is True

    def test_is_lost_property(self, db):
        """Test is_lost property."""
        open_opp = OpportunityFactory(statecode=OpportunityStateCode.OPEN)
        lost_opp = LostOpportunityFactory()

        assert open_opp.is_lost is False
        assert lost_opp.is_lost is True

    def test_state_name_property(self, db):
        """Test state_name property returns human-readable name."""
        open_opp = OpportunityFactory(statecode=OpportunityStateCode.OPEN)
        won_opp = WonOpportunityFactory()
        lost_opp = LostOpportunityFactory()

        assert open_opp.state_name == 'Open'
        assert won_opp.state_name == 'Won'
        assert lost_opp.state_name == 'Lost'

    def test_status_name_property(self, db):
        """Test status_name property returns human-readable name."""
        in_progress_opp = OpportunityFactory(statuscode=OpportunityStatusCode.IN_PROGRESS)
        won_opp = WonOpportunityFactory()

        assert in_progress_opp.status_name == 'In Progress'
        assert won_opp.status_name == 'Won'

    def test_stage_name_property(self, db):
        """Test stage_name property."""
        qualify_opp = OpportunityFactory(salesstage=SalesStage.QUALIFY)
        develop_opp = DevelopStageOpportunityFactory()
        propose_opp = ProposeStageOpportunityFactory()
        close_opp = CloseStageOpportunityFactory()

        assert qualify_opp.stage_name == 'Qualify'
        assert develop_opp.stage_name == 'Develop'
        assert propose_opp.stage_name == 'Propose'
        assert close_opp.stage_name == 'Close'

    def test_weighted_revenue_property(self, db):
        """Test weighted_revenue calculation."""
        opp = OpportunityFactory(
            estimatedrevenue=Decimal('100000.00'),
            probability=50
        )

        expected_weighted = Decimal('100000.00') * Decimal('0.50')
        assert opp.weighted_revenue == expected_weighted

    def test_weighted_revenue_property_zero_probability(self, db):
        """Test weighted_revenue with zero probability."""
        opp = OpportunityFactory(
            estimatedrevenue=Decimal('100000.00'),
            probability=0
        )

        assert opp.weighted_revenue == Decimal('0.00')

    def test_weighted_revenue_property_null_revenue(self, db):
        """Test weighted_revenue with null revenue."""
        opp = OpportunityFactory(
            estimatedrevenue=None,
            probability=50
        )

        assert opp.weighted_revenue is None

    def test_customer_name_property_from_account(self, db):
        """Test customer_name property from account."""
        owner = SalespersonFactory()
        account = AccountFactory(name='Acme Corp', ownerid=owner, createdby=owner, modifiedby=owner)
        opp = OpportunityFactory(accountid=account, contactid=None, ownerid=owner)

        assert opp.customer_name == 'Acme Corp'

    def test_customer_name_property_from_customername(self, db):
        """Test customer_name property falls back to customername."""
        opp = OpportunityFactory(
            accountid=None,
            contactid=None,
            customername='Test Customer'
        )

        assert opp.customer_name == 'Test Customer'


@pytest.mark.unit
class TestOpportunityValidation:
    """Tests for Opportunity model validation."""

    def test_name_required(self, db):
        """Test name is required."""
        owner = SalespersonFactory()

        with pytest.raises((ValidationError, IntegrityError)):
            opp = Opportunity(
                name='',
                ownerid=owner,
            )
            opp.full_clean()

    def test_ownerid_required(self, db):
        """Test ownerid is required."""
        opp = Opportunity(name='Test')

        with pytest.raises(IntegrityError):
            opp.save()

    def test_estimated_revenue_positive(self, db):
        """Test estimatedrevenue must be positive."""
        owner = SalespersonFactory()

        # Positive value is OK
        opp_valid = Opportunity(
            name='Test',
            estimatedrevenue=Decimal('1000.00'),
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )
        opp_valid.full_clean()  # Should not raise

        # Negative value fails
        opp_invalid = Opportunity(
            name='Test',
            estimatedrevenue=Decimal('-1000.00'),
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )

        with pytest.raises(ValidationError):
            opp_invalid.full_clean()

    def test_probability_range_validation(self, db):
        """Test probability must be 0-100."""
        owner = SalespersonFactory()

        # Valid probabilities
        for prob in [0, 50, 100]:
            opp = Opportunity(
                name='Test',
                probability=prob,
                ownerid=owner,
                createdby=owner,
                modifiedby=owner,
            )
            opp.full_clean()  # Should not raise

        # Invalid probabilities
        for prob in [-1, 101, 150]:
            opp_invalid = Opportunity(
                name='Test',
                probability=prob,
                ownerid=owner,
                createdby=owner,
                modifiedby=owner,
            )
            with pytest.raises(ValidationError):
                opp_invalid.full_clean()


@pytest.mark.unit
class TestOpportunityOrdering:
    """Tests for Opportunity model ordering."""

    def test_opportunities_ordered_by_createdon_desc(self, db):
        """Test that opportunities are ordered by createdon descending."""
        opp1 = OpportunityFactory()
        opp2 = OpportunityFactory()
        opp3 = OpportunityFactory()

        opps = list(Opportunity.objects.all())

        # Most recent first
        assert opps[0].opportunityid == opp3.opportunityid
        assert opps[1].opportunityid == opp2.opportunityid
        assert opps[2].opportunityid == opp1.opportunityid


@pytest.mark.unit
class TestOpportunityFactories:
    """Tests for Opportunity factories."""

    def test_high_value_opportunity_factory(self, db):
        """Test HighValueOpportunityFactory creates high-value opportunities."""
        opp = HighValueOpportunityFactory()

        assert opp.estimatedrevenue >= Decimal('100000.00')
        assert opp.salesstage == SalesStage.PROPOSE
        assert opp.probability >= 60

    def test_low_value_opportunity_factory(self, db):
        """Test LowValueOpportunityFactory creates low-value opportunities."""
        opp = LowValueOpportunityFactory()

        assert opp.estimatedrevenue <= Decimal('10000.00')
        assert opp.salesstage == SalesStage.DEVELOP

    def test_won_opportunity_factory(self, db):
        """Test WonOpportunityFactory creates won opportunities."""
        opp = WonOpportunityFactory()

        assert opp.statecode == OpportunityStateCode.WON
        assert opp.statuscode == OpportunityStatusCode.WON
        assert opp.probability == 100
        assert opp.actualrevenue == opp.estimatedrevenue
        assert opp.actualclosedate is not None

    def test_lost_opportunity_factory(self, db):
        """Test LostOpportunityFactory creates lost opportunities."""
        opp = LostOpportunityFactory()

        assert opp.statecode == OpportunityStateCode.LOST
        assert opp.statuscode in [
            OpportunityStatusCode.CANCELED,
            OpportunityStatusCode.OUT_SOLD
        ]
        assert opp.probability == 0
        assert opp.actualrevenue == Decimal('0.00')
        assert opp.actualclosedate is not None


@pytest.mark.unit
class TestOpportunityAuditFields:
    """Tests for Opportunity audit trail fields (from AuditMixin)."""

    def test_opportunity_has_audit_fields(self, db):
        """Test that opportunity has audit fields."""
        owner = SalespersonFactory()
        opp = OpportunityFactory(ownerid=owner, createdby=owner, modifiedby=owner)

        assert hasattr(opp, 'createdon')
        assert hasattr(opp, 'modifiedon')
        assert hasattr(opp, 'createdby')
        assert hasattr(opp, 'modifiedby')

        assert opp.createdon is not None
        assert opp.modifiedon is not None
        assert opp.createdby == owner
        assert opp.modifiedby == owner

    def test_modifiedon_updates_on_save(self, db):
        """Test that modifiedon updates when opportunity is saved."""
        opp = OpportunityFactory()
        original_modifiedon = opp.modifiedon

        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)

        opp.name = 'Updated Name'
        opp.save()

        assert opp.modifiedon > original_modifiedon
