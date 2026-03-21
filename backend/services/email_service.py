import smtplib
import random
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER   = os.getenv("SMTP_SERVER", "smtp-relay.brevo.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL  = os.getenv("SENDER_EMAIL")
SENDER_NAME   = os.getenv("SENDER_NAME", "ControlAnime No-Reply")


def generar_codigo() -> str:
    """Genera un código numérico de 6 dígitos."""
    return str(random.randint(100000, 999999))


def _build_html(code: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verifica tu cuenta</title>
</head>
<body style="
    margin: 0;
    padding: 0;
    background-color: #090909;
    font-family: Arial, Helvetica, sans-serif;
    color: #e8e8e8;
">

<table width="100%" cellpadding="0" cellspacing="0" style="padding: 48px 0;">
    <tr>
        <td align="center">

            <table width="580" cellpadding="0" cellspacing="0" style="
                background-color: #111111;
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid #222222;
            ">

                <!-- HEADER -->
                <tr>
                    <td style="
                        padding: 28px 40px;
                        border-bottom: 1px solid #222222;
                    ">
                        <span style="
                            font-family: Arial Black, sans-serif;
                            font-size: 22px;
                            font-weight: 900;
                            letter-spacing: 0.06em;
                            text-transform: uppercase;
                        ">
                            <span style="color: #f97316;">Control</span><span style="color: #e8e8e8;">Anime</span>
                        </span>
                    </td>
                </tr>

                <!-- BODY -->
                <tr>
                    <td style="padding: 40px;">

                        <p style="
                            font-size: 11px;
                            letter-spacing: 0.2em;
                            text-transform: uppercase;
                            color: #f97316;
                            font-weight: bold;
                            margin: 0 0 16px 0;
                        ">Verificación de cuenta</p>

                        <h1 style="
                            font-size: 28px;
                            font-weight: 900;
                            color: #ffffff;
                            margin: 0 0 16px 0;
                            line-height: 1.1;
                        ">Confirma tu correo electrónico</h1>

                        <p style="
                            font-size: 15px;
                            line-height: 1.7;
                            color: #777777;
                            margin: 0 0 32px 0;
                        ">
                            Gracias por registrarte en <strong style="color: #e8e8e8;">ControlAnime</strong>.
                            Ingresa el siguiente código en la página de verificación para activar tu cuenta.
                        </p>

                        <!-- CÓDIGO -->
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
                            <tr>
                                <td align="center">
                                    <div style="
                                        display: inline-block;
                                        background-color: #181818;
                                        border: 1px solid #222222;
                                        border-left: 4px solid #f97316;
                                        border-radius: 6px;
                                        padding: 20px 48px;
                                    ">
                                        <span style="
                                            font-size: 36px;
                                            font-weight: 900;
                                            letter-spacing: 10px;
                                            color: #f97316;
                                            font-family: 'Courier New', monospace;
                                        ">{code}</span>
                                    </div>
                                </td>
                            </tr>
                        </table>

                        <p style="
                            font-size: 13px;
                            color: #444444;
                            margin: 0;
                            line-height: 1.6;
                        ">
                            Este código expira en <strong style="color: #777777;">15 minutos</strong>.
                            Si no creaste esta cuenta, puedes ignorar este mensaje.
                        </p>

                    </td>
                </tr>

                <!-- FOOTER -->
                <tr>
                    <td style="
                        padding: 20px 40px;
                        border-top: 1px solid #222222;
                        background-color: #0a0a0a;
                    ">
                        <p style="
                            font-size: 11px;
                            color: #444444;
                            margin: 0;
                            text-align: center;
                            letter-spacing: 0.05em;
                        ">
                            ControlAnime · Proyecto personal sin fines de lucro · No respondas a este correo
                        </p>
                    </td>
                </tr>

            </table>

        </td>
    </tr>
</table>

</body>
</html>
"""


def enviar_codigo_verificacion(to_email: str, code: str) -> bool:
    """
    Envía el correo de verificación.
    Retorna True si se envió correctamente, False si falló.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"]      = to_email
        msg["Subject"] = "Verifica tu cuenta en ControlAnime"
        msg["X-Mailer"] = "ControlAnime Mailer"

        # Texto plano como fallback
        texto_plano = f"""
ControlAnime — Verificación de cuenta

Tu código de verificación es: {code}

Este código expira en 15 minutos.
Si no creaste esta cuenta, ignora este mensaje.
        """.strip()

        msg.attach(MIMEText(texto_plano, "plain"))
        msg.attach(MIMEText(_build_html(code), "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return True

    except smtplib.SMTPAuthenticationError:
        print("[EMAIL] Error de autenticación SMTP — verifica credenciales")
        return False
    except smtplib.SMTPRecipientsRefused:
        print(f"[EMAIL] Destinatario rechazado: {to_email}")
        return False
    except smtplib.SMTPException as e:
        print(f"[EMAIL] Error SMTP: {e}")
        return False
    except Exception as e:
        print(f"[EMAIL] Error inesperado: {e}")
        return False


def _build_html_recuperacion(code: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recupera tu contraseña</title>
</head>
<body style="
    margin: 0;
    padding: 0;
    background-color: #090909;
    font-family: Arial, Helvetica, sans-serif;
    color: #e8e8e8;
">

<table width="100%" cellpadding="0" cellspacing="0" style="padding: 48px 0;">
    <tr>
        <td align="center">

            <table width="580" cellpadding="0" cellspacing="0" style="
                background-color: #111111;
                border-radius: 8px;
                overflow: hidden;
                border: 1px solid #222222;
            ">

                <!-- HEADER -->
                <tr>
                    <td style="
                        padding: 28px 40px;
                        border-bottom: 1px solid #222222;
                    ">
                        <span style="
                            font-family: Arial Black, sans-serif;
                            font-size: 22px;
                            font-weight: 900;
                            letter-spacing: 0.06em;
                            text-transform: uppercase;
                        ">
                            <span style="color: #f97316;">Control</span><span style="color: #e8e8e8;">Anime</span>
                        </span>
                    </td>
                </tr>

                <!-- BODY -->
                <tr>
                    <td style="padding: 40px;">

                        <p style="
                            font-size: 11px;
                            letter-spacing: 0.2em;
                            text-transform: uppercase;
                            color: #f97316;
                            font-weight: bold;
                            margin: 0 0 16px 0;
                        ">Recuperación de contraseña</p>

                        <h1 style="
                            font-size: 28px;
                            font-weight: 900;
                            color: #ffffff;
                            margin: 0 0 16px 0;
                            line-height: 1.1;
                        ">Restablece tu contraseña</h1>

                        <p style="
                            font-size: 15px;
                            line-height: 1.7;
                            color: #777777;
                            margin: 0 0 32px 0;
                        ">
                            Recibimos una solicitud para restablecer la contraseña de tu cuenta en
                            <strong style="color: #e8e8e8;">ControlAnime</strong>.
                            Ingresa el siguiente código para continuar.
                        </p>

                        <!-- CÓDIGO -->
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
                            <tr>
                                <td align="center">
                                    <div style="
                                        display: inline-block;
                                        background-color: #181818;
                                        border: 1px solid #222222;
                                        border-left: 4px solid #f97316;
                                        border-radius: 6px;
                                        padding: 20px 48px;
                                    ">
                                        <span style="
                                            font-size: 36px;
                                            font-weight: 900;
                                            letter-spacing: 10px;
                                            color: #f97316;
                                            font-family: 'Courier New', monospace;
                                        ">{code}</span>
                                    </div>
                                </td>
                            </tr>
                        </table>

                        <p style="
                            font-size: 13px;
                            color: #444444;
                            margin: 0;
                            line-height: 1.6;
                        ">
                            Este código expira en <strong style="color: #777777;">15 minutos</strong>.
                            Si no solicitaste este cambio, puedes ignorar este mensaje —
                            tu contraseña no será modificada.
                        </p>

                    </td>
                </tr>

                <!-- FOOTER -->
                <tr>
                    <td style="
                        padding: 20px 40px;
                        border-top: 1px solid #222222;
                        background-color: #0a0a0a;
                    ">
                        <p style="
                            font-size: 11px;
                            color: #444444;
                            margin: 0;
                            text-align: center;
                            letter-spacing: 0.05em;
                        ">
                            ControlAnime · Proyecto personal sin fines de lucro · No respondas a este correo
                        </p>
                    </td>
                </tr>

            </table>

        </td>
    </tr>
</table>

</body>
</html>
"""


def enviar_codigo_recuperacion(to_email: str, code: str) -> bool:
    """
    Envía el correo de recuperación de contraseña.
    Retorna True si se envió correctamente, False si falló.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"]      = to_email
        msg["Subject"] = "Restablece tu contraseña en ControlAnime"
        msg["X-Mailer"] = "ControlAnime Mailer"

        texto_plano = f"""
ControlAnime — Recuperación de contraseña

Tu código para restablecer la contraseña es: {code}

Este código expira en 15 minutos.
Si no solicitaste este cambio, ignora este mensaje.
        """.strip()

        msg.attach(MIMEText(texto_plano, "plain"))
        msg.attach(MIMEText(_build_html_recuperacion(code), "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return True

    except smtplib.SMTPAuthenticationError:
        print("[EMAIL] Error de autenticación SMTP — verifica credenciales")
        return False
    except smtplib.SMTPRecipientsRefused:
        print(f"[EMAIL] Destinatario rechazado: {to_email}")
        return False
    except smtplib.SMTPException as e:
        print(f"[EMAIL] Error SMTP: {e}")
        return False
    except Exception as e:
        print(f"[EMAIL] Error inesperado: {e}")
        return False
