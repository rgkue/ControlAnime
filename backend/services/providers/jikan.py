"""
providers/jikan.py — Jikan v4 (MyAnimeList) · Proveedor PRINCIPAL
------------------------------------------------------------------
Jikan es ahora el proveedor base del catálogo de ControlAnime.

Provee directamente:
  - id (str(mal_id)) — ID canónico del sistema
  - titulo, titulo_alternativo, sinopsis
  - poster_url (images.jpg.large_image_url)
  - rating, score_count, popularidad
  - episodios, estado, tipo, duracion
  - genres (detallados de MAL)
  - estudio, anio, temporada, fecha_inicio, fecha_fin
  - mal_id (INTEGER)

NO provee:
  - cover_url (banner) → lo añade AniList

Rate limit: 3 req/seg. Usamos 0.4s de pausa mínima entre llamadas.
"""

import re
import time
import httpx

JIKAN_URL     = "https://api.jikan.moe/v4"
TIMEOUT       = 12
_MIN_INTERVAL = 0.4

_last_call: float = 0.0


# ── Throttle ──────────────────────────────────────────────────────────────────

def _throttle() -> None:
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call = time.time()


def _get(path: str, params: dict | None = None) -> dict | None:
    _throttle()
    try:
        resp = httpx.get(f"{JIKAN_URL}{path}", params=params, timeout=TIMEOUT)
        if resp.status_code == 429:
            print("[JIKAN] Rate limit — esperando 2s")
            time.sleep(2)
            resp = httpx.get(f"{JIKAN_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        print(f"[JIKAN] HTTP {e.response.status_code} en {path}")
        return None
    except Exception as e:
        print(f"[JIKAN] Error en {path}: {e}")
        return None


# ── Mapeos ────────────────────────────────────────────────────────────────────

_STATUS_MAP = {
    "Finished Airing":  "finished",
    "Currently Airing": "current",
    "Not yet aired":    "upcoming",
}

_TIPO_MAP = {
    "TV":      "TV",
    "Movie":   "Movie",
    "OVA":     "OVA",
    "ONA":     "ONA",
    "Special": "Special",
    "Music":   "Special",
    "Unknown": None,
}

_RELACION_MAP = {
    "Sequel":              "sequel",
    "Prequel":             "prequel",
    "Side story":          "side_story",
    "Parent story":        "parent_story",
    "Alternative version": "alternative_version",
    "Alternative setting": "alternative_setting",
    "Spin-off":            "spin_off",
    "Adaptation":          "adaptation",
    "Summary":             "summary",
    "Full story":          "full_story",
    "Character":           "character",
    "Other":               "other",
}


# ── Transformación ────────────────────────────────────────────────────────────

def _parsear_duracion(raw: str) -> int | None:
    if not raw:
        return None
    raw = raw.lower()
    try:
        if "hr" in raw:
            hrs  = re.search(r"(\d+)\s*hr",  raw)
            mins = re.search(r"(\d+)\s*min", raw)
            total = (int(hrs.group(1)) * 60 if hrs else 0) + (int(mins.group(1)) if mins else 0)
            return total or None
        if "min" in raw:
            nums = re.findall(r"\d+", raw)
            return int(nums[0]) if nums else None
    except Exception:
        pass
    return None


def _titulo_alternativo(anime: dict) -> str | None:
    for tipo in ("English", "Japanese"):
        for t in (anime.get("titles") or []):
            if t.get("type") == tipo and t.get("title"):
                return t["title"]
    return None


def extraer(anime: dict) -> dict:
    """
    Convierte un objeto anime de Jikan al formato interno completo.
    Función pública — usada por anime_service y sync_service.
    """
    mal_id = anime.get("mal_id")
    if not mal_id:
        return {}

    images = anime.get("images", {})
    poster = (images.get("jpg")  or {}).get("large_image_url") or \
             (images.get("webp") or {}).get("large_image_url")

    genres_raw = (
        anime.get("genres",       []) +
        anime.get("themes",       []) +
        anime.get("demographics", [])
    )
    genres_str = ", ".join(g["name"] for g in genres_raw if g.get("name")) or None

    # Traducir géneros al español usando mapa estático — sin costo de API
    from backend.services.providers.translation import traducir_genres
    genres_es = traducir_genres(genres_str)

    studios = anime.get("studios", [])
    estudio = studios[0]["name"] if studios else None

    aired        = anime.get("aired", {})
    fecha_inicio = (aired.get("from") or "")[:10] or None
    fecha_fin    = (aired.get("to")   or "")[:10] or None

    score  = anime.get("score")
    rating = round(float(score), 2) if score else None

    return {
        "id":                 str(mal_id),
        "mal_id":             mal_id,
        "titulo":             anime.get("title", ""),
        "titulo_alternativo": _titulo_alternativo(anime),
        "sinopsis":           anime.get("synopsis"),
        "poster_url":         poster,
        "cover_url":          None,   # AniList lo provee
        "rating":             rating,
        "score_count":        anime.get("scored_by"),
        "popularidad":        anime.get("popularity"),
        "episodios":          anime.get("episodes"),
        "estado":             _STATUS_MAP.get(anime.get("status", ""), None),
        "tipo":               _TIPO_MAP.get(anime.get("type", ""), None),
        "duracion":           _parsear_duracion(anime.get("duration", "")),
        "genres":             genres_str,
        "genres_es":          genres_es,
        "anio":               anime.get("year"),
        "temporada":          anime.get("season"),  # ya en minúsculas
        "fecha_inicio":       fecha_inicio,
        "fecha_fin":          fecha_fin,
        "estudio":            estudio,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATÁLOGO (sync principal)
# ══════════════════════════════════════════════════════════════════════════════

def descargar_catalogo_pagina(pagina: int, limit: int = 25) -> tuple[list[dict], bool]:
    """
    Descarga una página del catálogo MAL por score descendente.
    pagina: comienza en 1.
    Retorna (animes, hay_mas_paginas).
    """
    data = _get("/anime", params={
        "order_by": "score",
        "sort":     "desc",
        "limit":    limit,
        "page":     pagina,
        "type":     "tv",
        "sfw":      "true",
    })
    if not data:
        return [], False

    hay_mas = data.get("pagination", {}).get("has_next_page", False)
    animes  = [extraer(item) for item in data.get("data", []) if item.get("mal_id")]
    return animes, hay_mas


# ══════════════════════════════════════════════════════════════════════════════
# BÚSQUEDA
# ══════════════════════════════════════════════════════════════════════════════

def buscar(query: str, limite: int = 15) -> list[dict]:
    data = _get("/anime", params={
        "q":     query,
        "limit": limite,
        "sfw":   "true",
    })
    if not data:
        return []
    return [extraer(item) for item in data.get("data", []) if item.get("mal_id")]


def buscar_por_id(mal_id: int) -> dict | None:
    data = _get(f"/anime/{mal_id}")
    if not data:
        return None
    anime = data.get("data", {})
    return extraer(anime) if anime.get("mal_id") else None


def buscar_por_titulo(titulo: str) -> dict | None:
    resultados = buscar(titulo, limite=1)
    return resultados[0] if resultados else None


# ══════════════════════════════════════════════════════════════════════════════
# RELACIONADOS
# ══════════════════════════════════════════════════════════════════════════════

def buscar_relacionados(mal_id: int) -> list[dict]:
    """
    Retorna lista de { id, role, titulo, mal_id_rel }.
    Solo incluye entradas de tipo 'anime'.
    """
    data = _get(f"/anime/{mal_id}/relations")
    if not data:
        return []

    resultado = []
    for grupo in data.get("data", []):
        relacion = grupo.get("relation", "Other")
        role     = _RELACION_MAP.get(relacion, "other")
        for entry in grupo.get("entry", []):
            if entry.get("type") != "anime":
                continue
            rel_mal_id = entry.get("mal_id")
            if not rel_mal_id:
                continue
            resultado.append({
                "id":         str(rel_mal_id),
                "role":       role,
                "titulo":     entry.get("name", "Sin título"),
                "mal_id_rel": rel_mal_id,
            })
    return resultado
