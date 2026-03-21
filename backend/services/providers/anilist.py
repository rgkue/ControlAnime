"""
providers/anilist.py — AniList (GraphQL) · Proveedor SECUNDARIO
----------------------------------------------------------------
Rol en la nueva arquitectura:
  - Aporta cover_url (bannerImage) — lo más importante
  - Aporta anilist_id para lookups futuros sin buscar por título
  - Confirma/corrige: año, temporada, estudio, duración, tipo

Rate limit: ~90 req/min. Usamos 0.8s entre llamadas.
Sin API key — endpoint público.
"""

import httpx

ANILIST_URL = "https://graphql.anilist.co"
TIMEOUT     = 10

_QUERY_SEARCH = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    bannerImage
    title { romaji english native }
    seasonYear
    season
    episodes
    duration
    status
    averageScore
    popularity
    format
    startDate { year month day }
    endDate   { year month day }
    studios(isMain: true) { nodes { name } }
  }
}
"""

_QUERY_BY_ID = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    bannerImage
    title { romaji english native }
    seasonYear
    season
    episodes
    duration
    status
    averageScore
    popularity
    format
    startDate { year month day }
    endDate   { year month day }
    studios(isMain: true) { nodes { name } }
  }
}
"""

_FORMATO_MAP = {
    "TV":       "TV",
    "TV_SHORT": "TV",
    "MOVIE":    "Movie",
    "OVA":      "OVA",
    "ONA":      "ONA",
    "SPECIAL":  "Special",
    "MUSIC":    "Special",
}

_SEASON_MAP = {
    "WINTER": "winter",
    "SPRING": "spring",
    "SUMMER": "summer",
    "FALL":   "fall",
}


def _parse_fecha(date_obj: dict | None) -> str | None:
    if not date_obj:
        return None
    y, m, d = date_obj.get("year"), date_obj.get("month"), date_obj.get("day")
    if not y:
        return None
    if m and d:
        return f"{y}-{m:02d}-{d:02d}"
    if m:
        return f"{y}-{m:02d}-01"
    return f"{y}-01-01"


def _extraer(media: dict) -> dict:
    """Convierte Media de AniList al formato de enriquecimiento."""
    studios = media.get("studios", {}).get("nodes", [])
    estudio = studios[0].get("name") if studios else None

    score  = media.get("averageScore")
    rating = round(score / 10, 2) if score else None

    return {
        "anilist_id":   media.get("id"),
        "cover_url":    media.get("bannerImage"),  # ← banner como cover
        "anio":         media.get("seasonYear"),
        "temporada":    _SEASON_MAP.get(media.get("season", ""), None),
        "estudio":      estudio,
        "score_count":  media.get("popularity"),
        "popularidad":  media.get("popularity"),
        "tipo":         _FORMATO_MAP.get(media.get("format", ""), None),
        "duracion":     media.get("duration"),
        "fecha_inicio": _parse_fecha(media.get("startDate")),
        "fecha_fin":    _parse_fecha(media.get("endDate")),
        "rating":       rating,
        "episodios":    media.get("episodes"),
    }


def _post(query: str, variables: dict) -> dict | None:
    try:
        resp = httpx.post(
            ANILIST_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data   = resp.json()
        errors = data.get("errors")
        if errors:
            print(f"[ANILIST] GraphQL errors: {errors}")
            return None
        return data.get("data", {}).get("Media")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            print("[ANILIST] Rate limit alcanzado")
        else:
            print(f"[ANILIST] HTTP {e.response.status_code}")
        return None
    except Exception as e:
        print(f"[ANILIST] Error: {e}")
        return None


def buscar_por_titulo(titulo: str) -> dict | None:
    """Busca un anime por título. Retorna dict de enriquecimiento o None."""
    media = _post(_QUERY_SEARCH, {"search": titulo})
    if not media:
        return None
    print(f"[ANILIST] Encontrado: {media.get('title', {}).get('romaji')} (id={media.get('id')})")
    return _extraer(media)


def buscar_por_id(anilist_id: int) -> dict | None:
    """Búsqueda directa por AniList ID — más precisa que por título."""
    media = _post(_QUERY_BY_ID, {"id": anilist_id})
    if not media:
        return None
    return _extraer(media)
