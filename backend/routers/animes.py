"""
animes.py — Endpoints de búsqueda y datos de animes
------------------------------------------------------
v2: Jikan como proveedor principal. Kitsu eliminado.
    Traducción eliminada del router — se maneja en sync_service (Fase 3).
    Endpoint /animes/{id}/traducir eliminado.
    El frontend recibe sinopsis_es y genres_es ya traducidos desde la BD.
"""

import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.services.providers.translation import traducir_sinopsis
from backend.database.connection import guardar_sinopsis_es

from backend.database.anime_queries import (
    get_top_animes,
    get_emision,
    get_por_genero,
    get_por_tipo,
    get_por_temporada,
    get_temporadas_disponibles,
    get_hero,
    get_collage,
)
from backend.services.anime_service import (
    buscar_animes,
    obtener_anime_por_id,
    obtener_relacionados,
)

router = APIRouter()

# ── Cache en memoria para el collage ─────────────────────────────────────────
_collage_cache: list = []
_collage_ts:    float = 0.0
_COLLAGE_TTL:   int   = 600  # 10 minutos


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/animes/buscar")
def buscar(request: Request, q: str = ""):
    if not q or len(q.strip()) < 2:
        return JSONResponse(status_code=400, content={"error": "Escribe al menos 2 caracteres"})
    return JSONResponse(status_code=200, content={"resultados": buscar_animes(q.strip())})


@router.get("/animes/top")
def top(request: Request, offset: int = 0, limit: int = 28):
    limit = min(limit, 50)
    return JSONResponse(status_code=200, content={
        "resultados": get_top_animes(offset=offset, limit=limit),
        "offset":     offset,
        "limit":      limit,
    })


@router.get("/animes/emision")
def emision(request: Request, offset: int = 0, limit: int = 28):
    limit = min(limit, 50)
    return JSONResponse(status_code=200, content={
        "resultados": get_emision(offset=offset, limit=limit),
        "offset":     offset,
        "limit":      limit,
    })


@router.get("/animes/genero")
def genero(request: Request, g: str = "", offset: int = 0, limit: int = 28):
    """
    Filtra por género en inglés (MAL): 'Action', 'Romance', 'Fantasy', etc.
    La BD almacena genres en inglés y usa ILIKE para coincidencia parcial.
    El frontend muestra genres_es (ya traducido) al usuario.
    """
    if not g:
        return JSONResponse(status_code=400, content={"error": "Falta parámetro g"})
    limit = min(limit, 50)
    return JSONResponse(status_code=200, content={
        "resultados": get_por_genero(genero=g, offset=offset, limit=limit),
        "offset":     offset,
        "limit":      limit,
    })


@router.get("/animes/hero")
def hero(request: Request):
    """
    Público — 6 animes para el carrusel de la landing page.
    sinopsis_es y genres_es ya vienen traducidos desde la BD.
    """
    animes = get_hero()
    if not animes:
        return JSONResponse(status_code=500, content={"error": "Error interno"})
    return JSONResponse(status_code=200, content={"animes": animes})


@router.get("/animes/collage")
def collage(request: Request):
    """
    Público — 20 posters para el fondo de login/register/landing.
    Cache en memoria renovado cada 10 minutos.
    """
    global _collage_cache, _collage_ts
    ahora = time.time()
    if not _collage_cache or (ahora - _collage_ts) > _COLLAGE_TTL:
        _collage_cache = get_collage()
        _collage_ts    = ahora
        print("[COLLAGE] Cache renovado")
    return JSONResponse(status_code=200, content={"animes": _collage_cache})



@router.get("/animes/tipo")
def por_tipo(request: Request, t: str = "", offset: int = 0, limit: int = 28):
    """Filtra por tipo: TV | Movie | OVA | ONA | Special"""
    TIPOS = {"TV", "Movie", "OVA", "ONA", "Special"}
    if t not in TIPOS:
        return JSONResponse(status_code=400, content={"error": f"Tipo invalido. Usa: {', '.join(TIPOS)}"})
    limit = min(limit, 50)
    return JSONResponse(status_code=200, content={
        "resultados": get_por_tipo(tipo=t, offset=offset, limit=limit),
        "offset": offset, "limit": limit,
    })


@router.get("/animes/temporada")
def por_temporada(request: Request, t: str = "", anio: int = 0, offset: int = 0, limit: int = 28):
    """Filtra por temporada: winter | spring | summer | fall. anio es opcional."""
    TEMPORADAS = {"winter", "spring", "summer", "fall"}
    if t not in TEMPORADAS:
        return JSONResponse(status_code=400, content={"error": "Temporada invalida"})
    limit = min(limit, 50)
    return JSONResponse(status_code=200, content={
        "resultados": get_por_temporada(temporada=t, anio=anio or None, offset=offset, limit=limit),
        "offset": offset, "limit": limit,
    })


@router.get("/animes/temporadas")
def temporadas_disponibles(request: Request):
    """Lista de temporadas con animes disponibles en la BD."""
    return JSONResponse(status_code=200, content={"temporadas": get_temporadas_disponibles()})


@router.get("/animes/{anime_id}/relacionados")
def relacionados(request: Request, anime_id: str):
    if not anime_id or len(anime_id) > 20:
        return JSONResponse(status_code=400, content={"error": "ID inválido"})
    items = obtener_relacionados(anime_id)
    return JSONResponse(status_code=200, content={"relacionados": items})


@router.get("/animes/{anime_id}")
def detalle(request: Request, anime_id: str):
    if not anime_id or len(anime_id) > 20:
        return JSONResponse(status_code=400, content={"error": "ID inválido"})
    anime = obtener_anime_por_id(anime_id)
    if not anime:
        return JSONResponse(status_code=404, content={"error": "Anime no encontrado"})

    # Si no tiene sinopsis_es, traducir síncronamente y persistir antes de responder.
    # El frontend ya no llama /traducir — recibe la traducción directamente aquí.
    if not anime.get("sinopsis_es") and anime.get("sinopsis"):
        trad = traducir_sinopsis(anime["sinopsis"])
        if trad:
            guardar_sinopsis_es(anime_id, trad)
            anime["sinopsis_es"] = trad

    return JSONResponse(status_code=200, content=anime)
