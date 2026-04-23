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
