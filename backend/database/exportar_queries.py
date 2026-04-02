"""
exportar_queries.py — Queries para exportar la lista del usuario
----------------------------------------------------------------
Retorna tipos Python puros. Nunca JSONResponse.
"""

from backend.database.connection import get_db

TIPOS_VALIDOS = {"todo", "visto", "pendiente", "favorito"}


def get_lista_exportable(usuario_id: int, tipo: str = "todo") -> list:
    """
    Retorna la lista completa del usuario lista para exportar.
    tipo: 'todo' | 'visto' | 'pendiente' | 'favorito'
    """
    if tipo not in TIPOS_VALIDOS:
        tipo = "todo"

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            filtro = "" if tipo == "todo" else "AND la.tipo = %s"
            params = (usuario_id,) if tipo == "todo" else (usuario_id, tipo)

            cursor.execute(
                f"""
                SELECT
                    ac.titulo,
                    ac.titulo_alternativo,
                    la.tipo,
                    ac.rating,
                    ac.episodios,
                    la.episodios_vistos,
                    ac.genres_es,
                    ac.genres,
                    ac.estado,
                    ac.anio,
                    ac.temporada,
                    ac.estudio,
                    ac.tipo        AS anime_tipo,
                    ac.duracion,
                    la.fecha_inicio,
                    la.fecha_fin,
                    la.agregado_en,
                    ac.poster_url
                FROM lista_animes la
                JOIN animes_cache ac ON ac.id = la.anime_id
                WHERE la.usuario_id = %s {filtro}
                ORDER BY la.agregado_en DESC
                """,
                params,
            )
            cols = [
                "titulo", "titulo_alternativo", "tipo", "rating", "episodios",
                "episodios_vistos", "genres_es", "genres", "estado", "anio",
                "temporada", "estudio", "anime_tipo", "duracion",
                "fecha_inicio", "fecha_fin", "agregado_en", "poster_url",
            ]
            resultado = []
            for row in cursor.fetchall():
                entry = dict(zip(cols, row))
                # Serializar fechas
                for campo in ("fecha_inicio", "fecha_fin", "agregado_en"):
                    if entry[campo]:
                        entry[campo] = str(entry[campo])[:10]  # YYYY-MM-DD
                # Convertir Decimal a float
                if entry["rating"] is not None:
                    entry["rating"] = float(entry["rating"])
                resultado.append(entry)
            return resultado
        except Exception as e:
            print(f"[DB ERROR get_lista_exportable] {e}")
            return []
        finally:
            cursor.close()
