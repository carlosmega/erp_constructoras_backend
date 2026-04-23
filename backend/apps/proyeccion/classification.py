"""
Dimovere Catalog Classification Engine

Assigns familia (L2) and subfamilia (L3) to ConceptPriceCatalogItem records
with source=HISTORICO using keyword analysis of descriptions.

The classification follows the same hierarchy pattern as SICT:
  SICT:     L1=Libro,  L2=Título,    L3=Capítulo
  Dimovere: L1=(vacío), L2=Familia,   L3=Subfamilia

Usage:
    from apps.proyeccion.classification import classify_concept
    familia, subfamilia = classify_concept("Pintura vinilica en muros...")
    # -> ("Acabados", "Pintura")
"""

import unicodedata


def normalize(text: str) -> str:
    """Lowercase + remove accents for robust Spanish keyword matching."""
    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text


# ─── Classification Rules ───────────────────────────────────────────────────
# Each entry: (familia, subfamilia, [keywords])
# Order matters: first match wins. More specific rules go first.
# Keywords are matched after normalization (no accents, lowercase).

CLASSIFICATION_RULES: list[tuple[str, str, list[str]]] = [

    # ── Trabajos Preliminares ──────────────────────────────────
    ('Trabajos Preliminares', 'Trazo y Nivelación',
     ['trazo y nivelac', 'trazo', 'nivelacion', 'topograf', 'replanteo',
      'estacado']),

    ('Trabajos Preliminares', 'Limpiezas',
     ['limpieza general', 'limpieza final', 'limpieza de obra',
      'limpieza gruesa', 'limpieza fina', 'aseo general']),

    ('Trabajos Preliminares', 'Protecciones Provisionales',
     ['proteccion provisional', 'señalamiento de obra', 'barricada',
      'cinta de precaucion', 'tapial', 'proteccion para confinamiento',
      'confinamiento de las area', 'plastico grueso']),

    # ── Demoliciones y Desmontaje ──────────────────────────────
    ('Demoliciones y Desmontaje', 'Desmontaje de Instalaciones',
     ['cancelacion de instalacion', 'cancelac', 'desmontaje',
      'retiro de cableado', 'retiro de canalizacion', 'retiro de instalac',
      'retiro de luminaria', 'retiro de equipo', 'retiro de mueble',
      'retiro de aparato', 'retiro de plafon', 'retiro de piso',
      'retiro de azulejo', 'retiro de muro', 'retiro de puerta',
      'retiro de ventana', 'retiro de cancel', 'retiro de zoclo',
      'retiro de alfombra', 'retiro de loseta']),

    ('Demoliciones y Desmontaje', 'Demolición de Elementos',
     ['demolicion', 'demoler', 'picado', 'ruptura', 'ranurado',
      'cajeado', 'apertura de huecos', 'corte en muro']),

    ('Demoliciones y Desmontaje', 'Retiro de Escombro',
     ['retiro de escombro', 'acarreo de escombro', 'escombro',
      'tiro oficial', 'banco de tiro', 'tiro autorizado',
      'carga manual']),

    # ── Terracerías y Excavaciones ─────────────────────────────
    ('Terracerías y Excavaciones', 'Excavaciones',
     ['excavacion', 'excavac', 'zanja', 'zanjeo', 'cepa', 'cepeo',
      'despalme', 'desmonte y des', 'desenraice']),

    ('Terracerías y Excavaciones', 'Acarreos de Material',
     ['acarreo de material', 'acarreo de tierra', 'acarreo de producto',
      'transporte de material']),

    ('Terracerías y Excavaciones', 'Rellenos y Compactación',
     ['relleno', 'compactacion', 'tepetate', 'material seleccionado',
      'material de banco', 'sub-base', 'subbase']),

    # ── Concreto y Estructura ──────────────────────────────────
    ('Concreto y Estructura', 'Acero de Refuerzo',
     ['acero de refuerzo', 'varilla', 'armado de acero', 'alambre recocido',
      'fy=', 'acero del no', 'malla electrosoldada']),

    ('Concreto y Estructura', 'Cimentaciones',
     ['cimentacion', 'zapata', 'dado de concreto', 'plantilla de concreto',
      'contratrabe', 'trabe de cimentac']),

    ('Concreto y Estructura', 'Firmes y Losas',
     ['firme de concreto', 'losa de concreto', 'firme de',
      'entortado', 'mortero de nivelacion', 'losa plana',
      'junta de control', 'junta de pvc', 'junta constructiva']),

    ('Concreto y Estructura', 'Elementos Estructurales',
     ['concreto fc', "concreto f'c", 'colado de concreto', 'castillo',
      'dala', 'trabe', 'columna de concreto', 'viga', 'muro de concreto',
      'losa de entrepiso', 'concreto armado', 'banqueta de concreto',
      'concreto simple', 'concreto hecho en obra', 'registro de concreto',
      'registros de 20']),

    # ── Albañilería ────────────────────────────────────────────
    ('Albañilería', 'Muros de Mampostería',
     ['muro de block', 'muro de tabique', 'muro de ladrillo',
      'block hueco', 'block de concreto', 'muro de mamposteria',
      'tabique rojo', 'tabique de barro']),

    ('Albañilería', 'Aplanados y Repellados',
     ['aplanado', 'repellado', 'enlucido', 'empaste', 'junteado',
      'emboquillado', 'mezcla cemento arena']),

    # ── Impermeabilización ─────────────────────────────────────
    ('Impermeabilización', 'Membrana Prefabricada',
     ['membrana prefabricada', 'membrana app', 'membrana sbs',
      'membrana asfaltica']),

    ('Impermeabilización', 'Sistemas Impermeabilizantes',
     ['impermeabilizac', 'impermeabilizante', 'impermeabilizar',
      'cristalizante', 'sellador impermeab']),

    # ── Muros Secos y Particiones ──────────────────────────────
    ('Muros Secos y Particiones', 'Tablaroca',
     ['tablaroca', 'tabla roca', 'drywall', 'placa de yeso',
      'muro de yeso', 'canal de aluminio 3', 'sistema de tablaroca']),

    ('Muros Secos y Particiones', 'Cancelería y Mamparas',
     ['cancel de aluminio', 'mampara', 'division de aluminio',
      'panel divisorio', 'division de vidrio', 'canceleria']),

    # ── Acabados ───────────────────────────────────────────────
    ('Acabados', 'Plafones',
     ['plafon', 'cielo raso', 'falso plafon', 'plafon registrable',
      'plafon acustico', 'plafon metalico', 'plafon de suspension']),

    ('Acabados', 'Pintura',
     ['pintura', 'vinilica', 'esmalte', 'barniz', 'sellador',
      'resane', 'resanar', 'pintar', 'acabado en pintura']),

    ('Acabados', 'Pisos y Recubrimientos',
     ['piso ceramic', 'piso porcelan', 'piso de ceramica', 'piso de madera',
      'piso laminado', 'piso de vinyl', 'piso vinil', 'piso epoxic',
      'azulejo', 'loseta', 'mosaico', 'porcelanato', 'interceramic',
      'recubrimiento ceramic', 'recubrimiento de muro',
      'pasta de marmol', 'piso de concreto pulido', 'alfombra']),

    ('Acabados', 'Zoclos y Molduras',
     ['zoclo', 'rodapie', 'moldura', 'cornisa', 'cenefa',
      'angulo de aluminio', 'angulo de 3/4', 'perfil esquinero']),

    # ── Carpintería y Herrería ─────────────────────────────────
    ('Carpintería y Herrería', 'Puertas',
     ['puerta de madera', 'puerta tambor', 'puerta metalica',
      'puerta de acero', 'puerta de aluminio', 'marco de puerta',
      'chambrana', 'chapa', 'bisagra', 'puerta corrediza',
      'puerta plegadiza', 'canes de madera', 'triplay']),

    ('Carpintería y Herrería', 'Ventanas y Vidrios',
     ['ventana', 'cristal', 'vidrio templado', 'vidrio laminado',
      'doble vidrio', 'vitral']),

    ('Carpintería y Herrería', 'Muebles y Closets',
     ['mueble', 'closet', 'locker', 'archivero', 'cubiculo',
      'librero', 'modular', 'cocineta', 'barra de cocina',
      'estante', 'muscle rack', 'anaquel']),

    # ── Instalaciones Eléctricas ───────────────────────────────
    ('Instalaciones Eléctricas', 'Iluminación',
     ['luminaria', 'lampara', 'downlight', 'led empotrad', 'led tipo',
      'reflector', 'fluorescent', 'foco', 'aplique', 'spot']),

    ('Instalaciones Eléctricas', 'Salidas y Contactos',
     ['salida para contacto', 'contacto duplex', 'contacto polarizado',
      'contacto monofasico', 'apagador', 'switch', 'salida de piso',
      'salida de voz', 'salida de datos', 'nodo de datos', 'cctv',
      'barra de contacto', 'supresor de pico', 'multicontacto',
      'placa de contacto']),

    ('Instalaciones Eléctricas', 'Canalizaciones y Cableado',
     ['conduit', 'cable thw', 'cable pot', 'canaleta', 'charola',
      'tuberia conduit', 'ducto electrico', 'cableado', 'tubo pdg',
      'poliducto', 'cable de cobre', 'cable utp', 'cable cat',
      'cable uso rudo', 'belden', 'fibra optica']),

    ('Instalaciones Eléctricas', 'Tableros y Protecciones',
     ['tablero electr', 'tablero de distribuc', 'panel electr',
      'interruptor termomagne', 'itm', 'breaker', 'centro de carga',
      'pastilla termomag', 'dimmer', 'control de intensidad',
      'lutron']),

    ('Instalaciones Eléctricas', 'Tierras Físicas',
     ['tierra fisica', 'tierra electronica', 'electrodo',
      'sistema de tierras', 'varilla de cobre']),

    ('Instalaciones Eléctricas', 'General Eléctrico',
     ['instalacion electrica', 'instalac electrica', 'electrica',
      'electrico']),

    # ── Instalaciones Hidráulicas y Sanitarias ─────────────────
    ('Instalaciones Hidráulicas y Sanitarias', 'Drenaje Pluvial',
     ['bajada pluvial', 'drenaje pluvial', 'canaleta pluvial',
      'coladera pluvial', 'canalon']),

    ('Instalaciones Hidráulicas y Sanitarias', 'Drenaje Sanitario',
     ['drenaje sanitario', 'pvc sanitario', 'tubo sanitario',
      'registro sanitario', 'caja de registro', 'trampa de grasa',
      'coladera sanitaria', 'bajante sanitario', 'pvc dwv',
      'astm d 2665', 'cespol', 'desague']),

    ('Instalaciones Hidráulicas y Sanitarias', 'Red Hidráulica',
     ['tubo cpvc', 'tubo pex', 'tubo galvanizado', 'tubo de cobre',
      'codo de cobre', 'cople de cobre', 'tee de cobre', 'junta de cobre',
      'valvula', 'llave de paso', 'mezcladora', 'instalacion hidraulica',
      'red de agua', 'suministro de agua', 'toma domiciliaria',
      'tuberia hidraulica', 'tubo hidraulico',
      'pp-r', 'tuboplus', 'termofusion',
      'adaptador macho pvc', 'adaptador hembra pvc',
      'codo pvc', 'cople pvc', 'tee pvc', 'reduccion pvc',
      'brida flexible', 'brida de', 'niple',
      'llave angular', 'llave de nariz']),

    ('Instalaciones Hidráulicas y Sanitarias', 'Muebles y Accesorios Sanitarios',
     ['wc', 'lavabo', 'mingitorio', 'regadera', 'tina', 'fregadero',
      'inodoro', 'mueble de baño', 'accesorios de baño', 'toallero',
      'jabonera', 'portarrollo', 'tarja', 'barra de seguridad',
      'dispensador', 'secamanos', 'botaguas', 'contracanasta',
      'despachador de jabon', 'despachador de toalla', 'despachador manual',
      'kimberly clark', 'espejo', 'gancho doble', 'gancho helvex',
      'portaescoba', 'llave con rosca', 'llave de control',
      'llave tradicional', 'coflex', 'urrea',
      'barra recta de seguridad', 'sanitario']),

    ('Instalaciones Hidráulicas y Sanitarias', 'Drenaje y Accesorios',
     ['coladera', 'descarga sanitaria', 'registro de piso',
      'trampa antiolores', 'cuerpo de fierro colado',
      'rejilla de acero inoxidable']),

    # ── Instalaciones Mecánicas y HVAC ─────────────────────────
    ('Instalaciones Mecánicas y HVAC', 'Aire Acondicionado',
     ['aire acondicionado', 'mini split', 'minisplit', 'sistema vrf',
      'fan coil', 'fancoil', 'manejadora', 'condensador',
      'unidad evaporadora', 'split', 'enfriamiento']),

    ('Instalaciones Mecánicas y HVAC', 'Ventilación y Extracción',
     ['ventilacion', 'extractor', 'inyector', 'ducto de aire',
      'difusor', 'rejilla de ventilacion', 'campana de extraccion',
      'ducteria', 'ducto de', 'ducto redondo', 'lamina galvanizada',
      'rejilla de inyeccion', 'rejilla de retorno', 'rejilla de aire',
      'modelo bsc', 'modelo gsh', 'marca innes']),

    ('Instalaciones Mecánicas y HVAC', 'Refrigeración',
     ['gas refrigerante', 'r-410', 'r-22', 'refrigerante',
      'tuberia de refrigeracion', 'linea de refrigeracion']),

    ('Instalaciones Mecánicas y HVAC', 'Gas',
     ['instalacion de gas', 'tuberia de gas', 'red de gas',
      'detector de gas', 'medidor de gas']),

    # ── Instalaciones Especiales ───────────────────────────────
    ('Instalaciones Especiales', 'Sistemas contra Incendio',
     ['contra incendio', 'extintor', 'rociador', 'sprinkler',
      'detector de humo', 'alarma contra incendio', 'gabinete contra']),

    ('Instalaciones Especiales', 'Control de Acceso y Seguridad',
     ['control de acceso', 'cctv', 'camara de seguridad',
      'sistema de alarma', 'intercomunicacion', 'interfon']),

    ('Instalaciones Especiales', 'Audio, Video y Datos',
     ['hdmi', 'extensor', 'tripp lite', 'convertidor',
      'rack de comunicacion', 'patch panel', 'jack rj45',
      'patch cord', 'portapantalla', 'brazo articulado',
      'tablero de tomografia']),

    # ── Soportería y Fijaciones ────────────────────────────────
    ('Soportería y Fijaciones', 'Abrazaderas y Soportes',
     ['abrazadera', 'soporte', 'unicanal', 'strut', 'angulo de soporte',
      'riel de soporte', 'ancla', 'insert', 'perno de anclaje']),

    ('Soportería y Fijaciones', 'Anclajes y Fijaciones',
     ['anclaje', 'taquete', 'expansion', 'fijacion', 'tornillo de anclaje']),

    # ── Logística y Servicios Generales ───────────────────────
    ('Logística y Servicios Generales', 'Maniobras y Mudanzas',
     ['acarreo acomodo', 'acarreo y armado', 'maniobra', 'mudanza',
      'traslado de mueble', 'acomodo', 'apertura de sucursal',
      'flete', 'carga y descarga']),

    ('Logística y Servicios Generales', 'Servicios Generales',
     ['cuadrilla', 'mano de obra general', 'ayudante general',
      'jornal', 'desvelo', 'guardia', 'velador']),
]

FAMILIA_DEFAULT = 'Sin Clasificar'
SUBFAMILIA_DEFAULT = 'General'

# Pre-normalize all keywords at module load time
_NORMALIZED_RULES: list[tuple[str, str, list[str]]] = [
    (fam, sub, [normalize(kw) for kw in keywords])
    for fam, sub, keywords in CLASSIFICATION_RULES
]


def classify_concept(description: str) -> tuple[str, str]:
    """
    Classify a concept description into (familia, subfamilia).

    Returns ('Sin Clasificar', 'General') if no rule matches.

    >>> classify_concept("Pintura vinilica en muros y plafones, 2 manos")
    ('Acabados', 'Pintura')
    >>> classify_concept("Firme de concreto f'c=200 kg/cm2 de 10cm")
    ('Concreto y Estructura', 'Firmes y Losas')
    """
    normalized = normalize(description)

    for familia, subfamilia, keywords in _NORMALIZED_RULES:
        if any(kw in normalized for kw in keywords):
            return familia, subfamilia

    return FAMILIA_DEFAULT, SUBFAMILIA_DEFAULT


def get_all_familias() -> list[str]:
    """Return ordered list of unique familias in the taxonomy."""
    seen = []
    for fam, _, _ in CLASSIFICATION_RULES:
        if fam not in seen:
            seen.append(fam)
    return seen
