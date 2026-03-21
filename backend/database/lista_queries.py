"""
lista_queries.py — Queries de lista, likes y reseñas
------------------------------------------------------
Toda la lógica SQL que antes vivía inline en lista.py ahora vive aquí.
El router importa estas funciones y solo se ocupa de validar inputs
y devolver JSONResponse.

Retornan tipos Python puros. Nunca JSONResponse.
"""

from backend.database.connection import get_db


# ══════════════════════════════════════════════════════════════════════════════
# LISTA DE ANIMES
# ══════════════════════════════════════════════════════════════════════════════

def agregar_anime(
    usuario_id: int,
    anime_id: str,
    tipo: str,
    episodios_vistos: str | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> str | None:
    """
    Inserta o actualiza una entrada en lista_animes.
    Retorna la fecha de agregado como string, o None si falla.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO lista_animes
                    (usuario_id, anime_id, tipo, episodios_vistos, fecha_inicio, fecha_fin)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (usuario_id, anime_id) DO UPDATE SET
                    tipo             = EXCLUDED.tipo,
                    episodios_vistos = COALESCE(EXCLUDED.episodios_vistos, lista_animes.episodios_vistos),
                    fecha_inicio     = COALESCE(EXCLUDED.fecha_inicio,     lista_animes.fecha_inicio),
                    fecha_fin        = COALESCE(EXCLUDED.fecha_fin,        lista_animes.fecha_fin),
                    agregado_en      = NOW()
                RETURNING agregado_en
                """,
                (usuario_id, anime_id, tipo, episodios_vistos, fecha_inicio, fecha_fin),
            )
            row = cursor.fetchone()
            conn.commit()
            return str(row[0]) if row else None
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR agregar_anime] {e}")
            return None
        finally:
            cursor.close()


def eliminar_anime(usuario_id: int, anime_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM lista_animes WHERE anime_id = %s AND usuario_id = %s",
                (anime_id, usuario_id),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR eliminar_anime] {e}")
            return False
        finally:
            cursor.close()


def get_lista(usuario_id: int) -> dict:
    """
    Retorna { lista: [...], likes: [...], abandonados: [...] }.
    'lista' contiene vistos y pendientes.
    'likes' viene de la tabla anime_likes (separada).
    'abandonados' se filtra de lista antes de devolver.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Lista principal
            cursor.execute(
                """
                SELECT ac.id, ac.titulo, ac.titulo_alternativo, ac.sinopsis,
                       ac.poster_url, ac.cover_url, ac.rating, ac.episodios,
                       ac.estado, ac.genres, la.tipo, la.agregado_en, la.episodios_vistos
                FROM lista_animes la
                JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s
                ORDER BY la.agregado_en DESC
                """,
                (usuario_id,),
            )
            keys = [
                "id", "titulo", "titulo_alternativo", "sinopsis",
                "poster_url", "cover_url", "rating", "episodios",
                "estado", "genres", "tipo", "agregado_en", "episodios_vistos",
            ]
            todos = []
            for row in cursor.fetchall():
                d = dict(zip(keys, row))
                if d["rating"]:
                    d["rating"] = float(d["rating"])
                if d["agregado_en"]:
                    d["agregado_en"] = str(d["agregado_en"])
                todos.append(d)

            # Likes
            cursor.execute(
                """
                SELECT ac.id, ac.titulo, ac.titulo_alternativo, ac.poster_url,
                       ac.cover_url, ac.rating, ac.episodios, ac.genres, al.creado_en
                FROM anime_likes al
                JOIN animes_cache ac ON ac.id = al.anime_id
                WHERE al.usuario_id = %s
                ORDER BY al.creado_en DESC
                """,
                (usuario_id,),
            )
            like_keys = [
                "id", "titulo", "titulo_alternativo", "poster_url",
                "cover_url", "rating", "episodios", "genres", "agregado_en",
            ]
            likes = []
            for row in cursor.fetchall():
                d = dict(zip(like_keys, row))
                d["tipo"] = "like"
                if d["rating"]:
                    d["rating"] = float(d["rating"])
                if d["agregado_en"]:
                    d["agregado_en"] = str(d["agregado_en"])
                likes.append(d)

            abandonados   = [x for x in todos if x["tipo"] == "abandonado"]
            lista_filtrada = [x for x in todos if x["tipo"] != "abandonado"]

            return {"lista": lista_filtrada, "likes": likes, "abandonados": abandonados}

        except Exception as e:
            print(f"[DB ERROR get_lista] {e}")
            return {"lista": [], "likes": [], "abandonados": []}
        finally:
            cursor.close()


def borrar_lista(usuario_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM lista_animes WHERE usuario_id = %s", (usuario_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR borrar_lista] {e}")
            return False
        finally:
            cursor.close()


def eliminar_cuenta(usuario_id: int) -> bool:
    """
    Borra todos los datos del usuario en cascada.
    Orden importante: resenas → likes → top → lista → sesiones → codigos → usuario.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            tablas = [
                ("resenas",               "usuario_id"),
                ("anime_likes",           "usuario_id"),
                ("top_animes",            "usuario_id"),
                ("lista_animes",          "usuario_id"),
                ("sesiones",              "usuario_id"),
                ("codigos_verificacion",  "usuario_id"),
            ]
            for tabla, campo in tablas:
                cursor.execute(
                    f"DELETE FROM {tabla} WHERE {campo} = %s", (usuario_id,)
                )
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
            conn.commit()
            print(f"[CUENTA] Usuario {usuario_id} eliminado")
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR eliminar_cuenta] {e}")
            return False
        finally:
            cursor.close()


def get_lista_export(usuario_id: int, filtro: str = "todo") -> list:
    """
    Retorna la lista para exportar a JSON o XLSX.
    filtro: 'todo' | 'visto' | 'pendiente'
    """
    _FILTROS = {
        "todo":      None,
        "visto":     "visto",
        "pendiente": "pendiente",
    }
    tipo_filtro = _FILTROS.get(filtro)

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if tipo_filtro:
                cursor.execute(
                    """
                    SELECT ac.id, ac.titulo, ac.episodios, ac.genres, la.tipo, la.agregado_en
                    FROM lista_animes la
                    JOIN animes_cache ac ON ac.id = la.anime_id
                    WHERE la.usuario_id = %s AND la.tipo = %s
                    ORDER BY la.agregado_en DESC
                    """,
                    (usuario_id, tipo_filtro),
                )
            else:
                cursor.execute(
                    """
                    SELECT ac.id, ac.titulo, ac.episodios, ac.genres, la.tipo, la.agregado_en
                    FROM lista_animes la
                    JOIN animes_cache ac ON ac.id = la.anime_id
                    WHERE la.usuario_id = %s
                    ORDER BY la.agregado_en DESC
                    """,
                    (usuario_id,),
                )
            return [
                {
                    "id":          r[0],
                    "titulo":      r[1],
                    "episodios":   r[2],
                    "genres":      r[3],
                    "tipo":        r[4],
                    "agregado_en": str(r[5]) if r[5] else None,
                }
                for r in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[DB ERROR get_lista_export] {e}")
            return []
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# ESTADO DE ANIME (para la ficha /dashboard/anime/:id)
# ══════════════════════════════════════════════════════════════════════════════

def get_estado_anime(usuario_id: int, anime_id: str) -> dict:
    """
    Retorna el estado completo del anime para el usuario:
    tipo en lista, episodios vistos, fechas, like y reseña propia.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT tipo, episodios_vistos, fecha_inicio, fecha_fin
                FROM lista_animes
                WHERE usuario_id = %s AND anime_id = %s
                """,
                (usuario_id, anime_id),
            )
            row_lista = cursor.fetchone()

            cursor.execute(
                "SELECT 1 FROM anime_likes WHERE usuario_id = %s AND anime_id = %s",
                (usuario_id, anime_id),
            )
            like = cursor.fetchone() is not None

            cursor.execute(
                "SELECT id, rating, comentario FROM resenas "
                "WHERE usuario_id = %s AND anime_id = %s",
                (usuario_id, anime_id),
            )
            row_resena = cursor.fetchone()

            return {
                "tipo":             row_lista[0] if row_lista else None,
                "episodios_vistos": row_lista[1] if row_lista else None,
                "fecha_inicio":     str(row_lista[2]) if row_lista and row_lista[2] else None,
                "fecha_fin":        str(row_lista[3]) if row_lista and row_lista[3] else None,
                "like":             like,
                "resena": {
                    "id":         row_resena[0],
                    "rating":     row_resena[1],
                    "comentario": row_resena[2],
                } if row_resena else None,
            }
        except Exception as e:
            print(f"[DB ERROR get_estado_anime] {e}")
            return {"tipo": None, "like": False, "resena": None}
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# LIKES
# ══════════════════════════════════════════════════════════════════════════════

def dar_like(usuario_id: int, anime_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO anime_likes (usuario_id, anime_id) "
                "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (usuario_id, anime_id),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR dar_like] {e}")
            return False
        finally:
            cursor.close()


def quitar_like(usuario_id: int, anime_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM anime_likes WHERE usuario_id = %s AND anime_id = %s",
                (usuario_id, anime_id),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR quitar_like] {e}")
            return False
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# RESEÑAS
# ══════════════════════════════════════════════════════════════════════════════

def get_resenas(anime_id: str, usuario_id_actual: int) -> list:
    """Retorna las últimas 50 reseñas públicas de un anime."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT r.id, u.username, u.foto_perfil, r.rating, r.comentario,
                       r.creado_en, r.editado_en, r.usuario_id
                FROM resenas r
                JOIN usuarios u ON u.id = r.usuario_id
                WHERE r.anime_id = %s
                ORDER BY r.creado_en DESC
                LIMIT 50
                """,
                (anime_id,),
            )
            return [
                {
                    "id":         r[0],
                    "nombre":     r[1],
                    "foto_url":   r[2],
                    "rating":     r[3],
                    "comentario": r[4],
                    "creado_en":  str(r[5]),
                    "editado_en": str(r[6]) if r[6] else None,
                    "es_propia":  r[7] == usuario_id_actual,
                }
                for r in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[DB ERROR get_resenas] {e}")
            return []
        finally:
            cursor.close()


def upsert_resena(
    usuario_id: int,
    anime_id: str,
    rating: int,
    comentario: str | None,
) -> dict | None:
    """
    Crea o actualiza la reseña del usuario para un anime.
    Retorna { id, creado_en } o None si falla.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO resenas (usuario_id, anime_id, rating, comentario)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (usuario_id, anime_id) DO UPDATE SET
                    rating     = EXCLUDED.rating,
                    comentario = EXCLUDED.comentario,
                    editado_en = NOW()
                RETURNING id, creado_en
                """,
                (usuario_id, anime_id, rating, comentario or None),
            )
            row = cursor.fetchone()
            conn.commit()
            return {"id": row[0], "creado_en": str(row[1])} if row else None
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR upsert_resena] {e}")
            return None
        finally:
            cursor.close()


def eliminar_resena(resena_id: int, usuario_id: int) -> bool:
    """
    Retorna True si se eliminó, False si no existía o no pertenecía al usuario.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM resenas WHERE id = %s AND usuario_id = %s",
                (resena_id, usuario_id),
            )
            eliminadas = cursor.rowcount
            conn.commit()
            return eliminadas > 0
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR eliminar_resena] {e}")
            return False
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# DETALLE DE ENTRADA EN LISTA (página /mi-lista/anime/:id)
# ══════════════════════════════════════════════════════════════════════════════

def get_detalle_lista(usuario_id: int, anime_id: str) -> dict | None:
    """
    Retorna el detalle completo de una entrada en lista:
    datos del anime + estado de lista + like + reseña propia.
    None si el anime no está en la lista del usuario.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT la.tipo, la.episodios_vistos, la.fecha_inicio, la.fecha_fin, la.agregado_en,
                       ac.titulo, ac.poster_url, ac.cover_url, ac.episodios, ac.rating, ac.sinopsis
                FROM lista_animes la
                LEFT JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s AND la.anime_id = %s
                """,
                (usuario_id, anime_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            tipo, eps_vistos, f_inicio, f_fin, agregado_en, \
                titulo, poster, cover, eps_total, rating, sinopsis = row

            cursor.execute(
                "SELECT 1 FROM anime_likes WHERE usuario_id = %s AND anime_id = %s",
                (usuario_id, anime_id),
            )
            like = cursor.fetchone() is not None

            cursor.execute(
                """
                SELECT id, rating, comentario, creado_en, editado_en
                FROM resenas WHERE usuario_id = %s AND anime_id = %s
                """,
                (usuario_id, anime_id),
            )
            r = cursor.fetchone()
            resena = {
                "id":         r[0],
                "rating":     float(r[1]) if r[1] else None,
                "comentario": r[2],
                "creado_en":  str(r[3]) if r[3] else None,
                "editado_en": str(r[4]) if r[4] else None,
            } if r else None

            return {
                "anime": {
                    "id":        anime_id,
                    "titulo":    titulo or "",
                    "poster_url": poster or "",
                    "cover_url": cover or "",
                    "episodios": eps_total,
                    "rating":    float(rating) if rating else None,
                    "sinopsis":  sinopsis or "",
                },
                "entrada": {
                    "tipo":             tipo,
                    "episodios_vistos": eps_vistos,
                    "fecha_inicio":     str(f_inicio) if f_inicio else None,
                    "fecha_fin":        str(f_fin) if f_fin else None,
                    "agregado_en":      str(agregado_en) if agregado_en else None,
                },
                "like":   like,
                "resena": resena,
            }
        except Exception as e:
            print(f"[DB ERROR get_detalle_lista] {e}")
            return None
        finally:
            cursor.close()


def actualizar_detalle_lista(
    usuario_id: int,
    anime_id: str,
    campos: dict,
) -> bool:
    """
    Actualiza dinámicamente los campos permitidos de una entrada en lista_animes.
    Campos permitidos: tipo, episodios_vistos, fecha_inicio, fecha_fin, agregado_en.
    """
    _PERMITIDOS = {"tipo", "episodios_vistos", "fecha_inicio", "fecha_fin", "agregado_en"}
    campos_validos = {k: v for k, v in campos.items() if k in _PERMITIDOS}
    if not campos_validos:
        return False

    set_clause = ", ".join(f"{k} = %s" for k in campos_validos)
    valores    = list(campos_validos.values()) + [usuario_id, anime_id]

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE lista_animes SET {set_clause} "
                f"WHERE usuario_id = %s AND anime_id = %s",
                valores,
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR actualizar_detalle_lista] {e}")
            return False
        finally:
            cursor.close()
