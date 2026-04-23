from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.proyeccion.models import DistributionPresence


class Command(BaseCommand):
    help = 'Remove distribution presence entries older than 7 days.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=7)
        deleted, _ = DistributionPresence.objects.filter(last_seen__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f'Cleaned up {deleted} zombie presence entries.'))
