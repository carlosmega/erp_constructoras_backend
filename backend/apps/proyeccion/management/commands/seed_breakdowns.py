"""Seed CDU breakdown lines for every concept, linking each line to a real
SupplyCatalogItem so the "Explosión de Insumos" view consolidates correctly
and the cuadre indicator turns green.

Convention from the source Excel ("Desglose de C.D.U.") and the existing
load_estudio_fortificacion command:
    quantity   = 1 (one standard unit of the resource)
    unitprice  = market price of that unit
    yieldvalue = how much of the resource is consumed per unit of concept
    amount     = quantity * unitprice * yieldvalue

Breakdown lines for the 5 catalog-mappable categories (Materials, Hauling,
Machinery, Labor, Subcontracts) are linked to a SupplyCatalogItem via
``supplyid``. Herramienta Menor and EPP follow the 3%-of-labor rule and have
no catalog mapping (no supplytype for them).

Usage:
    python manage.py seed_breakdowns <project_id>
    python manage.py seed_breakdowns <project_id> --clear
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import random
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.proyeccion.models import (
    BudgetConcept,
    EstimationProject,
    UnitCostBreakdown,
    SupplyCatalogItem,
    BreakdownCategoryCode,
    SupplyTypeCode,
)
from apps.users.models import SystemUser


D = Decimal


# Map: breakdown category -> supply catalog supplytype
CATEGORY_TO_SUPPLY_TYPE = {
    BreakdownCategoryCode.MATERIALS:    SupplyTypeCode.MATERIAL,
    BreakdownCategoryCode.HAULING:      SupplyTypeCode.HAULING,
    BreakdownCategoryCode.MACHINERY:    SupplyTypeCode.MACHINERY,
    BreakdownCategoryCode.LABOR:        SupplyTypeCode.LABOR,
    BreakdownCategoryCode.SUBCONTRACTS: SupplyTypeCode.SUBCONTRACT,
}

# Probability that a category appears in a given concept (Materials and Labor
# almost always; the others vary so concepts feel diverse).
CATEGORY_INCLUSION_PROB = {
    BreakdownCategoryCode.MATERIALS:    1.0,
    BreakdownCategoryCode.LABOR:        1.0,
    BreakdownCategoryCode.MACHINERY:    0.7,
    BreakdownCategoryCode.HAULING:      0.5,
    BreakdownCategoryCode.SUBCONTRACTS: 0.2,
}

# Number of distinct supplies to pick per category.
CATEGORY_LINES_RANGE = {
    BreakdownCategoryCode.MATERIALS:    (2, 5),
    BreakdownCategoryCode.LABOR:        (1, 3),
    BreakdownCategoryCode.MACHINERY:    (1, 2),
    BreakdownCategoryCode.HAULING:      (1, 2),
    BreakdownCategoryCode.SUBCONTRACTS: (1, 1),
}

# Realistic yield ranges per category (consumption of the resource per unit
# of concept). Keep these wide to mirror real construction projects.
CATEGORY_YIELD_RANGE = {
    BreakdownCategoryCode.MATERIALS:    (D('0.04'),  D('20')),
    BreakdownCategoryCode.HAULING:      (D('0.5'),   D('1.5'))
    ,
    BreakdownCategoryCode.MACHINERY:    (D('0.005'), D('0.05')),
    BreakdownCategoryCode.LABOR:        (D('0.005'), D('0.04')),
    BreakdownCategoryCode.SUBCONTRACTS: (D('0.5'),   D('2'))
    ,
}

# Random ±10% jitter on top of catalog reference price for realism.
PRICE_JITTER = D('0.10')


class Command(BaseCommand):
    help = 'Seed realistic CDU breakdown lines linked to the supply catalog.'

    def add_arguments(self, parser):
        parser.add_argument('project_id', type=str, help='EstimationProject UUID')
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Hard-delete existing breakdowns for the project before seeding.',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Random seed for reproducibility (default 42).',
        )

    def handle(self, *args, **options):
        project_id = options['project_id']
        clear = options['clear']
        seed = options['seed']

        try:
            UUID(project_id)
        except ValueError:
            raise CommandError(f'Invalid UUID: {project_id!r}')

        try:
            project = EstimationProject.objects.get(estimationprojectid=project_id)
        except EstimationProject.DoesNotExist:
            raise CommandError(f'EstimationProject {project_id} not found')

        owner = project.ownerid or SystemUser.objects.first()
        if owner is None:
            raise CommandError('No SystemUser in DB; cannot attribute breakdowns.')

        # Build supply pools per supplytype
        supplies_by_type = defaultdict(list)
        for s in SupplyCatalogItem.objects.filter(statecode=0):
            supplies_by_type[s.supplytype].append(s)
        if not supplies_by_type:
            raise CommandError(
                'Supply catalog is empty. Run `python manage.py seed_supply_catalog` first.'
            )

        missing_types = [
            cat.label for cat, st in CATEGORY_TO_SUPPLY_TYPE.items()
            if not supplies_by_type.get(st)
        ]
        if missing_types:
            self.stdout.write(self.style.WARNING(
                f'Catalog missing supplies for: {", ".join(missing_types)}. '
                f'Those categories will be skipped.'
            ))

        rng = random.Random(seed)
        concepts = list(BudgetConcept.objects.filter(projectid=project_id, statecode=0))
        if not concepts:
            self.stdout.write(self.style.WARNING(
                f'Project {project.estimationnumber} has no concepts.'
            ))
            return

        self.stdout.write(
            f'Seeding breakdowns for {len(concepts)} concepts in '
            f'{project.estimationnumber} ({project.name})'
        )
        self.stdout.write(
            f'  Catalog pool: {sum(len(v) for v in supplies_by_type.values())} supplies '
            f'across {len(supplies_by_type)} types.'
        )

        if clear:
            deleted, _ = UnitCostBreakdown.objects.filter(
                conceptid__projectid=project_id,
            ).delete()
            self.stdout.write(self.style.WARNING(f'  Cleared {deleted} existing breakdown rows.'))

        created_total = 0
        skipped_total = 0
        with transaction.atomic():
            for concept in concepts:
                if not clear and concept.directunitcost > 0:
                    skipped_total += 1
                    continue

                created = self._seed_concept(
                    concept=concept,
                    user=owner,
                    rng=rng,
                    supplies_by_type=supplies_by_type,
                )
                created_total += created
                self.stdout.write(
                    f'  {concept.code:<10} -> {created} lineas, CDU=${concept.directunitcost:,.2f}'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Created {created_total} breakdown lines across '
            f'{len(concepts) - skipped_total} concepts ({skipped_total} skipped, already had data).'
        ))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _seed_concept(
        self,
        *,
        concept: BudgetConcept,
        user: SystemUser,
        rng: random.Random,
        supplies_by_type: dict,
    ) -> int:
        created = 0
        labor_amount = D('0')

        for category, prob in CATEGORY_INCLUSION_PROB.items():
            if rng.random() > prob:
                continue
            supply_type = CATEGORY_TO_SUPPLY_TYPE[category]
            pool = supplies_by_type.get(supply_type, [])
            if not pool:
                continue
            n_min, n_max = CATEGORY_LINES_RANGE[category]
            n_lines = rng.randint(n_min, min(n_max, len(pool)))
            chosen = rng.sample(pool, n_lines)
            yield_min, yield_max = CATEGORY_YIELD_RANGE[category]

            for idx, supply in enumerate(chosen):
                # Price = referenceprice ± 10% jitter
                ref_price = D(str(supply.referenceprice or 0))
                if ref_price > 0:
                    jitter = D(str(rng.uniform(-float(PRICE_JITTER), float(PRICE_JITTER))))
                    unitprice = (ref_price * (D('1') + jitter)).quantize(D('0.01'), ROUND_HALF_UP)
                else:
                    unitprice = D('1')

                yieldvalue = self._random_decimal(rng, yield_min, yield_max, 6)
                quantity = D('1')
                amount = (quantity * unitprice * yieldvalue).quantize(D('0.01'), ROUND_HALF_UP)

                UnitCostBreakdown.objects.create(
                    conceptid=concept,
                    categorycode=category,
                    linenumber=idx + 1,
                    description=supply.description,
                    unit=supply.unit,
                    quantity=quantity,
                    unitprice=unitprice,
                    yieldvalue=yieldvalue,
                    amount=amount,
                    supplyid=supply,
                )
                if category == BreakdownCategoryCode.LABOR:
                    labor_amount += amount
                created += 1

        # HM = 3% labor, EPP = 3% labor (Excel convention; no catalog mapping).
        if labor_amount > 0:
            for category, desc in [
                (BreakdownCategoryCode.MINOR_TOOLS, 'HERRAMIENTA MENOR'),
                (BreakdownCategoryCode.PPE, 'EPP'),
            ]:
                quantity = D('0.03')
                unitprice = labor_amount.quantize(D('0.01'), ROUND_HALF_UP)
                yieldvalue = D('1')
                amount = (quantity * unitprice * yieldvalue).quantize(D('0.01'), ROUND_HALF_UP)

                UnitCostBreakdown.objects.create(
                    conceptid=concept,
                    categorycode=category,
                    linenumber=1,
                    description=desc,
                    unit='%',
                    quantity=quantity,
                    unitprice=unitprice,
                    yieldvalue=yieldvalue,
                    amount=amount,
                )
                created += 1

        from apps.proyeccion.services import UnitCostBreakdownService
        UnitCostBreakdownService._recalc_concept(concept.conceptid, user)
        concept.refresh_from_db()
        return created

    @staticmethod
    def _random_decimal(rng: random.Random, lo: Decimal, hi: Decimal, places: int) -> Decimal:
        f = rng.uniform(float(lo), float(hi))
        q = D('1').scaleb(-places)
        return D(str(f)).quantize(q, ROUND_HALF_UP)
