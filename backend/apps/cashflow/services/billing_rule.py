"""BillingRuleService — replace rules atomically with suma=100% validation."""
from decimal import Decimal
from uuid import UUID
from typing import Iterable
from django.db import transaction
from apps.cashflow.models import ProjectBillingRule
from core.exceptions import ValidationError

_TOLERANCE = Decimal('0.0001')
_MAX_RULES = 10


class BillingRuleService:

    @staticmethod
    def list_rules(project_id: UUID):
        return list(
            ProjectBillingRule.objects.filter(projectid_id=project_id).order_by('sequence')
        )

    @staticmethod
    @transaction.atomic
    def replace(project_id: UUID, rules: Iterable[dict]) -> list[ProjectBillingRule]:
        rules = list(rules)

        if not rules:
            raise ValidationError('Debe haber al menos un tramo de facturación')
        if len(rules) > _MAX_RULES:
            raise ValidationError(f'Máximo {_MAX_RULES} tramos de facturación')

        sequences = [r['sequence'] for r in rules]
        if len(set(sequences)) != len(sequences):
            raise ValidationError('Las secuencias deben ser únicas')

        total = sum((Decimal(str(r['percent'])) for r in rules), Decimal('0'))
        if abs(total - Decimal('1')) > _TOLERANCE:
            raise ValidationError(
                f'La suma de porcentajes debe ser 100% (actual: {total * 100}%)'
            )

        for r in rules:
            if not (Decimal('0') <= Decimal(str(r['percent'])) <= Decimal('1')):
                raise ValidationError('Cada porcentaje debe estar entre 0 y 1')
            if r['lagperiods'] < 0 or r['lagperiods'] > 120:
                raise ValidationError('lagperiods debe estar entre 0 y 120')

        # Replace atomically
        ProjectBillingRule.objects.filter(projectid_id=project_id).delete()
        created = [
            ProjectBillingRule.objects.create(
                projectid_id=project_id,
                sequence=r['sequence'],
                percent=Decimal(str(r['percent'])),
                lagperiods=r['lagperiods'],
            )
            for r in sorted(rules, key=lambda r: r['sequence'])
        ]
        return created
