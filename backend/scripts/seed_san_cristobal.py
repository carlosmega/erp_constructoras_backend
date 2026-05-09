"""Seed Datos Generales de la proyección 'ENTRONQUE SAN CRISTOBAL'.

Datos extraídos del Excel:
  docs/samples/001. Estudio Oferta Entronque San Cristobal COMPLETO.xlsx
  hoja "Hoja Cierre Estudio".
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.db import transaction

from apps.accounts.models import Account
from apps.users.models import SystemUser
from apps.proyeccion.services import EstimationProjectService


def run():
    with transaction.atomic():
        user = SystemUser.objects.get(emailaddress1='admin@crm.com')

        account, created = Account.objects.get_or_create(
            name='CONCESIONARIA DE AUTOPISTAS DEL SURESTE',
            defaults={
                'address1_country': 'México',
                'customertypecode': 3,
                'creditonhold': False,
                'statecode': 0,
                'statuscode': 1,
                'ownerid': user,
                'createdby': user,
                'modifiedby': user,
            },
        )
        print(f"Account {'created' if created else 'reused'}: {account.accountid} - {account.name}")

        dto = SimpleNamespace(
            name='ENTRONQUE SAN CRISTOBAL',
            description=(
                'Estudio de oferta para construcción del entronque San Cristóbal. '
                'Cliente: Concesionaria de Autopistas del Sureste. '
                'Adjudicación directa, periodo de ejecución 3 meses, pago mensual.'
            ),
            accountid=account.accountid,
            opportunityid=None,
            presentationdate=date(2025, 5, 23),
            estimatedstartdate=date(2025, 5, 30),
            estimatedenddate=date(2025, 8, 30),
            durationmonths=3,
            projecttype=0,
            biddingtype=2,
            periodtype=1,
            estimatedcontractamount=Decimal('27891738.72'),
            exchangerate_mxn_usd=Decimal('20.0000'),
            profitpercent=Decimal('15.00'),
        )

        project = EstimationProjectService.create_project(dto, user)
        project.profitpercent = dto.profitpercent
        project.save(update_fields=['profitpercent'])

        print()
        print('=== Proyeccion creada ===')
        print(f'  ID:                     {project.estimationprojectid}')
        print(f'  Numero:                 {project.estimationnumber}')
        print(f'  Nombre:                 {project.name}')
        print(f'  Cliente:                {project.accountid.name}')
        print(f'  Fecha presentacion:     {project.presentationdate}')
        print(f'  Fecha inicio estimada:  {project.estimatedstartdate}')
        print(f'  Fecha fin estimada:     {project.estimatedenddate}')
        print(f'  Duracion (meses):       {project.durationmonths}')
        print(f'  Tipo proyecto:          {project.projecttype} (0=Publica, 1=Privada)')
        print(f'  Tipo licitacion:        {project.biddingtype} (0=Publica, 1=Inv3, 2=AdjDirecta)')
        print(f'  Tipo periodo:           {project.periodtype} (0=Semanal, 1=Quincenal)')
        print(f'  Monto estimado:         ${project.estimatedcontractamount:,.2f} MXN')
        print(f'  Tipo de cambio MXN/USD: {project.exchangerate_mxn_usd}')
        print(f'  % Utilidad:             {project.profitpercent}%')
        print(f'  Estado:                 {project.statecode} ({project.state_name})')
        print(f'  Responsable:            {project.ownerid.fullname}')


if __name__ == '__main__':
    run()
