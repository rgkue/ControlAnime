"""
sync_service.py — Servicio de sincronización · ControlAnime v2
----------------------------------------------------------------
Jikan (MAL) es el proveedor principal. Kitsu eliminado del sync.

Flujo de cada sincronización:
  Fase 1 — Jikan:   Descarga 2000 animes por score (80 páginas × 25)
  Fase 2 — AniList: Añade cover_url (bannerImage) + anilist_id

Modo servicio: corre indefinidamente, sync cada 3 días a las 00:00.
Modo inmediato: python sync_service.py --now

Rate limits respetados:
  Jikan:   0.4s entre requests (integrado en jikan.py)
  AniList: 0.8s entre requests
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

# ── Path y pool ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database.connection import init_pool, close_pool
init_pool(min_conn=1, max_conn=3)

from backend.database.connection import get_db, guardar_animes_cache
from backend.services.providers import jikan, anilist
from backend.services.providers.translation import traducir_sinopsis

# ── Configuración ─────────────────────────────────────────────────────────────
SYNC_HORA      = 0
SYNC_CADA_DIAS = 3
META_ANIMES    = 2000   # objetivo local; aumentar a 5000 en producción
PAGINAS_LIMIT  = 25     # animes por página de Jikan
RL_ANILIST     = 0.8

LOG_DIR      = Path(__file__).parent / "logs"
LOG_FILE     = LOG_DIR / "sync_service.log"
MAX_LOG_BYTES = 5 * 1024 * 1024


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def _log(msg: str) -> None:
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(linea, flush=True)
    LOG_DIR.mkdir(exist_ok=True)
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size >= MAX_LOG_BYTES:
            viejo = LOG_FILE.with_suffix(".log.1")
            if viejo.exists():
                viejo.unlink()
            LOG_FILE.rename(viejo)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# FASE 1 — JIKAN: DESCARGA DEL CATÁLOGO
# ══════════════════════════════════════════════════════════════════════════════

def fase_jikan(meta: int = META_ANIMES) -> list:
    """
    Descarga animes desde Jikan paginando por score.
    Guarda en BD en lotes de 25 con marcar_jikan=True.
    Retorna la lista completa de animes descargados.
    """
    _log(f"[FASE 1] Jikan — objetivo: {meta} animes")
    paginas_necesarias = (meta + PAGINAS_LIMIT - 1) // PAGINAS_LIMIT
    total     = 0
    resultado = []

    for pagina in range(1, paginas_necesarias + 1):
        animes, hay_mas = jikan.descargar_catalogo_pagina(pagina, limit=PAGINAS_LIMIT)

        if not animes:
            _log(f"[JIKAN] Sin datos en página {pagina} — deteniendo")
            break

        guardar_animes_cache(animes, marcar_jikan=True)
        resultado.extend(animes)
        total += len(animes)

        if pagina % 10 == 0:
            _log(f"[JIKAN] Página {pagina}/{paginas_necesarias} — {total} animes guardados")

        if not hay_mas:
            _log(f"[JIKAN] MAL no tiene más páginas en página {pagina}")
            break

        if total >= meta:
            break

    _log(f"[FASE 1] Jikan completo: {total} animes descargados")
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# FASE 2 — ANILIST: COVER_URL Y ENRIQUECIMIENTO
# ══════════════════════════════════════════════════════════════════════════════

def _animes_sin_cover(limite: int = 600) -> list:
    """
    Retorna animes sin cover_url o sin anilist_id y sin enriquecimiento reciente.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, anilist_id
                FROM animes_cache
                WHERE (cover_url IS NULL OR cover_url = '')
                   OR enriquecido_anilist_en IS NULL
                   OR enriquecido_anilist_en < NOW() - INTERVAL '30 days'
                ORDER BY rating DESC NULLS LAST
                LIMIT %s
            """, (limite,))
            return cursor.fetchall()
        except Exception as e:
            _log(f"[ANILIST] Error leyendo pendientes: {e}")
            return []
        finally:
            cursor.close()


def _guardar_cover(anime_id: str, datos: dict) -> None:
    """Guarda cover_url, anilist_id y timestamp en animes_cache."""
    campos_validos = {
        k: v for k, v in datos.items()
        if k in ("cover_url", "anilist_id", "anio", "temporada", "estudio",
                 "duracion", "tipo", "fecha_inicio", "fecha_fin")
        and v is not None
    }
    if not campos_validos:
        return

    set_parts = ["enriquecido_anilist_en = NOW()"]
    valores   = []
    for k, v in campos_validos.items():
        set_parts.append(f"{k} = %s")
        valores.append(v)
    valores.append(anime_id)

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE animes_cache SET {', '.join(set_parts)} WHERE id = %s",
                valores,
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            _log(f"[ANILIST] Error al guardar cover para {anime_id}: {e}")
        finally:
            cursor.close()


def fase_anilist(limite: int = 600) -> None:
    """
    Enriquece animes sin cover_url usando AniList.
    Aporta bannerImage como cover_url + anilist_id + datos complementarios.
    """
    pendientes = _animes_sin_cover(limite)
    _log(f"[FASE 2] AniList — {len(pendientes)} animes a enriquecer")

    ok = 0
    for idx, (anime_id, titulo, anilist_id_db) in enumerate(pendientes, 1):
        time.sleep(RL_ANILIST)
        try:
            datos = (
                anilist.buscar_por_id(anilist_id_db)
                if anilist_id_db
                else anilist.buscar_por_titulo(titulo)
            )
            if datos:
                _guardar_cover(str(anime_id), datos)
                ok += 1
        except Exception as e:
            _log(f"[ANILIST] Error en '{titulo}': {e}")

        if idx % 50 == 0:
            _log(f"[ANILIST] Progreso: {idx}/{len(pendientes)} ({ok} con cover)")

    _log(f"[FASE 2] AniList completo: {ok}/{len(pendientes)} con cover_url")


# ══════════════════════════════════════════════════════════════════════════════
# SINCRONIZACIÓN COMPLETA
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# FASE 3 — TRADUCCIÓN DE SINOPSIS
# ══════════════════════════════════════════════════════════════════════════════

def _animes_sin_sinopsis_es(limite: int = 500) -> list:
    """Animes con sinopsis en inglés pero sin traducción al español."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, sinopsis
                FROM animes_cache
                WHERE sinopsis IS NOT NULL
                  AND sinopsis != ''
                  AND (sinopsis_es IS NULL OR sinopsis_es = '')
                ORDER BY rating DESC NULLS LAST
                LIMIT %s
            """, (limite,))
            return cursor.fetchall()
        except Exception as e:
            _log(f"[SINOPSIS] Error leyendo pendientes: {e}")
            return []
        finally:
            cursor.close()


def _guardar_sinopsis_es(anime_id: str, sinopsis_es: str) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE animes_cache SET sinopsis_es = %s WHERE id = %s",
                (sinopsis_es, anime_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            _log(f"[SINOPSIS] Error guardando para {anime_id}: {e}")
        finally:
            cursor.close()


def fase_sinopsis(limite: int = 500) -> None:
    """
    Traduce sinopsis del inglés al español en batch.
    Google Translate primero, MyMemory como fallback.
    Pausa 0.3s entre traducciones para no saturar las APIs.
    """
    pendientes = _animes_sin_sinopsis_es(limite)
    _log(f"[FASE 3] Sinopsis — {len(pendientes)} animes a traducir")

    ok = 0
    for idx, (anime_id, titulo, sinopsis) in enumerate(pendientes, 1):
        time.sleep(0.3)
        try:
            trad = traducir_sinopsis(sinopsis)
            if trad:
                _guardar_sinopsis_es(str(anime_id), trad)
                ok += 1
        except Exception as e:
            _log(f"[SINOPSIS] Error en '{titulo}': {e}")

        if idx % 100 == 0:
            _log(f"[SINOPSIS] Progreso: {idx}/{len(pendientes)} ({ok} traducidas)")

    _log(f"[FASE 3] Sinopsis completo: {ok}/{len(pendientes)} traducidas")


# ══════════════════════════════════════════════════════════════════════════════
# FASE 4 — TRADUCCIÓN RETROACTIVA DE GÉNEROS
# ══════════════════════════════════════════════════════════════════════════════

def _animes_sin_genres_es(limite: int = 2000) -> list:
    """Retorna animes con genres en inglés pero sin genres_es."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, genres
                FROM animes_cache
                WHERE genres IS NOT NULL
                  AND genres != ''
                  AND (genres_es IS NULL OR genres_es = '')
                ORDER BY rating DESC NULLS LAST
                LIMIT %s
            """, (limite,))
            return cursor.fetchall()
        except Exception as e:
            _log(f"[GENRES_ES] Error leyendo pendientes: {e}")
            return []
        finally:
            cursor.close()


def _guardar_genres_es(anime_id: str, genres_es: str) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE animes_cache SET genres_es = %s WHERE id = %s",
                (genres_es, anime_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            _log(f"[GENRES_ES] Error guardando para {anime_id}: {e}")
        finally:
            cursor.close()


def fase_genres_es(limite: int = 2000) -> None:
    """
    Traduce genres_es retroactivamente para animes que ya estan en BD
    pero no tienen la traduccion al espanol.
    Usa el mapa estatico de translation.py — instantaneo, sin costo de API
    en el 95% de casos.
    """
    from backend.services.providers.translation import traducir_genres
    pendientes = _animes_sin_genres_es(limite)
    _log(f"[FASE 4] Genres ES — {len(pendientes)} animes sin traduccion")
    if not pendientes:
        _log("[FASE 4] Todo esta al dia.")
        return

    ok = 0
    for anime_id, genres in pendientes:
        try:
            genres_es = traducir_genres(genres)
            if genres_es:
                _guardar_genres_es(str(anime_id), genres_es)
                ok += 1
        except Exception as e:
            _log(f"[GENRES_ES] Error en {anime_id}: {e}")

    _log(f"[FASE 4] Genres ES completo: {ok}/{len(pendientes)} traducidos")

def sincronizar_todo() -> None:
    inicio = time.time()
    _log("=" * 60)
    _log(f"SINCRONIZACIÓN COMPLETA INICIADA (objetivo: {META_ANIMES} animes)")
    _log("=" * 60)

    fase_jikan(meta=META_ANIMES)
    fase_anilist(limite=600)
    fase_sinopsis(limite=500)
    fase_genres_es(limite=2000)

    duracion = int(time.time() - inicio)
    mins, segs = divmod(duracion, 60)
    _log("=" * 60)
    _log(f"SINCRONIZACIÓN COMPLETA FINALIZADA — {mins}m {segs}s")
    _log("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════

def _proxima_ejecucion() -> datetime:
    ahora  = datetime.now()
    hoy_00 = ahora.replace(hour=SYNC_HORA, minute=0, second=0, microsecond=0)
    return hoy_00 if ahora < hoy_00 else hoy_00 + timedelta(days=SYNC_CADA_DIAS)


def _esperar_hasta(objetivo: datetime) -> None:
    while True:
        restante = (objetivo - datetime.now()).total_seconds()
        if restante <= 0:
            return
        if restante > 3600:
            _log(f"[SCHEDULER] Próxima sync: {objetivo:%Y-%m-%d %H:%M} (en ~{int(restante//3600)}h)")
            time.sleep(3600)
        elif restante > 60:
            time.sleep(60)
        else:
            time.sleep(restante)
            return


def servicio() -> None:
    _log("ControlAnime Sync Service v2 iniciado (Jikan primario)")
    _log(f"Configuración: cada {SYNC_CADA_DIAS} días a las {SYNC_HORA:02d}:00 — meta {META_ANIMES} animes")

    while True:
        proxima = _proxima_ejecucion()
        _esperar_hasta(proxima)
        try:
            sincronizar_todo()
        except Exception as e:
            _log(f"[ERROR] Sync falló: {e}")
            _log("[SCHEDULER] Reintentando en 1 hora")
            time.sleep(3600)
        time.sleep(3600)  # evitar re-ejecución el mismo día


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        if "--now" in sys.argv:
            _log("Modo --now: sincronización inmediata")
            sincronizar_todo()
        else:
            servicio()
    finally:
        close_pool()
