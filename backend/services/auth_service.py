# -- Funciones de autenticacion --
import bcrypt
import re
import uuid
from backend.services.email_service import generar_codigo, enviar_codigo_verificacion
from backend.database.connection import (
    insertar_usuario, obtener_usuario_por_email, crear_sesion,
    guardar_codigo_verificacion, obtener_usuario_id_por_email
)

_PASSWORDS_COMUNES = {
    "12345678","123456789","1234567890","password","password1",
    "qwerty123","abc12345","iloveyou","admin123","welcome1",
    "monkey123","dragon12","master12","sunshine","princess",
    "letmein1","shadow12","michael1","football","baseball1"
}

def email_valido(email: str) -> bool:
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]{2,}\.[a-zA-Z]{2,}$'
    return bool(re.match(patron, email))

def hashear_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verificar_password(password: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(password.encode(), hash_guardado.encode())

def _password_fuerte(password: str):
    """Retorna None si es válida, o un string con el error."""
    import re
    if not password.strip():
        return "password_vacia"
    if len(password) < 8:
        return "password_corta"
    if len(password) > 128:
        return "password_larga"
    if not re.search(r'[A-Z]', password):
        return "password_sin_mayuscula"
    if not re.search(r'[0-9]', password):
        return "password_sin_numero"
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>_\-\+=/\\\'`~\[\];]', password):
        return "password_sin_especial"
    if password.lower() in _PASSWORDS_COMUNES:
        return "password_comun"
    return None

def registrar_usuario(email: str, password: str):
    if not email or not password:
        return "campos_vacios"
    if not email_valido(email):
        return "email_invalido"

    error_pwd = _password_fuerte(password)
    if error_pwd:
        return error_pwd

    password_hash = hashear_password(password)
    resultado = insertar_usuario(email, password_hash)
    print(f"[DEBUG] insertar_usuario retorno: {resultado}")

    if resultado != True:
        return resultado

    usuario_id = obtener_usuario_id_por_email(email)
    print(f"[DEBUG] usuario_id: {usuario_id}")

    if not usuario_id:
        return "error_db"

    codigo = generar_codigo()
    guardar_codigo_verificacion(usuario_id, codigo)
    enviar_codigo_verificacion(email, codigo)

    return {"ok": True, "usuario_id": usuario_id}

def iniciar_sesion(email: str, password: str):
    if not email or not password:
        return "campos_vacios"
    if not email_valido(email):
        return "email_invalido"

    usuario = obtener_usuario_por_email(email)
    if not usuario:
        return "credenciales_invalidas"

    usuario_id, password_hash, email_verificado = usuario  # ← desempacar 3 campos

    if not verificar_password(password, password_hash):
        return "credenciales_invalidas"

    if not email_verificado:                               # ← bloqueo nuevo
        return "email_no_verificado"

    token = str(uuid.uuid4())
    csrf_token: str = crear_sesion(usuario_id, token)
    return {"token": token, "csrf_token": csrf_token}

def cambiar_password(token: str, password_actual: str, password_nueva: str):
    from backend.database.connection import obtener_usuario_por_token, actualizar_perfil
    usuario = obtener_usuario_por_token(token)
    if not usuario:
        return "Sesion invalida"
    email = usuario[0]
    user_db = obtener_usuario_por_email(email)
    if not user_db:
        return "Usuario no encontrado"
    _, password_hash = user_db
    if not verificar_password(password_actual, password_hash):
        return "La contrasena actual es incorrecta"
    nuevo_hash = hashear_password(password_nueva)
    actualizar_perfil(token, {'password_hash': nuevo_hash})
    return True
