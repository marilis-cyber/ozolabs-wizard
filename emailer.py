"""
OZOLABS' WIZARD - Envío de informes y alertas por email
Usa smtplib + email.mime para enviar correos con o sin adjuntos.
Configuración en config.EMAIL_CONFIG.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import os


# =========================================================
# CONFIG HELPERS
# =========================================================
def _config():
    """Devuelve EMAIL_CONFIG de config.py o un dict vacío."""
    try:
        from config import EMAIL_CONFIG
        return EMAIL_CONFIG
    except Exception:
        return {}


def _empresa():
    """Devuelve EMPRESA de config.py o un dict mínimo."""
    try:
        from config import EMPRESA
        return EMPRESA
    except Exception:
        return {"razon_social": "OZOLABS", "email": "info@ozolabs.com"}


# =========================================================
# HELPER PRINCIPAL
# =========================================================
def _enviar(destinatarios, asunto, cuerpo, adjuntos=None):
    """
    Envía un email usando SMTP según config.EMAIL_CONFIG.

    Args:
        destinatarios: lista de emails.
        asunto: str.
        cuerpo: str (texto plano).
        adjuntos: lista opcional de rutas a archivos a adjuntar.

    Returns:
        True si se envió correctamente, False en caso contrario.
    """
    cfg = _config()
    if not cfg.get("activo"):
        print("⚠ El envío de emails está desactivado en config.py")
        return False

    if not destinatarios:
        print("✘ No hay destinatarios.")
        return False

    asunto_final = f"{cfg.get('asunto_prefijo', '[OZOLABS]')} {asunto}"

    # Construir mensaje MIME
    msg = MIMEMultipart()
    msg["From"] = cfg["remitente"]
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = asunto_final
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    # Adjuntos
    if adjuntos:
        for ruta in adjuntos:
            if not ruta or not os.path.exists(ruta):
                print(f"⚠ Adjunto no encontrado: {ruta}")
                continue
            try:
                with open(ruta, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{os.path.basename(ruta)}"',
                )
                msg.attach(part)
            except Exception as e:
                print(f"✘ Error añadiendo adjunto {ruta}: {e}")

    # Conexión SMTP
    try:
        contexto = ssl.create_default_context()
        if cfg.get("usar_tls", True):
            server = smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"])
            server.starttls(context=contexto)
        else:
            server = smtplib.SMTP_SSL(
                cfg["smtp_server"], cfg["smtp_port"], context=contexto
            )
        server.login(cfg["remitente"], cfg["password"])
        server.send_message(msg)
        server.quit()
        print(f"✔ Email enviado a: {', '.join(destinatarios)}")
        return True
    except Exception as e:
        print(f"✘ Error al enviar email: {e}")
        return False


# =========================================================
# FUNCIONES PÚBLICAS
# =========================================================
def enviar_informe_email(ruta_pdf, lote, producto,
                          destinatarios=None, asunto_extra="",
                          cuerpo_extra=""):
    """
    Envía un informe PDF por email como adjunto.

    Args:
        ruta_pdf: ruta del archivo PDF.
        lote: identificador del lote.
        producto: nombre del producto.
        destinatarios: lista de emails (None = usar config).
        asunto_extra: texto opcional para el asunto.
        cuerpo_extra: texto opcional para el cuerpo.

    Returns:
        True si el envío fue correcto.
    """
    cfg = _config()
    if not cfg.get("activo"):
        print("⚠ El envío de emails está desactivado en config.py")
        return False

    if not ruta_pdf or not os.path.exists(ruta_pdf):
        print(f"✘ No existe el archivo {ruta_pdf}")
        return False

    destinatarios = destinatarios or cfg.get("destinatarios", [])

    asunto = f"Informe de producción lote {lote} · {producto}"
    if asunto_extra:
        asunto += f" · {asunto_extra}"

    empresa = _empresa()
    cuerpo = f"""Hola,

Adjunto el informe de producción del lote {lote} ({producto}),
generado automáticamente por OZOLABS' WIZARD.

Fecha de envío: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{cuerpo_extra}

Un saludo,
OZOLABS' WIZARD
{empresa.get('razon_social', 'OZOLABS')} · {empresa.get('email', '')}
"""

    return _enviar(destinatarios, asunto, cuerpo, adjuntos=[ruta_pdf])


def enviar_alerta_stock(asunto, cuerpo, destinatarios=None):
    """
    Envía una alerta simple (sin adjuntos).

    Args:
        asunto: str.
        cuerpo: str.
        destinatarios: lista de emails (None = usar config).

    Returns:
        True si el envío fue correcto.
    """
    cfg = _config()
    destinatarios = destinatarios or cfg.get("destinatarios", [])
    return _enviar(destinatarios, asunto, cuerpo, adjuntos=None)


__all__ = ["enviar_informe_email", "enviar_alerta_stock"]
