import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
django.setup()

from apps.users.models import SystemUser
from apps.leads.models import Lead
from apps.opportunities.models import Opportunity
from apps.accounts.models import Account
from apps.contacts.models import Contact

print("\n=== USERS ===")
for u in SystemUser.objects.all():
    role_name = u.securityroleid.name if u.securityroleid else "None"
    print(f"{u.fullname} - {u.emailaddress1} - Role: {role_name}")

print("\n=== ACCOUNTS (Top 3) ===")
for a in Account.objects.all()[:3]:
    print(f"{a.name} - {a.emailaddress1}")

print("\n=== CONTACTS (Top 3) ===")
for c in Contact.objects.all()[:3]:
    account_name = c.parentcustomerid.name if c.parentcustomerid else "Independent"
    print(f"{c.fullname} - {c.emailaddress1} - Company: {account_name}")

print("\n=== LEADS (Top 3) ===")
for l in Lead.objects.all()[:3]:
    print(f"{l.fullname} - {l.companyname} - Status: {l.get_statuscode_display()}")

print("\n=== OPPORTUNITIES (Top 3) ===")
for o in Opportunity.objects.all()[:3]:
    customer = o.customer_name or "N/A"
    print(f"{o.name} - ${o.estimatedrevenue:,.2f} - Customer: {customer}")
