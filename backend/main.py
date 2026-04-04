"""
main.py — Aplicación principal ControlAnime
--------------------------------------------
Fase 5: Seguridad completa
  - AuthMiddleware          — verifica sesión válida en rutas privadas
  - CSRFMiddleware          — valida X-CSRF-Token en métodos mutantes
  - SecurityHeadersMiddleware — headers HTTP + Content-Security-Policy
  - Límite de tamaño de request (2MB)
  - /docs /redoc /openapi.json deshabilitados
  - 404 HTML puro, 500 sin detalles internos

Pool de conexiones:
  - init_pool() se llama al arrancar la app (lifespan)
  - close_pool() se llama al apagar la app (lifespan)
  - El pool mantiene 2–10 conexiones reutilizables a PostgreSQL
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Routers
from backend.routers import auth, lista, animes, ranking
from backend.routers import exportar
from backend.routers import estadisticas
from backend.routers import importar

# Middlewares propios
from backend.middleware import AuthMiddleware, CSRFMiddleware, SecurityHeadersMiddleware

# Pool de conexiones
from backend.database.connection import init_pool, close_pool

# Límite máximo de request: 2MB
MAX_REQUEST_SIZE = 2 * 1024 * 1024


# ── Lifespan — arranque y apagado de la app ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Código que corre UNA VEZ al arrancar y al apagar la app.
    - Arranque : inicializa el pool de conexiones a PostgreSQL.
    - Apagado  : cierra todas las conexiones del pool limpiamente.
    """
    init_pool(min_conn=2, max_conn=10)
    yield
    close_pool()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


# ── Middleware de tamaño máximo de request ────────────────────────────────────
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(
            status_code=413,
            content={"error": "Payload demasiado grande (máximo 2MB)"}
        )
    return await call_next(request)


# ── Middlewares (orden: primero declarado = último en ejecutarse) ─────────────
#
# Flujo real de una request:
#   SecurityHeaders → CSRF → Auth → Router → handler
#
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://controlanime.com",
        "http://controlanime.com",
        "http://localhost",
        "http://localhost:80",
        "http://localhost:8000",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With", "Cookie", "X-CSRF-Token"],
)


# ── Archivos estáticos ────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# --- Ruta de Ranking (Excepcion) ---
@app.get("/ranking")
async def ranking_page():
    return FileResponse("frontend/pages/ranking/index.html")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(lista.router)
app.include_router(animes.router)
app.include_router(ranking.router)
app.include_router(estadisticas.router)
app.include_router(exportar.router)
app.include_router(importar.router)

# ── Rutas de páginas HTML ─────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("frontend/pages/index/index.html")

@app.get("/login")
async def login_page():
    return FileResponse("frontend/pages/login/index.html")

@app.get("/registro")
async def registro_page():
    return FileResponse("frontend/pages/register/index.html")

@app.get("/verificar")
async def verificar_page():
    return FileResponse("frontend/pages/verify_email/index.html")

@app.get("/dashboard")
async def dashboard_page():
    return FileResponse("frontend/pages/dashboard/index.html")

@app.get("/dashboard/anime/{anime_id}")
async def dashboard_anime(anime_id: str):
    return FileResponse("frontend/pages/dashboard/anime/index.html")

@app.get("/mi-lista")
async def milista_page():
    return FileResponse("frontend/pages/mi-lista/index.html")

@app.get("/mi-lista/anime/{anime_id}")
async def milista_anime(anime_id: str):
    return FileResponse("frontend/pages/mi-lista/anime/index.html")

@app.get("/mi-top")
async def mitop_page():
    return FileResponse("frontend/pages/mi-top/index.html")

@app.get("/populares")
async def populares_page():
    return FileResponse("frontend/pages/populares/index.html")

@app.get("/populares/peliculas")
async def peliculas_page():
    return FileResponse("frontend/pages/populares/peliculas/index.html")

@app.get("/populares/temporada")
async def temporada_page():
    return FileResponse("frontend/pages/populares/temporada/index.html")

@app.get("/emision")
async def emision_page():
    return FileResponse("frontend/pages/emision/index.html")

@app.get("/usuario/{id}")
async def usuario_page(id: str):
    return FileResponse("frontend/pages/usuarios/index.html")

@app.get("/configuracion")
async def configuracion_page():
    return FileResponse("frontend/pages/configuracion/index.html")

@app.get("/estadisticas")
async def estadisticas_page():
    return FileResponse("frontend/pages/estadisticas/index.html")

@app.get("/exportar")
async def exportar_page():
    return FileResponse("frontend/pages/exportar/index.html")

@app.get("/importar")
async def importar_page():
    return FileResponse("frontend/pages/importar/index.html")

# ── Handlers de error ─────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return HTMLResponse(
        content=_html_404(request.url.path),
        status_code=404,
        headers={"Content-Type": "text/html; charset=utf-8"}
    )

@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    return JSONResponse(status_code=405, content={"error": "Método no permitido"})

@app.exception_handler(413)
async def payload_too_large_handler(request: Request, exc):
    return JSONResponse(status_code=413, content={"error": "Payload demasiado grande"})

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    print(f"[ERROR 500] {request.method} {request.url.path} — {exc}")
    return JSONResponse(status_code=500, content={"error": "Error interno del servidor"})


def _html_404(path: str) -> str:
    safe_path = path[:80].replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>404 — Página no encontrada · ControlAnime</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background: #0f0f0f; color: #e5e5e5;
      font-family: 'Segoe UI', Arial, sans-serif;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; text-align: center; padding: 24px;
    }}
    .container {{ max-width: 480px; }}
    .brand {{ font-size: 1rem; font-weight: 700; letter-spacing: .15em;
      text-transform: uppercase; margin-bottom: 40px; }}
    .brand span {{ color: #f97316; }}
    .code {{ font-size: 6rem; font-weight: 900; line-height: 1;
      color: #f97316; letter-spacing: -4px; margin-bottom: 16px; }}
    .title {{ font-size: 1.4rem; font-weight: 600; color: #fff; margin-bottom: 12px; }}
    .desc {{ font-size: .95rem; color: #777; margin-bottom: 8px; line-height: 1.6; }}
    .path {{ display: inline-block; background: #1a1a1a; border: 1px solid #2a2a2a;
      border-radius: 6px; padding: 6px 14px; font-family: monospace;
      font-size: .85rem; color: #f97316; margin: 16px 0 32px; word-break: break-all; }}
    .btn {{ display: inline-block; background: #f97316; color: #000;
      font-weight: 700; font-size: .9rem; padding: 12px 28px;
      border-radius: 8px; text-decoration: none; transition: opacity .15s; }}
    .btn:hover {{ opacity: .85; }}
    .footer {{ margin-top: 48px; font-size: .75rem; color: #444; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="brand"><span>CONTROL</span>ANIME</div>
    <div class="code">404</div>
    <div class="title">Página no encontrada</div>
    <p class="desc">La ruta que buscas no existe o no tienes permiso para acceder.</p>
    <div class="path">{safe_path}</div><br>
    <a href="/" class="btn">Volver al inicio</a>
    <div class="footer">ControlAnime &copy; 2026</div>
  </div>
</body>
</html>"""
