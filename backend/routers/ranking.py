"""
ranking.py — Endpoints de ranking, top5 personal y perfiles
-------------------------------------------------------------
Fase 5: Todos los endpoints (excepto /ranking y /perfil/:id)
requieren sesión válida via AuthMiddleware.

Refactor: toda la lógica SQL migrada a backend/database/ranking_queries.py.
El router solo coordina: valida input → llama query → devuelve JSONResponse.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database.ranking_queries import (
    get_ranking,
    get_mi_top5,
    guardar_top5,
    eliminar_top5_pos,
    get_header_perfil,
    actualizar_header_perfil,
    get_perfil_publico,
)

router = APIRouter()


def _uid(request: Request) -> int:
    return request.state.usuario_id


# ══════════════════════════════════════════════════════════════════════════════
# RANKING GLOBAL (público)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/ranking/data")
def obtener_ranking():
    """Top 50 usuarios con más animes vistos. Perfiles privados aparecen anonimizados."""
    ranking = get_ranking()
    return JSONResponse(status_code=200, content={"ranking": ranking})


# ══════════════════════════════════════════════════════════════════════════════
# TOP 5 PERSONAL
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/mi-top5")
def obtener_mi_top5(request: Request):
    top5 = get_mi_top5(_uid(request))
    return JSONResponse(status_code=200, content={"top5": top5})


@router.post("/mi-top5/guardar")
def guardar_mi_top5(request: Request, datos: dict):
    posicion = datos.get("posicion")
    anime_id = datos.get("anime_id")

    if not isinstance(posicion, int) or posicion not in range(1, 6):
        return JSONResponse(status_code=400, content={"error": "Posición inválida (1–5)"})
    if not anime_id:
        return JSONResponse(status_code=400, content={"error": "Falta anime_id"})

    resultado = guardar_top5(_uid(request), str(anime_id), posicion)

    if resultado == "no_en_lista":
        return JSONResponse(status_code=400, content={"error": "El anime debe existir en tu lista"})
    if resultado == "error":
        return JSONResponse(status_code=500, content={"error": "Error interno"})

    return JSONResponse(status_code=200, content={"mensaje": "Top actualizado"})


@router.post("/mi-top5/eliminar")
def eliminar_mi_top5(request: Request, datos: dict):
    posicion = datos.get("posicion")

    if not isinstance(posicion, int) or posicion not in range(1, 6):
        return JSONResponse(status_code=400, content={"error": "Posición inválida (1–5)"})

    ok = eliminar_top5_pos(_uid(request), posicion)
    if not ok:
        return JSONResponse(status_code=500, content={"error": "Error interno"})

    return JSONResponse(status_code=200, content={"mensaje": "Eliminado"})


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL — HEADER
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/mi-perfil/header")
def obtener_mi_header(request: Request):
    data = get_header_perfil(_uid(request))
    if data is None:
        return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
    return JSONResponse(status_code=200, content=data)


@router.post("/perfil/header")
def actualizar_header(request: Request, datos: dict):
    resultado = actualizar_header_perfil(_uid(request), datos)

    if resultado == "imagen_grande":
        return JSONResponse(status_code=400, content={"error": "Imagen demasiado grande (máx 3MB)"})
    if resultado == "color_invalido":
        return JSONResponse(status_code=400, content={"error": "Color inválido"})
    if resultado == "datos_invalidos":
        return JSONResponse(status_code=400, content={"error": "Datos inválidos"})
    if resultado == "error":
        return JSONResponse(status_code=500, content={"error": "Error interno"})

    return JSONResponse(status_code=200, content={"mensaje": "Header actualizado"})


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/perfil/{usuario_id}")
def ver_perfil(usuario_id: int, request: Request):
    """Perfil público de un usuario: vistos + top5 + stats + redes sociales."""
    data = get_perfil_publico(usuario_id)

    if data is None:
        return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
    if data.get("privado"):
        return JSONResponse(status_code=403, content={"error": "Perfil privado"})

    return JSONResponse(status_code=200, content=data)
