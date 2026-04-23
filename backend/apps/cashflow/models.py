"""Cashflow & PNT models."""
import uuid
from decimal import Decimal
from django.db import models
from core.models import AuditMixin


class ProjectFinancialSettings(AuditMixin):
    """Financial parameters for a construction project (1:1)."""

    settingsid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='settingsid',
    )
    projectid = models.OneToOneField(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='financial_settings',
    )

    # Client retentions (deducted from each invoice)
    imssretentionrate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0.0500'),
        db_column='imssretentionrate',
    )
    otherretentionrate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0'),
        db_column='otherretentionrate',
    )
    retentionreturnperiod = models.IntegerField(
        null=True, blank=True,
        db_column='retentionreturnperiod',
    )

    # Advance payment handling (amount lives on ConstructionProject.advancepayment_notax)
    advanceamortizationrate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0'),
        db_column='advanceamortizationrate',
    )
    anticipoentryperiod = models.IntegerField(
        default=1,
        db_column='anticipoentryperiod',
    )

    # Withdrawals (cash outflows not tied to imputation codes)
    transversalcost = models.DecimalField(
        max_digits=19, decimal_places=2,
        default=Decimal('0'),
        db_column='transversalcost',
    )
    transversalwithdrawalperiod = models.IntegerField(
        default=1,
        db_column='transversalwithdrawalperiod',
    )
    utilitycost = models.DecimalField(
        max_digits=19, decimal_places=2,
        default=Decimal('0'),
        db_column='utilitycost',
    )
    utilitywithdrawalperiod = models.IntegerField(
        default=1,
        db_column='utilitywithdrawalperiod',
    )

    # Finance cost (rate applied per period on negative cumulative cash)
    financecostrate = models.DecimalField(
        max_digits=7, decimal_places=6,
        default=Decimal('0.001000'),
        db_column='financecostrate',
    )

    class Meta:
        db_table = 'projectfinancialsettings'
        verbose_name = 'Project Financial Settings'
        verbose_name_plural = 'Project Financial Settings'

    def __str__(self):
        return f"Financial settings for {self.projectid.projectnumber}"


class ProjectBillingRule(AuditMixin):
    """N billing tranches per project (e.g. 50%/30%/20% at lags 0/1/2)."""

    ruleid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='ruleid',
    )
    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='billing_rules',
    )
    sequence = models.IntegerField(db_column='sequence')
    percent = models.DecimalField(
        max_digits=5, decimal_places=4,
        db_column='percent',
    )
    lagperiods = models.IntegerField(db_column='lagperiods')

    class Meta:
        db_table = 'projectbillingrule'
        verbose_name = 'Project Billing Rule'
        verbose_name_plural = 'Project Billing Rules'
        ordering = ['projectid', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['projectid', 'sequence'],
                name='unique_billing_rule_seq',
            ),
        ]

    def __str__(self):
        return f"{self.projectid.projectnumber} #{self.sequence}: {self.percent} @ +{self.lagperiods}"
