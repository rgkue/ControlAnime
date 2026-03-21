"""
ranking_queries.py — Queries de ranking, top5 y perfiles
---------------------------------------------------------
Toda la lógica SQL que antes vivía inline en ranking.py vive aquí.
El router solo coordina: valida inputs, llama estas funciones y
devuelve JSONResponse.

Retornan tipos Python puros. Nunca JSONResponse.
"""

from backend.database.connection import get_db


# ══════════════════════════════════════════════════════════════════════════════
# RANKING GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def get_ranking() -> list:
    """
    Top 50 usuarios con más animes vistos.
    Los perfiles privados aparecen anonimizados (sin nombre, foto ni redes).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.foto_perfil,
                    u.perfil_publico,
                    COUNT(DISTINCT la.anime_id) FILTER (WHERE la.tipo = 'visto') AS vistos,
                    u.instagram,
                    u.discord,
                    u.tiktok
                FROM usuarios u
                LEFT JOIN lista_animes la ON la.usuario_id = u.id
                GROUP BY u.id
                HAVING COUNT(DISTINCT la.anime_id) FILTER (WHERE la.tipo = 'visto') > 0
                ORDER BY vistos DESC
                LIMIT 50
                """
            )
            cols = [
                "id", "username", "foto_perfil", "perfil_publico",
                "vistos", "instagram", "discord", "tiktok",
            ]
            resultado = []
            for row in cursor.fetchall():
                entry = dict(zip(cols, row))
                if not entry["perfil_publico"]:
                    entry["username"]    = entry["username"] or "Usuario anónimo"
                    entry["foto_perfil"] = None
                    entry["instagram"]   = None
                    entry["discord"]     = None
                    entry["tiktok"]      = None
                resultado.append(entry)
            return resultado
        except Exception as e:
            print(f"[DB ERROR get_ranking] {e}")
            return []
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# TOP 5 PERSONAL
# ══════════════════════════════════════════════════════════════════════════════

def get_mi_top5(usuario_id: int) -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT ta.posicion, ac.id, ac.titulo, ac.poster_url, ac.cover_url, ac.rating
                FROM top_animes ta
                JOIN animes_cache ac ON ac.id = ta.anime_id
                WHERE ta.usuario_id = %s
                ORDER BY ta.posicion ASC
                """,
                (usuario_id,),
            )
            return [
                {
                    "posicion":   r[0],
                    "id":         r[1],
                    "titulo":     r[2],
                    "poster_url": r[3],
                    "cover_url":  r[4],
                    "rating":     float(r[5]) if r[5] else None,
                }
                for r in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[DB ERROR get_mi_top5] {e}")
            return []
        finally:
            cursor.close()


def guardar_top5(usuario_id: int, anime_id: str, posicion: int) -> str:
    """
    Guarda o reemplaza una posición en el top5.
    El anime debe existir en la lista del usuario.
    Retorna 'ok', 'no_en_lista' o 'error'.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Verificar que el anime esté en su lista
            cursor.execute(
                "SELECT 1 FROM lista_animes WHERE usuario_id = %s AND anime_id = %s",
                (usuario_id, anime_id),
            )
            if not cursor.fetchone():
                return "no_en_lista"

            # Eliminar si ya estaba en otra posición
            cursor.execute(
                "DELETE FROM top_animes WHERE usuario_id = %s AND anime_id = %s",
                (usuario_id, anime_id),
            )
            # Insertar en la posición indicada (reemplaza si ya había otro)
            cursor.execute(
                """
                INSERT INTO top_animes (usuario_id, anime_id, posicion)
                VALUES (%s, %s, %s)
                ON CONFLICT (usuario_id, posicion)
                DO UPDATE SET anime_id = EXCLUDED.anime_id
                """,
                (usuario_id, anime_id, posicion),
            )
            conn.commit()
            return "ok"
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR guardar_top5] {e}")
            return "error"
        finally:
            cursor.close()


def eliminar_top5_pos(usuario_id: int, posicion: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM top_animes WHERE usuario_id = %s AND posicion = %s",
                (usuario_id, posicion),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR eliminar_top5_pos] {e}")
            return False
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL — HEADER
# ══════════════════════════════════════════════════════════════════════════════

def get_header_perfil(usuario_id: int) -> dict | None:
    """Retorna { header_color, header_imagen } o None si no existe el usuario."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT perfil_header_color, perfil_header_imagen FROM usuarios WHERE id = %s",
                (usuario_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {"header_color": row[0], "header_imagen": row[1]}
        except Exception as e:
            print(f"[DB ERROR get_header_perfil] {e}")
            return None
        finally:
            cursor.close()


def actualizar_header_perfil(usuario_id: int, datos: dict) -> str:
    """
    Actualiza el header del perfil.
    datos puede contener: reset=True | imagen=str | color=str
    Retorna 'ok', 'imagen_grande', 'color_invalido', 'datos_invalidos' o 'error'.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if datos.get("reset"):
                cursor.execute(
                    "UPDATE usuarios SET perfil_header_color = NULL, "
                    "perfil_header_imagen = NULL WHERE id = %s",
                    (usuario_id,),
                )

            elif "imagen" in datos:
                imagen = datos["imagen"]
                if imagen and len(imagen) > 4_000_000:
                    return "imagen_grande"
                cursor.execute(
                    "UPDATE usuarios SET perfil_header_imagen = %s, "
                    "perfil_header_color = NULL WHERE id = %s",
                    (imagen, usuario_id),
                )

            elif "color" in datos:
                color = datos["color"]
                if color and not color.startswith("#"):
                    return "color_invalido"
                cursor.execute(
                    "UPDATE usuarios SET perfil_header_color = %s, "
                    "perfil_header_imagen = NULL WHERE id = %s",
                    (color, usuario_id),
                )

            else:
                return "datos_invalidos"

            conn.commit()
            return "ok"
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR actualizar_header_perfil] {e}")
            return "error"
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

def get_perfil_publico(usuario_id: int) -> dict | None:
    """
    Retorna el perfil completo de un usuario si es público:
    datos de usuario, lista de vistos, top5 y estadísticas de géneros.

    Retorna None si no existe.
    Retorna { "privado": True } si el perfil es privado.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, username, foto_perfil, perfil_publico, creado_en,
                       instagram, discord, tiktok,
                       perfil_header_color, perfil_header_imagen
                FROM usuarios WHERE id = %s
                """,
                (usuario_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            cols = [
                "id", "username", "foto_perfil", "perfil_publico", "creado_en",
                "instagram", "discord", "tiktok",
                "perfil_header_color", "perfil_header_imagen",
            ]
            usuario = dict(zip(cols, row))

            if not usuario["perfil_publico"]:
                return {"privado": True}

            usuario["creado_en"] = str(usuario["creado_en"])

            # Animes vistos
            cursor.execute(
                """
                SELECT ac.id, ac.titulo, ac.poster_url, ac.rating, ac.genres, la.agregado_en
                FROM lista_animes la
                JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s AND la.tipo = 'visto'
                ORDER BY la.agregado_en DESC
                """,
                (usuario_id,),
            )
            vistos = [
                {
                    "id":          r[0],
                    "titulo":      r[1],
                    "poster_url":  r[2],
                    "rating":      float(r[3]) if r[3] else None,
                    "genres":      r[4],
                    "agregado_en": str(r[5]),
                }
                for r in cursor.fetchall()
            ]

            # Top 5
            cursor.execute(
                """
                SELECT ta.posicion, ac.id, ac.titulo, ac.poster_url, ac.cover_url, ac.rating
                FROM top_animes ta
                JOIN animes_cache ac ON ac.id = ta.anime_id
                WHERE ta.usuario_id = %s
                ORDER BY ta.posicion ASC
                """,
                (usuario_id,),
            )
            top5 = [
                {
                    "posicion":   r[0],
                    "id":         r[1],
                    "titulo":     r[2],
                    "poster_url": r[3],
                    "cover_url":  r[4],
                    "rating":     float(r[5]) if r[5] else None,
                }
                for r in cursor.fetchall()
            ]

            # Stats: géneros más vistos
            generos: dict[str, int] = {}
            for a in vistos:
                for g in (a["genres"] or "").split(","):
                    g = g.strip()
                    if g:
                        generos[g] = generos.get(g, 0) + 1
            top_generos = sorted(generos.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                "usuario": usuario,
                "vistos":  vistos,
                "top5":    top5,
                "stats": {
                    "total_vistos": len(vistos),
                    "top_generos": [
                        {"nombre": n, "cantidad": c} for n, c in top_generos
                    ],
                },
            }

        except Exception as e:
            print(f"[DB ERROR get_perfil_publico] {e}")
            return None
        finally:
            cursor.close()
