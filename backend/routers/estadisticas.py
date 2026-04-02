"""
estadisticas.py — Endpoints de estadísticas personales
-------------------------------------------------------
Requiere sesión válida via AuthMiddleware.
Toda la lógica SQL está en backend/database/estadisticas_queries.py.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.database.estadisticas_queries import (
    get_resumen,
    get_actividad_mensual,
    get_generos,
    get_ultimos_agregados,
    get_score_promedio,
)

router = APIRouter()


def _uid(request: Request) -> int:
    return request.state.usuario_id


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN GENERAL
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/estadisticas/resumen")
def obtener_resumen(request: Request):
    data = get_resumen(_uid(request))
    if data is None:
        return JSONResponse(status_code=500, content={"error": "Error interno"})
    return JSONResponse(status_code=200, content=data)


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL DE ACTIVIDAD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/estadisticas/actividad")
def obtener_actividad(request: Request):
    data = get_actividad_mensual(_uid(request))
    return JSONResponse(status_code=200, content={"actividad": data})


# ══════════════════════════════════════════════════════════════════════════════
# GÉNEROS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/estadisticas/generos")
def obtener_generos(request: Request):
    data = get_generos(_uid(request))
    return JSONResponse(status_code=200, content={"generos": data})


# ══════════════════════════════════════════════════════════════════════════════
# ÚLTIMOS AGREGADOS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/estadisticas/ultimos")
def obtener_ultimos(request: Request):
    data = get_ultimos_agregados(_uid(request))
    return JSONResponse(status_code=200, content={"ultimos": data})


# ══════════════════════════════════════════════════════════════════════════════
# SCORE PROMEDIO
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/estadisticas/score")
def obtener_score(request: Request):
    data = get_score_promedio(_uid(request))
    return JSONResponse(status_code=200, content=data)


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT AGREGADO (todo en una sola llamada)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/estadisticas/data")
def obtener_todo(request: Request):
    """Devuelve todo en una sola llamada para reducir round-trips del frontend."""
    uid = _uid(request)
    resumen   = get_resumen(uid)
    actividad = get_actividad_mensual(uid)
    generos   = get_generos(uid)
    ultimos   = get_ultimos_agregados(uid)
    score     = get_score_promedio(uid)

    if resumen is None:
        return JSONResponse(status_code=500, content={"error": "Error interno"})

    return JSONResponse(status_code=200, content={
        "resumen":   resumen,
        "actividad": actividad,
        "generos":   generos,
        "ultimos":   ultimos,
        "score":     score.get("promedio"),
    })
