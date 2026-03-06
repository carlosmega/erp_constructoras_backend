"""
CFDI v4.0 XML Parser.

Parses Mexican SAT CFDI v4.0 invoices using xml.etree.ElementTree (stdlib).
Mirrors the frontend parser at features/construction-projects/utils/cfdi-parser.ts.

Namespace references:
- cfdi: http://www.sat.gob.mx/cfd/4
- tfd:  http://www.sat.gob.mx/TimbreFiscalDigital
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Optional


CFDI_NS = 'http://www.sat.gob.mx/cfd/4'
TFD_NS = 'http://www.sat.gob.mx/TimbreFiscalDigital'


class CfdiParseError(Exception):
    """Raised when CFDI XML parsing fails."""
    pass


@dataclass
class CfdiConcepto:
    """A single line item from the CFDI."""
    claveprodserv: Optional[str] = None
    cantidad: Decimal = Decimal('0')
    claveunidad: Optional[str] = None
    unidad: Optional[str] = None
    descripcion: str = 'Sin descripcion'
    valorunitario: Decimal = Decimal('0')
    importe: Decimal = Decimal('0')
    descuento: Optional[Decimal] = None


@dataclass
class CfdiParsedData:
    """Structured data extracted from a CFDI XML."""
    version: str = '4.0'
    serie: Optional[str] = None
    folio: Optional[str] = None
    fecha: Optional[datetime] = None
    formapago: Optional[str] = None
    metodopago: Optional[str] = None
    moneda: str = 'MXN'
    tipocambio: Optional[Decimal] = None
    subtotal: Decimal = Decimal('0.00')
    descuento: Decimal = Decimal('0.00')
    total: Decimal = Decimal('0.00')

    # Emisor
    emisor_rfc: str = ''
    emisor_nombre: str = ''
    emisor_regimenfiscal: Optional[str] = None

    # Receptor
    receptor_rfc: str = ''
    receptor_nombre: str = ''
    receptor_usocfdi: Optional[str] = None

    # Line items
    conceptos: list[CfdiConcepto] = field(default_factory=list)

    # Taxes
    total_impuestos_trasladados: Decimal = Decimal('0.00')
    total_impuestos_retenidos: Decimal = Decimal('0.00')

    # Timbre fiscal
    uuid: Optional[str] = None
    fechatimbrado: Optional[datetime] = None

    # Parse issues (non-fatal)
    warnings: list[str] = field(default_factory=list)


def _parse_decimal(value: Optional[str]) -> Decimal:
    """Parse a string to Decimal, returning 0 on failure."""
    if not value:
        return Decimal('0')
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string from CFDI."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _find_element(root: ET.Element, namespace: str, tag: str) -> Optional[ET.Element]:
    """Find element by namespace+tag, falling back to local name."""
    el = root.find(f'{{{namespace}}}{tag}')
    if el is not None:
        return el
    # Fallback: search without namespace
    for child in root.iter():
        if child.tag.endswith(f'}}{tag}') or child.tag == tag:
            return child
    return None


def _find_all_elements(root: ET.Element, namespace: str, tag: str) -> list[ET.Element]:
    """Find all elements by namespace+tag, falling back to local name."""
    elements = root.findall(f'.//{{{namespace}}}{tag}')
    if elements:
        return elements
    # Fallback
    return [el for el in root.iter() if el.tag.endswith(f'}}{tag}') or el.tag == tag]


class CfdiParser:
    """Parse CFDI v4.0 XML content into structured data."""

    @staticmethod
    def parse(xml_content: bytes | str) -> CfdiParsedData:
        """
        Parse raw XML bytes or string into CfdiParsedData.

        Raises CfdiParseError if XML is invalid or missing required elements.
        """
        if isinstance(xml_content, str):
            xml_content = xml_content.encode('utf-8')

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise CfdiParseError(f'XML invalido: {e}')

        data = CfdiParsedData()

        # Find Comprobante root (may be the root itself or a child)
        comprobante = root
        if not (root.tag.endswith('Comprobante') or root.tag == 'Comprobante'):
            comp = _find_element(root, CFDI_NS, 'Comprobante')
            if comp is None:
                raise CfdiParseError(
                    'Elemento Comprobante no encontrado. Verifique que sea un CFDI valido.'
                )
            comprobante = comp

        # Version check
        version = comprobante.get('Version', '')
        if version and not version.startswith('4'):
            raise CfdiParseError(
                f'Version CFDI {version} no soportada. Solo se acepta CFDI v4.0.'
            )
        data.version = version or '4.0'

        # Comprobante attributes
        data.serie = comprobante.get('Serie')
        data.folio = comprobante.get('Folio')
        data.fecha = _parse_datetime(comprobante.get('Fecha'))
        data.formapago = comprobante.get('FormaPago')
        data.metodopago = comprobante.get('MetodoPago')
        data.moneda = comprobante.get('Moneda', 'MXN')
        tipocambio = comprobante.get('TipoCambio')
        data.tipocambio = _parse_decimal(tipocambio) if tipocambio else None
        data.subtotal = _parse_decimal(comprobante.get('SubTotal'))
        data.descuento = _parse_decimal(comprobante.get('Descuento'))
        data.total = _parse_decimal(comprobante.get('Total'))

        # Emisor
        emisor = _find_element(comprobante, CFDI_NS, 'Emisor')
        if emisor is None:
            raise CfdiParseError('Elemento Emisor no encontrado en el CFDI')
        data.emisor_rfc = emisor.get('Rfc', '')
        data.emisor_nombre = emisor.get('Nombre', '')
        data.emisor_regimenfiscal = emisor.get('RegimenFiscal')

        # Receptor
        receptor = _find_element(comprobante, CFDI_NS, 'Receptor')
        if receptor is None:
            raise CfdiParseError('Elemento Receptor no encontrado en el CFDI')
        data.receptor_rfc = receptor.get('Rfc', '')
        data.receptor_nombre = receptor.get('Nombre', '')
        data.receptor_usocfdi = receptor.get('UsoCFDI')

        # Conceptos
        conceptos_elements = _find_all_elements(comprobante, CFDI_NS, 'Concepto')
        for el in conceptos_elements:
            data.conceptos.append(CfdiConcepto(
                claveprodserv=el.get('ClaveProdServ'),
                cantidad=_parse_decimal(el.get('Cantidad')),
                claveunidad=el.get('ClaveUnidad'),
                unidad=el.get('Unidad'),
                descripcion=el.get('Descripcion', 'Sin descripcion'),
                valorunitario=_parse_decimal(el.get('ValorUnitario')),
                importe=_parse_decimal(el.get('Importe')),
                descuento=_parse_decimal(el.get('Descuento')) or None,
            ))

        # Impuestos
        impuestos = _find_element(comprobante, CFDI_NS, 'Impuestos')
        if impuestos is not None:
            data.total_impuestos_trasladados = _parse_decimal(
                impuestos.get('TotalImpuestosTrasladados')
            )
            data.total_impuestos_retenidos = _parse_decimal(
                impuestos.get('TotalImpuestosRetenidos')
            )

        # TimbreFiscalDigital
        timbre = _find_element(root, TFD_NS, 'TimbreFiscalDigital')
        if timbre is None:
            # Also search within Complemento
            timbre = _find_element(comprobante, TFD_NS, 'TimbreFiscalDigital')
        if timbre is not None:
            data.uuid = timbre.get('UUID')
            data.fechatimbrado = _parse_datetime(timbre.get('FechaTimbrado'))
        else:
            data.warnings.append('TimbreFiscalDigital no encontrado — UUID no disponible')

        return data
