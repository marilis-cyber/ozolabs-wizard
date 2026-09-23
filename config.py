"""OZOLABS' WIZARD - Configuración general
Edita este archivo para adaptarlo a tu entorno.
"""

# ============ EMAIL ============
EMAIL_CONFIG = {
    "activo": False,                    # ponlo a True cuando lo configures
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "usar_tls": True,
    "remitente": "tu_correo@gmail.com",
    "password": "tu_app_password",      # NO uses tu contraseña normal
    "destinatarios": [
        "responsable@ozolabs.com",
    ],
    "asunto_prefijo": "[OZOLABS' WIZARD]",
}

# ============ URL PÚBLICA ============
# Si publicas la app en un servidor, pon aquí su URL base
# para que los QR de las etiquetas apunten al informe online.
URL_BASE_INFORMES = "http://localhost:8501/informe"

# ============ EMPRESA ============
EMPRESA = {
    "nombre": "OZOLABS",
    "razon_social": "OZOLABS S.L.",
    "cif": "B-00000000",
    "direccion": "Calle Ejemplo 1, 28000 Madrid",
    "email": "info@ozolabs.com",
    "web": "www.ozolabs.com",
}
