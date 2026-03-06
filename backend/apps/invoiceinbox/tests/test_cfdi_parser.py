"""Unit tests for CFDI v4.0 XML parser."""

import pytest
from decimal import Decimal

from apps.invoiceinbox.cfdi_parser import CfdiParser, CfdiParseError


# =============================================================================
# Test XML Data
# =============================================================================

VALID_CFDI_V40_XML = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Serie="A"
    Folio="12345"
    Fecha="2026-01-15T10:30:00"
    FormaPago="03"
    MetodoPago="PUE"
    Moneda="MXN"
    SubTotal="10000.00"
    Descuento="500.00"
    Total="11040.00">
  <cfdi:Emisor Rfc="XAXX010101000" Nombre="Proveedor SA de CV" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XEXX010101000" Nombre="ConstruPro SA de CV" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Unidad="Servicio" Descripcion="Servicio de consultoria" ValorUnitario="10000.00" Importe="10000.00"/>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="1540.00">
    <cfdi:Traslados>
      <cfdi:Traslado Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1540.00"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" UUID="6A5B3C2D-1E4F-5A6B-7C8D-9E0F1A2B3C4D" FechaTimbrado="2026-01-15T10:35:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""

CFDI_MISSING_EMISOR_XML = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0"
    SubTotal="1000.00"
    Total="1160.00">
  <cfdi:Receptor Rfc="XEXX010101000" Nombre="ConstruPro SA de CV" UsoCFDI="G03"/>
</cfdi:Comprobante>"""

CFDI_MISSING_TIMBRE_XML = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0"
    Serie="B"
    Folio="99999"
    Fecha="2026-02-01T08:00:00"
    SubTotal="5000.00"
    Total="5800.00">
  <cfdi:Emisor Rfc="ABC010101AAA" Nombre="Sin Timbre SA" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XEXX010101000" Nombre="ConstruPro SA de CV" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="Material" ValorUnitario="5000.00" Importe="5000.00"/>
  </cfdi:Conceptos>
</cfdi:Comprobante>"""

CFDI_V33_XML = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/3"
    Version="3.3"
    SubTotal="1000.00"
    Total="1160.00">
  <cfdi:Emisor Rfc="XAXX010101000" Nombre="Old Version SA" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XEXX010101000" Nombre="ConstruPro SA de CV" UsoCFDI="G03"/>
</cfdi:Comprobante>"""

INVALID_XML = """<not-valid-xml><<<>>>"""

CFDI_PRECISION_XML = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Serie="C"
    Folio="77777"
    Fecha="2026-03-01T12:00:00"
    SubTotal="12345.67"
    Descuento="123.45"
    Total="14178.18"
    Moneda="MXN">
  <cfdi:Emisor Rfc="PREC010101000" Nombre="Precision SA" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XEXX010101000" Nombre="ConstruPro SA de CV" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="80101500" Cantidad="3.5000" ClaveUnidad="E48" Descripcion="Servicio medido" ValorUnitario="3527.3343" Importe="12345.67"/>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="1955.96">
    <cfdi:Traslados>
      <cfdi:Traslado Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1955.96"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" UUID="AAAA1111-BB22-CC33-DD44-EEEE5555FFFF" FechaTimbrado="2026-03-01T12:05:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""


# =============================================================================
# CfdiParser Tests
# =============================================================================

@pytest.mark.unit
class TestCfdiParser:
    """Tests for CFDI v4.0 XML parser."""

    def test_parse_valid_cfdi_v40(self):
        """Parse a complete valid CFDI v4.0 XML and verify all fields."""
        result = CfdiParser.parse(VALID_CFDI_V40_XML)

        # Version and header
        assert result.version == '4.0'
        assert result.serie == 'A'
        assert result.folio == '12345'
        assert result.formapago == '03'
        assert result.metodopago == 'PUE'
        assert result.moneda == 'MXN'

        # Date
        assert result.fecha is not None
        assert result.fecha.year == 2026
        assert result.fecha.month == 1
        assert result.fecha.day == 15
        assert result.fecha.hour == 10
        assert result.fecha.minute == 30

        # Amounts
        assert result.subtotal == Decimal('10000.00')
        assert result.descuento == Decimal('500.00')
        assert result.total == Decimal('11040.00')

        # Emisor
        assert result.emisor_rfc == 'XAXX010101000'
        assert result.emisor_nombre == 'Proveedor SA de CV'
        assert result.emisor_regimenfiscal == '601'

        # Receptor
        assert result.receptor_rfc == 'XEXX010101000'
        assert result.receptor_nombre == 'ConstruPro SA de CV'
        assert result.receptor_usocfdi == 'G03'

        # Conceptos
        assert len(result.conceptos) == 1
        concepto = result.conceptos[0]
        assert concepto.claveprodserv == '80101500'
        assert concepto.cantidad == Decimal('1')
        assert concepto.claveunidad == 'E48'
        assert concepto.unidad == 'Servicio'
        assert concepto.descripcion == 'Servicio de consultoria'
        assert concepto.valorunitario == Decimal('10000.00')
        assert concepto.importe == Decimal('10000.00')

        # Impuestos
        assert result.total_impuestos_trasladados == Decimal('1540.00')

        # Timbre fiscal
        assert result.uuid == '6A5B3C2D-1E4F-5A6B-7C8D-9E0F1A2B3C4D'
        assert result.fechatimbrado is not None
        assert result.fechatimbrado.year == 2026
        assert result.fechatimbrado.month == 1
        assert result.fechatimbrado.day == 15

        # No warnings on valid CFDI
        assert len(result.warnings) == 0

    def test_parse_missing_emisor(self):
        """Missing Emisor element should raise CfdiParseError."""
        with pytest.raises(CfdiParseError, match='Emisor'):
            CfdiParser.parse(CFDI_MISSING_EMISOR_XML)

    def test_parse_missing_timbre(self):
        """Missing TimbreFiscalDigital should set uuid to None with warning."""
        result = CfdiParser.parse(CFDI_MISSING_TIMBRE_XML)

        assert result.uuid is None
        assert result.fechatimbrado is None
        assert len(result.warnings) > 0
        assert any('TimbreFiscalDigital' in w for w in result.warnings)

        # Other fields should still be parsed correctly
        assert result.version == '4.0'
        assert result.serie == 'B'
        assert result.folio == '99999'
        assert result.emisor_rfc == 'ABC010101AAA'
        assert result.emisor_nombre == 'Sin Timbre SA'
        assert result.subtotal == Decimal('5000.00')
        assert result.total == Decimal('5800.00')

    def test_parse_invalid_xml(self):
        """Invalid XML content should raise CfdiParseError."""
        with pytest.raises(CfdiParseError, match='XML invalido'):
            CfdiParser.parse(INVALID_XML)

    def test_parse_wrong_version(self):
        """CFDI v3.3 should raise CfdiParseError (only v4.0 supported)."""
        with pytest.raises(CfdiParseError, match='3.3'):
            CfdiParser.parse(CFDI_V33_XML)

    def test_parse_decimal_precision(self):
        """Verify amounts are parsed as Decimal with correct precision."""
        result = CfdiParser.parse(CFDI_PRECISION_XML)

        # Verify types are Decimal, not float
        assert isinstance(result.subtotal, Decimal)
        assert isinstance(result.descuento, Decimal)
        assert isinstance(result.total, Decimal)
        assert isinstance(result.total_impuestos_trasladados, Decimal)

        # Verify exact values
        assert result.subtotal == Decimal('12345.67')
        assert result.descuento == Decimal('123.45')
        assert result.total == Decimal('14178.18')
        assert result.total_impuestos_trasladados == Decimal('1955.96')

        # Verify concepto amounts are Decimal
        assert len(result.conceptos) == 1
        concepto = result.conceptos[0]
        assert isinstance(concepto.cantidad, Decimal)
        assert isinstance(concepto.valorunitario, Decimal)
        assert isinstance(concepto.importe, Decimal)
        assert concepto.cantidad == Decimal('3.5000')
        assert concepto.valorunitario == Decimal('3527.3343')
        assert concepto.importe == Decimal('12345.67')

    def test_parse_bytes_input(self):
        """Parser should handle bytes input as well as string."""
        xml_bytes = VALID_CFDI_V40_XML.encode('utf-8')
        result = CfdiParser.parse(xml_bytes)

        assert result.version == '4.0'
        assert result.emisor_rfc == 'XAXX010101000'
        assert result.uuid == '6A5B3C2D-1E4F-5A6B-7C8D-9E0F1A2B3C4D'

    def test_parse_empty_string(self):
        """Empty string should raise CfdiParseError."""
        with pytest.raises(CfdiParseError):
            CfdiParser.parse('')
