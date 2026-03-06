"""
Django management command to sync invoice inbox from project shared mailboxes
via Microsoft Graph API.

Usage:
    python manage.py sync_project_invoices                    # All active projects with email
    python manage.py sync_project_invoices --days 7           # Last 7 days only
    python manage.py sync_project_invoices --max-emails 100   # Fetch up to 100 emails
    python manage.py sync_project_invoices --dry-run          # Preview without creating records
"""

from django.core.management.base import BaseCommand

from apps.graph.models import MicrosoftToken
from apps.invoiceinbox.graph_inbox_service import GraphInboxService
from apps.invoiceinbox.models import SyncTriggerCode
from apps.projects.models import ConstructionProject


class Command(BaseCommand):
    help = 'Sync invoice inbox from project shared mailboxes via Microsoft Graph API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=30,
            help='Number of days to look back (default: 30)',
        )
        parser.add_argument(
            '--max-emails', type=int, default=50,
            help='Max emails to fetch per project (default: 50)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Preview mode, no records created',
        )
        parser.add_argument(
            '--user-email', type=str, default=None,
            help='Email of the user whose Microsoft account to use for sync',
        )

    def handle(self, *args, **options):
        # Find a user with Microsoft connection
        token_query = MicrosoftToken.objects.select_related('userid')

        if options['user_email']:
            token_query = token_query.filter(
                userid__emailaddress1__iexact=options['user_email']
            )

        token = token_query.first()

        if not token:
            self.stderr.write(self.style.ERROR(
                'No Microsoft account connected. '
                'A user must connect their Microsoft account first.'
            ))
            return

        user = token.userid
        self.stdout.write(
            f'Using Microsoft account: {token.microsoft_email} '
            f'(user: {user.emailaddress1})'
        )

        # Find projects with email configured (Graph API protocol = 1)
        projects = ConstructionProject.objects.filter(
            statecode=0,  # ACTIVE
            emailconfigured=True,
            emailprotocol=1,  # GRAPH_API
        ).exclude(
            projectemail__isnull=True,
        ).exclude(
            projectemail='',
        )

        if not projects.exists():
            self.stdout.write(self.style.WARNING(
                'No active projects with Graph API email configured.'
            ))
            return

        self.stdout.write(
            f'Found {projects.count()} project(s) with email configured'
        )

        if options['dry_run']:
            for project in projects:
                self.stdout.write(self.style.NOTICE(
                    f'  DRY RUN: Would sync {project.projectnumber} '
                    f'({project.projectemail}) - last {options["days"]} days, '
                    f'max {options["max_emails"]} emails'
                ))
            return

        total_xml = 0
        total_pdf = 0
        total_errors = 0

        for project in projects:
            self.stdout.write(
                f'Syncing {project.projectnumber} '
                f'({project.projectemail}) - last {options["days"]} days...'
            )

            sync_log = GraphInboxService.sync_inbox(
                project=project,
                user=user,
                triggered_by=SyncTriggerCode.MANAGEMENT_COMMAND,
                since_days=options['days'],
                max_results=options['max_emails'],
            )

            self.stdout.write(
                f'  Fetched: {sync_log.totalemailsfetched}, '
                f'New XML: {sync_log.newxmlattachments}, '
                f'New PDF: {sync_log.newpdfattachments}, '
                f'Duplicates: {sync_log.duplicatesskipped}, '
                f'Errors: {sync_log.errorscount}'
            )

            if sync_log.errorsdetail:
                for err in sync_log.errorsdetail:
                    self.stderr.write(self.style.WARNING(f'  {err}'))

            total_xml += sync_log.newxmlattachments
            total_pdf += sync_log.newpdfattachments
            total_errors += sync_log.errorscount

        self.stdout.write('')
        if total_errors:
            self.stdout.write(self.style.WARNING(
                f'Done. Total: {total_xml} XML, {total_pdf} PDF, {total_errors} errors'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Done. Total: {total_xml} XML, {total_pdf} PDF'
            ))
