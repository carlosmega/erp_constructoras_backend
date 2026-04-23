"""Management command to classify Dimovere historical concepts.

Analyzes descriptions and assigns familia (L2) + subfamilia (L3) using
keyword matching. Also rebuilds the `category` field as "Familia > Subfamilia".

Usage:
    python manage.py classify_dimovere_concepts              # Classify all
    python manage.py classify_dimovere_concepts --dry-run     # Preview only
    python manage.py classify_dimovere_concepts --reclassify  # Overwrite existing
"""

from collections import Counter
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.proyeccion.models import ConceptPriceCatalogItem, CatalogSourceCode
from apps.proyeccion.classification import classify_concept


class Command(BaseCommand):
    help = 'Classify Dimovere historical concepts into familia/subfamilia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview classification without writing to database',
        )
        parser.add_argument(
            '--reclassify',
            action='store_true',
            help='Overwrite existing classifications (default: skip already classified)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reclassify = options['reclassify']

        # Fetch Dimovere concepts
        queryset = ConceptPriceCatalogItem.objects.filter(
            source=CatalogSourceCode.HISTORICO,
            statecode=0,
        )

        if not reclassify:
            # Only classify items without L2
            queryset = queryset.filter(classificationl2='')

        items = list(queryset)
        total = len(items)

        if total == 0:
            self.stdout.write(self.style.WARNING(
                'No concepts to classify. Use --reclassify to overwrite existing.'
            ))
            return

        self.stdout.write(f'Classifying {total} Dimovere concepts...\n')

        # Classify
        familia_counter = Counter()
        subfamilia_counter = Counter()
        unclassified = []
        updates = []

        for item in items:
            familia, subfamilia = classify_concept(item.description)

            familia_counter[familia] += 1
            subfamilia_counter[f'{familia} > {subfamilia}'] += 1

            if familia == 'Sin Clasificar':
                unclassified.append(item)

            item.classificationl1 = ''  # Dimovere has no L1 equivalent
            item.classificationl2 = familia
            item.classificationl3 = subfamilia
            item.category = f'{familia} > {subfamilia}'
            updates.append(item)

        # ── Report ───────────────────────────────────────────────────
        self.stdout.write('-- Familias (L2) ----------------------------')
        for familia, count in familia_counter.most_common():
            marker = '!' if familia == 'Sin Clasificar' else '*'
            self.stdout.write(f'  {marker} {familia}: {count}')

        self.stdout.write(f'\n-- Subfamilias (L3) - {len(subfamilia_counter)} total --')
        for path, count in sorted(subfamilia_counter.items()):
            self.stdout.write(f'  {path}: {count}')

        classified = total - len(unclassified)
        pct = (classified / total * 100) if total else 0
        self.stdout.write(f'\n-- Resumen ---------------------------------')
        self.stdout.write(f'  Total:          {total}')
        self.stdout.write(f'  Clasificados:   {classified} ({pct:.1f}%)')
        self.stdout.write(f'  Sin clasificar: {len(unclassified)}')

        if unclassified:
            self.stdout.write(f'\n-- Sin clasificar (primeros 20) ------------')
            for item in unclassified[:20]:
                self.stdout.write(
                    f'  [{item.code}] {item.description[:90]}...'
                )
            if len(unclassified) > 20:
                self.stdout.write(f'  ... y {len(unclassified) - 20} mas')

        # ── Write ────────────────────────────────────────────────────
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - no se escribio nada'))
            return

        with transaction.atomic():
            ConceptPriceCatalogItem.objects.bulk_update(
                updates,
                ['classificationl1', 'classificationl2', 'classificationl3', 'category'],
                batch_size=200,
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nOK: {len(updates)} conceptos actualizados en la base de datos'
        ))
