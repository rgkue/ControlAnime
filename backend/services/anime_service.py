"""
anime_service.py — Lógica de negocio de animes (Jikan primario + AniList enriquece)
-------------------------------------------------------------------------------------
v2: Jikan como proveedor principal. Kitsu eliminado completamente.

Flujo:
  1. BD (animes_cache) — respuesta inmediata si existe
  2. Jikan — si no está en caché, descarga datos completos
  3. Enricher (background) — AniList añade cover_url y anilist_id
"""

import threading
from backend.database.connection import get_db, buscar_anime_cache, guardar_animes_cache, guardar_sinopsis_es
from backend.services.providers import jikan

# ── Claves de columnas ────────────────────────────────────────────────────────
_KEYS_BASE = [
    "id","titulo","titulo_alternativo","sinopsis","poster_url",
    "cover_url","rating","episodios","estado","genres","sinopsis_es",
]

_KEYS_FULL = _KEYS_BASE + [
    "anio","temporada","estudio","score_count","popularidad",
    "tipo","duracion","fecha_inicio","fecha_fin",
]


def _to_list(rows: list, keys: list) -> list:
    result = []
    for row in rows:
        d = dict(zip(keys, row))
        if d.get("rating"):
            d["rating"] = float(d["rating"])
        if d.get("fecha_inicio"):
            d["fecha_inicio"] = str(d["fecha_inicio"])
        if d.get("fecha_fin"):
            d["fecha_fin"] = str(d["fecha_fin"])
        result.append(d)
    return result


def _enriquecer_bg(anime_id: str, titulo: str) -> None:
    """Lanza enriquecimiento AniList en un thread daemon."""
    try:
        from backend.services.providers.enricher import enriquecer_en_background
        threading.Thread(
            target=enriquecer_en_background,
            args=(anime_id, titulo),
            daemon=True,
        ).start()
    except Exception as e:
        print(f"[SERVICE] Error al lanzar enricher para {anime_id}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# BÚSQUEDA
# ══════════════════════════════════════════════════════════════════════════════

def buscar_animes(query: str) -> list:
    """Busca por texto. BD primero, Jikan si no hay caché."""
    cache = buscar_anime_cache(query)
    if cache:
        print(f"[CACHE] '{query}' → {len(cache)} desde BD")
        for anime in cache:
            if not anime.get("cover_url"):
                _enriquecer_bg(anime["id"], anime["titulo"])
        return cache

    print(f"[JIKAN] '{query}' → buscando en MAL")
    animes = jikan.buscar(query)
    if animes:
        guardar_animes_cache(animes, marcar_jikan=True)
        for anime in animes:
            _enriquecer_bg(anime["id"], anime["titulo"])
    return animes


# ══════════════════════════════════════════════════════════════════════════════
# POR ID
# ══════════════════════════════════════════════════════════════════════════════

def obtener_anime_por_id(anime_id: str) -> dict | None:
    """
    anime_id es str(mal_id) en el nuevo esquema.
    BD primero (incluye todos los campos enriquecidos), luego Jikan.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres, sinopsis_es,
                       anio, temporada, estudio, score_count, popularidad,
                       tipo, duracion, fecha_inicio, fecha_fin
                FROM animes_cache WHERE id = %s
            """, (anime_id,))
            row = cursor.fetchone()
            if row:
                d = _to_list([row], _KEYS_FULL)[0]
                if not d.get("cover_url"):
                    _enriquecer_bg(anime_id, d["titulo"])
                return d
        except Exception as e:
            print(f"[DB ERROR obtener_anime_por_id] {e}")
        finally:
            cursor.close()

    # Fallback: Jikan directo por MAL ID
    print(f"[JIKAN] anime {anime_id} no en caché → descargando")
    try:
        anime = jikan.buscar_por_id(int(anime_id))
    except (ValueError, TypeError):
        return None

    if anime:
        guardar_animes_cache([anime], marcar_jikan=True)
        _enriquecer_bg(anime_id, anime["titulo"])
    return anime


# ══════════════════════════════════════════════════════════════════════════════
# LISTADOS (para routers que paginan desde BD)
# ══════════════════════════════════════════════════════════════════════════════

def obtener_mejor_valorados(limite: int = 20) -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres, sinopsis_es
                FROM animes_cache
                WHERE rating IS NOT NULL AND cached_en > NOW() - INTERVAL '7 days'
                ORDER BY rating DESC LIMIT %s
            """, (limite,))
            rows = cursor.fetchall()
            if len(rows) >= limite:
                print(f"[CACHE] mejor valorados → {len(rows)} desde BD")
                return _to_list(rows, _KEYS_BASE)
        except Exception as e:
            print(f"[DB ERROR obtener_mejor_valorados] {e}")
            return []
        finally:
            cursor.close()

    # Sin caché suficiente → Jikan top page 1
    print("[JIKAN] mejor valorados → página 1")
    animes, _ = jikan.descargar_catalogo_pagina(1, limit=limite)
    if animes:
        guardar_animes_cache(animes, marcar_jikan=True)
    return animes


# ══════════════════════════════════════════════════════════════════════════════
# RELACIONADOS
# ══════════════════════════════════════════════════════════════════════════════

RELACION_LABEL = {
    "sequel":              "Secuela",
    "prequel":             "Precuela",
    "side_story":          "Historia paralela",
    "parent_story":        "Historia principal",
    "full_story":          "Historia completa",
    "spin_off":            "Spin-off",
    "adaptation":          "Adaptación",
    "alternative_setting": "Entorno alternativo",
    "alternative_version": "Versión alternativa",
    "summary":             "Resumen",
    "character":           "Personaje",
    "other":               "Relacionado",
}


def obtener_relacionados(anime_id: str) -> list:
    """
    anime_id = str(mal_id). Consulta BD primero, luego Jikan relations.
    """
    # 1 — BD
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT ar.rel_id, ar.rel_tipo,
                       ac.titulo, ac.poster_url, ac.rating, ac.estado
                FROM anime_relacionados ar
                LEFT JOIN animes_cache ac ON ac.id = ar.rel_id
                WHERE ar.anime_id = %s
                ORDER BY ar.rel_tipo, ar.rel_id
            """, (anime_id,))
            rows = cursor.fetchall()
            if rows:
                print(f"[CACHE] relacionados de {anime_id} → {len(rows)} desde BD")
                return [
                    {
                        "id":         r[0],
                        "rel_tipo":   r[1],
                        "rel_label":  RELACION_LABEL.get(r[1], "Relacionado"),
                        "titulo":     r[2] or "Sin título",
                        "poster_url": r[3] or "",
                        "rating":     float(r[4]) if r[4] else None,
                        "estado":     r[5] or "",
                    }
                    for r in rows
                ]
        except Exception as e:
            print(f"[DB ERROR relacionados cache] {e}")
        finally:
            cursor.close()

    # 2 — Jikan relations
    print(f"[JIKAN] relacionados de {anime_id} → consultando API")
    try:
        mal_id = int(anime_id)
    except (ValueError, TypeError):
        return []

    rels = jikan.buscar_relacionados(mal_id)
    if not rels:
        return []

    animes_a_cachear = []
    resultado        = []

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            for rel in rels:
                # Intentar obtener datos del anime relacionado de BD o Jikan
                rel_id  = rel["id"]
                rel_mal = rel["mal_id_rel"]

                with get_db() as conn2:
                    cur2 = conn2.cursor()
                    try:
                        cur2.execute(
                            "SELECT titulo, poster_url, rating, estado FROM animes_cache WHERE id = %s",
                            (rel_id,)
                        )
                        row = cur2.fetchone()
                    finally:
                        cur2.close()

                if row:
                    titulo, poster, rating, estado = row
                else:
                    # Descargar el relacionado de Jikan en background
                    titulo, poster, rating, estado = rel["titulo"], "", None, ""

                try:
                    cursor.execute("""
                        INSERT INTO anime_relacionados (anime_id, rel_id, rel_tipo)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (anime_id, rel_id) DO UPDATE SET rel_tipo = EXCLUDED.rel_tipo
                    """, (anime_id, rel_id, rel["role"]))
                except Exception as ex:
                    print(f"[DB] Error insert relacionado: {ex}")

                resultado.append({
                    "id":         rel_id,
                    "rel_tipo":   rel["role"],
                    "rel_label":  RELACION_LABEL.get(rel["role"], "Relacionado"),
                    "titulo":     titulo,
                    "poster_url": poster or "",
                    "rating":     float(rating) if rating else None,
                    "estado":     estado or "",
                })

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR relacionados commit] {e}")
        finally:
            cursor.close()

    print(f"[JIKAN] {len(resultado)} relacionados guardados para {anime_id}")
    return resultado
