"""
providers/translation.py — Traducción centralizada · ControlAnime
------------------------------------------------------------------
Todo lo relacionado con traducción vive aquí.
El frontend nunca llama APIs externas — recibe los campos ya en español.

Funciones públicas:
  traducir_genres(genres_en: str) -> str
  traducir_sinopsis(texto: str)   -> str | None
"""

import httpx

# ══════════════════════════════════════════════════════════════════════════════
# GÉNEROS — mapa estático (MAL tiene ~60 géneros fijos)
# ══════════════════════════════════════════════════════════════════════════════
# Cualquier género no listado aquí pasa al fallback de traducción automática.

_GENEROS_MAP: dict[str, str] = {
    # Géneros principales
    "Action":           "Acción",
    "Adventure":        "Aventura",
    "Comedy":           "Comedia",
    "Drama":            "Drama",
    "Fantasy":          "Fantasía",
    "Horror":           "Terror",
    "Mystery":          "Misterio",
    "Romance":          "Romance",
    "Sci-Fi":           "Ciencia Ficción",
    "Slice of Life":    "Vida Cotidiana",
    "Sports":           "Deportes",
    "Supernatural":     "Sobrenatural",
    "Thriller":         "Thriller",
    "Ecchi":            "Ecchi",
    "Hentai":           "Hentai",
    "Erotica":          "Erótico",
    "Boys Love":        "Boys Love",
    "Girls Love":       "Girls Love",
    # Temáticas / Themes
    "Isekai":           "Isekai",
    "Mecha":            "Mecha",
    "Music":            "Música",
    "Psychological":    "Psicológico",
    "Magic":            "Magia",
    "School":           "Escolar",
    "Harem":            "Harén",
    "Military":         "Militar",
    "Historical":       "Histórico",
    "Martial Arts":     "Artes Marciales",
    "Super Power":      "Superpoderes",
    "Vampire":          "Vampiros",
    "Samurai":          "Samurái",
    "Space":            "Espacio",
    "Game":             "Videojuegos",
    "Parody":           "Parodia",
    "Cars":             "Automóviles",
    "Demons":           "Demonios",
    "Police":           "Policía",
    "Gore":             "Gore",
    "Survival":         "Supervivencia",
    "Time Travel":      "Viajes en el tiempo",
    "Reincarnation":    "Reencarnación",
    "Strategy Game":    "Juegos de estrategia",
    "Crossdressing":    "Crossdressing",
    "Anthropomorphic":  "Antropomórfico",
    "Gag Humor":        "Humor absurdo",
    "Delinquents":      "Delincuentes",
    "Love Polygon":     "Polígono amoroso",
    "Mythology":        "Mitología",
    "Organized Crime":  "Crimen organizado",
    "Performing Arts":  "Artes escénicas",
    "Racing":           "Carreras",
    "Reverse Harem":    "Harén inverso",
    "Showbiz":          "Espectáculo",
    "Suspense":         "Suspenso",
    "Team Sports":      "Deportes en equipo",
    "Video Game":       "Videojuegos",
    "Visual Arts":      "Artes visuales",
    "Work Life":        "Vida laboral",
    # Demografías
    "Shounen":          "Shōnen",
    "Shoujo":           "Shōjo",
    "Seinen":           "Seinen",
    "Josei":            "Josei",
    "Kids":             "Infantil",
}


def traducir_genres(genres_en: str | None) -> str | None:
    """
    Traduce una cadena de géneros MAL al español.
    Entrada:  "Action, Adventure, Fantasy"
    Salida:   "Acción, Aventura, Fantasía"

    Géneros no encontrados en el mapa estático se traducen
    automáticamente y se añaden al log para revisar.
    Géneros vacíos o None retornan None.
    """
    if not genres_en:
        return None

    generos = [g.strip() for g in genres_en.split(",") if g.strip()]
    traducidos = []
    sin_mapeo  = []

    for g in generos:
        if g in _GENEROS_MAP:
            traducidos.append(_GENEROS_MAP[g])
        else:
            sin_mapeo.append(g)

    # Fallback: traducción automática para los que no están en el mapa
    if sin_mapeo:
        batch = ", ".join(sin_mapeo)
        trad  = _traducir_texto(batch)
        if trad:
            traducidos.extend([t.strip() for t in trad.split(",")])
            print(f"[TRANSLATE] Géneros sin mapeo traducidos: {sin_mapeo}")
        else:
            # Si falla la API, usar el inglés original para no perder datos
            traducidos.extend(sin_mapeo)

    return ", ".join(traducidos) if traducidos else None


# ══════════════════════════════════════════════════════════════════════════════
# SINOPSIS
# ══════════════════════════════════════════════════════════════════════════════

def traducir_sinopsis(texto: str | None) -> str | None:
    """
    Traduce una sinopsis del inglés al español.
    Usa Google primero, MyMemory como fallback.
    Retorna None si la traducción falla o el texto ya está en español.
    """
    if not texto or not texto.strip():
        return None
    # Limitar a 500 chars para respetar límites de las APIs gratuitas
    return _traducir_texto(texto[:500])


# ══════════════════════════════════════════════════════════════════════════════
# MOTOR DE TRADUCCIÓN INTERNO
# ══════════════════════════════════════════════════════════════════════════════

def _traducir_con_google(texto: str) -> str | None:
    """Endpoint no oficial de Google Translate. Sin API key."""
    try:
        resp = httpx.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "es", "dt": "t", "q": texto},
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        data   = resp.json()
        partes = data[0] if data else []
        trad   = "".join(p[0] for p in partes if p and p[0])
        if not trad or trad.strip().lower() == texto.strip().lower():
            return None
        return trad
    except Exception as e:
        print(f"[TRANSLATE] Google error: {e}")
        return None


def _traducir_con_mymemory(texto: str) -> str | None:
    """Fallback: MyMemory (~5000 chars/día gratis)."""
    try:
        resp = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": texto, "langpair": "en|es"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        trad = (data.get("responseData") or {}).get("translatedText", "")
        if not trad or "MYMEMORY WARNING" in trad.upper():
            return None
        if trad.strip().lower() == texto.strip().lower():
            return None
        return trad
    except Exception as e:
        print(f"[TRANSLATE] MyMemory error: {e}")
        return None


def _traducir_texto(texto: str) -> str | None:
    """Google primero, MyMemory como fallback."""
    return _traducir_con_google(texto) or _traducir_con_mymemory(texto)
