"""
anime_queries.py — Queries de animes para los routers
------------------------------------------------------
v2: get_hero sin requerir cover_url — prioriza pero no bloquea.
    get_por_genero usa ILIKE para coincidencia parcial (géneros MAL son strings libres).
"""

from backend.database.connection import get_db

_KEYS = [
    "id","titulo","titulo_alternativo","sinopsis",
    "poster_url","cover_url","rating","episodios","estado","genres","genres_es",
]
_KEYS_ES = _KEYS + ["sinopsis_es"]


def _to_anime(row: tuple, keys: list = _KEYS) -> dict:
    d = dict(zip(keys, row))
    if d.get("rating") is not None:
        d["rating"] = float(d["rating"])
    return d


def get_top_animes(offset: int = 0, limit: int = 28) -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres, genres_es
                FROM animes_cache
                WHERE rating IS NOT NULL
                  AND poster_url IS NOT NULL AND poster_url != ''
                ORDER BY rating DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return [_to_anime(r) for r in cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR get_top_animes] {e}")
            return []
        finally:
            cursor.close()


def get_emision(offset: int = 0, limit: int = 28) -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres, genres_es
                FROM animes_cache
                WHERE estado = 'current'
                  AND poster_url IS NOT NULL AND poster_url != ''
                ORDER BY rating DESC NULLS LAST
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return [_to_anime(r) for r in cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR get_emision] {e}")
            return []
        finally:
            cursor.close()


def get_emision_count() -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*)
                FROM animes_cache
                WHERE estado = 'current'
                  AND poster_url IS NOT NULL AND poster_url != ''
            """)
            row = cursor.fetchone()
            return row[0] if row else 0
        except Exception as e:
            print(f"[DB ERROR get_emision_count] {e}")
            return 0
        finally:
            cursor.close()


def get_por_genero(genero: str, offset: int = 0, limit: int = 28) -> list:
    """
    ILIKE con % para coincidencia parcial.
    En el nuevo esquema los géneros son strings de MAL como 'Action, Adventure, Fantasy'.
    Buscar 'accion' no coincidirá — el frontend debe enviar el nombre en inglés
    tal como aparece en MAL: 'Action', 'Romance', etc.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres, genres_es
                FROM animes_cache
                WHERE genres ILIKE %s
                  AND poster_url IS NOT NULL AND poster_url != ''
                ORDER BY rating DESC NULLS LAST
                LIMIT %s OFFSET %s
            """, (f"%{genero}%", limit, offset))
            return [_to_anime(r) for r in cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR get_por_genero] {e}")
            return []
        finally:
            cursor.close()




def get_por_tipo(tipo: str, offset: int = 0, limit: int = 28) -> list:
    """
    Filtra por tipo: TV | Movie | OVA | ONA | Special
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres, genres_es
                FROM animes_cache
                WHERE tipo = %s
                  AND poster_url IS NOT NULL AND poster_url != ''
                ORDER BY rating DESC NULLS LAST
                LIMIT %s OFFSET %s
            """, (tipo, limit, offset))
            return [_to_anime(r) for r in cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR get_por_tipo] {e}")
            return []
        finally:
            cursor.close()


def get_por_temporada(temporada: str, anio: int | None = None, offset: int = 0, limit: int = 28) -> list:
    """
    Filtra por temporada: winter | spring | summer | fall
    anio es opcional — si no se pasa, devuelve de todos los años.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if anio:
                cursor.execute("""
                    SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                           rating, episodios, estado, genres, genres_es
                    FROM animes_cache
                    WHERE temporada = %s AND anio = %s
                      AND poster_url IS NOT NULL AND poster_url != ''
                    ORDER BY rating DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """, (temporada, anio, limit, offset))
            else:
                cursor.execute("""
                    SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                           rating, episodios, estado, genres, genres_es
                    FROM animes_cache
                    WHERE temporada = %s
                      AND poster_url IS NOT NULL AND poster_url != ''
                    ORDER BY anio DESC NULLS LAST, rating DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """, (temporada, limit, offset))
            return [_to_anime(r) for r in cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR get_por_temporada] {e}")
            return []
        finally:
            cursor.close()


def get_temporadas_disponibles() -> list:
    """
    Retorna lista de (temporada, anio) disponibles en la BD ordenadas por año desc.
    Usada para poblar el selector de temporadas en el frontend.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT temporada, anio, COUNT(*) as total
                FROM animes_cache
                WHERE temporada IS NOT NULL AND anio IS NOT NULL
                GROUP BY temporada, anio
                HAVING COUNT(*) >= 3
                ORDER BY anio DESC, 
                    CASE temporada
                        WHEN 'winter' THEN 1
                        WHEN 'spring' THEN 2
                        WHEN 'summer' THEN 3
                        WHEN 'fall'   THEN 4
                    END
            """)
            return [
                {"temporada": r[0], "anio": r[1], "total": r[2]}
                for r in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[DB ERROR get_temporadas_disponibles] {e}")
            return []
        finally:
            cursor.close()

def get_hero() -> list:
    """
    Top 6 para el carrusel de la landing page.
    Prioriza animes con cover_url (banner AniList) pero no los requiere,
    para que el carrusel funcione incluso antes de que AniList enriquezca.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres, sinopsis_es
                FROM animes_cache
                WHERE rating IS NOT NULL
                  AND poster_url IS NOT NULL AND poster_url != ''
                ORDER BY
                    (CASE WHEN cover_url IS NOT NULL AND cover_url != '' THEN 0 ELSE 1 END),
                    rating DESC
                LIMIT 6
            """)
            return [_to_anime(r, _KEYS_ES) for r in cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR get_hero] {e}")
            return []
        finally:
            cursor.close()


def get_collage() -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, poster_url
                FROM animes_cache
                WHERE poster_url IS NOT NULL AND poster_url != ''
                ORDER BY RANDOM()
                LIMIT 20
            """)
            return [{"id": r[0], "titulo": r[1], "poster_url": r[2]} for r in cursor.fetchall()]
        except Exception as e:
            print(f"[DB ERROR get_collage] {e}")
            return []
        finally:
            cursor.close()


def get_sinopsis_raw(anime_id: str) -> tuple | None:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT sinopsis, sinopsis_es FROM animes_cache WHERE id = %s",
                (anime_id,)
            )
            return cursor.fetchone()
        except Exception as e:
            print(f"[DB ERROR get_sinopsis_raw] {e}")
            return None
        finally:
            cursor.close()
