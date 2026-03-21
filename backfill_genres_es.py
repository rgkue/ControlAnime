"""
backfill_genres_es.py — Rellena genres_es para todos los animes en BD
----------------------------------------------------------------------
Ejecutar UNA SOLA VEZ después de migrate_genres_es.sql para traducir
los géneros de los animes que ya estaban en la BD antes de que
translation.py existiera.

Usa el mapa estático — sin costo de API, casi instantáneo.

Ejecutar con:
  .venv\Scripts\python.exe backfill_genres_es.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database.connection import init_pool, close_pool, get_db
from backend.services.providers.translation import traducir_genres

init_pool(min_conn=1, max_conn=3)

def run():
    # 1 — Leer todos los animes sin genres_es
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, genres
            FROM animes_cache
            WHERE genres IS NOT NULL AND genres != ''
              AND (genres_es IS NULL OR genres_es = '')
            ORDER BY rating DESC NULLS LAST
        """)
        pendientes = cursor.fetchall()
        cursor.close()

    total = len(pendientes)
    print(f"[BACKFILL] {total} animes sin genres_es")

    if not total:
        print("[BACKFILL] Nada que hacer.")
        return

    # 2 — Traducir y guardar en lotes de 100
    ok = 0
    lote = []

    for anime_id, genres in pendientes:
        genres_es = traducir_genres(genres)
        if genres_es:
            lote.append((genres_es, str(anime_id)))
            ok += 1

        if len(lote) >= 100:
            _guardar_lote(lote)
            print(f"[BACKFILL] {ok}/{total} guardados...")
            lote = []

    if lote:
        _guardar_lote(lote)

    print(f"[BACKFILL] Completo: {ok}/{total} animes con genres_es.")


def _guardar_lote(lote: list) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(
                "UPDATE animes_cache SET genres_es = %s WHERE id = %s",
                lote
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[BACKFILL ERROR] {e}")
        finally:
            cursor.close()


if __name__ == "__main__":
    try:
        run()
    finally:
        close_pool()
