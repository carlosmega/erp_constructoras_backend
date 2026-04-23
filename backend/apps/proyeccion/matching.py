"""
Concept Matching Engine

Matches imported concept descriptions against the ConceptPriceCatalog
using keyword overlap scoring with Spanish text normalization.

Usage:
    from apps.proyeccion.matching import match_concepts
    results = match_concepts(rows, queryset=None)
"""

import unicodedata
import re
from typing import Optional

from apps.proyeccion.models import ConceptPriceCatalogItem


# ── Spanish stopwords (construction context) ─────────────────────────────────

STOPWORDS = frozenset({
    'a', 'al', 'con', 'de', 'del', 'e', 'el', 'en', 'es', 'la', 'las', 'lo',
    'los', 'o', 'para', 'por', 'que', 'se', 'su', 'sus', 'un', 'una', 'y',
    # Construction boilerplate
    'incluye', 'incluir', 'material', 'materiales', 'mano', 'obra',
    'herramienta', 'herramientas', 'equipo', 'equipos', 'menor',
    'necesario', 'necesaria', 'correcta', 'correcto', 'ejecucion',
    'todo', 'todo lo', 'acuerdo', 'especificaciones',
    'suministro', 'colocacion', 'instalacion',
    'puot', 'p.u.o.t', 'p.u.o.t.', 'puot.',
})

# ── Normalization ─────────────────────────────────────────────────────────────


def normalize(text: str) -> str:
    """Lowercase + remove accents."""
    text = text.lower().strip()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text


def extract_keywords(description: str) -> list[str]:
    """
    Extract significant keywords from a concept description.
    Returns ordered list (first words have higher weight in scoring).
    """
    text = normalize(description)
    # Remove common boilerplate suffixes
    for suffix in ['p.u.o.t.', 'p.u.o.t', 'puot', 'p.u.o.t']:
        text = text.replace(suffix, '')
    # Split on non-alphanumeric (keep numbers for dimensions like 4mm, 200kg)
    tokens = re.split(r'[^a-z0-9]+', text)
    # Filter: length > 2, not stopword, not pure number
    keywords = [
        t for t in tokens
        if len(t) > 2 and t not in STOPWORDS and not t.isdigit()
    ]
    return keywords


def normalize_unit(unit: str) -> str:
    """Normalize unit strings for comparison."""
    u = normalize(unit).strip().rstrip('.')
    # Common aliases
    aliases = {
        'm2': 'm2', 'mt2': 'm2', 'm²': 'm2',
        'm3': 'm3', 'mt3': 'm3', 'm³': 'm3',
        'ml': 'ml', 'mts': 'ml', 'm': 'ml',
        'pza': 'pza', 'pieza': 'pza', 'piezas': 'pza', 'pz': 'pza',
        'kg': 'kg', 'kgs': 'kg', 'kilogramo': 'kg',
        'lt': 'lt', 'lts': 'lt', 'litro': 'lt', 'litros': 'lt',
        'hr': 'hr', 'hrs': 'hr', 'hora': 'hr',
        'jor': 'jor', 'jornal': 'jor',
        'lote': 'lote', 'evento': 'evento', 'servicio': 'servicio',
        'estudio': 'estudio', 'global': 'global', 'viaje': 'viaje',
        'ha': 'ha', 'hectarea': 'ha',
        'ton': 'ton', 'tonelada': 'ton',
        'salida': 'salida',
    }
    return aliases.get(u, u)


# ── Scoring ───────────────────────────────────────────────────────────────────

def compute_score(excel_keywords: list[str], catalog_keywords: list[str]) -> float:
    """
    Compute match score between two keyword lists.

    First 4 keywords of the Excel row get 2x weight (they're usually the
    concept name: "Trazo y nivelacion topografica" vs. the long "incluye..."
    boilerplate).
    """
    if not excel_keywords or not catalog_keywords:
        return 0.0

    catalog_set = set(catalog_keywords)
    weighted_matches = 0.0
    weighted_total = 0.0

    for i, kw in enumerate(excel_keywords):
        weight = 2.0 if i < 4 else 1.0
        weighted_total += weight
        # Check if keyword appears in catalog (substring match for partial words)
        if kw in catalog_set or any(kw in ck or ck in kw for ck in catalog_set):
            weighted_matches += weight

    return weighted_matches / weighted_total if weighted_total > 0 else 0.0


# ── Main API ──────────────────────────────────────────────────────────────────

THRESHOLD_EXACT = 0.85
THRESHOLD_PARTIAL = 0.50


def classify_match(score: float) -> str:
    """Classify a match score into exact/partial/none."""
    if score >= THRESHOLD_EXACT:
        return 'exact'
    elif score >= THRESHOLD_PARTIAL:
        return 'partial'
    return 'none'


def find_best_match(
    description: str,
    unit: str,
    catalog_cache: Optional[list[tuple]] = None,
) -> dict:
    """
    Find the best matching catalog item for a concept description.

    Args:
        description: The Excel row description
        unit: The Excel row unit
        catalog_cache: Pre-computed list of (item, normalized_unit, keywords).
                       If None, loads from DB.

    Returns:
        {
            match_status: 'exact'|'partial'|'none',
            match_score: float,
            match_candidate: ConceptPriceCatalogItem | None,
        }
    """
    excel_keywords = extract_keywords(description)
    excel_unit = normalize_unit(unit)

    if not excel_keywords:
        return {'match_status': 'none', 'match_score': 0.0, 'match_candidate': None}

    if catalog_cache is None:
        catalog_cache = _build_catalog_cache()

    best_score = 0.0
    best_item = None

    for item, cat_unit, cat_keywords in catalog_cache:
        # Unit compatibility bonus: if units match, boost score
        unit_match = (cat_unit == excel_unit) if excel_unit and cat_unit else True

        score = compute_score(excel_keywords, cat_keywords)

        # Apply unit bonus/penalty
        if unit_match:
            score = min(score * 1.1, 1.0)  # 10% boost, cap at 1.0
        else:
            score *= 0.7  # 30% penalty for unit mismatch

        if score > best_score:
            best_score = score
            best_item = item

    status = classify_match(best_score)

    return {
        'match_status': status,
        'match_score': round(best_score, 4),
        'match_candidate': best_item if status != 'none' else None,
    }


def match_concepts(rows: list[dict]) -> list[dict]:
    """
    Match multiple concept rows against the catalog.

    Args:
        rows: List of dicts with keys: description, unit
              (and any other pass-through fields like row, code, partida, quantity)

    Returns:
        List of dicts with original fields + match_status, match_score, match_candidate
    """
    cache = _build_catalog_cache()
    results = []

    for row in rows:
        match = find_best_match(
            description=row.get('description', ''),
            unit=row.get('unit', ''),
            catalog_cache=cache,
        )
        results.append({**row, **match})

    return results


# ── Cache builder ─────────────────────────────────────────────────────────────

def _build_catalog_cache() -> list[tuple]:
    """
    Pre-compute keywords for all active catalog items.
    Returns list of (ConceptPriceCatalogItem, normalized_unit, keywords).
    """
    items = ConceptPriceCatalogItem.objects.filter(statecode=0).only(
        'catalogitemid', 'code', 'description', 'unit', 'source',
        'category', 'classificationl1', 'classificationl2', 'classificationl3',
        'averageprice', 'minprice', 'maxprice', 'referencecount',
    )

    cache = []
    for item in items:
        cat_unit = normalize_unit(item.unit)
        cat_keywords = extract_keywords(item.description)
        cache.append((item, cat_unit, cat_keywords))

    return cache
