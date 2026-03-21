"""
providers/kitsu.py — Proveedor Kitsu.io
----------------------------------------
Fuente primaria de datos base:
  - ID canónico (kitsu_id)
  - Título, título alternativo
  - Sinopsis (en inglés)
  - Poster y cover
  - Rating, episodios, estado

Debilidades conocidas:
  - Sinopsis siempre en inglés
  - Géneros incompletos o ausentes
  - Catálogo limitado vs MAL/AniList
  - No provee: año, temporada, estudio, duración, popularidad

Por eso se usa como base y se enriquece con AniList y Jikan.
"""

import httpx

KITSU_URL = "https://kitsu.io/api/edge"
TIMEOUT   = 8


def transformar(item: dict, genero_forzado: str = "") -> dict:
    """Convierte un item de la API de Kitsu al formato interno."""
    attrs      = item.get("attributes", {})
    poster     = attrs.get("posterImage") or {}
    cover      = attrs.get("coverImage")  or {}
    rating_raw = attrs.get("averageRating")
    try:
        rating = round(float(rating_raw) / 10, 2) if rating_raw else None
    except Exception:
        rating = None

    return {
        "id":                 item["id"],
        "titulo":             attrs.get("canonicalTitle", ""),
        "titulo_alternativo": (attrs.get("titles") or {}).get("en")
                              or (attrs.get("titles") or {}).get("ja_jp"),
        "sinopsis":           attrs.get("synopsis"),
        "poster_url":         poster.get("medium") or poster.get("small"),
        "cover_url":          cover.get("large")   or cover.get("original"),
        "rating":             rating,
        "episodios":          attrs.get("episodeCount"),
        "estado":             attrs.get("status"),
        "tipo":               attrs.get("subtype"),
        "genres":             genero_forzado,
    }


def buscar(query: str, limite: int = 15) -> list[dict]:
    """Busca animes por texto. Incluye categorías para géneros."""
    try:
        resp = httpx.get(f"{KITSU_URL}/anime", params={
            "filter[text]":    query,
            "page[limit]":     limite,
            "filter[subtype]": "TV",
            "include":         "categories",
        }, timeout=TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        print(f"[KITSU] Error en búsqueda '{query}': {e}")
        return []

    genres_map = {
        inc["id"]: inc["attributes"].get("title", "")
        for inc in body.get("included", [])
        if inc.get("type") == "categories"
    }

    animes = []
    for item in body.get("data", []):
        cat_ids    = item.get("relationships", {}).get("categories", {}).get("data", [])
        genres_str = ", ".join(genres_map[c["id"]] for c in cat_ids if c["id"] in genres_map)
        animes.append(transformar(item, genero_forzado=genres_str))

    return animes


def buscar_por_id(kitsu_id: str) -> dict | None:
    """Obtiene un anime concreto por su ID de Kitsu."""
    try:
        resp = httpx.get(f"{KITSU_URL}/anime/{kitsu_id}", timeout=TIMEOUT)
        resp.raise_for_status()
        item = resp.json().get("data", {})
        return transformar(item) if item else None
    except Exception as e:
        print(f"[KITSU] Error al obtener anime {kitsu_id}: {e}")
        return None


def buscar_por_genero(genero_kitsu: str, limite: int = 20) -> list[dict]:
    """Busca animes por categoría (nombre en inglés según GENEROS_KITSU)."""
    try:
        resp = httpx.get(f"{KITSU_URL}/anime", params={
            "filter[categories]": genero_kitsu,
            "filter[subtype]":    "TV",
            "sort":               "-averageRating",
            "page[limit]":        limite,
        }, timeout=TIMEOUT)
        resp.raise_for_status()
        return [transformar(item) for item in resp.json().get("data", [])]
    except Exception as e:
        print(f"[KITSU] Error por género '{genero_kitsu}': {e}")
        return []


def buscar_en_emision(limite: int = 20) -> list[dict]:
    """Animes actualmente en emisión."""
    try:
        resp = httpx.get(f"{KITSU_URL}/anime", params={
            "filter[status]":  "current",
            "filter[subtype]": "TV",
            "sort":            "-averageRating",
            "page[limit]":     limite,
        }, timeout=TIMEOUT)
        resp.raise_for_status()
        return [transformar(item) for item in resp.json().get("data", [])]
    except Exception as e:
        print(f"[KITSU] Error en emisión: {e}")
        return []


def buscar_relacionados(kitsu_id: str) -> list[dict]:
    """
    Retorna los animes relacionados a un anime.
    Formato: [{ id, role, anime: dict }]
    """
    try:
        resp = httpx.get(
            f"{KITSU_URL}/anime/{kitsu_id}/media-relationships",
            params={"include": "destination", "page[limit]": 20},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        print(f"[KITSU] Error en relacionados de {kitsu_id}: {e}")
        return []

    included_map = {
        item["id"]: item
        for item in body.get("included", [])
        if item.get("type") == "anime"
    }

    resultado = []
    for rel in body.get("data", []):
        attrs     = rel.get("attributes", {})
        role      = attrs.get("role", "other")
        dest_ref  = rel.get("relationships", {}).get("destination", {}).get("data", {})
        dest_id   = dest_ref.get("id")
        dest_type = dest_ref.get("type", "")

        if not dest_id or dest_type != "anime":
            continue
        anime_data = included_map.get(dest_id)
        if not anime_data:
            continue

        resultado.append({
            "id":    dest_id,
            "role":  role,
            "anime": transformar(anime_data),
        })

    return resultado
