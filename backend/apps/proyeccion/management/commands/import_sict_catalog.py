"""Management command to import SICT 2024 catalog into ConceptPriceCatalog.

Loads 2,524 standardized construction work concepts from the Tabulador SICT 2024.
Each concept gets a single price reference: "Tabulador SICT 2024 - Zona Centro".

Usage:
    python manage.py import_sict_catalog                 # Import
    python manage.py import_sict_catalog --dry-run       # Preview
    python manage.py import_sict_catalog --clear          # Clear and re-import
"""

import json
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.proyeccion.models import (
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
)
from apps.users.models import SystemUser

REFERENCE_PROJECT = 'Tabulador SICT 2024 - Zona Centro'
DATA_FILE = os.path.join(os.path.dirname(__file__), 'sict_catalog_data.json')


class Command(BaseCommand):
    help = 'Import SICT 2024 Tabulador into ConceptPriceCatalog'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without writing to database',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing SICT catalog items before importing',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clear = options['clear']

        # ── Load JSON data ───────────────────────────────────────────────
        self.stdout.write(f'Loading SICT data from {DATA_FILE}')
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            sict_items = json.load(f)

        self.stdout.write(f'Loaded {len(sict_items)} SICT concepts')

        with_price = sum(1 for i in sict_items if i.get('directcost', 0) > 0)
        self.stdout.write(f'With directcost > 0: {with_price}')

        # ── Dry run ──────────────────────────────────────────────────────
        if dry_run:
            self._print_preview(sict_items)
            return

        # ── Get audit user ───────────────────────────────────────────────
        owner = SystemUser.objects.first()
        if not owner:
            self.stderr.write(self.style.ERROR(
                'No SystemUser found. Run load_dummy_data first.'
            ))
            return

        # ── Clear if requested ───────────────────────────────────────────
        if clear:
            deleted_refs = ConceptPriceReference.objects.filter(
                catalogitemid__source=CatalogSourceCode.SICT
            ).delete()[0]
            deleted_items = ConceptPriceCatalogItem.objects.filter(
                source=CatalogSourceCode.SICT
            ).delete()[0]
            self.stdout.write(self.style.WARNING(
                f'Cleared: {deleted_items} catalog items, {deleted_refs} references'
            ))

        # ── Import with deduplication ────────────────────────────────────
        self._import(sict_items, owner)

    def _import(self, sict_items, owner):
        """Import SICT items with deduplication."""
        # Build lookup of existing SICT items by code
        existing = {}
        for item in ConceptPriceCatalogItem.objects.filter(
            source=CatalogSourceCode.SICT, statecode=0
        ):
            existing[item.code] = item

        # Build lookup of existing references
        existing_refs = set()
        if existing:
            for ref in ConceptPriceReference.objects.filter(
                catalogitemid__in=[i.catalogitemid for i in existing.values()],
                statecode=0
            ):
                existing_refs.add((str(ref.catalogitemid_id), ref.projectname))

        created_items = 0
        deduped_items = 0
        created_refs = 0
        skipped_refs = 0

        seen_codes = set()
        with transaction.atomic():
            for data in sict_items:
                code = f"SICT-{data['code']}"
                if code in seen_codes:
                    continue  # skip duplicates within JSON
                seen_codes.add(code)
                description = data.get('description', '')
                unit = data.get('unit', '') or ''
                directcost = data.get('directcost', 0)

                # Build category from SICT hierarchy
                # e.g., "Construccion > Terracerias > Desmonte"
                parts = [
                    data.get('bookname', ''),
                    data.get('titlename', ''),
                    data.get('chaptername', ''),
                ]
                category = ' > '.join(p for p in parts if p)

                if code in existing:
                    catalog_item = existing[code]
                    deduped_items += 1
                else:
                    catalog_item = ConceptPriceCatalogItem(
                        code=code,
                        description=description,
                        unit=unit,
                        source=CatalogSourceCode.SICT,
                        category=category,
                        createdby=owner,
                        modifiedby=owner,
                    )
                    catalog_item.save()
                    created_items += 1

                # Add price reference if directcost > 0
                ref_added = False
                if directcost and directcost > 0:
                    ref_key = (str(catalog_item.catalogitemid), REFERENCE_PROJECT)
                    if ref_key not in existing_refs:
                        ConceptPriceReference(
                            catalogitemid=catalog_item,
                            projectname=REFERENCE_PROJECT,
                            projectlocation='Nacional (Zona Centro)',
                            unitprice=Decimal(str(directcost)),
                            notes=f"SICT 2024 Tabulador, {data.get('chaptercode', '')}",
                            createdby=owner,
                            modifiedby=owner,
                        ).save()
                        created_refs += 1
                        ref_added = True
                    else:
                        skipped_refs += 1

                # Update stats
                if ref_added or code not in existing:
                    catalog_item.update_price_stats()
                    catalog_item.save()

        self.stdout.write(self.style.SUCCESS(
            f'\nImport complete:'
            f'\n  Catalog items created: {created_items}'
            f'\n  Catalog items already existed (deduped): {deduped_items}'
            f'\n  Price references created: {created_refs}'
            f'\n  Price references skipped (already existed): {skipped_refs}'
        ))

    def _print_preview(self, sict_items):
        """Print a preview of what would be imported."""
        self.stdout.write(self.style.WARNING('\nDRY RUN — no data written\n'))

        # Group by book
        books = {}
        for item in sict_items:
            bn = item.get('bookname', 'Unknown')
            if bn not in books:
                books[bn] = 0
            books[bn] += 1

        self.stdout.write('By book:')
        for book, count in sorted(books.items()):
            self.stdout.write(f'  {book}: {count} concepts')

        # Show samples
        self.stdout.write('\nSample items:')
        for item in sict_items[:10]:
            price = item.get('directcost', 0)
            price_str = f'${price:,.2f}' if price else 'N/A'
            self.stdout.write(
                f"  SICT-{item['code']} [{item.get('unit', '?')}] "
                f"{item.get('description', '')[:70]}... "
                f"-> {price_str}"
            )

        self.stdout.write(f'\n  ... and {len(sict_items) - 10} more')

        existing_count = ConceptPriceCatalogItem.objects.filter(
            source=CatalogSourceCode.SICT, statecode=0
        ).count()
        if existing_count:
            self.stdout.write(self.style.WARNING(
                f'\n  Note: {existing_count} SICT items already in DB '
                f'(duplicates will be skipped on import)'
            ))
