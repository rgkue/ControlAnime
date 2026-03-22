"""
auth.py — Endpoints de autenticación
--------------------------------------
Fase 5:
  - Login envía cookie csrf_token (no HttpOnly) para que JS la lea
  - Modelos Pydantic con longitudes máximas y validación estricta
  - Rate limiting en login, registro y reenvío de código
  - /me y /update-profile usan request.state.usuario_id del middleware
  - Logout invalida sesión en BD + borra ambas cookies correctamente

Refactor: reemplaza get_connection() por get_db() context manager.
"""

import time
import os
import re
from collections import defaultdict

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, field_validator
from typing import Optional

from backend.services.auth_service import (
    registrar_usuario, iniciar_sesion, cambiar_password
)
from backend.database.connection import (
    get_db,
    verificar_codigo, obtener_email_por_id,
    obtener_usuario_por_token, actualizar_perfil,
    invalidar_sesion, guardar_codigo_verificacion,
    obtener_usuario_id_por_token, obtener_usuario_id_por_email,
    obtener_sesiones_activas, cerrar_sesion_por_id, cerrar_otras_sesiones,
    eliminar_lista_usuario, eliminar_cuenta_usuario,
)
from backend.services.auth_service import generar_codigo, hashear_password
from backend.services.email_service import enviar_codigo_verificacion, enviar_codigo_recuperacion

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Rate limiting simple en memoria ──────────────────────────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)

def _check_rate_limit(ip: str, max_intentos: int = 10, ventana_seg: int = 60) -> bool:
    ahora = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if ahora - t < ventana_seg]
    if len(_rate_store[ip]) >= max_intentos:
        return False
    _rate_store[ip].append(ahora)
    return True

def _ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class DatosRegistro(BaseModel):
    model_config = {"extra": "forbid"}
    email:    str
    password: str

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 254:
            raise ValueError("Email demasiado largo")
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]{2,}\.[a-zA-Z]{2,}$', v):
            raise ValueError("Formato de email inválido")
        return v

@field_validator("password")
@classmethod
def password_valida(cls, v: str) -> str:
    COMUNES = {
        "12345678","123456789","1234567890","password","password1",
        "qwerty123","abc12345","iloveyou","admin123","welcome1",
        "monkey123","dragon12","master12","sunshine","princess",
        "letmein1","shadow12","michael1","football","baseball1"
    }
    if not v.strip():
        raise ValueError("La contraseña no puede estar vacía")
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if len(v) > 128:
        raise ValueError("Contraseña demasiado larga")
    if not re.search(r'[A-Z]', v):
        raise ValueError("La contraseña debe tener al menos una letra mayúscula")
    if not re.search(r'[0-9]', v):
        raise ValueError("La contraseña debe tener al menos un número")
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>_\-\+=/\\\'`~\[\];]', v):
        raise ValueError("La contraseña debe tener al menos un carácter especial")
    if v.lower() in COMUNES:
        raise ValueError("La contraseña es demasiado común, elige una más segura")
    return v

class DatosLogin(BaseModel):
    model_config = {"extra": "forbid"}
    email:    str
    password: str

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str) -> str:
        return v.strip().lower()[:254]

    @field_validator("password")
    @classmethod
    def password_longitud(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Contraseña inválida")
        return v


class DatosPerfil(BaseModel):
    model_config = {"extra": "forbid"}
    username:       Optional[str]  = None
    foto_perfil:    Optional[str]  = None
    perfil_publico: Optional[bool] = None
    instagram:      Optional[str]  = None
    discord:        Optional[str]  = None
    tiktok:         Optional[str]  = None

    @field_validator("username")
    @classmethod
    def username_valido(cls, v):
        if v is None:
            return v
        v = v.strip()
        if len(v) > 32:
            raise ValueError("Username máximo 32 caracteres")
        if not re.match(r'^[a-zA-Z0-9_.\-áéíóúÁÉÍÓÚñÑ ]+$', v):
            raise ValueError("Username contiene caracteres no permitidos")
        return v

    @field_validator("instagram", "discord", "tiktok")
    @classmethod
    def red_usuario(cls, v):
        if v is None:
            return v
        v = v.strip().lstrip("@")
        if len(v) > 64:
            raise ValueError("Nombre de usuario demasiado largo")
        return v

    @field_validator("foto_perfil")
    @classmethod
    def foto_tamano(cls, v):
        if v is None:
            return v
        if len(v) > 4_200_000:
            raise ValueError("Imagen demasiado grande (max 3MB)")
        return v


class DatosPassword(BaseModel):
    model_config = {"extra": "forbid"}
    password_actual: str
    password_nueva:  str

    @field_validator("password_actual", "password_nueva")
    @classmethod
    def longitud(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Contraseña demasiado larga")
        return v

    @field_validator("password_nueva")
    @classmethod
    def nueva_suficiente(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La contraseña no puede estar vacía")
        if len(v) < 8:
            raise ValueError("La contraseña nueva debe tener al menos 8 caracteres")
        return v



class DatosApariencia(BaseModel):
    model_config = {"extra": "forbid"}
    perfil_header_color:  Optional[str]  = None
    perfil_header_imagen: Optional[str]  = None
    perfil_publico:       Optional[bool] = None

    @field_validator("perfil_header_color")
    @classmethod
    def color_valido(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not re.match(r'^#[0-9a-fA-F]{6}$', v):
            raise ValueError("Color inválido. Usa formato hex (#rrggbb)")
        return v

    @field_validator("perfil_header_imagen")
    @classmethod
    def imagen_tamano(cls, v):
        if v is None:
            return v
        if len(v) > 4_200_000:
            raise ValueError("Imagen demasiado grande (max 3MB)")
        return v


class DatosEmail(BaseModel):
    model_config = {"extra": "forbid"}
    email_nuevo:    str
    password_actual: str

    @field_validator("email_nuevo")
    @classmethod
    def email_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 254:
            raise ValueError("Email demasiado largo")
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]{2,}\.[a-zA-Z]{2,}$', v):
            raise ValueError("Formato de email inválido")
        return v

    @field_validator("password_actual")
    @classmethod
    def pwd_longitud(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Contraseña inválida")
        return v


class DatosEliminarCuenta(BaseModel):
    model_config = {"extra": "forbid"}
    password: str

    @field_validator("password")
    @classmethod
    def pwd_len(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Contraseña inválida")
        return v

# ── Páginas HTML ──────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
def pagina_register():
    with open(os.path.join(BASE_DIR, "frontend", "pages", "register", "index.html"), encoding="utf-8") as f:
        return f.read()

@router.get("/login", response_class=HTMLResponse)
def pagina_login():
    with open(os.path.join(BASE_DIR, "frontend", "pages", "login", "index.html"), encoding="utf-8") as f:
        return f.read()

@router.get("/verify-email", response_class=HTMLResponse)
def pagina_verify():
    with open(os.path.join(BASE_DIR, "frontend", "pages", "verify_email", "index.html"), encoding="utf-8") as f:
        return f.read()


# ── Registro y verificación ───────────────────────────────────────────────────

@router.post("/register")
def register(request: Request, datos: DatosRegistro):
    ip = _ip(request)
    if not _check_rate_limit(f"reg:{ip}", max_intentos=5, ventana_seg=600):
        return JSONResponse(status_code=429, content={"error": "Demasiados intentos. Espera unos minutos."})

    resultado = registrar_usuario(datos.email, datos.password)

    if resultado == "email_duplicado":
        return JSONResponse(status_code=400, content={"error": "Ese email ya está registrado"})
    if resultado == "password_corta":
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos 8 caracteres"})
    if resultado == "campos_vacios":
        return JSONResponse(status_code=400, content={"error": "Email y contraseña son requeridos"})
    if resultado == "email_invalido":
        return JSONResponse(status_code=400, content={"error": "El email no tiene un formato válido"})
    if resultado == "error_db":
        return JSONResponse(status_code=500, content={"error": "Error interno del servidor"})
    if resultado == "password_sin_mayuscula":
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos una letra mayúscula"})
    if resultado == "password_sin_numero":
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos un número"})
    if resultado == "password_sin_especial":
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos un carácter especial (!@#$...)"})
    if resultado == "password_comun":
        return JSONResponse(status_code=400, content={"error": "La contraseña es demasiado común, elige una más segura"})
    if resultado == "password_vacia":
        return JSONResponse(status_code=400, content={"error": "La contraseña no puede estar vacía"})
    if resultado == "password_larga":
        return JSONResponse(status_code=400, content={"error": "Contraseña demasiado larga"})
    if resultado == "password_sin_mayuscula":
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos una letra mayúscula"})
    if resultado == "password_sin_numero":
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos un número"})
    if resultado == "password_sin_especial":
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos un carácter especial (!@#$...)"})
    if resultado == "password_comun":
        return JSONResponse(status_code=400, content={"error": "La contraseña es demasiado común, elige una más segura"})
    if resultado == "password_vacia":
        return JSONResponse(status_code=400, content={"error": "La contraseña no puede estar vacía"})
    if resultado == "password_larga":
        return JSONResponse(status_code=400, content={"error": "Contraseña demasiado larga"})

    respuesta = JSONResponse(status_code=201, content={"mensaje": "Código enviado a tu correo"})
    respuesta.set_cookie(
        key="pending_uid",
        value=str(resultado["usuario_id"]),
        httponly=True,
        samesite="lax",
        path="/"
    )
    return respuesta


@router.post("/login")
def login(request: Request, datos: DatosLogin):
    ip = _ip(request)
    if not _check_rate_limit(f"login:{ip}", max_intentos=10, ventana_seg=60):
        return JSONResponse(status_code=429, content={"error": "Demasiados intentos. Espera un minuto."})

    resultado = iniciar_sesion(datos.email, datos.password)

    if resultado == "campos_vacios":
        return JSONResponse(status_code=400, content={"error": "Email y contraseña son requeridos"})
    if resultado == "email_invalido":
        return JSONResponse(status_code=400, content={"error": "El email no tiene un formato válido"})
    if resultado == "credenciales_invalidas":
        return JSONResponse(status_code=401, content={"error": "Email o contraseña incorrectos"})
    if resultado == "email_no_verificado":
        return JSONResponse(status_code=403, content={"error": "Debes verificar tu correo antes de iniciar sesión"})

    token      = resultado["token"]
    csrf_token = resultado["csrf_token"]

    print(f"[AUTH] Login exitoso — token generado")
    respuesta = JSONResponse(status_code=200, content={"mensaje": "Sesión iniciada"})
    respuesta.set_cookie(
        key="session", value=token,
        httponly=True, samesite="lax", path="/",
        max_age=7 * 24 * 3600
        # secure=True  # habilitar con HTTPS
    )
    respuesta.set_cookie(
        key="csrf_token", value=csrf_token,
        httponly=False, samesite="lax", path="/",
        max_age=7 * 24 * 3600
        # secure=True  # habilitar con HTTPS
    )
    return respuesta


@router.post("/verify-email")
def verify_email(request: Request, datos: dict):
    ip = _ip(request)
    if not _check_rate_limit(f"verify:{ip}", max_intentos=10, ventana_seg=900):
        return JSONResponse(status_code=429, content={"error": "Demasiados intentos. Espera unos minutos."})

    usuario_id = request.cookies.get("pending_uid")
    if not usuario_id:
        return JSONResponse(status_code=400, content={"error": "Sesión expirada, regístrate de nuevo"})

    codigo = str(datos.get("codigo", "")).strip()
    if not codigo or len(codigo) > 10:
        return JSONResponse(status_code=400, content={"error": "Ingresa el código"})

    ok = verificar_codigo(int(usuario_id), codigo)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "Código incorrecto o expirado"})

    return JSONResponse(status_code=200, content={"mensaje": "Cuenta verificada correctamente"})


@router.post("/resend-verification")
def resend_verification(request: Request):
    ip = _ip(request)
    if not _check_rate_limit(f"resend:{ip}", max_intentos=3, ventana_seg=600):
        return JSONResponse(status_code=429, content={"error": "Demasiados reenvíos. Espera unos minutos."})

    usuario_id = request.cookies.get("pending_uid")
    if not usuario_id:
        return JSONResponse(status_code=400, content={"error": "Sesión expirada, regístrate de nuevo"})

    email = obtener_email_por_id(int(usuario_id))
    if not email:
        return JSONResponse(status_code=400, content={"error": "Usuario no encontrado"})

    codigo = generar_codigo()
    guardar_codigo_verificacion(int(usuario_id), codigo)
    enviar_codigo_verificacion(email, codigo)
    return JSONResponse(status_code=200, content={"mensaje": "Código reenviado"})


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get("session")
    if token:
        invalidar_sesion(token)
        print(f"[AUTH] Logout — sesión invalidada en BD")
    respuesta = JSONResponse(status_code=200, content={"mensaje": "Sesión cerrada"})
    respuesta.set_cookie(key="session",    value="", httponly=True,  samesite="lax", path="/", max_age=0)
    respuesta.set_cookie(key="csrf_token", value="", httponly=False, samesite="lax", path="/", max_age=0)
    return respuesta


# ── Endpoints privados (protegidos por AuthMiddleware) ────────────────────────

@router.get("/me")
def me(request: Request):
    """
    Devuelve datos del usuario autenticado y su lista completa.
    Usa request.state.usuario_id inyectado por el middleware.
    """
    token = request.cookies.get("session")
    usuario = obtener_usuario_por_token(token)
    if not usuario:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})

    usuario_id = request.state.usuario_id
    lista = {"visto": [], "pendiente": [], "favorito": []}

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT a.id, a.titulo, a.titulo_alternativo, a.poster_url,
                           a.cover_url, a.rating, a.episodios, a.estado, la.tipo, la.agregado_en
                    FROM lista_animes la
                    JOIN animes_cache a ON a.id = la.anime_id
                    WHERE la.usuario_id = %s
                    ORDER BY la.agregado_en DESC
                """, (usuario_id,))
                for row in cursor.fetchall():
                    tipo = row[8]
                    if tipo not in lista:
                        lista[tipo] = []
                    lista[tipo].append({
                        "id":                 row[0],
                        "titulo":             row[1],
                        "titulo_alternativo": row[2],
                        "poster_url":         row[3],
                        "cover_url":          row[4],
                        "rating":             float(row[5]) if row[5] else None,
                        "episodios":          row[6],
                        "estado":             row[7],
                        "agregado_en":        str(row[9]) if row[9] else None,
                    })
            finally:
                cursor.close()
    except Exception as e:
        print(f"[DB ERROR /me lista] {e}")

    creado_en = usuario[1]
    return JSONResponse(status_code=200, content={
        "email":          usuario[0],
        "creado_en":      creado_en.isoformat() if hasattr(creado_en, "isoformat") else str(creado_en),
        "username":       usuario[2] or "",
        "foto_perfil":    usuario[3] or None,
        "perfil_publico": usuario[4] or False,
        "instagram":      usuario[5] or "",
        "discord":        usuario[6] or "",
        "tiktok":         usuario[7] or "",
        "lista":          lista,
    })


@router.post("/update-profile")
def update_profile(request: Request, datos: DatosPerfil):
    token = request.cookies.get("session")
    ok = actualizar_perfil(token, datos.model_dump(exclude_none=True))
    if not ok:
        return JSONResponse(status_code=500, content={"error": "Error al actualizar"})
    return JSONResponse(status_code=200, content={"mensaje": "Perfil actualizado"})


@router.post("/update-password")
def update_password(request: Request, datos: DatosPassword):
    token = request.cookies.get("session")
    resultado = cambiar_password(token, datos.password_actual, datos.password_nueva)
    if resultado is not True:
        return JSONResponse(status_code=400, content={"error": resultado})
    return JSONResponse(status_code=200, content={"mensaje": "Contraseña actualizada"})


# ── Recuperación de contraseña (sin sesión activa) ────────────────────────────

@router.post("/recuperar-contrasena")
def recuperar_contrasena(request: Request, datos: dict):
    """
    Paso 1: el usuario ingresa su email.
    Siempre responde igual para no revelar si el email existe.
    """
    ip = _ip(request)
    if not _check_rate_limit(f"recuperar:{ip}", max_intentos=5, ventana_seg=600):
        return JSONResponse(status_code=429, content={"error": "Demasiados intentos. Espera unos minutos."})

    email = str(datos.get("email", "")).strip().lower()
    if not email or len(email) > 254:
        return JSONResponse(status_code=400, content={"error": "Ingresa un email válido"})

    usuario_id = obtener_usuario_id_por_email(email)
    if usuario_id:
        codigo = generar_codigo()
        guardar_codigo_verificacion(usuario_id, codigo)
        enviar_codigo_recuperacion(email, codigo)
        print(f"[RECUPERAR] Código enviado a {email}")

    return JSONResponse(status_code=200, content={"mensaje": "Si ese correo está registrado, recibirás un código."})


@router.post("/cambiar-contrasena-reset")
def cambiar_contrasena_reset(request: Request, datos: dict):
    """
    Paso 2: valida el código y guarda la nueva contraseña.
    No requiere sesión activa.
    """
    ip = _ip(request)
    if not _check_rate_limit(f"reset:{ip}", max_intentos=10, ventana_seg=600):
        return JSONResponse(status_code=429, content={"error": "Demasiados intentos. Espera unos minutos."})

    email          = str(datos.get("email", "")).strip().lower()
    codigo         = str(datos.get("codigo", "")).strip()
    password_nueva = str(datos.get("password_nueva", ""))

    if not email or not codigo or not password_nueva:
        return JSONResponse(status_code=400, content={"error": "Faltan datos"})
    if not password_nueva.strip():
        return JSONResponse(status_code=400, content={"error": "La contraseña no puede estar vacía"})
    if len(password_nueva) < 8:
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos 8 caracteres"})
    if len(password_nueva) > 128:
        return JSONResponse(status_code=400, content={"error": "Contraseña demasiado larga"})

    usuario_id = obtener_usuario_id_por_email(email)
    if not usuario_id:
        return JSONResponse(status_code=400, content={"error": "Código incorrecto o expirado"})

    ok = verificar_codigo(usuario_id, codigo)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "Código incorrecto o expirado"})

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                nuevo_hash = hashear_password(password_nueva)
                cursor.execute(
                    "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                    (nuevo_hash, usuario_id),
                )
                conn.commit()
                print(f"[RECUPERAR] Contraseña actualizada para usuario {usuario_id}")
            finally:
                cursor.close()
    except Exception as e:
        print(f"[DB ERROR cambiar-contrasena-reset] {e}")
        return JSONResponse(status_code=500, content={"error": "Error interno"})

    return JSONResponse(status_code=200, content={"mensaje": "Contraseña actualizada correctamente"})

# ── Configuración — Sesiones ──────────────────────────────────────────────────

@router.get("/sesiones")
def listar_sesiones(request: Request):
    token = request.cookies.get("session")
    usuario_id = obtener_usuario_id_por_token(token)
    if not usuario_id:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})
    sesiones = obtener_sesiones_activas(usuario_id)
    return JSONResponse(status_code=200, content={"sesiones": sesiones, "token_actual": token})


@router.delete("/sesiones/{sesion_id}")
def cerrar_sesion(request: Request, sesion_id: int):
    token = request.cookies.get("session")
    usuario_id = obtener_usuario_id_por_token(token)
    if not usuario_id:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})
    ok = cerrar_sesion_por_id(sesion_id, usuario_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Sesión no encontrada"})
    return JSONResponse(status_code=200, content={"mensaje": "Sesión cerrada"})


@router.post("/sesiones/cerrar-otras")
def cerrar_otras(request: Request):
    token = request.cookies.get("session")
    usuario_id = obtener_usuario_id_por_token(token)
    if not usuario_id:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})
    cerrar_otras_sesiones(usuario_id, token)
    return JSONResponse(status_code=200, content={"mensaje": "Otras sesiones cerradas"})


# ── Configuración — Apariencia ────────────────────────────────────────────────

@router.post("/update-apariencia")
def update_apariencia(request: Request, datos: DatosApariencia):
    token = request.cookies.get("session")
    ok = actualizar_perfil(token, datos.model_dump(exclude_none=True))
    if not ok:
        return JSONResponse(status_code=500, content={"error": "Error al actualizar"})
    return JSONResponse(status_code=200, content={"mensaje": "Apariencia actualizada"})


# ── Configuración — Email ─────────────────────────────────────────────────────

@router.post("/update-email")
def update_email(request: Request, datos: DatosEmail):
    from backend.services.auth_service import verificar_password as vp
    token = request.cookies.get("session")
    usuario_id = obtener_usuario_id_por_token(token)
    if not usuario_id:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})

    # Verificar password actual
    from backend.database.connection import obtener_usuario_por_token as gup
    usuario = gup(token)
    if not usuario:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})

    from backend.database.connection import get_db as gdb
    with gdb() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT password_hash FROM usuarios WHERE id = %s", (usuario_id,))
            row = cursor.fetchone()
            if not row or not vp(datos.password_actual, row[0]):
                return JSONResponse(status_code=400, content={"error": "Contraseña incorrecta"})
            # Verificar que el nuevo email no esté en uso
            cursor.execute("SELECT id FROM usuarios WHERE email = %s", (datos.email_nuevo,))
            if cursor.fetchone():
                return JSONResponse(status_code=400, content={"error": "Ese email ya está en uso"})
            # Guardar pending_email y enviar código
            cursor.execute("UPDATE usuarios SET pending_email = %s WHERE id = %s", (datos.email_nuevo, usuario_id))
            conn.commit()
        finally:
            cursor.close()

    from backend.services.email_service import enviar_codigo_verificacion as env_cod
    from backend.services.auth_service import generar_codigo as gc
    from backend.database.connection import guardar_codigo_verificacion as gcv
    codigo = gc()
    gcv(usuario_id, codigo)
    env_cod(datos.email_nuevo, codigo)
    return JSONResponse(status_code=200, content={"mensaje": "Código enviado al nuevo email"})


@router.post("/confirmar-email")
def confirmar_email(request: Request, datos: dict):
    token = request.cookies.get("session")
    usuario_id = obtener_usuario_id_por_token(token)
    if not usuario_id:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})
    codigo = str(datos.get("codigo", "")).strip()
    if not codigo:
        return JSONResponse(status_code=400, content={"error": "Código requerido"})
    from backend.database.connection import confirmar_cambio_email
    resultado = confirmar_cambio_email(usuario_id, codigo)
    if resultado == "sin_pending":
        return JSONResponse(status_code=400, content={"error": "No hay cambio de email pendiente"})
    if resultado == "codigo_invalido":
        return JSONResponse(status_code=400, content={"error": "Código incorrecto o expirado"})
    if resultado == "error_db":
        return JSONResponse(status_code=500, content={"error": "Error interno"})
    return JSONResponse(status_code=200, content={"mensaje": "Email actualizado correctamente"})


# ── Configuración — Zona de peligro ──────────────────────────────────────────

@router.post("/eliminar-lista")
def eliminar_lista(request: Request, datos: DatosEliminarCuenta):
    from backend.services.auth_service import verificar_password as vp
    token = request.cookies.get("session")
    usuario_id = obtener_usuario_id_por_token(token)
    if not usuario_id:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT password_hash FROM usuarios WHERE id = %s", (usuario_id,))
            row = cursor.fetchone()
            if not row or not vp(datos.password, row[0]):
                return JSONResponse(status_code=400, content={"error": "Contraseña incorrecta"})
        finally:
            cursor.close()
    ok = eliminar_lista_usuario(usuario_id)
    if not ok:
        return JSONResponse(status_code=500, content={"error": "Error al eliminar la lista"})
    return JSONResponse(status_code=200, content={"mensaje": "Lista eliminada correctamente"})


@router.post("/eliminar-cuenta")
def eliminar_cuenta(request: Request, datos: DatosEliminarCuenta):
    from backend.services.auth_service import verificar_password as vp
    token = request.cookies.get("session")
    usuario_id = obtener_usuario_id_por_token(token)
    if not usuario_id:
        return JSONResponse(status_code=401, content={"error": "Sesión inválida"})
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT password_hash FROM usuarios WHERE id = %s", (usuario_id,))
            row = cursor.fetchone()
            if not row or not vp(datos.password, row[0]):
                return JSONResponse(status_code=400, content={"error": "Contraseña incorrecta"})
        finally:
            cursor.close()
    ok = eliminar_cuenta_usuario(usuario_id)
    if not ok:
        return JSONResponse(status_code=500, content={"error": "Error al eliminar la cuenta"})
    respuesta = JSONResponse(status_code=200, content={"mensaje": "Cuenta eliminada"})
    respuesta.set_cookie(key="session",    value="", httponly=True,  samesite="lax", path="/", max_age=0)
    respuesta.set_cookie(key="csrf_token", value="", httponly=False, samesite="lax", path="/", max_age=0)
    return respuesta
