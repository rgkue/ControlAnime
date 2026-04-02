"""
estadisticas_queries.py — Queries de estadísticas personales
-------------------------------------------------------------
Toda la lógica SQL para el dashboard de estadísticas del usuario.
Retorna tipos Python puros. Nunca JSONResponse.
"""

from backend.database.connection import get_db


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN GENERAL
# ══════════════════════════════════════════════════════════════════════════════

def get_resumen(usuario_id: int) -> dict | None:
    """
    Retorna contadores globales del usuario:
    total, vistos, pendientes, favoritos, horas estimadas y fecha de registro.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Contadores por tipo
            cursor.execute(
                """
                SELECT
                    COUNT(*)                                                        AS total,
                    COUNT(*) FILTER (WHERE la.tipo = 'visto')                      AS vistos,
                    COUNT(*) FILTER (WHERE la.tipo = 'pendiente')                  AS pendientes,
                    COUNT(*) FILTER (WHERE la.tipo = 'favorito')                   AS favoritos,
                    COALESCE(SUM(ac.episodios) FILTER (WHERE la.tipo = 'visto'), 0) AS eps_vistos
                FROM lista_animes la
                LEFT JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s
                """,
                (usuario_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {"total": 0, "vistos": 0, "pendientes": 0, "favoritos": 0, "horas": 0, "minutos": 0, "miembro_desde": None}

            total, vistos, pendientes, favoritos, eps = row
            minutos = int(eps or 0) * 24   # 24 min promedio por episodio
            horas   = round(minutos / 60, 1)

            # Fecha de registro
            cursor.execute("SELECT creado_en FROM usuarios WHERE id = %s", (usuario_id,))
            fecha_row = cursor.fetchone()
            miembro_desde = str(fecha_row[0]) if fecha_row and fecha_row[0] else None

            return {
                "total":         int(total or 0),
                "vistos":        int(vistos or 0),
                "pendientes":    int(pendientes or 0),
                "favoritos":     int(favoritos or 0),
                "eps_vistos":    int(eps or 0),
                "minutos":       minutos,
                "horas":         horas,
                "miembro_desde": miembro_desde,
            }
        except Exception as e:
            print(f"[DB ERROR get_resumen] {e}")
            return None
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL DE ACTIVIDAD (animes agregados por mes)
# ══════════════════════════════════════════════════════════════════════════════

def get_actividad_mensual(usuario_id: int) -> list:
    """
    Retorna lista de { mes: 'YYYY-MM', cantidad: N } de los últimos 13 meses.
    Incluye meses con 0 actividad para que el gráfico sea continuo.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    TO_CHAR(DATE_TRUNC('month', agregado_en), 'YYYY-MM') AS mes,
                    COUNT(*) AS cantidad
                FROM lista_animes
                WHERE usuario_id = %s
                  AND agregado_en >= DATE_TRUNC('month', NOW()) - INTERVAL '12 months'
                GROUP BY mes
                ORDER BY mes ASC
                """,
                (usuario_id,),
            )
            rows = cursor.fetchall()
            # Construir mapa para rellenar meses vacíos
            data_map = {r[0]: int(r[1]) for r in rows}

            # Generar los 13 meses (mes actual + 12 atrás)
            cursor.execute(
                """
                SELECT TO_CHAR(
                    DATE_TRUNC('month', NOW()) - (s.n || ' months')::INTERVAL,
                    'YYYY-MM'
                )
                FROM generate_series(12, 0, -1) AS s(n)
                """
            )
            meses = [r[0] for r in cursor.fetchall()]

            return [
                {"mes": m, "cantidad": data_map.get(m, 0)}
                for m in meses
            ]
        except Exception as e:
            print(f"[DB ERROR get_actividad_mensual] {e}")
            return []
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# GÉNEROS
# ══════════════════════════════════════════════════════════════════════════════

def get_generos(usuario_id: int) -> list:
    """
    Top 10 géneros de la lista completa del usuario (todos los tipos).
    Retorna lista de { nombre, cantidad, porcentaje }.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT ac.genres
                FROM lista_animes la
                JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s AND ac.genres IS NOT NULL AND ac.genres != ''
                """,
                (usuario_id,),
            )
            rows = cursor.fetchall()

            conteo: dict[str, int] = {}
            for (genres_str,) in rows:
                for g in genres_str.split(","):
                    g = g.strip()
                    if g:
                        conteo[g] = conteo.get(g, 0) + 1

            if not conteo:
                return []

            total = sum(conteo.values())
            ordenados = sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:10]

            return [
                {
                    "nombre":     nombre,
                    "cantidad":   cant,
                    "porcentaje": round(cant / total * 100, 1),
                }
                for nombre, cant in ordenados
            ]
        except Exception as e:
            print(f"[DB ERROR get_generos] {e}")
            return []
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# ÚLTIMOS AGREGADOS
# ══════════════════════════════════════════════════════════════════════════════

def get_ultimos_agregados(usuario_id: int, limite: int = 10) -> list:
    """
    Últimos N animes agregados a la lista (cualquier tipo), con fecha y tipo.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    ac.id, ac.titulo, ac.poster_url, ac.rating,
                    la.tipo, la.agregado_en
                FROM lista_animes la
                JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s
                ORDER BY la.agregado_en DESC
                LIMIT %s
                """,
                (usuario_id, limite),
            )
            return [
                {
                    "id":          r[0],
                    "titulo":      r[1],
                    "poster_url":  r[2],
                    "rating":      float(r[3]) if r[3] else None,
                    "tipo":        r[4],
                    "agregado_en": str(r[5]),
                }
                for r in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[DB ERROR get_ultimos_agregados] {e}")
            return []
        finally:
            cursor.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCORE PROMEDIO
# ══════════════════════════════════════════════════════════════════════════════

def get_score_promedio(usuario_id: int) -> dict:
    """
    Rating promedio de los animes vistos del usuario.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT ROUND(AVG(ac.rating)::NUMERIC, 2)
                FROM lista_animes la
                JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s
                  AND la.tipo = 'visto'
                  AND ac.rating IS NOT NULL
                """,
                (usuario_id,),
            )
            row = cursor.fetchone()
            avg = float(row[0]) if row and row[0] else None
            return {"promedio": avg}
        except Exception as e:
            print(f"[DB ERROR get_score_promedio] {e}")
            return {"promedio": None}
        finally:
            cursor.close()
