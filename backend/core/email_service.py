"""
Email service for sending document emails with HTML templates.

Wraps django.core.mail.EmailMessage with template rendering and PDF attachment support.
"""

import logging
import re
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger('core')


class EmailSendError(Exception):
    """Raised when email sending fails."""
    pass


def parse_email_list(raw: str) -> list[str]:
    """Parse a string of emails separated by ; or , into a clean list."""
    if not raw or not raw.strip():
        return []
    # Split by semicolon or comma
    emails = re.split(r'[;,]', raw)
    return [e.strip() for e in emails if e.strip()]


def send_document_email(
    *,
    to: str,
    subject: str,
    body: str,
    document_type: str,
    sender_name: str = 'Sales Team',
    cc: str = '',
    bcc: str = '',
    pdf_content: bytes | None = None,
    pdf_filename: str | None = None,
) -> None:
    """Send a document email with an HTML template and optional PDF attachment.

    Args:
        to: Recipient email(s), separated by ; or ,
        subject: Email subject line
        body: Plain text body (rendered with linebreaksbr in template)
        document_type: One of 'quote', 'order', 'invoice'
        sender_name: Name of the sender for footer display
        cc: CC email(s), separated by ; or ,
        bcc: BCC email(s), separated by ; or ,
        pdf_content: Raw PDF bytes to attach
        pdf_filename: Filename for the PDF attachment

    Raises:
        EmailSendError: If the email fails to send
    """
    to_list = parse_email_list(to)
    cc_list = parse_email_list(cc)
    bcc_list = parse_email_list(bcc)

    if not to_list:
        raise EmailSendError('At least one recipient email is required.')

    # Pick the document-specific template, fallback to base
    template_name = f'emails/{document_type}_email.html'
    try:
        html_content = render_to_string(template_name, {
            'subject': subject,
            'body': body,
            'document_type': document_type,
            'sender_name': sender_name,
            'has_attachment': pdf_content is not None,
            'attachment_filename': pdf_filename or '',
        })
    except Exception:
        # Fallback to base template if specific one not found
        html_content = render_to_string('emails/base_email.html', {
            'subject': subject,
            'body': body,
            'document_type': document_type,
            'sender_name': sender_name,
            'has_attachment': pdf_content is not None,
            'attachment_filename': pdf_filename or '',
        })

    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_list,
        cc=cc_list,
        bcc=bcc_list,
    )
    email.content_subtype = 'html'

    if pdf_content and pdf_filename:
        email.attach(pdf_filename, pdf_content, 'application/pdf')

    try:
        email.send(fail_silently=False)
        logger.info('Document email sent to=%s subject="%s" type=%s', to, subject, document_type)
    except Exception as exc:
        logger.error('Failed to send document email to=%s: %s', to, exc)
        raise EmailSendError(f'Failed to send email: {exc}') from exc
