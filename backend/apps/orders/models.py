"""Order management models - Phase 9"""
from django.db import models
from django.core.validators import MinValueValidator
from core.models import AuditMixin
from decimal import Decimal
import uuid


class OrderStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    SUBMITTED = 1, 'Submitted'
    CANCELED = 2, 'Canceled'
    FULFILLED = 3, 'Fulfilled'
    INVOICED = 4, 'Invoiced'


class OrderStatusCode(models.IntegerChoices):
    NEW = 1, 'New'
    PENDING = 2, 'Pending'
    IN_PROGRESS = 3, 'In Progress'
    NO_MONEY = 4, 'No Money'
    COMPLETE = 5, 'Complete'
    PARTIAL = 6, 'Partial'
    CANCELED = 7, 'Canceled'


class SalesOrder(AuditMixin):
    """Sales order from accepted quote - CDS Entity: salesorder"""
    salesorderid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='salesorderid')
    name = models.CharField(max_length=300, db_column='name')
    ordernumber = models.CharField(max_length=100, unique=True, db_column='ordernumber')

    quoteid = models.ForeignKey('quotes.Quote', on_delete=models.PROTECT, null=True, blank=True,
                                 db_column='quoteid', related_name='orders')
    opportunityid = models.ForeignKey('opportunities.Opportunity', on_delete=models.PROTECT, null=True, blank=True,
                                       db_column='opportunityid', related_name='orders')
    accountid = models.ForeignKey('accounts.Account', on_delete=models.PROTECT, null=True, blank=True,
                                   db_column='accountid', related_name='orders')
    contactid = models.ForeignKey('contacts.Contact', on_delete=models.PROTECT, null=True, blank=True,
                                   db_column='contactid', related_name='orders')

    totalamount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'), db_column='totalamount')
    totaldiscountamount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'), db_column='totaldiscountamount')
    totaltax = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'), db_column='totaltax')
    totallineitemamount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'), db_column='totallineitemamount')

    requestdeliveryby = models.DateField(null=True, blank=True, db_column='requestdeliveryby')
    datefulfilled = models.DateTimeField(null=True, blank=True, db_column='datefulfilled')

    statecode = models.IntegerField(choices=OrderStateCode.choices, default=OrderStateCode.ACTIVE, db_column='statecode')
    statuscode = models.IntegerField(choices=OrderStatusCode.choices, default=OrderStatusCode.NEW, db_column='statuscode')
    description = models.TextField(blank=True, null=True, db_column='description')
    ownerid = models.ForeignKey('users.SystemUser', on_delete=models.PROTECT, db_column='ownerid', related_name='owned_orders')

    class Meta:
        db_table = 'salesorder'
        ordering = ['-createdon']
        indexes = [models.Index(fields=['statecode', 'ownerid']), models.Index(fields=['quoteid'])]

    def __str__(self):
        return f"{self.ordernumber} - {self.name}"

    @property
    def customer_name(self):
        if self.accountid:
            return self.accountid.name
        elif self.contactid:
            return self.contactid.fullname
        return None


class SalesOrderDetail(models.Model):
    """Order line items - CDS Entity: salesorderdetail"""
    salesorderdetailid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='salesorderdetailid')
    salesorderid = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, db_column='salesorderid', related_name='order_details')

    productname = models.CharField(max_length=100, db_column='productname')
    productdescription = models.TextField(blank=True, null=True, db_column='productdescription')
    quantity = models.DecimalField(max_digits=19, decimal_places=2, validators=[MinValueValidator(0)], db_column='quantity')
    priceperunit = models.DecimalField(max_digits=19, decimal_places=2, validators=[MinValueValidator(0)], db_column='priceperunit')
    manualdiscountamount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'), db_column='manualdiscountamount')
    tax = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal('0.00'), db_column='tax')
    baseamount = models.DecimalField(max_digits=19, decimal_places=2, db_column='baseamount')
    extendedamount = models.DecimalField(max_digits=19, decimal_places=2, db_column='extendedamount')
    sequencenumber = models.IntegerField(default=1, db_column='sequencenumber')

    createdon = models.DateTimeField(auto_now_add=True, db_column='createdon')
    modifiedon = models.DateTimeField(auto_now=True, db_column='modifiedon')

    class Meta:
        db_table = 'salesorderdetail'
        ordering = ['salesorderid', 'sequencenumber']

    def save(self, *args, **kwargs):
        self.baseamount = self.quantity * self.priceperunit
        self.extendedamount = self.baseamount - self.manualdiscountamount + self.tax
        super().save(*args, **kwargs)
