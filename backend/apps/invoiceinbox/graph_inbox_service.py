"""
Graph API inbox service for fetching invoice attachments from project shared mailboxes.

Extends the existing Microsoft Graph integration to download email attachments
(XML/PDF) from each project's O365 shared mailbox, parse CFDI XMLs, and create
IncomingInvoice records in Draft state (project auto-assigned).
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from django.core.files.base import ContentFile
from django.utils import timezone as dj_timezone

from apps.graph.services import MicrosoftAuthService, GRAPH_BASE_URL
from apps.invoiceinbox.cfdi_parser import CfdiParser, CfdiParseError
from apps.invoiceinbox.models import (
    IncomingInvoice,
    IncomingInvoiceStateCode,
    InboxSyncLog,
    SyncStatusCode,
    SyncTriggerCode,
)
from apps.invoiceinbox.services import InboxMatchingService
from apps.projects.models import ConstructionProject
from apps.users.models import SystemUser

logger = logging.getLogger(__name__)

# Attachment content types we care about
XML_CONTENT_TYPES = {'text/xml', 'application/xml', 'application/xslt+xml'}

# Max attachment size to download (10 MB)
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024


class GraphInboxService:
    """Fetches invoice attachments from project shared mailboxes via Microsoft Graph API."""

    @staticmethod
    def sync_inbox(
        project: ConstructionProject,
        user: SystemUser,
        triggered_by: int = SyncTriggerCode.MANUAL,
        since_days: int = 30,
        max_results: int = 50,
    ) -> InboxSyncLog:
        """
        Sync inbox for a specific project's shared mailbox.

        Uses /users/{projectemail}/messages to read the project's shared mailbox.

        1. Get authenticated Graph session
        2. Fetch recent messages with attachments from project's shared mailbox
        3. For each message with XML/PDF attachments:
           a. Check dedup (graphmessageid)
           b. Download attachments
           c. If XML: parse CFDI, create IncomingInvoice in Draft (auto-assigned to project)
           d. If PDF from same email: attach to matching IncomingInvoice
        4. Run matching against existing expenses
        5. Return InboxSyncLog
        """
        sync_log = InboxSyncLog(
            projectid=project,
            syncstatus=SyncStatusCode.SUCCESS,
            triggeredby=triggered_by,
            triggeredbyuserid=user,
        )

        if not project.projectemail:
            sync_log.syncstatus = SyncStatusCode.FAILED
            sync_log.errorscount = 1
            sync_log.errorsdetail = [
                f'Project {project.projectnumber} has no email configured'
            ]
            sync_log.completedon = dj_timezone.now()
            sync_log.save()
            return sync_log

        errors = []

        try:
            session = MicrosoftAuthService.get_authenticated_session(user)
        except Exception as e:
            sync_log.syncstatus = SyncStatusCode.FAILED
            sync_log.errorscount = 1
            sync_log.errorsdetail = [f'Authentication failed: {e}']
            sync_log.completedon = dj_timezone.now()
            sync_log.save()
            return sync_log

        # Fetch messages with attachments from the project's shared mailbox
        try:
            messages = GraphInboxService._fetch_messages(
                session, project.projectemail, since_days, max_results
            )
        except Exception as e:
            sync_log.syncstatus = SyncStatusCode.FAILED
            sync_log.errorscount = 1
            sync_log.errorsdetail = [f'Failed to fetch emails: {e}']
            sync_log.completedon = dj_timezone.now()
            sync_log.save()
            return sync_log

        sync_log.totalemailsfetched = len(messages)

        for msg in messages:
            graph_msg_id = msg.get('id', '')

            # Dedup by Graph message ID
            if IncomingInvoice.objects.filter(graphmessageid=graph_msg_id).exists():
                sync_log.duplicatesskipped += 1
                continue

            try:
                xml_count = GraphInboxService._process_message(
                    session, msg, project, user
                )
                sync_log.newxmlattachments += xml_count
            except Exception as e:
                error_msg = (
                    f'Error processing email '
                    f'"{msg.get("subject", "?")[:50]}": {e}'
                )
                logger.warning(error_msg)
                errors.append(error_msg)

        if errors:
            sync_log.syncstatus = SyncStatusCode.PARTIAL
            sync_log.errorscount = len(errors)
            sync_log.errorsdetail = errors

        sync_log.completedon = dj_timezone.now()
        sync_log.save()

        logger.info(
            'Inbox sync for project %s: fetched=%d, new_xml=%d, new_pdf=%d, dupes=%d, errors=%d',
            project.projectnumber, sync_log.totalemailsfetched,
            sync_log.newxmlattachments, sync_log.newpdfattachments,
            sync_log.duplicatesskipped, sync_log.errorscount,
        )

        return sync_log

    @staticmethod
    def _fetch_messages(
        session, project_email: str, since_days: int, max_results: int
    ) -> list[dict]:
        """Fetch messages with attachments from the project's shared mailbox.

        Uses the same pattern as GraphProjectEmailService.fetch_emails (which
        works reliably): params dict, $orderby only, NO $filter.

        Graph API shared mailbox endpoint (/users/{email}/messages) rejects
        $filter + $orderby combinations with 400 Bad Request, so we fetch
        more results and filter client-side by date and hasAttachments.
        """
        since_dt = datetime.now(timezone.utc) - timedelta(days=since_days)

        url = f'{GRAPH_BASE_URL}/users/{project_email}/messages'
        params = {
            '$select': 'id,subject,from,receivedDateTime,internetMessageId,hasAttachments',
            '$top': str(max_results * 3),
            '$orderby': 'receivedDateTime desc',
        }

        try:
            resp = session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            messages = resp.json().get('value', [])

            # Filter client-side: only messages with attachments + within date range
            result = []
            for m in messages:
                if not m.get('hasAttachments'):
                    continue
                received = GraphInboxService._parse_datetime(m.get('receivedDateTime'))
                if received and received < since_dt:
                    break  # Messages are ordered desc, so we can stop early
                result.append(m)
                if len(result) >= max_results:
                    break

            return result
        except Exception as e:
            logger.error(
                'Graph API message fetch failed for %s: %s', project_email, e
            )
            raise

    @staticmethod
    def _process_message(
        session, msg: dict, project: ConstructionProject, user: SystemUser
    ) -> int:
        """
        Process a single message: fetch its XML attachments and create invoices.

        Returns xml_count of new IncomingInvoice records created.
        PDFs are ignored — the XML CFDI contains all the fiscal data needed.
        """
        graph_msg_id = msg.get('id', '')
        project_email = project.projectemail
        email_metadata = {
            'emailmessageid': msg.get('internetMessageId', ''),
            'emailsubject': (msg.get('subject') or '(Sin asunto)')[:500],
            'emailfrom': (
                msg.get('from', {}).get('emailAddress', {}).get('address', '')
            ),
            'emailreceivedon': GraphInboxService._parse_datetime(
                msg.get('receivedDateTime')
            ),
            'graphmessageid': graph_msg_id,
        }

        # Fetch attachments list using the project's shared mailbox
        attachments = GraphInboxService._fetch_attachments(
            session, graph_msg_id, project_email
        )

        xml_count = 0

        for att in attachments:
            content_type = (att.get('contentType') or '').lower()
            filename = att.get('name', '')
            size = att.get('size', 0)

            if size > MAX_ATTACHMENT_SIZE:
                continue

            is_xml = (
                content_type in XML_CONTENT_TYPES or
                filename.lower().endswith('.xml')
            )

            if is_xml:
                content_bytes = GraphInboxService._get_attachment_content(att)
                if content_bytes:
                    invoice = GraphInboxService._create_from_xml(
                        content_bytes, filename, project, email_metadata, user
                    )
                    if invoice:
                        xml_count += 1

        return xml_count

    @staticmethod
    def _fetch_attachments(
        session, message_id: str, project_email: str
    ) -> list[dict]:
        """Fetch attachment list for a message from the project's shared mailbox."""
        url = f'{GRAPH_BASE_URL}/users/{project_email}/messages/{message_id}/attachments'

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json().get('value', [])
        except Exception as e:
            logger.warning('Failed to fetch attachments for message %s: %s', message_id, e)
            return []

    @staticmethod
    def _get_attachment_content(attachment: dict) -> Optional[bytes]:
        """Extract content bytes from attachment (base64 decoded)."""
        content_b64 = attachment.get('contentBytes')
        if not content_b64:
            return None
        try:
            return base64.b64decode(content_b64)
        except Exception:
            return None

    @staticmethod
    def _create_from_xml(
        xml_content: bytes,
        filename: str,
        project: ConstructionProject,
        email_metadata: dict,
        user: SystemUser,
    ) -> Optional[IncomingInvoice]:
        """Parse XML and create IncomingInvoice in Draft state, auto-assigned to project."""
        try:
            cfdi = CfdiParser.parse(xml_content)
        except CfdiParseError as e:
            # Still create the record but mark as having parse errors
            invoice = IncomingInvoice(
                projectid=project,
                statecode=IncomingInvoiceStateCode.DRAFT,
                parseerrors=str(e),
                createdby=user,
                modifiedby=user,
                **email_metadata,
            )
            invoice.xmlfile.save(filename, ContentFile(xml_content), save=False)
            invoice.xmlfilename = filename
            invoice.xmlfilesize = len(xml_content)
            invoice.save()
            return invoice

        # Check for duplicate UUID
        if cfdi.uuid and IncomingInvoice.objects.filter(uuid=cfdi.uuid).exists():
            logger.info('Duplicate CFDI UUID %s, skipping', cfdi.uuid)
            return None

        parse_errors = None
        if cfdi.warnings:
            parse_errors = '; '.join(cfdi.warnings)

        # Build conceptos JSON
        conceptos_json = [
            {
                'claveprodserv': c.claveprodserv,
                'cantidad': str(c.cantidad),
                'claveunidad': c.claveunidad,
                'unidad': c.unidad,
                'descripcion': c.descripcion,
                'valorunitario': str(c.valorunitario),
                'importe': str(c.importe),
                'descuento': str(c.descuento) if c.descuento else None,
            }
            for c in cfdi.conceptos
        ]

        invoice = IncomingInvoice(
            projectid=project,
            statecode=IncomingInvoiceStateCode.DRAFT,
            cfdiversion=cfdi.version,
            uuid=cfdi.uuid,
            serie=cfdi.serie,
            folio=cfdi.folio,
            fecha=cfdi.fecha,
            fechatimbrado=cfdi.fechatimbrado,
            emisorrfc=cfdi.emisor_rfc,
            emisornombre=cfdi.emisor_nombre,
            emisorregimenfiscal=cfdi.emisor_regimenfiscal,
            receptorrfc=cfdi.receptor_rfc,
            receptornombre=cfdi.receptor_nombre,
            receptorusocfdi=cfdi.receptor_usocfdi,
            moneda=cfdi.moneda,
            tipocambio=cfdi.tipocambio or cfdi.tipocambio,
            subtotal=cfdi.subtotal,
            descuento=cfdi.descuento,
            totalimpuestostrasladados=cfdi.total_impuestos_trasladados,
            totalimpuestosretenidos=cfdi.total_impuestos_retenidos,
            total=cfdi.total,
            formapago=cfdi.formapago,
            metodopago=cfdi.metodopago,
            conceptosjson=conceptos_json,
            parseerrors=parse_errors,
            createdby=user,
            modifiedby=user,
            **email_metadata,
        )
        invoice.xmlfile.save(filename, ContentFile(xml_content), save=False)
        invoice.xmlfilename = filename
        invoice.xmlfilesize = len(xml_content)
        invoice.save()

        # Try auto-matching
        try:
            InboxMatchingService.auto_suggest_match(invoice)
        except Exception as e:
            logger.warning('Auto-match failed for %s: %s', invoice.incominginvoiceid, e)

        return invoice

    @staticmethod
    def _parse_datetime(iso_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO 8601 datetime from Graph API."""
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
