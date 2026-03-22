"""
connection.py — Pool de conexiones y acceso a datos · ControlAnime
------------------------------------------------------------------
v2: guardar_animes_cache actualizado para el esquema completo
    con todos los campos enriquecidos (Jikan como fuente primaria).
"""

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
import os
import secrets
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

_pool: ThreadedConnectionPool | None = None


def init_pool(min_conn: int = 2, max_conn: int = 10) -> None:
    global _pool
    _pool = ThreadedConnectionPool(
        min_conn, max_conn,
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )
    print(f"[DB] Pool inicializado ({min_conn}–{max_conn} conexiones)")


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        print("[DB] Pool cerrado")


@contextmanager
def get_db():
    if _pool is None:
        raise RuntimeError("[DB] Pool no inicializado. Llama init_pool() al arrancar la app.")
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def _is_duplicate(e: Exception) -> bool:
    msg = str(e).lower()
    return "unique" in msg or "unicidad" in msg or "duplicate" in msg


# ══════════════════════════════════════════════════════════════════════════════
# USUARIOS Y AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def insertar_usuario(email: str, password_hash: str):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO usuarios (email, password_hash) VALUES (%s, %s)",
                (email, password_hash),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR insertar_usuario] {e}")
            return "email_duplicado" if _is_duplicate(e) else "error_db"
        finally:
            cursor.close()


def obtener_usuario_por_email(email: str):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, password_hash, email_verificado FROM usuarios WHERE email = %s", (email,)
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def obtener_usuario_id_por_email(email: str):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()


def obtener_email_por_id(usuario_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT email FROM usuarios WHERE id = %s", (usuario_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()


def obtener_usuario_por_token(token: str):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT u.email, u.creado_en, u.username, u.foto_perfil,
                       u.perfil_publico, u.instagram, u.discord, u.tiktok
                FROM sesiones s
                JOIN usuarios u ON u.id = s.usuario_id
                WHERE s.token = %s AND s.expira_en > NOW()
            """, (token,))
            return cursor.fetchone()
        except Exception as e:
            print(f"[DB ERROR obtener_usuario_por_token] {e}")
            return None
        finally:
            cursor.close()


def obtener_usuario_id_por_token(token: str):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT usuario_id FROM sesiones WHERE token = %s AND expira_en > NOW()",
                (token,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"[DB ERROR obtener_usuario_id_por_token] {e}")
            return None
        finally:
            cursor.close()


def actualizar_perfil(token: str, datos: dict):
    _ALLOWED = (
        "username", "email", "foto_perfil", "password_hash",
        "perfil_publico", "perfil_header_color", "perfil_header_imagen",
        "instagram", "discord", "tiktok",
    )
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            campos  = [f"{f} = %s" for f in _ALLOWED if f in datos]
            valores = [datos[f] for f in _ALLOWED if f in datos]
            if not campos:
                return False
            valores.append(token)
            cursor.execute(
                f"""UPDATE usuarios SET {', '.join(campos)}
                    WHERE id = (SELECT usuario_id FROM sesiones
                                WHERE token = %s AND expira_en > NOW())""",
                valores,
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR actualizar_perfil] {e}")
            return False
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# SESIONES Y CSRF
# ══════════════════════════════════════════════════════════════════════════════

def crear_sesion(usuario_id: int, token: str) -> str:
    csrf_token = secrets.token_hex(32)
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM sesiones WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("""
                INSERT INTO sesiones (usuario_id, token, csrf_token, expira_en)
                VALUES (%s, %s, %s, NOW() + INTERVAL '7 days')
            """, (usuario_id, token, csrf_token))
            conn.commit()
            return csrf_token
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR crear_sesion] {e}")
            return ""
        finally:
            cursor.close()


def validar_csrf(session_token: str, csrf_enviado: str) -> bool:
    if not csrf_enviado or not session_token:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT csrf_token FROM sesiones WHERE token = %s AND expira_en > NOW()",
                (session_token,)
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return False
            return secrets.compare_digest(row[0], csrf_enviado)
        except Exception as e:
            print(f"[DB ERROR validar_csrf] {e}")
            return False
        finally:
            cursor.close()


def invalidar_sesion(token: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM sesiones WHERE token = %s", (token,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR invalidar_sesion] {e}")
            return False
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# VERIFICACIÓN DE EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def guardar_codigo_verificacion(usuario_id: int, codigo: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE codigos_verificacion SET usado = true WHERE usuario_id = %s AND usado = false",
                (usuario_id,)
            )
            expira_en = datetime.now() + timedelta(minutes=15)
            cursor.execute(
                "INSERT INTO codigos_verificacion (usuario_id, codigo, expira_en) VALUES (%s, %s, %s)",
                (usuario_id, codigo, expira_en)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR guardar_codigo_verificacion] {e}")
            return False
        finally:
            cursor.close()


def verificar_codigo(usuario_id: int, codigo: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id FROM codigos_verificacion
                WHERE usuario_id = %s AND codigo = %s
                  AND usado = false AND expira_en > NOW()
                ORDER BY creado_en DESC LIMIT 1
            """, (usuario_id, codigo))
            row = cursor.fetchone()
            if not row:
                return False
            cursor.execute("UPDATE codigos_verificacion SET usado = true WHERE id = %s", (row[0],))
            cursor.execute("UPDATE usuarios SET email_verificado = true WHERE id = %s", (usuario_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR verificar_codigo] {e}")
            return False
        finally:
            cursor.close()


def guardar_pending_email(usuario_id: int, nuevo_email: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE usuarios SET pending_email = %s WHERE id = %s", (nuevo_email, usuario_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR guardar_pending_email] {e}")
            return False
        finally:
            cursor.close()


def confirmar_cambio_email(usuario_id: int, codigo: str) -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT pending_email FROM usuarios WHERE id = %s", (usuario_id,))
            row = cursor.fetchone()
            if not row or not row[0]:
                return "sin_pending"
            nuevo_email = row[0]
            cursor.execute("""
                SELECT id FROM codigos_verificacion
                WHERE usuario_id = %s AND codigo = %s AND usado = false AND expira_en > NOW()
                ORDER BY creado_en DESC LIMIT 1
            """, (usuario_id, codigo))
            cod_row = cursor.fetchone()
            if not cod_row:
                return "codigo_invalido"
            cursor.execute("UPDATE codigos_verificacion SET usado = true WHERE id = %s", (cod_row[0],))
            cursor.execute("UPDATE usuarios SET email = %s, pending_email = NULL WHERE id = %s", (nuevo_email, usuario_id))
            conn.commit()
            return "ok"
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR confirmar_cambio_email] {e}")
            return "error_db"
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# CACHÉ DE ANIMES — ESQUEMA COMPLETO (v2 con Jikan como primario)
# ══════════════════════════════════════════════════════════════════════════════

def guardar_animes_cache(animes: list, marcar_jikan: bool = False) -> None:
    """
    Inserta o actualiza animes en animes_cache con el esquema completo.

    Reglas de CONFLICT:
    - cover_url:    COALESCE(EXCLUDED, existente) — no borrar el banner de AniList
    - sinopsis_es:  COALESCE(existente, EXCLUDED) — nunca sobreescribir traducción
    - timestamps de enriquecimiento: COALESCE(existente, EXCLUDED) — no resetear
    - El resto: siempre actualiza con el valor más reciente

    marcar_jikan=True → establece enriquecido_jikan_en = NOW()
    """
    if not animes:
        return

    jikan_ts_sql = "NOW()" if marcar_jikan else "COALESCE(animes_cache.enriquecido_jikan_en, EXCLUDED.enriquecido_jikan_en)"

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            for a in animes:
                if not a.get("id"):
                    continue
                cursor.execute(f"""
                    INSERT INTO animes_cache (
                        id, titulo, titulo_alternativo, sinopsis,
                        poster_url, cover_url, rating, episodios, estado,
                        genres, genres_es, tipo, duracion, anio, temporada,
                        fecha_inicio, fecha_fin, estudio,
                        score_count, popularidad, mal_id,
                        cached_en
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        titulo            = EXCLUDED.titulo,
                        titulo_alternativo= COALESCE(EXCLUDED.titulo_alternativo, animes_cache.titulo_alternativo),
                        sinopsis          = COALESCE(EXCLUDED.sinopsis, animes_cache.sinopsis),
                        poster_url        = COALESCE(EXCLUDED.poster_url, animes_cache.poster_url),
                        cover_url         = COALESCE(EXCLUDED.cover_url, animes_cache.cover_url),
                        rating            = COALESCE(EXCLUDED.rating, animes_cache.rating),
                        episodios         = COALESCE(EXCLUDED.episodios, animes_cache.episodios),
                        estado            = COALESCE(EXCLUDED.estado, animes_cache.estado),
                        genres            = COALESCE(EXCLUDED.genres, animes_cache.genres),
                        genres_es         = COALESCE(EXCLUDED.genres_es, animes_cache.genres_es),
                        tipo              = COALESCE(EXCLUDED.tipo, animes_cache.tipo),
                        duracion          = COALESCE(EXCLUDED.duracion, animes_cache.duracion),
                        anio              = COALESCE(EXCLUDED.anio, animes_cache.anio),
                        temporada         = COALESCE(EXCLUDED.temporada, animes_cache.temporada),
                        fecha_inicio      = COALESCE(EXCLUDED.fecha_inicio, animes_cache.fecha_inicio),
                        fecha_fin         = COALESCE(EXCLUDED.fecha_fin, animes_cache.fecha_fin),
                        estudio           = COALESCE(EXCLUDED.estudio, animes_cache.estudio),
                        score_count       = COALESCE(EXCLUDED.score_count, animes_cache.score_count),
                        popularidad       = COALESCE(EXCLUDED.popularidad, animes_cache.popularidad),
                        mal_id            = COALESCE(EXCLUDED.mal_id, animes_cache.mal_id),
                        sinopsis_es       = COALESCE(animes_cache.sinopsis_es, EXCLUDED.sinopsis_es),
                        enriquecido_jikan_en = {jikan_ts_sql},
                        enriquecido_anilist_en = COALESCE(animes_cache.enriquecido_anilist_en, EXCLUDED.enriquecido_anilist_en),
                        cached_en         = NOW()
                """, (
                    a.get("id"), a.get("titulo"), a.get("titulo_alternativo"), a.get("sinopsis"),
                    a.get("poster_url"), a.get("cover_url"), a.get("rating"), a.get("episodios"), a.get("estado"),
                    a.get("genres"), a.get("genres_es"), a.get("tipo"), a.get("duracion"), a.get("anio"), a.get("temporada"),
                    a.get("fecha_inicio"), a.get("fecha_fin"), a.get("estudio"),
                    a.get("score_count"), a.get("popularidad"), a.get("mal_id"),
                ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR guardar_animes_cache] {e}")
        finally:
            cursor.close()


def guardar_sinopsis_es(anime_id: str, sinopsis_es: str) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE animes_cache SET sinopsis_es = %s WHERE id = %s",
                (sinopsis_es, anime_id)
            )
            conn.commit()
            print(f"[DB] sinopsis_es guardada para anime {anime_id}")
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR guardar_sinopsis_es] {e}")
        finally:
            cursor.close()


def buscar_anime_cache(query: str) -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, titulo, titulo_alternativo, sinopsis, poster_url, cover_url,
                       rating, episodios, estado, genres
                FROM animes_cache
                WHERE (LOWER(titulo) LIKE LOWER(%s) OR LOWER(titulo_alternativo) LIKE LOWER(%s))
                  AND cached_en > NOW() - INTERVAL '7 days'
                ORDER BY rating DESC NULLS LAST
                LIMIT 15
            """, (f"%{query}%", f"%{query}%"))
            rows = cursor.fetchall()
            keys = ["id","titulo","titulo_alternativo","sinopsis","poster_url",
                    "cover_url","rating","episodios","estado","genres"]
            return [
                dict(zip(keys, [*r[:6], float(r[6]) if r[6] else None, *r[7:]]))
                for r in rows
            ]
        except Exception as e:
            print(f"[DB ERROR buscar_anime_cache] {e}")
            return []
        finally:
            cursor.close()

# ══════════════════════════════════════════════════════════════════════════════
# SESIONES ACTIVAS
# ══════════════════════════════════════════════════════════════════════════════

def obtener_sesiones_activas(usuario_id: int) -> list:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, token, creado_en, expira_en
                FROM sesiones
                WHERE usuario_id = %s AND expira_en > NOW()
                ORDER BY creado_en DESC
            """, (usuario_id,))
            rows = cursor.fetchall()
            return [
                {
                    "id":        r[0],
                    "token":     r[1][:8] + "...",
                    "creado_en": r[2].isoformat() if r[2] else None,
                    "expira_en": r[3].isoformat() if r[3] else None,
                }
                for r in rows
            ]
        except Exception as e:
            print(f"[DB ERROR obtener_sesiones_activas] {e}")
            return []
        finally:
            cursor.close()


def cerrar_sesion_por_id(sesion_id: int, usuario_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM sesiones WHERE id = %s AND usuario_id = %s",
                (sesion_id, usuario_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR cerrar_sesion_por_id] {e}")
            return False
        finally:
            cursor.close()


def cerrar_otras_sesiones(usuario_id: int, token_actual: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM sesiones WHERE usuario_id = %s AND token != %s",
                (usuario_id, token_actual)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR cerrar_otras_sesiones] {e}")
            return False
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# ZONA DE PELIGRO
# ══════════════════════════════════════════════════════════════════════════════

def eliminar_lista_usuario(usuario_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM lista_animes WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM resenas WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM anime_likes WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM top_animes WHERE usuario_id = %s", (usuario_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR eliminar_lista_usuario] {e}")
            return False
        finally:
            cursor.close()


def eliminar_cuenta_usuario(usuario_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Eliminar en orden para respetar FK
            cursor.execute("DELETE FROM lista_animes          WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM resenas               WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM anime_likes           WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM top_animes            WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM codigos_verificacion  WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM sesiones              WHERE usuario_id = %s", (usuario_id,))
            cursor.execute("DELETE FROM usuarios              WHERE id = %s",         (usuario_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR eliminar_cuenta_usuario] {e}")
            return False
        finally:
            cursor.close()
