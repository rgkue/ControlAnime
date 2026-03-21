"""
middleware.py — Seguridad central de ControlAnime
--------------------------------------------------
Responsabilidades:
  1. AuthMiddleware        — verifica sesion valida en todas las rutas privadas.
  2. CSRFMiddleware        — valida X-CSRF-Token en metodos mutantes (POST/PUT/PATCH/DELETE).
  3. SecurityHeadersMiddleware — agrega headers HTTP de seguridad a todas las respuestas,
                                 incluyendo Content-Security-Policy.

Orden de ejecucion (FastAPI aplica middlewares en orden inverso al de declaracion):
  SecurityHeaders  →  CSRF  →  Auth  →  Router
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.database.connection import obtener_usuario_id_por_token, validar_csrf

# ── Rutas completamente publicas (sin sesion) ────────────────────────────────
PUBLIC_PATHS = {
    "/",
    "/login",
    "/registro",
    "/verificar",
    "/recuperar",
    "/favicon.ico",
}

PUBLIC_PREFIXES = (
    "/static/",
    "/favicon",
)

# Rutas de autenticacion: no requieren sesion previa
AUTH_ROUTES = {
    "/login",
    "/logout",
    "/register",
    "/verify-email",
    "/resend-verification",
    "/recuperar",
}

# Rutas de API que cualquiera puede ver sin sesion
API_PUBLIC = {
    "/ranking",
    "/animes/hero",     # carrusel landing page
    "/animes/collage",  # collage fondo login/register
}

# Metodos que modifican estado — requieren CSRF
CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Rutas exentas de CSRF (el servidor genera el token, o son flujos sin cookie de sesion)
CSRF_EXEMPT = {
    "/login",
    "/register",
    "/logout",
    "/verify-email",
    "/resend-verification",
    "/recuperar",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path   = request.url.path
        method = request.method

        print(f"[MW] {method} {path}")

        if method == "OPTIONS":
            return await call_next(request)

        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        if path in PUBLIC_PATHS or path in AUTH_ROUTES:
            return await call_next(request)

        if path in API_PUBLIC:
            return await call_next(request)

        if path == "/dashboard" or path.startswith("/dashboard/"):
            return await call_next(request)

        token = request.cookies.get("session")
        if not token:
            return JSONResponse(
                status_code=401,
                content={"error": "No autenticado"},
                headers={"X-Auth-Required": "true"}
            )

        usuario_id = obtener_usuario_id_por_token(token)
        if not usuario_id:
            # Sesion expirada: instruir al browser a borrar la cookie
            return JSONResponse(
                status_code=401,
                content={"error": "Sesion expirada", "codigo": "SESSION_EXPIRED"},
                headers={
                    "X-Session-Expired": "true",
                    "Set-Cookie": "session=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax"
                }
            )

        request.state.usuario_id = usuario_id
        print(f"[MW] AUTORIZADO uid={usuario_id}")
        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Valida el header X-CSRF-Token en todas las requests mutantes de rutas privadas.
    El token fue generado al hacer login y enviado como cookie 'csrf_token' (no HttpOnly).
    El frontend lo lee de la cookie y lo reenvía como header.
    """
    async def dispatch(self, request: Request, call_next):
        path   = request.url.path
        method = request.method

        if method not in CSRF_METHODS:
            return await call_next(request)

        if path in CSRF_EXEMPT:
            return await call_next(request)

        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        session_token = request.cookies.get("session")
        if not session_token:
            # Sin sesion — AuthMiddleware rechazara luego; no duplicar error
            return await call_next(request)

        csrf_enviado = request.headers.get("X-CSRF-Token", "")
        if not validar_csrf(session_token, csrf_enviado):
            print(f"[CSRF] RECHAZADO {method} {path} — token invalido o ausente")
            return JSONResponse(
                status_code=403,
                content={"error": "CSRF token invalido. Recarga la pagina e intenta de nuevo."}
            )

        print(f"[CSRF] OK {method} {path}")
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Agrega headers de seguridad HTTP a TODAS las respuestas.
    Content-Security-Policy ajustada para permitir:
      - Scripts/estilos inline del dashboard (unsafe-inline necesario por arquitectura actual)
      - Imagenes desde kitsu.io y data: URIs (posters/covers)
      - Fetch a api.mymemory.translated.net (traduccion de sinopsis)
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Previene que el browser infiera el tipo MIME
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Bloquea iframes — protege contra clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content-Security-Policy
        # 'unsafe-inline' en script-src/style-src es necesario porque el dashboard
        # usa JS y CSS inline. En una refactorizacion futura se pueden mover a
        # archivos externos y usar nonces.
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: "
                "https://media.kitsu.app https://media.kitsu.io "
                "https://myanimelist.net https://cdn.myanimelist.net "
                "https://s4.anilist.co; "
            "connect-src 'self' https://api.mymemory.translated.net https://translate.googleapis.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["Content-Security-Policy"] = csp

        # En produccion con HTTPS habilitar:
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
