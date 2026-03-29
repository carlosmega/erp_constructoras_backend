"""Tests for file upload feature on ExpenseAttachment.

Covers:
- Model: FileField on ExpenseAttachment
- Service: add_attachment with file, remove_attachment deletes physical file, get_attachment
- Schema: download_url resolver
- Router: multipart upload endpoint, download endpoint
"""

import os
import pytest
from uuid import uuid4
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.expenses.models import ExpenseAttachment, AttachmentTypeCode
from apps.expenses.services import AttachmentService
from apps.expenses.schemas import ExpenseAttachmentSchema
from apps.expenses.tests.factories import (
    ProjectExpenseFactory,
    ExpenseAttachmentFactory,
)
from apps.projects.tests.factories import ConstructionProjectFactory
from apps.budgets.tests.factories import ImputationPeriodFactory
from core.exceptions import NotFound


# =============================================================================
# Model Tests
# =============================================================================

@pytest.mark.unit
class TestExpenseAttachmentFileField:
    """Tests for the FileField on ExpenseAttachment model."""

    def test_attachment_file_field_is_nullable(self, db):
        """FileField should be nullable for backwards compatibility."""
        attachment = ExpenseAttachmentFactory()
        assert attachment.file.name is None or attachment.file.name == ''

    def test_attachment_with_file_saves_to_disk(self, db, settings):
        """Attachment with a real file saves to MEDIA_ROOT."""
        xml_content = b'<?xml version="1.0"?><cfdi>test</cfdi>'
        uploaded = SimpleUploadedFile(
            'factura.xml',
            xml_content,
            content_type='application/xml',
        )

        expense = ProjectExpenseFactory()
        attachment = ExpenseAttachment.objects.create(
            expenseid=expense,
            filename='factura.xml',
            suggestedfilename='factura.xml',
            filetype=AttachmentTypeCode.XML,
            filesize=len(xml_content),
            mimetype='application/xml',
            file=uploaded,
        )

        assert attachment.file is not None
        assert attachment.file.name != ''
        assert 'expenses/attachments/' in attachment.file.name
        # Verify file is on disk
        assert os.path.exists(attachment.file.path)

        # Cleanup
        attachment.file.delete(save=False)

    def test_attachment_without_file_still_works(self, db):
        """Attachment without a file (legacy) still works."""
        attachment = ExpenseAttachmentFactory(storageurl='https://example.com/file.pdf')
        assert attachment.attachmentid is not None
        assert attachment.storageurl == 'https://example.com/file.pdf'


# =============================================================================
# Service Tests
# =============================================================================

@pytest.mark.unit
class TestAttachmentServiceFileUpload:
    """Tests for AttachmentService with file upload support."""

    def test_add_attachment_with_file(self, db, salesperson):
        """add_attachment with a real file saves it via FileField."""
        expense = ProjectExpenseFactory(ownerid=salesperson)
        xml_content = b'<?xml version="1.0"?><cfdi>data</cfdi>'
        uploaded = SimpleUploadedFile(
            'invoice.xml',
            xml_content,
            content_type='application/xml',
        )

        attachment = AttachmentService.add_attachment(
            expense_id=expense.expenseid,
            filename='invoice.xml',
            suggestedfilename='invoice.xml',
            filetype=AttachmentTypeCode.XML,
            filesize=len(xml_content),
            mimetype='application/xml',
            file=uploaded,
            user=salesperson,
        )

        assert attachment.attachmentid is not None
        assert attachment.filename == 'invoice.xml'
        assert attachment.file is not None
        assert attachment.file.name != ''
        assert os.path.exists(attachment.file.path)

        # Cleanup
        attachment.file.delete(save=False)

    def test_add_attachment_without_file(self, db, salesperson):
        """add_attachment without file creates metadata-only record."""
        expense = ProjectExpenseFactory(ownerid=salesperson)

        attachment = AttachmentService.add_attachment(
            expense_id=expense.expenseid,
            filename='manual.pdf',
            suggestedfilename='manual.pdf',
            filetype=AttachmentTypeCode.PDF,
            filesize=1024,
            mimetype='application/pdf',
            user=salesperson,
        )

        assert attachment.attachmentid is not None
        assert attachment.filename == 'manual.pdf'
        assert not attachment.file

    def test_add_attachment_invalid_expense_raises_not_found(self, db, salesperson):
        """add_attachment with non-existent expense raises NotFound."""
        with pytest.raises(NotFound):
            AttachmentService.add_attachment(
                expense_id=uuid4(),
                filename='test.pdf',
                suggestedfilename='test.pdf',
                filetype=AttachmentTypeCode.PDF,
                filesize=100,
                mimetype='application/pdf',
                user=salesperson,
            )

    def test_get_attachment(self, db, salesperson):
        """get_attachment returns an attachment by ID."""
        expense = ProjectExpenseFactory(ownerid=salesperson)
        attachment = ExpenseAttachmentFactory(expenseid=expense)

        result = AttachmentService.get_attachment(attachment.attachmentid)
        assert result.attachmentid == attachment.attachmentid

    def test_get_attachment_not_found(self, db):
        """get_attachment raises NotFound for non-existent ID."""
        with pytest.raises(NotFound):
            AttachmentService.get_attachment(uuid4())

    def test_remove_attachment_deletes_physical_file(self, db, salesperson):
        """remove_attachment deletes the physical file from disk."""
        expense = ProjectExpenseFactory(ownerid=salesperson)
        xml_content = b'<?xml version="1.0"?><cfdi>delete-me</cfdi>'
        uploaded = SimpleUploadedFile(
            'to_delete.xml',
            xml_content,
            content_type='application/xml',
        )

        attachment = AttachmentService.add_attachment(
            expense_id=expense.expenseid,
            filename='to_delete.xml',
            suggestedfilename='to_delete.xml',
            filetype=AttachmentTypeCode.XML,
            filesize=len(xml_content),
            mimetype='application/xml',
            file=uploaded,
            user=salesperson,
        )

        file_path = attachment.file.path
        assert os.path.exists(file_path)

        AttachmentService.remove_attachment(attachment.attachmentid, salesperson)

        # File should be deleted from disk
        assert not os.path.exists(file_path)
        # Record should be deleted from DB
        assert not ExpenseAttachment.objects.filter(
            attachmentid=attachment.attachmentid
        ).exists()

    def test_remove_attachment_without_file(self, db, salesperson):
        """remove_attachment works for attachments without physical files."""
        expense = ProjectExpenseFactory(ownerid=salesperson)
        attachment = ExpenseAttachmentFactory(expenseid=expense)

        AttachmentService.remove_attachment(attachment.attachmentid, salesperson)

        assert not ExpenseAttachment.objects.filter(
            attachmentid=attachment.attachmentid
        ).exists()

    def test_remove_attachment_not_found(self, db, salesperson):
        """remove_attachment raises NotFound for non-existent ID."""
        with pytest.raises(NotFound):
            AttachmentService.remove_attachment(uuid4(), salesperson)

    def test_list_attachments(self, db, salesperson):
        """list_attachments returns all attachments for an expense."""
        expense = ProjectExpenseFactory(ownerid=salesperson)
        ExpenseAttachmentFactory(expenseid=expense)
        ExpenseAttachmentFactory(expenseid=expense)

        attachments = AttachmentService.list_attachments(expense.expenseid)
        assert attachments.count() == 2


# =============================================================================
# Schema Tests
# =============================================================================

@pytest.mark.unit
class TestExpenseAttachmentSchemaDownloadUrl:
    """Tests for download_url resolver on ExpenseAttachmentSchema."""

    def test_download_url_with_file(self, db):
        """download_url returns API endpoint when file is present."""
        expense = ProjectExpenseFactory()
        xml_content = b'<?xml version="1.0"?><cfdi>schema-test</cfdi>'
        uploaded = SimpleUploadedFile(
            'schema_test.xml',
            xml_content,
            content_type='application/xml',
        )

        attachment = ExpenseAttachment.objects.create(
            expenseid=expense,
            filename='schema_test.xml',
            suggestedfilename='schema_test.xml',
            filetype=AttachmentTypeCode.XML,
            filesize=len(xml_content),
            mimetype='application/xml',
            file=uploaded,
        )

        url = ExpenseAttachmentSchema.resolve_download_url(attachment)
        assert url == f"/api/attachments/attachments/{attachment.attachmentid}/download/"

        # Cleanup
        attachment.file.delete(save=False)

    def test_download_url_fallback_to_storageurl(self, db):
        """download_url falls back to storageurl when no file."""
        attachment = ExpenseAttachmentFactory(
            storageurl='https://example.com/legacy.pdf'
        )

        url = ExpenseAttachmentSchema.resolve_download_url(attachment)
        assert url == 'https://example.com/legacy.pdf'

    def test_download_url_returns_none_when_no_file_or_url(self, db):
        """download_url returns None when neither file nor storageurl."""
        attachment = ExpenseAttachmentFactory(storageurl='')

        url = ExpenseAttachmentSchema.resolve_download_url(attachment)
        assert url is None


# =============================================================================
# Router Tests
# =============================================================================

@pytest.mark.contract
class TestAttachmentUploadEndpoint:
    """Tests for multipart file upload endpoint."""

    def test_upload_attachment_returns_201(self, auth_client, salesperson):
        """POST multipart upload returns 201 with attachment data."""
        project = ConstructionProjectFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson
        )
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )

        xml_content = b'<?xml version="1.0"?><cfdi>upload-test</cfdi>'

        response = auth_client.post(
            f'/api/attachments/expenses/{expense.expenseid}/attachments/',
            {
                'file': SimpleUploadedFile('test.xml', xml_content, content_type='application/xml'),
                'filename': 'test.xml',
                'suggestedfilename': 'test.xml',
                'filetype': str(AttachmentTypeCode.XML),
                'filesize': str(len(xml_content)),
                'mimetype': 'application/xml',
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data['filename'] == 'test.xml'
        assert data['download_url'] is not None
        assert '/download/' in data['download_url']

        # Cleanup: delete the uploaded file
        att = ExpenseAttachment.objects.get(attachmentid=data['attachmentid'])
        if att.file:
            att.file.delete(save=False)

    def test_upload_pdf_attachment(self, auth_client, salesperson):
        """POST multipart upload works for PDF files."""
        project = ConstructionProjectFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson
        )
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )

        pdf_content = b'%PDF-1.4 fake pdf content'

        response = auth_client.post(
            f'/api/attachments/expenses/{expense.expenseid}/attachments/',
            {
                'file': SimpleUploadedFile('report.pdf', pdf_content, content_type='application/pdf'),
                'filename': 'report.pdf',
                'suggestedfilename': 'report.pdf',
                'filetype': str(AttachmentTypeCode.PDF),
                'filesize': str(len(pdf_content)),
                'mimetype': 'application/pdf',
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data['mimetype'] == 'application/pdf'

        # Cleanup
        att = ExpenseAttachment.objects.get(attachmentid=data['attachmentid'])
        if att.file:
            att.file.delete(save=False)


@pytest.mark.contract
class TestAttachmentDownloadEndpoint:
    """Tests for file download endpoint."""

    def test_download_attachment_returns_file(self, auth_client, salesperson):
        """GET download endpoint returns file content."""
        project = ConstructionProjectFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson
        )
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )

        xml_content = b'<?xml version="1.0"?><cfdi>download-test</cfdi>'
        uploaded = SimpleUploadedFile('download.xml', xml_content, content_type='application/xml')

        attachment = AttachmentService.add_attachment(
            expense_id=expense.expenseid,
            filename='download.xml',
            suggestedfilename='download.xml',
            filetype=AttachmentTypeCode.XML,
            filesize=len(xml_content),
            mimetype='application/xml',
            file=uploaded,
            user=salesperson,
        )

        response = auth_client.get(
            f'/api/attachments/attachments/{attachment.attachmentid}/download/'
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/xml'
        # FileResponse uses streaming_content
        content = b''.join(response.streaming_content)
        assert b'download-test' in content

        # Cleanup
        attachment.file.delete(save=False)

    def test_download_attachment_without_file_returns_404(self, auth_client, salesperson):
        """GET download for attachment without physical file returns 404."""
        project = ConstructionProjectFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson
        )
        period = ImputationPeriodFactory(projectid=project, createdby=salesperson)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        attachment = ExpenseAttachmentFactory(expenseid=expense)

        response = auth_client.get(
            f'/api/attachments/attachments/{attachment.attachmentid}/download/'
        )

        assert response.status_code == 404

    def test_download_nonexistent_attachment_returns_404(self, auth_client, salesperson):
        """GET download for non-existent attachment returns 404."""
        fake_id = uuid4()
        response = auth_client.get(
            f'/api/attachments/attachments/{fake_id}/download/'
        )

        assert response.status_code == 404


@pytest.mark.contract
class TestAttachmentDeleteEndpoint:
    """Tests for attachment deletion endpoint with file cleanup."""

    def test_delete_attachment_with_file(self, admin_auth_client, system_admin):
        """DELETE removes attachment record and physical file."""
        project = ConstructionProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        period = ImputationPeriodFactory(projectid=project, createdby=system_admin)
        expense = ProjectExpenseFactory(
            projectid=project, periodid=period,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )

        xml_content = b'<?xml version="1.0"?><cfdi>delete-via-api</cfdi>'
        uploaded = SimpleUploadedFile('api_delete.xml', xml_content, content_type='application/xml')

        attachment = AttachmentService.add_attachment(
            expense_id=expense.expenseid,
            filename='api_delete.xml',
            suggestedfilename='api_delete.xml',
            filetype=AttachmentTypeCode.XML,
            filesize=len(xml_content),
            mimetype='application/xml',
            file=uploaded,
            user=system_admin,
        )

        file_path = attachment.file.path
        assert os.path.exists(file_path)

        response = admin_auth_client.delete(
            f'/api/attachments/attachments/{attachment.attachmentid}/'
        )

        assert response.status_code == 204
        assert not os.path.exists(file_path)
        assert not ExpenseAttachment.objects.filter(
            attachmentid=attachment.attachmentid
        ).exists()
