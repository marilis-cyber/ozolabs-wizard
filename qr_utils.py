"""
OZOLABS' WIZARD - Generación de códigos QR para trazabilidad
Usa qrcode + PIL. Opcionalmente incrusta el logo en el centro.
"""
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from PIL import Image, ImageDraw
import os


def generar_qr(url_o_texto, ruta_salida=None, con_logo=False,
               color_relleno=(75, 0, 130), color_fondo=(255, 255, 255)):
    """
    Genera un QR con estilo OZOLABS' WIZARD (redondeado, morado).
    Si con_logo=True y existe assets/logo_icon.png, incrusta el logo en el centro.

    Args:
        url_o_texto: contenido del QR (URL o texto).
        ruta_salida: ruta del PNG de salida. Por defecto "qr.png".
        con_logo: si True, intenta incrustar el logo.
        color_relleno: tupla RGB del color de los módulos.
        color_fondo: tupla RGB del fondo.

    Returns:
        Ruta del PNG generado.
    """
    if not ruta_salida:
        ruta_salida = "qr.png"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(url_o_texto)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=color_fondo,
            front_color=color_relleno,
        ),
    ).convert("RGB")

    if con_logo:
        try:
            logo_png = "assets/logo_icon.png"
            if os.path.exists(logo_png):
                logo = Image.open(logo_png).convert("RGBA")
                tam_qr = img.size[0]
                tam_logo = tam_qr // 4
                logo = logo.resize((tam_logo, tam_logo))
                pos = ((tam_qr - tam_logo) // 2, (tam_qr - tam_logo) // 2)

                # Círculo blanco de fondo para el logo
                fondo = Image.new("RGB", img.size, (255, 255, 255))
                draw = ImageDraw.Draw(fondo)
                centro = tam_qr // 2
                radio = tam_logo // 2 + 6
                draw.ellipse(
                    (centro - radio, centro - radio,
                     centro + radio, centro + radio),
                    fill=(255, 255, 255),
                )
                img.paste(fondo, (0, 0), fondo)
                img.paste(logo, pos, logo)
        except Exception as e:
            print(f"⚠ No se pudo incrustar el logo en el QR: {e}")

    img.save(ruta_salida)
    return ruta_salida


def url_informe(lote_pt):
    """
    Devuelve la URL que enlaza al informe de un lote.
    Se construye a partir de config.URL_BASE_INFORMES.
    """
    try:
        from config import URL_BASE_INFORMES
        return f"{URL_BASE_INFORMES}/{lote_pt}"
    except Exception:
        return f"http://localhost:8501/informe/{lote_pt}"


__all__ = ["generar_qr", "url_informe"]
