# -- Funciones de autenticacion --
import bcrypt
import re
import uuid
from backend.database.connection import (
    insertar_usuario, obtener_usuario_por_email, crear_sesion,
    guardar_codigo_verificacion, obtener_usuario_id_por_email
)
from backend.services.email_service import generar_codigo, enviar_codigo_verificacion

def email_valido(email: str) -> bool:
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]{2,}\.[a-zA-Z]{2,}$'
    return bool(re.match(patron, email))

def hashear_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verificar_password(password: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(password.encode(), hash_guardado.encode())

def registrar_usuario(email: str, password: str):
    if not email or not password:
        return "campos_vacios"
    if not email_valido(email):
        return "email_invalido"
    if len(password) < 8:
        return "password_corta"

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

    usuario_id, password_hash = usuario
    if not verificar_password(password, password_hash):
        return "credenciales_invalidas"

    token = str(uuid.uuid4())
    # crear_sesion ahora devuelve el csrf_token generado
    csrf_token = crear_sesion(usuario_id, token)
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
