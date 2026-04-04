"""
importar_queries.py — Queries para importar listas de anime
------------------------------------------------------------
Lógica de búsqueda/matching en animes_cache y escritura en lista_animes.
Retorna tipos Python puros. Nunca JSONResponse.
"""

import re
from backend.database.connection import get_db


# ══════════════════════════════════════════════════════════════════════════════
# MATCHING DE TÍTULOS
# ══════════════════════════════════════════════════════════════════════════════

def _normalizar(titulo: str) -> str:
    """Normaliza un título para comparación fuzzy: minúsculas, sin puntuación extra."""
    t = titulo.lower().strip()
    t = re.sub(r"[:\-–—!?.,'\"]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def buscar_anime_por_titulo(titulo: str) -> dict | None:
    """
    Busca un anime en animes_cache por título exacto primero,
    luego por coincidencia normalizada.
    Retorna { id, titulo, poster_url, rating } o None.
    """
    if not titulo or not titulo.strip():
        return None

    titulo_norm = _normalizar(titulo)

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # 1. Exacto (case-insensitive) en titulo y titulo_alternativo
            cursor.execute(
                """
                SELECT id, titulo, poster_url, rating
                FROM animes_cache
                WHERE LOWER(TRIM(titulo)) = LOWER(TRIM(%s))
                   OR LOWER(TRIM(titulo_alternativo)) = LOWER(TRIM(%s))
                LIMIT 1
                """,
                (titulo, titulo),
            )
            row = cursor.fetchone()
            if row:
                return _row_to_match(row)

            # 2. Fuzzy: buscar por palabras clave del título
            # Tomar las primeras 4 palabras significativas
            palabras = [p for p in titulo_norm.split() if len(p) > 2][:4]
            if not palabras:
                return None

            # Buscar animes que contengan esas palabras en el título
            condiciones = " AND ".join(
                f"LOWER(titulo) LIKE %s" for _ in palabras
            )
            params = [f"%{p}%" for p in palabras]
            cursor.execute(
                f"""
                SELECT id, titulo, poster_url, rating
                FROM animes_cache
                WHERE {condiciones}
                LIMIT 1
                """,
                params,
            )
            row = cursor.fetchone()
            if row:
                return _row_to_match(row)

            # 3. Fuzzy sobre titulo_alternativo
            cursor.execute(
                f"""
                SELECT id, titulo, poster_url, rating
                FROM animes_cache
                WHERE {condiciones.replace('titulo', 'titulo_alternativo')}
                LIMIT 1
                """,
                params,
            )
            row = cursor.fetchone()
            return _row_to_match(row) if row else None

        except Exception as e:
            print(f"[DB ERROR buscar_anime_por_titulo] {e}")
            return None
        finally:
            cursor.close()


def _row_to_match(row) -> dict:
    return {
        "id":         row[0],
        "titulo":     row[1],
        "poster_url": row[2],
        "rating":     float(row[3]) if row[3] else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# RESOLVER LISTA COMPLETA (parse → match en batch)
# ══════════════════════════════════════════════════════════════════════════════

def resolver_lista(items: list[dict]) -> dict:
    """
    Recibe lista de { titulo, tipo, episodios_vistos? } y devuelve:
    {
      encontrados: [ { titulo_original, anime_id, titulo_db, poster_url, tipo }, ... ],
      no_encontrados: [ { titulo_original, tipo }, ... ]
    }
    """
    encontrados = []
    no_encontrados = []

    for item in items:
        titulo = (item.get("titulo") or "").strip()
        if not titulo:
            continue

        match = buscar_anime_por_titulo(titulo)
        tipo_ca = _mapear_tipo(item.get("tipo", ""))

        if match:
            encontrados.append({
                "titulo_original":  titulo,
                "anime_id":         match["id"],
                "titulo_db":        match["titulo"],
                "poster_url":       match["poster_url"],
                "rating":           match["rating"],
                "tipo":             tipo_ca,
                "episodios_vistos": item.get("episodios_vistos"),
            })
        else:
            no_encontrados.append({
                "titulo_original": titulo,
                "tipo":            tipo_ca,
            })

    return {"encontrados": encontrados, "no_encontrados": no_encontrados}


# ══════════════════════════════════════════════════════════════════════════════
# IMPORTAR CONFIRMADO
# ══════════════════════════════════════════════════════════════════════════════

def importar_animes(usuario_id: int, animes: list[dict]) -> dict:
    """
    Inserta en lista_animes todos los animes confirmados.
    animes: [ { anime_id, tipo, episodios_vistos? }, ... ]
    Retorna { importados: N, errores: N }
    """
    from backend.database.lista_queries import agregar_anime

    importados = 0
    errores    = 0

    for a in animes:
        anime_id = a.get("anime_id")
        tipo     = a.get("tipo", "visto")
        eps      = a.get("episodios_vistos")

        if not anime_id or tipo not in ("visto", "pendiente", "favorito"):
            errores += 1
            continue

        resultado = agregar_anime(
            usuario_id=usuario_id,
            anime_id=str(anime_id),
            tipo=tipo,
            episodios_vistos=str(eps) if eps else None,
        )
        if resultado:
            importados += 1
        else:
            errores += 1

    return {"importados": importados, "errores": errores}


# ══════════════════════════════════════════════════════════════════════════════
# MAPEO DE TIPOS
# ══════════════════════════════════════════════════════════════════════════════

def _mapear_tipo(status: str) -> str:
    """
    Mapea estados de MAL / AniList / texto libre al tipo de ControlAnime.
    ControlAnime acepta: 'visto', 'pendiente', 'favorito'
    """
    s = (status or "").lower().strip()
    # MAL: Completed, Watching, Plan to Watch, On-Hold, Dropped
    if s in ("completed", "visto", "watched", "finished", "complete"):
        return "visto"
    if s in ("plan to watch", "plantowatch", "plan_to_watch", "pendiente",
             "want to watch", "watching", "on-hold", "on hold", "paused"):
        return "pendiente"
    if s in ("favorito", "favorite", "favourites", "favourite"):
        return "favorito"
    # Default: si viene del export propio de CA
    if s in ("visto", "pendiente", "favorito"):
        return s
    return "visto"
