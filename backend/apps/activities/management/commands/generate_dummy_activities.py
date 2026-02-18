"""
Django management command to generate dummy activities.
Usage: python manage.py generate_dummy_activities
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.activities.models import Activity, Email, PhoneCall, Task, Appointment
from apps.users.models import SystemUser
from apps.leads.models import Lead
from apps.opportunities.models import Opportunity
from apps.accounts.models import Account
from apps.contacts.models import Contact
import random


class Command(BaseCommand):
    help = 'Genera actividades dummy para pruebas'

    def handle(self, *args, **options):
        self.stdout.write('[INFO] Generando datos dummy para Activities...')

        # Get a user to assign as owner
        try:
            owner = SystemUser.objects.filter(isdisabled=False).first()
            if not owner:
                self.stdout.write(self.style.ERROR('[ERROR] No se encontró ningún usuario activo'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[ERROR] Error al obtener usuario: {e}'))
            return

        # Get some entities to link activities to
        leads = list(Lead.objects.all()[:3])
        opportunities = list(Opportunity.objects.all()[:3])
        accounts = list(Account.objects.all()[:3])
        contacts = list(Contact.objects.all()[:3])

        # Combine all entities for random selection
        regarding_entities = []
        for lead in leads:
            regarding_entities.append(('lead', lead.leadid))
        for opp in opportunities:
            regarding_entities.append(('opportunity', opp.opportunityid))
        for acc in accounts:
            regarding_entities.append(('account', acc.accountid))
        for contact in contacts:
            regarding_entities.append(('contact', contact.contactid))

        if not regarding_entities:
            self.stdout.write(self.style.WARNING('[WARNING] No se encontraron entidades (Leads/Opportunities/Accounts/Contacts) para relacionar actividades'))

        # Sample email activities data
        emails_data = [
            {
                'subject': 'Seguimiento de propuesta comercial',
                'description': 'Email de seguimiento después de la reunión',
                'to': 'cliente@empresa.com',
                'sender': 'ventas@micrm.com',
                'body': 'Estimado cliente,\n\nGracias por su tiempo en la reunión. Adjunto la propuesta discutida.',
                'directioncode': True,  # Outgoing
            },
            {
                'subject': 'Consulta sobre licencias Office 365',
                'description': 'Cliente solicita información de precios',
                'to': 'ventas@micrm.com',
                'sender': 'contacto@cliente.com',
                'body': 'Buenos días,\n\nNecesito cotización para 50 licencias de Office 365.',
                'directioncode': False,  # Incoming
            },
            {
                'subject': 'Confirmación de reunión',
                'description': 'Confirmación de cita para demo',
                'to': 'prospecto@tech.com',
                'sender': 'ventas@micrm.com',
                'body': 'Hola,\n\nConfirmo nuestra reunión del viernes a las 10:00 AM.',
                'directioncode': True,
            },
        ]

        # Sample phone call activities
        phonecalls_data = [
            {
                'subject': 'Llamada de prospección',
                'description': 'Cliente interesado en Dynamics 365',
                'phonenumber': '+52-55-1234-5678',
                'directioncode': True,
                'scheduledstart': timezone.now() + timedelta(hours=2),
                'scheduledend': timezone.now() + timedelta(hours=2, minutes=30),
            },
            {
                'subject': 'Seguimiento post-venta',
                'description': 'Verificar satisfacción del cliente',
                'phonenumber': '+52-55-9876-5432',
                'directioncode': True,
                'scheduledstart': timezone.now() + timedelta(days=1, hours=10),
                'scheduledend': timezone.now() + timedelta(days=1, hours=10, minutes=15),
            },
        ]

        # Sample task activities
        tasks_data = [
            {
                'subject': 'Preparar presentación para cliente',
                'description': 'Crear slides con propuesta de valor de Dynamics 365',
                'scheduledstart': timezone.now() + timedelta(days=2),
                'scheduledend': timezone.now() + timedelta(days=4),
                'prioritycode': 2,  # High
            },
            {
                'subject': 'Enviar contrato firmado',
                'description': 'Enviar copia del contrato al cliente',
                'scheduledstart': timezone.now() + timedelta(days=1),
                'scheduledend': timezone.now() + timedelta(days=2),
                'prioritycode': 1,  # Normal
            },
        ]

        # Sample appointment activities
        appointments_data = [
            {
                'subject': 'Reunión de presentación de producto',
                'description': 'Demo del sistema CRM con equipo de TI',
                'location': 'Oficinas cliente - Sala de juntas A',
                'scheduledstart': timezone.now() + timedelta(days=5, hours=14),
                'scheduledend': timezone.now() + timedelta(days=5, hours=15, minutes=30),
                'requiredattendees': '[]',
            },
        ]

        # Create Email activities
        created_emails = 0
        for email_data in emails_data:
            regarding_id = None
            regarding_type = None
            if regarding_entities:
                regarding_type, regarding_id = random.choice(regarding_entities)

            try:
                # Create Activity first
                activity = Activity.objects.create(
                    activitytypecode='email',
                    subject=email_data['subject'],
                    description=email_data['description'],
                    regardingobjectid=regarding_id,
                    regardingobjectidtype=regarding_type,
                    ownerid=owner,
                    statecode=random.choice([0, 1]),
                    createdby=owner,
                    modifiedby=owner
                )

                # Create Email
                Email.objects.create(
                    activity=activity,
                    to=email_data['to'],
                    sender=email_data['sender'],
                    body=email_data['body'],
                    directioncode=email_data['directioncode']
                )

                created_emails += 1
                self.stdout.write(f'[OK] Email creado: {email_data["subject"]}')
            except Exception as e:
                self.stdout.write(f'[ERROR] Error creando email: {e}')

        # Create PhoneCall activities
        created_calls = 0
        for call_data in phonecalls_data:
            regarding_id = None
            regarding_type = None
            if regarding_entities:
                regarding_type, regarding_id = random.choice(regarding_entities)

            try:
                # Create Activity first
                activity = Activity.objects.create(
                    activitytypecode='phonecall',
                    subject=call_data['subject'],
                    description=call_data['description'],
                    scheduledstart=call_data['scheduledstart'],
                    scheduledend=call_data['scheduledend'],
                    regardingobjectid=regarding_id,
                    regardingobjectidtype=regarding_type,
                    ownerid=owner,
                    statecode=random.choice([0, 1, 3]),
                    createdby=owner,
                    modifiedby=owner
                )

                # Create PhoneCall
                PhoneCall.objects.create(
                    activity=activity,
                    phonenumber=call_data['phonenumber'],
                    directioncode=call_data['directioncode']
                )

                created_calls += 1
                self.stdout.write(f'[OK] Llamada creada: {call_data["subject"]}')
            except Exception as e:
                self.stdout.write(f'[ERROR] Error creando llamada: {e}')

        # Create Task activities
        created_tasks = 0
        for task_data in tasks_data:
            regarding_id = None
            regarding_type = None
            if regarding_entities:
                regarding_type, regarding_id = random.choice(regarding_entities)

            try:
                # Create Activity first
                activity = Activity.objects.create(
                    activitytypecode='task',
                    subject=task_data['subject'],
                    description=task_data['description'],
                    scheduledstart=task_data['scheduledstart'],
                    scheduledend=task_data['scheduledend'],
                    prioritycode=task_data['prioritycode'],
                    regardingobjectid=regarding_id,
                    regardingobjectidtype=regarding_type,
                    ownerid=owner,
                    statecode=random.choice([0, 1]),
                    createdby=owner,
                    modifiedby=owner
                )

                # Create Task
                Task.objects.create(
                    activity=activity,
                    percentcomplete=0
                )

                created_tasks += 1
                self.stdout.write(f'[OK] Tarea creada: {task_data["subject"]}')
            except Exception as e:
                self.stdout.write(f'[ERROR] Error creando tarea: {e}')

        # Create Appointment activities
        created_appointments = 0
        for appt_data in appointments_data:
            regarding_id = None
            regarding_type = None
            if regarding_entities:
                regarding_type, regarding_id = random.choice(regarding_entities)

            try:
                # Create Activity first
                activity = Activity.objects.create(
                    activitytypecode='appointment',
                    subject=appt_data['subject'],
                    description=appt_data['description'],
                    scheduledstart=appt_data['scheduledstart'],
                    scheduledend=appt_data['scheduledend'],
                    regardingobjectid=regarding_id,
                    regardingobjectidtype=regarding_type,
                    ownerid=owner,
                    statecode=random.choice([0, 3]),
                    createdby=owner,
                    modifiedby=owner
                )

                # Create Appointment
                Appointment.objects.create(
                    activity=activity,
                    location=appt_data['location'],
                    requiredattendees=appt_data['requiredattendees']
                )

                created_appointments += 1
                self.stdout.write(f'[OK] Cita creada: {appt_data["subject"]}')
            except Exception as e:
                self.stdout.write(f'[ERROR] Error creando cita: {e}')

        # Summary
        total_activities = Activity.objects.count()
        self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Generación completada:'))
        self.stdout.write(f'  - Emails creados: {created_emails}')
        self.stdout.write(f'  - Llamadas creadas: {created_calls}')
        self.stdout.write(f'  - Tareas creadas: {created_tasks}')
        self.stdout.write(f'  - Citas creadas: {created_appointments}')
        self.stdout.write(f'  - Total actividades: {total_activities}')
