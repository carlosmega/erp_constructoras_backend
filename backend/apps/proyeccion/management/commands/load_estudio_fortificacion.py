"""
Management command to load data from '001. Estudio Obra Fortificacion Taludes.xlsx'
into the Proyecciones module.
"""
import uuid
from decimal import Decimal
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject, ConceptFamily, ConceptSubfamily, BudgetConcept,
    UnitCostBreakdown, IndirectCostDetail, OfferAlternative,
    BreakdownCategoryCode, ChecklistStatusCode, EstimationStateCode,
)
from apps.proyeccion.services import external_name_to_category
from apps.users.models import SystemUser


D = Decimal


class Command(BaseCommand):
    help = 'Load Estudio Obra Fortificación Taludes data into Proyecciones module'

    @transaction.atomic
    def handle(self, *args, **options):
        owner = SystemUser.objects.first()
        self.stdout.write(f"Using owner: {owner.fullname}")

        # =====================================================================
        # 1. EstimationProject
        # =====================================================================
        project = EstimationProject.objects.create(
            name='FORTIFICACIÓN TALUD PARQUE EÓLICO LOS ALTOS',
            description='Estudio de obra para fortificación de taludes en parque eólico. '
                        'Cliente: CENTAURO ENERGY. Ubicación: Ojuelos, Jalisco. '
                        'Tipo: Privado, Adjudicación Directa. '
                        'Consorcio: Oscar Villavicencio (33%) + Dimovere (66%).',
            estimationnumber='EST-2026-001',
            presentationdate=date(2026, 2, 7),
            estimatedstartdate=date(2026, 2, 10),
            estimatedenddate=date(2026, 4, 10),
            durationmonths=2,
            projecttype=1,       # Private
            biddingtype=2,       # Direct
            periodtype=1,        # Fortnightly (quincenal)
            estimatedcontractamount=D('6188822.93'),
            exchangerate_mxn_usd=D('20.0000'),
            statecode=EstimationStateCode.IN_REVIEW,
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Created EstimationProject: {project.estimationnumber} - {project.name}"
        ))

        # =====================================================================
        # 2. ConceptFamily (1 family "A" = "01. FAMILIA")
        # =====================================================================
        family = ConceptFamily.objects.create(
            projectid=project,
            name='01. FAMILIA',
            code='A',
            sortorder=1,
            createdby=owner,
            modifiedby=owner,
        )

        # =====================================================================
        # 3. ConceptSubfamilies (5 subfamilies from E7 sheet)
        # =====================================================================
        subfamilies_data = [
            ('01', 'GABINETE', 1),
            ('02', 'PRELIMINARES', 2),
            ('03', 'MOVIMIENTO DE TIERRAS Y ABATIMIENTO', 3),
            ('04', 'FORTIFICACIÓN DE TALUD', 4),
            ('05', 'OBRAS DE FORTIFICACIÓN PUNTUAL', 5),
        ]

        subfamilies = {}
        for code, name, order in subfamilies_data:
            sf = ConceptSubfamily.objects.create(
                familyid=family,
                projectid=project,
                name=name,
                code=code,
                sortorder=order,
                createdby=owner,
                modifiedby=owner,
            )
            subfamilies[code] = sf

        self.stdout.write(f"Created {len(subfamilies)} subfamilies")

        # =====================================================================
        # 4. BudgetConcepts + UnitCostBreakdowns
        # =====================================================================
        concepts_data = [
            # (subfamily_code, concept_code, seq, description, unit, qty,
            #  direct_unit_cost, indirect_unit_cost, utility_unit_cost, unit_price, total,
            #  breakdowns: [(cat, line, desc, unit, qty, price, yield, amount), ...])

            # --- GABINETE ---
            ('01', 'A1', 1,
             'Elaboración de proyecto ejecutivo acorde a las necesidades de '
             'fortificación expresadas por el cliente',
             'Estudio', D('1'),
             D('53000.0000'), D('15416.8000'), D('13683.3600'),
             D('82100.1600'), D('82100.16'),
             [
                 # Labor
                 (BreakdownCategoryCode.LABOR, 1,
                  'Proyecto ejecutivo acorde a necesidad del cliente',
                  'Estudio', D('1'), D('50000'), D('1'), D('50000')),
                 # HM
                 (BreakdownCategoryCode.MINOR_TOOLS, 1,
                  'HERRAMIENTA MENOR', '%', D('0.03'), D('1'), D('1'), D('1500')),
                 # EPP
                 (BreakdownCategoryCode.PPE, 1,
                  'EPP', '%', D('0.03'), D('1'), D('1'), D('1500')),
             ]),

            # --- PRELIMINARES ---
            ('02', 'A11', 1,
             'TRAZO Y NIVELACIÓN TOPOGRÁFICA Trazo, nivelación y referencia de '
             'líneas de ceros para delimitación de zonas de corte en talud y bermas '
             'de acuerdo a proyecto geométrico. Incluye brigada de topografía, '
             'equipo de precisión (estación total y niveles), estacas, mojoneras, '
             'pintura, referenciación de niveles, mano de obra especializada y '
             'herramienta. P.U.O.T.',
             'M2', D('14087'),
             D('15.9000'), D('4.6250'), D('4.1050'),
             D('24.6300'), D('346963.49'),
             [
                 (BreakdownCategoryCode.LABOR, 1,
                  'Topógrafo + Aytes. Incluso trabajos en gabinete',
                  'm2', D('1'), D('15'), D('1'), D('15')),
                 (BreakdownCategoryCode.MINOR_TOOLS, 1,
                  'HERRAMIENTA MENOR', '%', D('0.03'), D('1'), D('1'), D('0.45')),
                 (BreakdownCategoryCode.PPE, 1,
                  'EPP', '%', D('0.03'), D('1'), D('1'), D('0.45')),
             ]),

            ('02', 'A12', 2,
             'Deshierbe, Desmonte y despalme en zona de coronamiento y hombro del '
             'talud previo al inicio de los cortes. Incluye corte de vegetación, '
             'desenraice, retiro de capa vegetal, acamellonamiento de material fuera '
             'de la zona de trabajo, mano de obra y herramienta menor. P.U.O.T.',
             'M2', D('1408.7'),
             D('59.9466'), D('17.4374'), D('15.4768'),
             D('92.8608'), D('130813.05'),
             [
                 (BreakdownCategoryCode.MATERIALS, 1,
                  'Diesel', 'Lt', D('1'), D('23.09'), D('0.862'), D('19.9036')),
                 (BreakdownCategoryCode.MACHINERY, 1,
                  'Excavadora 336', 'Hr', D('1'), D('900'), D('0.034074'), D('30.6666')),
                 (BreakdownCategoryCode.LABOR, 1,
                  'Operador 336', 'jor', D('1'), D('1071.4286'), D('0.004259'), D('4.5635')),
                 (BreakdownCategoryCode.LABOR, 2,
                  'Viático Operador 336', 'semana', D('1'), D('2000'), D('0.000710'), D('1.4197')),
                 (BreakdownCategoryCode.MINOR_TOOLS, 1,
                  'HERRAMIENTA MENOR', '%', D('0.03'), D('1'), D('1'), D('1.6966')),
                 (BreakdownCategoryCode.PPE, 1,
                  'EPP', '%', D('0.03'), D('1'), D('1'), D('1.6966')),
             ]),

            ('02', 'A13', 3,
             'Implantación y retiro de equipo de obra. De Santa María Huatulco, '
             'Oaxaca, a Ojuelos Jalisco. Incluye traslado de maquinaria y personal '
             'calificado a sitio de obra',
             'Lote', D('1'),
             D('254400.0000'), D('74000.6401'), D('65680.1280'),
             D('394080.7681'), D('394080.77'),
             [
                 (BreakdownCategoryCode.MACHINERY, 1,
                  'Flete de Llegada 336', 'evento', D('1'), D('60000'), D('1'), D('60000')),
                 (BreakdownCategoryCode.MACHINERY, 2,
                  'Flete Salida 336', 'evento', D('1'), D('60000'), D('1'), D('60000')),
                 (BreakdownCategoryCode.MACHINERY, 3,
                  'Flete llegada Cargador Frontal', 'evento', D('1'), D('60000'), D('1'), D('60000')),
                 (BreakdownCategoryCode.MACHINERY, 4,
                  'Flete Salida Cargador frontal', 'evento', D('1'), D('60000'), D('1'), D('60000')),
                 (BreakdownCategoryCode.MINOR_TOOLS, 1,
                  'HERRAMIENTA MENOR', '%', D('0.03'), D('1'), D('1'), D('7200')),
                 (BreakdownCategoryCode.PPE, 1,
                  'EPP', '%', D('0.03'), D('1'), D('1'), D('7200')),
             ]),

            # --- MOVIMIENTO DE TIERRAS Y ABATIMIENTO ---
            ('03', 'A22', 1,
             'Amacice y retiro de bloques de roca sueltos o inestables detectados '
             'en la cara del talud. Incluye inspección técnica; amacice mecánico '
             'con retroexcavadora / excavadora, equipo de seguridad, y maniobras de '
             'descenso seguro de material. P.U.O.T.',
             'm2', D('14087'),
             D('53.8731'), D('15.6708'), D('13.9088'),
             D('83.4526'), D('1175597.38'),
             [
                 (BreakdownCategoryCode.MATERIALS, 1,
                  'Diesel', 'Lt', D('1'), D('23.09'), D('0.862'), D('19.9036')),
                 (BreakdownCategoryCode.MACHINERY, 1,
                  'Excavadora 336', 'Hr', D('1'), D('900'), D('0.028395'), D('25.5555')),
                 (BreakdownCategoryCode.LABOR, 1,
                  'Operador 336', 'jor', D('1'), D('1071.4286'), D('0.003549'), D('3.8029')),
                 (BreakdownCategoryCode.LABOR, 2,
                  'Viático Operador 336', 'semana', D('1'), D('2000'), D('0.000639'), D('1.2778')),
                 (BreakdownCategoryCode.LABOR, 3,
                  'Pasaje llegada 336', 'evento', D('1'), D('2000'), D('0.000071'), D('0.1420')),
                 (BreakdownCategoryCode.LABOR, 4,
                  'Pasaje salida 336', 'evento', D('1'), D('2000'), D('0.000071'), D('0.1420')),
                 (BreakdownCategoryCode.MINOR_TOOLS, 1,
                  'HERRAMIENTA MENOR', '%', D('0.03'), D('1'), D('1'), D('1.5247')),
                 (BreakdownCategoryCode.PPE, 1,
                  'EPP', '%', D('0.03'), D('1'), D('1'), D('1.5247')),
             ]),

            ('03', 'A23', 2,
             'CARGA Y ACARREO INTERNO DE MATERIAL (1er KM) Carga mecánica y acarreo '
             'en camión de volteo de material producto de excavación y despalme. '
             'Incluye Carga, abundamiento y acarreo interno a plancha de acopio de '
             'material determinada por el cliente a una distancia no mayor a 1 km.',
             'm3', D('5000'),
             D('91.2206'), D('26.5345'), D('23.5510'),
             D('141.3061'), D('706530.52'),
             [
                 (BreakdownCategoryCode.MACHINERY, 1,
                  'Cargador Frontal', 'Hr', D('1'), D('900'), D('0.048'), D('43.2')),
                 (BreakdownCategoryCode.MACHINERY, 2,
                  'Camión de volteo 14m3', 'jor', D('1'), D('6000'), D('0.006'), D('36')),
                 (BreakdownCategoryCode.LABOR, 1,
                  'Operador Cargador Frontal', 'jor', D('1'), D('928.5714'), D('0.0048'), D('4.4571')),
                 (BreakdownCategoryCode.LABOR, 2,
                  'Viático Operador cargador frontal', 'semana', D('1'), D('2000'), D('0.0008'), D('1.6')),
                 (BreakdownCategoryCode.LABOR, 3,
                  'Pasaje llegada cargador frontal', 'evento', D('1'), D('2000'), D('0.0002'), D('0.4')),
                 (BreakdownCategoryCode.LABOR, 4,
                  'Pasaje salida cargador frontal', 'evento', D('1'), D('2000'), D('0.0002'), D('0.4')),
                 (BreakdownCategoryCode.MINOR_TOOLS, 1,
                  'HERRAMIENTA MENOR', '%', D('0.03'), D('1'), D('1'), D('2.5817')),
                 (BreakdownCategoryCode.PPE, 1,
                  'EPP', '%', D('0.03'), D('1'), D('1'), D('2.5817')),
             ]),

            # --- FORTIFICACIÓN DE TALUD ---
            ('04', 'A34', 1,
             'Suministro y colocación de malla triple torsión de 8x10, calibre 12.5 '
             'Fy=4,200 kg/cm2, sujeta al talud en la corona superior mediante '
             'anclaje con acero corrugado #04 y 1.5m de longitud. En la parte '
             'inferior mediante varilla corrugada #04 y 1.0m de longitud. Con cable '
             'de amarre de acero galvanizado de 3/8" en pie de talud y 1/2" en '
             'corona. Incluye material, mano de obra especializada en trabajos de '
             'altura, maquinaria, herramienta y todo lo necesario para su correcta '
             'ejecución.',
             'm2', D('7043.5'),
             D('263.6538'), D('76.6924'), D('68.0692'),
             D('408.4155'), D('2876674.26'),
             [
                 (BreakdownCategoryCode.MATERIALS, 1,
                  'Malla triple torsión 8x10 calibre 12', 'm2', D('1'), D('96'), D('1.2'), D('115.20')),
                 (BreakdownCategoryCode.MATERIALS, 2,
                  'Cable de acero Galv 1/2"', 'ml', D('1'), D('42'), D('0.17'), D('7.14')),
                 (BreakdownCategoryCode.MATERIALS, 3,
                  'Cable de acero Galv 3/8"', 'ml', D('1'), D('42'), D('0.17'), D('7.14')),
                 (BreakdownCategoryCode.MATERIALS, 4,
                  'Varilla corrugada 1/2"', 'kg', D('1'), D('19'), D('0.75'), D('14.25')),
                 (BreakdownCategoryCode.MATERIALS, 5,
                  'Cemento/ Mortero (Grout para anclaje)', 'kg', D('1'), D('5'), D('1'), D('5')),
                 (BreakdownCategoryCode.LABOR, 1,
                  'Cuadrilla 1 cabo + 4 instaladores', 'jor', D('1'), D('5500'), D('0.018182'), D('100')),
                 (BreakdownCategoryCode.MINOR_TOOLS, 1,
                  'HERRAMIENTA MENOR', '%', D('0.03'), D('1'), D('1'), D('7.4619')),
                 (BreakdownCategoryCode.PPE, 1,
                  'EPP', '%', D('0.03'), D('1'), D('1'), D('7.4619')),
             ]),
        ]

        concept_count = 0
        breakdown_count = 0

        for (sf_code, c_code, seq, desc, unit, qty,
             direct, indirect, utility, up, total, breakdowns) in concepts_data:
            concept = BudgetConcept.objects.create(
                projectid=project,
                subfamilyid=subfamilies[sf_code],
                code=c_code,
                sequencenumber=seq,
                description=desc,
                unit=unit,
                quantity=qty,
                directunitcost=direct,
                indirectunitcost=indirect,
                utilityunitcost=utility,
                unitprice=up,
                totalamount=total,
                breakdownmethod=0,  # Detailed
                isprintable=True,
                createdby=owner,
                modifiedby=owner,
            )
            concept_count += 1

            for (cat, line, bdesc, bunit, bqty, bprice, byield, bamount) in breakdowns:
                UnitCostBreakdown.objects.create(
                    conceptid=concept,
                    categorycode=cat,
                    linenumber=line,
                    description=bdesc,
                    unit=bunit,
                    quantity=bqty,
                    unitprice=bprice,
                    yieldvalue=byield,
                    amount=bamount,
                )
                breakdown_count += 1

        self.stdout.write(f"Created {concept_count} concepts with {breakdown_count} breakdowns")

        # =====================================================================
        # 5. Indirect Costs (C1-C8 from "Costo Indirecto" sheet)
        # =====================================================================
        indirect_costs_data = [
            # C1 - PERSONAL
            ('C1', 'PERSONAL', [
                (1, 'Gerente de Proyecto', 'Gerente de Proyecto', D('30000'), D('1'), D('2'), D('60000')),
                (2, 'Gerente Administración', 'Gerente Administración', D('30000'), D('1'), D('2'), D('60000')),
                (3, 'Técnico de compras/ control de Costos', 'Técnico de compras/ control de Costos', D('5400'), D('1'), D('2'), D('10800')),
                (4, 'Aux. Administrativo', 'Aux. Administrativo', D('5400'), D('1'), D('2'), D('10800')),
                (5, 'Jefe de Obra', 'Jefe de Obra', D('45000'), D('1'), D('2'), D('90000')),
            ]),
            # C2 - EQUIPAMIENTO PARA PERSONAL DE OBRA
            ('C2', 'EQUIPAMIENTO PARA PERSONAL DE OBRA', [
                (1, 'Vehículo Jefe de Obra', 'Vehículo Jefe de Obra', D('16000'), D('1'), D('2'), D('32000')),
                (2, 'Combustible para vehículos de trabajo', 'Combustible para vehículos de trabajo', D('17500'), D('1'), D('2'), D('35000')),
                (3, 'Viáticos para personal de obra', 'Viáticos para personal de obra', D('10000'), D('1'), D('2'), D('20000')),
            ]),
            # C3 - TRASLADOS Y HOSPEDAJES
            ('C3', 'TRASLADOS Y HOSPEDAJES PERSONAL DE OBRA', [
                (1, 'Casa Jefe de Obra', 'Casa Jefe de Obra', D('10000'), D('1'), D('2'), D('20000')),
            ]),
            # C4 - GASTOS DE OFICINA CENTRAL (all 0 in this project)
            # C5 - IMPLANTACIÓN EN SITIO DE OBRA (all 0)
            # C6 - OTROS COSTOS OPERATIVOS
            ('C6', 'OTROS COSTOS OPERATIVOS', [
                (1, 'Señalética seguridad', 'Señalética seguridad', D('2000'), D('1'), D('2'), D('4000')),
            ]),
            # C7 - FIANZAS, SEGUROS Y OTROS PREVIOS
            ('C7', 'FIANZAS, SEGUROS Y OTROS PREVIOS', [
                (1, 'Fianza Anticipo (Aprox 1.3% del valor del anticipo c/IVA)', 'Fianza Anticipo', D('15834'), D('1'), D('1'), D('15834')),
                (2, 'Fianza Cumplimiento (Aprox 1.7% del valor afianzado)', 'Fianza Cumplimiento', D('20706'), D('1'), D('1'), D('20706')),
                (3, 'Fianza Vicios Ocultos (Aprox 1.3% del valor del anticipo)', 'Fianza Vicios Ocultos', D('15834'), D('1'), D('1'), D('15834')),
                (4, 'Seg. Resp. Civil (Aprox 0.11% del contrato c/IVA)', 'Seguro Resp. Civil', D('8278'), D('1'), D('1'), D('8278')),
                (5, 'Costos fase de Licitación', 'Costos fase de Licitación', D('15000'), D('1'), D('1'), D('15000')),
            ]),
            # C8 - PROYECTOS, GESTIONES E IMPUESTOS
            ('C8', 'PROYECTOS, GESTIONES E IMPUESTOS', [
                (1, 'Gestiones especiales', 'Gestiones especiales', D('5014052.28'), D('0.1'), D('1'), D('501405.23')),
                (2, 'Impuestos (ISR Prov) Aprox 2.84% S/neto', 'Impuestos ISR Provisional', D('138087.00'), D('1'), D('1'), D('138087.00')),
                (3, 'Elaboración de Proyecto', 'Elaboración de Proyecto', D('15000'), D('1'), D('1'), D('15000')),
            ]),
        ]

        indirect_count = 0
        for cat_code, area_name, items in indirect_costs_data:
            for line, desc, area, monthly, units, months, amount in items:
                IndirectCostDetail.objects.create(
                    projectid=project,
                    categorycode=cat_code,
                    linenumber=line,
                    area=area_name,
                    description=desc,
                    monthlycost=monthly,
                    units=units,
                    months=months,
                    amount=amount,
                    createdby=owner,
                    modifiedby=owner,
                )
                indirect_count += 1

        self.stdout.write(f"Created {indirect_count} indirect cost details")

        # =====================================================================
        # 6. Offer Alternatives (from Hoja Cierre Estudio)
        # =====================================================================
        # Base (P.U. Asignado)
        alt_base = OfferAlternative.objects.create(
            projectid=project,
            alternativenumber=1,
            name='P.U. Asignado (Base)',
            description='Precio unitario base asignado, coeficiente 1.0',
            transversalpercent=D('0.0500'),
            profitpercent=D('0.1500'),
            coefficient=D('1.000000'),
            directcosttotal=D('3687888.80'),
            indirectcosttotal=D('1072744.23'),
            constructioncost=D('4760633.02'),
            salepricenet=D('5712759.63'),
            taxamount=D('914041.54'),
            salepricetotal=D('6626801.17'),
            saleusd=D('331340.06'),
            ischosen=False,
            createdby=owner,
            modifiedby=owner,
        )

        # Alternativa 1
        alt1 = OfferAlternative.objects.create(
            projectid=project,
            alternativenumber=2,
            name='Alternativa 1',
            description='Margen de utilidad 31%, coeficiente 1.05',
            transversalpercent=D('0.0500'),
            profitpercent=D('0.3100'),
            coefficient=D('1.050000'),
            directcosttotal=D('3687888.80'),
            indirectcosttotal=D('1072744.23'),
            constructioncost=D('4760633.02'),
            salepricenet=D('6474460.91'),
            taxamount=D('1035913.75'),
            salepricetotal=D('7510374.66'),
            saleusd=D('375518.73'),
            ischosen=False,
            createdby=owner,
            modifiedby=owner,
        )

        # Alternativa elegida (coef 0.998)
        alt_chosen = OfferAlternative.objects.create(
            projectid=project,
            alternativenumber=3,
            name='Alternativa Elegida',
            description='Margen de utilidad 25%, coeficiente 0.998. '
                        'Venta neta: $6,188,822.93 MXN ($358,951.73 USD inc. IVA)',
            transversalpercent=D('0.0500'),
            profitpercent=D('0.2500'),
            coefficient=D('0.998000'),
            directcosttotal=D('3687888.80'),
            indirectcosttotal=D('1072744.23'),
            constructioncost=D('4760633.02'),
            salepricenet=D('6188822.93'),
            taxamount=D('990211.67'),
            salepricetotal=D('7179034.60'),
            saleusd=D('358951.73'),
            ischosen=True,
            createdby=owner,
            modifiedby=owner,
        )

        self.stdout.write(f"Created 3 offer alternatives (chosen: Alt 3)")

        # =====================================================================
        # 7. External Cost Items (from Hoja Cierre Estudio)
        # =====================================================================
        external_items = [
            ('Fianza Anticipo (Aprox 1.3% del valor del anticipo c/IVA)',
             ChecklistStatusCode.YES, D('0.0026'), 1),
            ('Fianza Cumplimiento (Aprox 1.7% del valor afianzado)',
             ChecklistStatusCode.YES, D('0.0033'), 2),
            ('Fianza Vicios Ocultos (Aprox 1.3% del valor del anticipo)',
             ChecklistStatusCode.YES, D('0.0026'), 3),
            ('Seg. Resp. Civil (Aprox 0.11% del contrato c/IVA)',
             ChecklistStatusCode.YES, D('0.0013'), 4),
            ('Seguro GMM para empleados',
             ChecklistStatusCode.NO, None, 5),
            ('Otros seguros',
             ChecklistStatusCode.NO, None, 6),
            ('Diseño/ Ingeniería de Proyecto',
             ChecklistStatusCode.NO, None, 7),
            ('Financiamiento',
             ChecklistStatusCode.NO, None, 8),
            ('Efecto inflación',
             ChecklistStatusCode.NO, None, 9),
            ('Usos jurídicos',
             ChecklistStatusCode.NO, None, 10),
            ('Relaciones públicas y Publicidad',
             ChecklistStatusCode.NO, None, 11),
            ('Pruebas de laboratorio',
             ChecklistStatusCode.NO, None, 12),
            ('Barreras de desvío de tráfico',
             ChecklistStatusCode.NO, None, 13),
            ('Bandereros',
             ChecklistStatusCode.NO, None, 14),
            ('Costos fase de Licitación',
             ChecklistStatusCode.YES, D('0.0024'), 15),
            ('Gestiones especiales',
             ChecklistStatusCode.YES, D('0.0810'), 16),
            ('Impuestos (ISR Prov) Aprox 2.84% S/neto',
             ChecklistStatusCode.YES, D('0.0223'), 17),
            ('Efectos cambiarios',
             ChecklistStatusCode.NO, None, 18),
            ('Margen de seguridad',
             ChecklistStatusCode.NO, None, 19),
            ('Elaboración de Proyecto',
             ChecklistStatusCode.YES, D('0.0024'), 20),
        ]

        for name, applies, pct, order in external_items:
            cat = external_name_to_category(name)
            from django.db.models import Max as _Max
            agg = IndirectCostDetail.objects.filter(
                projectid=project, categorycode=cat
            ).aggregate(m=_Max('linenumber'))
            next_line = (agg['m'] or 0) + 1
            IndirectCostDetail.objects.create(
                projectid=project,
                categorycode=cat,
                linenumber=next_line,
                imputationcode='',
                area='',
                description=name,
                monthlycost=D('0'),
                units=1,
                months=1,
                applies=applies,
                percentofsale=pct,
                amount=D('0'),
                formulakey='',
                createdby=owner,
                modifiedby=owner,
            )

        self.stdout.write(f"Created {len(external_items)} external cost items (as IndirectCostDetail)")

        # =====================================================================
        # Summary
        # =====================================================================
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\n"
            f"LOAD COMPLETE\n"
            f"{'='*60}\n"
            f"Project: {project.estimationnumber} - {project.name}\n"
            f"Family: 1 (01. FAMILIA)\n"
            f"Subfamilies: {len(subfamilies)}\n"
            f"Concepts: {concept_count}\n"
            f"Breakdowns: {breakdown_count}\n"
            f"Indirect Costs: {indirect_count}\n"
            f"Offer Alternatives: 3\n"
            f"External Costs: {len(external_items)}\n"
            f"{'='*60}"
        ))
