"""
providers/enricher.py — Orquestador de enriquecimiento secuencial
------------------------------------------------------------------
Estrategia:
  1. AniList  — busca por título → guarda año, temporada, estudio,
                score_count, popularidad, tipo, duración, fechas, anilist_id.
  2. Jikan    — busca por título (o mal_id si ya lo tenemos) →
                completa campos que AniList dejó vacíos + mal_id + géneros MAL.

Reglas:
  - Nunca sobreescribe un campo ya poblado con None/vacío.
  - Si AniList ya dio géneros y Jikan también, Jikan gana (más detallado).
  - Los campos de Kitsu (titulo, sinopsis, poster, cover, rating base) NO
    se tocan aquí. Solo se enriquece lo que Kitsu no provee.
  - Si el enriquecimiento fue hace menos de TTL_DIAS días, se omite.
  - Siempre se llama en un thread daemon (no bloquea requests HTTP).

Uso desde anime_service.py:
    import threading
    from backend.services.providers.enricher import enriquecer_en_background

    threading.Thread(
        target=enriquecer_en_background,
        args=(anime_id, titulo_canonico),
        daemon=True,
    ).start()
"""

from backend.database.connection import get_db
from backend.services.providers import anilist, jikan

TTL_DIAS = 30  # días antes de re-enriquecer


def _necesita_enriquecer(anime_id: str) -> tuple[bool, bool, int | None, int | None]:
    """
    Comprueba si el anime necesita enriquecimiento con AniList y/o Jikan.
    Retorna (necesita_anilist, necesita_jikan, anilist_id_guardado, mal_id_guardado).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT anilist_id, mal_id,
                       enriquecido_anilist_en, enriquecido_jikan_en
                FROM animes_cache WHERE id = %s
            """, (anime_id,))
            row = cursor.fetchone()
            if not row:
                return True, True, None, None

            anilist_id, mal_id, ts_anilist, ts_jikan = row

            from datetime import datetime, timedelta, timezone
            ahora    = datetime.now(timezone.utc)
            ttl      = timedelta(days=TTL_DIAS)

            necesita_anilist = (
                ts_anilist is None or
                (ahora - ts_anilist.replace(tzinfo=timezone.utc)) > ttl
            )
            necesita_jikan = (
                ts_jikan is None or
                (ahora - ts_jikan.replace(tzinfo=timezone.utc)) > ttl
            )
            return necesita_anilist, necesita_jikan, anilist_id, mal_id
        except Exception as e:
            print(f"[ENRICHER] Error al comprobar estado: {e}")
            return True, True, None, None
        finally:
            cursor.close()


def _merge(base: dict, nuevo: dict) -> dict:
    """
    Fusiona nuevo en base. Solo sobreescribe si el valor en base
    es None o cadena vacía, EXCEPTO para genres y mal_id/anilist_id
    que siempre se actualizan si el nuevo tiene valor.
    """
    SIEMPRE_ACTUALIZAR = {"genres", "anilist_id", "mal_id", "score_count", "popularidad"}
    resultado = dict(base)
    for k, v in nuevo.items():
        if v is None:
            continue
        if k in SIEMPRE_ACTUALIZAR:
            resultado[k] = v
        elif not resultado.get(k):
            resultado[k] = v
    return resultado


def _guardar_enriquecimiento(anime_id: str, datos: dict, proveedor: str) -> None:
    """
    Actualiza los campos enriquecidos en animes_cache.
    proveedor: 'anilist' | 'jikan'
    """
    _CAMPOS_PERMITIDOS = {
        "anio", "temporada", "estudio", "score_count", "popularidad",
        "tipo", "duracion", "fecha_inicio", "fecha_fin",
        "anilist_id", "mal_id", "genres",
        # También puede actualizar rating y episodios si son mejores
        "rating", "episodios",
    }
    campos = {k: v for k, v in datos.items() if k in _CAMPOS_PERMITIDOS and v is not None}
    if not campos:
        print(f"[ENRICHER] Sin campos válidos para {proveedor} en anime {anime_id}")
        return

    ts_col = f"enriquecido_{proveedor}_en"
    campos[ts_col] = "NOW()"  # marcador especial

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Construir SET dinámico, con NOW() para el timestamp
            set_parts = []
            valores   = []
            for k, v in campos.items():
                if v == "NOW()":
                    set_parts.append(f"{k} = NOW()")
                else:
                    set_parts.append(f"{k} = %s")
                    valores.append(v)
            valores.append(anime_id)

            cursor.execute(
                f"UPDATE animes_cache SET {', '.join(set_parts)} WHERE id = %s",
                valores,
            )
            conn.commit()
            print(f"[ENRICHER] {proveedor.upper()} → {len(campos)-1} campos actualizados para anime {anime_id}")
        except Exception as e:
            conn.rollback()
            print(f"[ENRICHER] Error al guardar {proveedor}: {e}")
        finally:
            cursor.close()


def enriquecer_en_background(anime_id: str, titulo: str) -> None:
    """
    Punto de entrada principal. Llamar siempre desde un thread daemon.

    Flujo:
      1. Comprobar si necesita enriquecimiento (TTL)
      2. AniList primero → guarda datos + anilist_id
      3. Jikan segundo → completa lo que faltó
    """
    necesita_anilist, necesita_jikan, anilist_id_db, mal_id_db = _necesita_enriquecer(anime_id)

    if not necesita_anilist and not necesita_jikan:
        print(f"[ENRICHER] Anime {anime_id} ya enriquecido y vigente. Skip.")
        return

    datos_fusionados: dict = {}

    # ── Paso 1: AniList ───────────────────────────────────────────
    if necesita_anilist:
        print(f"[ENRICHER] AniList → buscando '{titulo}'")
        datos_al = None

        # Si ya tenemos el anilist_id, usar búsqueda directa (más precisa)
        if anilist_id_db:
            datos_al = anilist.buscar_por_id(anilist_id_db)
        else:
            datos_al = anilist.buscar_por_titulo(titulo)

        if datos_al:
            datos_fusionados = _merge(datos_fusionados, datos_al)
            _guardar_enriquecimiento(anime_id, datos_al, "anilist")
        else:
            print(f"[ENRICHER] AniList no encontró '{titulo}'")

    # ── Paso 2: Jikan ─────────────────────────────────────────────
    if necesita_jikan:
        print(f"[ENRICHER] Jikan → buscando '{titulo}'")
        datos_jk = None

        # Si ya tenemos mal_id, búsqueda directa
        if mal_id_db:
            datos_jk = jikan.buscar_por_id(mal_id_db)
        else:
            datos_jk = jikan.buscar_por_titulo(titulo)

        if datos_jk:
            # Fusionar: Jikan completa los huecos que AniList dejó
            datos_para_guardar = {}
            for k, v in datos_jk.items():
                if v is None:
                    continue
                # Géneros: Jikan siempre gana (más detallado que Kitsu/AniList)
                if k == "genres":
                    datos_para_guardar[k] = v
                # Para el resto, solo guardar si aún no tenemos el dato
                elif not datos_fusionados.get(k):
                    datos_para_guardar[k] = v
                # mal_id siempre
                elif k == "mal_id":
                    datos_para_guardar[k] = v

            if datos_para_guardar:
                _guardar_enriquecimiento(anime_id, datos_para_guardar, "jikan")
            else:
                # Marcar igual como procesado (aunque no hubiera campos nuevos)
                _guardar_enriquecimiento(anime_id, {"mal_id": datos_jk.get("mal_id")}, "jikan")
        else:
            print(f"[ENRICHER] Jikan no encontró '{titulo}'")
