"""Unit tests for QuoteTemplateService."""

import pytest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock

from apps.quotes.template_services import QuoteTemplateService
from apps.quotes.template_schemas import CreateQuoteTemplateDto, UpdateQuoteTemplateDto
from apps.quotes.models import QuoteTemplate
from apps.quotes.tests.factories import QuoteFactory, QuoteDetailFactory
from core.exceptions import NotFound, PermissionDenied


@pytest.mark.unit
class TestListTemplates:
    """Test QuoteTemplateService.list_templates."""

    def test_list_own_templates(self, db, salesperson):
        QuoteTemplate.objects.create(
            name='Template A', templatedata={'lines': []},
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = QuoteTemplateService.list_templates(salesperson)
        assert len(result) >= 1

    def test_list_shared_templates(self, db, salesperson, salesperson2):
        QuoteTemplate.objects.create(
            name='Shared T', templatedata={'lines': []}, isshared=True,
            ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2,
        )
        result = QuoteTemplateService.list_templates(salesperson, shared=True)
        assert any(t.name == 'Shared T' for t in result)

    def test_list_filter_by_owner(self, db, salesperson, salesperson2):
        QuoteTemplate.objects.create(
            name='Owner Filter', templatedata={},
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        QuoteTemplate.objects.create(
            name='Other', templatedata={},
            ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2,
        )
        result = QuoteTemplateService.list_templates(
            salesperson, owner=salesperson.systemuserid
        )
        assert all(t.ownerid == salesperson for t in result)


@pytest.mark.unit
class TestGetTemplateById:
    """Test QuoteTemplateService.get_template_by_id."""

    def test_get_existing_template(self, db, salesperson):
        tpl = QuoteTemplate.objects.create(
            name='Get Test', templatedata={'key': 'val'},
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = QuoteTemplateService.get_template_by_id(tpl.quotetemplateid, salesperson)
        assert result.name == 'Get Test'

    def test_get_not_found(self, db, salesperson):
        with pytest.raises(NotFound):
            QuoteTemplateService.get_template_by_id(uuid4(), salesperson)

    def test_shared_template_visible_to_all(self, db, salesperson, salesperson2):
        tpl = QuoteTemplate.objects.create(
            name='Shared Visible', templatedata={}, isshared=True,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = QuoteTemplateService.get_template_by_id(tpl.quotetemplateid, salesperson2)
        assert result.quotetemplateid == tpl.quotetemplateid

    def test_non_shared_template_denied_for_other_user(self, db, salesperson, salesperson2):
        tpl = QuoteTemplate.objects.create(
            name='Private', templatedata={}, isshared=False,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        with pytest.raises(PermissionDenied):
            QuoteTemplateService.get_template_by_id(tpl.quotetemplateid, salesperson2)


@pytest.mark.unit
class TestCreateTemplate:
    """Test QuoteTemplateService.create_template."""

    def test_create_minimal(self, db, salesperson):
        dto = CreateQuoteTemplateDto(name='New Template', templatedata={'lines': []})
        tpl = QuoteTemplateService.create_template(dto, salesperson)

        assert tpl.name == 'New Template'
        assert tpl.ownerid == salesperson
        assert tpl.isshared is False
        assert tpl.usagecount == 0

    def test_create_with_category(self, db, salesperson):
        dto = CreateQuoteTemplateDto(
            name='Categorized', templatedata={'lines': []}, category='standard',
        )
        tpl = QuoteTemplateService.create_template(dto, salesperson)
        assert tpl.category == 'standard'

    def test_create_with_invalid_owner(self, db, salesperson):
        dto = CreateQuoteTemplateDto(
            name='Bad Owner', templatedata={}, ownerid=uuid4(),
        )
        with pytest.raises(NotFound, match='Owner not found'):
            QuoteTemplateService.create_template(dto, salesperson)


@pytest.mark.unit
class TestUpdateTemplate:
    """Test QuoteTemplateService.update_template."""

    def test_update_name(self, db, salesperson):
        tpl = QuoteTemplate.objects.create(
            name='Old Name', templatedata={},
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = UpdateQuoteTemplateDto(name='New Name')
        result = QuoteTemplateService.update_template(tpl.quotetemplateid, dto, salesperson)
        assert result.name == 'New Name'

    def test_update_not_found(self, db, salesperson):
        dto = UpdateQuoteTemplateDto(name='X')
        with pytest.raises(NotFound):
            QuoteTemplateService.update_template(uuid4(), dto, salesperson)

    def test_update_denied_for_other_user(self, db, salesperson, salesperson2):
        tpl = QuoteTemplate.objects.create(
            name='Locked', templatedata={},
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = UpdateQuoteTemplateDto(name='Hacked')
        with pytest.raises(PermissionDenied):
            QuoteTemplateService.update_template(tpl.quotetemplateid, dto, salesperson2)


@pytest.mark.unit
class TestDeleteTemplate:
    """Test QuoteTemplateService.delete_template."""

    def test_delete_success(self, db, salesperson):
        tpl = QuoteTemplate.objects.create(
            name='Delete Me', templatedata={},
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        QuoteTemplateService.delete_template(tpl.quotetemplateid, salesperson)
        assert not QuoteTemplate.objects.filter(quotetemplateid=tpl.quotetemplateid).exists()

    def test_delete_not_found(self, db, salesperson):
        with pytest.raises(NotFound):
            QuoteTemplateService.delete_template(uuid4(), salesperson)

    def test_delete_denied_for_other_user(self, db, salesperson, salesperson2):
        tpl = QuoteTemplate.objects.create(
            name='Protected', templatedata={},
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        with pytest.raises(PermissionDenied):
            QuoteTemplateService.delete_template(tpl.quotetemplateid, salesperson2)


@pytest.mark.unit
class TestUseTemplate:
    """Test QuoteTemplateService.use_template."""

    def test_use_returns_template_data(self, db, salesperson):
        tpl = QuoteTemplate.objects.create(
            name='Usable', templatedata={'discount': '10', 'lines': [{'item': 'A'}]},
            isshared=True,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        data = QuoteTemplateService.use_template(tpl.quotetemplateid, {}, salesperson)
        assert data['discount'] == '10'
        assert 'ownerid' in data

    def test_use_applies_overrides(self, db, salesperson):
        tpl = QuoteTemplate.objects.create(
            name='Override', templatedata={'discount': '10', 'name': 'Original'},
            isshared=True,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        data = QuoteTemplateService.use_template(
            tpl.quotetemplateid, {'name': 'Overridden'}, salesperson
        )
        assert data['name'] == 'Overridden'

    def test_use_increments_usage_count(self, db, salesperson):
        tpl = QuoteTemplate.objects.create(
            name='Count', templatedata={}, isshared=True,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert tpl.usagecount == 0
        QuoteTemplateService.use_template(tpl.quotetemplateid, {}, salesperson)
        tpl.refresh_from_db()
        assert tpl.usagecount == 1

    def test_use_non_shared_denied(self, db, salesperson, salesperson2):
        tpl = QuoteTemplate.objects.create(
            name='Private Use', templatedata={}, isshared=False,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        with pytest.raises(PermissionDenied):
            QuoteTemplateService.use_template(tpl.quotetemplateid, {}, salesperson2)


@pytest.mark.unit
class TestCreateFromQuote:
    """Test QuoteTemplateService.create_from_quote."""

    def test_creates_template_from_quote(self, db, salesperson):
        quote = QuoteFactory(ownerid=salesperson)
        QuoteDetailFactory(
            quoteid=quote, productname='Widget', quantity=Decimal('5'),
            priceperunit=Decimal('100.00'), sequencenumber=1,
        )
        QuoteDetailFactory(
            quoteid=quote, productname='Gadget', quantity=Decimal('2'),
            priceperunit=Decimal('250.00'), sequencenumber=2,
        )

        tpl = QuoteTemplateService.create_from_quote(
            quote.quoteid, 'From Quote', salesperson,
            description='Auto-generated', category='custom', isshared=True,
        )

        assert tpl.name == 'From Quote'
        assert tpl.isshared is True
        assert tpl.category == 'custom'
        assert len(tpl.templatedata['lines']) == 2
        assert tpl.templatedata['lines'][0]['productname'] == 'Widget'

    def test_create_from_quote_not_found(self, db, salesperson):
        with pytest.raises(NotFound, match='Quote not found'):
            QuoteTemplateService.create_from_quote(uuid4(), 'X', salesperson)

    def test_create_from_quote_denied(self, db, salesperson, salesperson2):
        quote = QuoteFactory(ownerid=salesperson)
        with pytest.raises(PermissionDenied):
            QuoteTemplateService.create_from_quote(quote.quoteid, 'X', salesperson2)
