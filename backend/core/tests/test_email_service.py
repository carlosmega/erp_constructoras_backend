"""Tests for the email service module."""

import pytest
from unittest.mock import patch, MagicMock
from core.email_service import parse_email_list, send_document_email, EmailSendError


class TestParseEmailList:
    def test_semicolon_separated(self):
        result = parse_email_list("a@test.com;b@test.com")
        assert result == ["a@test.com", "b@test.com"]

    def test_comma_separated(self):
        result = parse_email_list("a@test.com, b@test.com")
        assert result == ["a@test.com", "b@test.com"]

    def test_empty_string(self):
        assert parse_email_list("") == []

    def test_none(self):
        assert parse_email_list(None) == []

    def test_whitespace_only(self):
        assert parse_email_list("   ") == []

    def test_single_email(self):
        assert parse_email_list("test@example.com") == ["test@example.com"]


class TestSendDocumentEmail:
    @patch('core.email_service.EmailMessage')
    @patch('core.email_service.render_to_string', return_value='<html>test</html>')
    def test_sends_email_successfully(self, mock_render, mock_email_cls):
        mock_email = MagicMock()
        mock_email_cls.return_value = mock_email

        send_document_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body",
            document_type="quote",
        )

        mock_email.send.assert_called_once_with(fail_silently=False)

    @patch('core.email_service.EmailMessage')
    @patch('core.email_service.render_to_string', return_value='<html>test</html>')
    def test_sends_with_pdf_attachment(self, mock_render, mock_email_cls):
        mock_email = MagicMock()
        mock_email_cls.return_value = mock_email

        send_document_email(
            to="test@example.com",
            subject="Invoice",
            body="Please find attached",
            document_type="invoice",
            pdf_content=b"PDF_DATA",
            pdf_filename="invoice.pdf",
        )

        mock_email.attach.assert_called_once_with("invoice.pdf", b"PDF_DATA", "application/pdf")
        mock_email.send.assert_called_once()

    def test_raises_on_empty_recipient(self):
        with pytest.raises(EmailSendError, match="recipient"):
            send_document_email(
                to="",
                subject="Test",
                body="Test",
                document_type="quote",
            )

    @patch('core.email_service.EmailMessage')
    @patch('core.email_service.render_to_string', side_effect=[Exception("Template not found"), '<html>fallback</html>'])
    def test_falls_back_to_base_template(self, mock_render, mock_email_cls):
        mock_email = MagicMock()
        mock_email_cls.return_value = mock_email

        send_document_email(
            to="test@example.com",
            subject="Test",
            body="Test",
            document_type="unknown",
        )

        # Should have tried specific template first, then base template
        assert mock_render.call_count == 2
        assert mock_render.call_args_list[1][0][0] == 'emails/base_email.html'

    @patch('core.email_service.EmailMessage')
    @patch('core.email_service.render_to_string', return_value='<html>test</html>')
    def test_raises_on_send_failure(self, mock_render, mock_email_cls):
        mock_email = MagicMock()
        mock_email.send.side_effect = Exception("SMTP error")
        mock_email_cls.return_value = mock_email

        with pytest.raises(EmailSendError, match="SMTP error"):
            send_document_email(
                to="test@example.com",
                subject="Test",
                body="Test",
                document_type="quote",
            )

    @patch('core.email_service.EmailMessage')
    @patch('core.email_service.render_to_string', return_value='<html>test</html>')
    def test_sends_with_cc_and_bcc(self, mock_render, mock_email_cls):
        mock_email = MagicMock()
        mock_email_cls.return_value = mock_email

        send_document_email(
            to="to@example.com",
            subject="Test",
            body="Test",
            document_type="order",
            cc="cc@example.com",
            bcc="bcc@example.com",
        )

        mock_email_cls.assert_called_once()
        call_kwargs = mock_email_cls.call_args[1]
        assert call_kwargs['cc'] == ['cc@example.com']
        assert call_kwargs['bcc'] == ['bcc@example.com']
