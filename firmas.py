"""
OZOLABS' WIZARD - Firma digital en pantalla
Guarda firmas como imágenes base64 en la tabla `firmas` y las
exporta a PNG cuando haga falta (por ejemplo para incrustarlas en PDFs).

El base64 puede venir con o sin prefijo "data:image/png;base64,".
Ambos casos se manejan correctamente.
"""
from database import conectar
from datetime import datetime
import base64
import os


# =========================================================
# HELPERS INTERNOS
# =========================================================
def _limpiar_base64(b64):
    """
    Quita el prefijo "data:image/png;base64," si existe.
    Devuelve la cadena base64 limpia lista para decodificar.
    """
    if not b64:
        return b64
    if "," in b64:
        return b64.split(",", 1)[1]
    return b64


def _decodificar_base64(b64):
    """
    Decodifica una cadena base64 en bytes.
    Acepta tanto con prefijo como sin él.
    """
    limpio = _limpiar_base64(b64)
    return base64.b64decode(limpio)


# =========================================================
# CRUD FIRMAS
# =========================================================
def guardar_firma(pedido_numero, tipo, nombre, imagen_base64):
    """
    Guarda una firma en la tabla `firmas`.

    Args:
        pedido_numero: número de pedido asociado.
        tipo: "preparado", "verificado" u otro identificador.
        nombre: nombre del firmante.
        imagen_base64: cadena base64 (con o sin prefijo data:image/png;base64,).
    """
    conn = conectar()
    conn.execute("""
        INSERT INTO firmas
        (pedido_numero, tipo, nombre, imagen_base64, fecha)
        VALUES (?, ?, ?, ?, ?)
    """, (pedido_numero, tipo, nombre, imagen_base64,
          datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"✔ Firma '{tipo}' guardada para el pedido {pedido_numero}.")


def obtener_firma(pedido_numero, tipo):
    """
    Devuelve la última firma registrada para un pedido y tipo.

    Returns:
        Tupla (nombre, imagen_base64, fecha) o None si no existe.
    """
    conn = conectar()
    row = conn.execute("""
        SELECT nombre, imagen_base64, fecha
        FROM firmas
        WHERE pedido_numero = ? AND tipo = ?
        ORDER BY id DESC LIMIT 1
    """, (pedido_numero, tipo)).fetchone()
    conn.close()
    return row


def tiene_firma(pedido_numero, tipo):
    """Devuelve True si existe alguna firma de ese tipo para el pedido."""
    return obtener_firma(pedido_numero, tipo) is not None


# =========================================================
# EXPORTAR A PNG
# =========================================================
def exportar_firma_png(pedido_numero, tipo, ruta):
    """
    Decodifica el base64 de la firma y la escribe como PNG en `ruta`.

    Args:
        pedido_numero: número de pedido.
        tipo: "preparado", "verificado", etc.
        ruta: ruta de salida del archivo PNG.

    Returns:
        La ruta del PNG generado o None si no había firma.
    """
    firma = obtener_firma(pedido_numero, tipo)
    if not firma:
        return None

    _, b64, _ = firma
    try:
        datos = _decodificar_base64(b64)
    except Exception as e:
        print(f"✘ Error decodificando base64 de firma: {e}")
        return None

    with open(ruta, "wb") as f:
        f.write(datos)
    return ruta


# =========================================================
# WIDGET STREAMLIT
# =========================================================
def firma_widget(pedido_numero, tipo, etiqueta="Firma digital"):
    """
    Widget de Streamlit para dibujar, guardar y borrar una firma.

    Requiere `streamlit-drawable-canvas` (pip install streamlit-drawable-canvas).

    Args:
        pedido_numero: número de pedido.
        tipo: "preparado", "verificado", etc.
        etiqueta: título que se muestra encima del canvas.

    Returns:
        True si hay firma guardada (nueva o existente), False en caso contrario.
    """
    try:
        from streamlit_drawable_canvas import st_canvas
    except ImportError:
        import streamlit as st
        st.warning(
            "Instala `streamlit-drawable-canvas` para poder firmar: "
            "`pip install streamlit-drawable-canvas`"
        )
        return False

    import streamlit as st
    from PIL import Image
    from io import BytesIO

    st.markdown(f"**{etiqueta}**")

    # --- Firma ya existente ---
    firma_existente = obtener_firma(pedido_numero, tipo)
    if firma_existente:
        nombre, b64, fecha = firma_existente
        st.success(f"✔ Firmado por **{nombre}** el {fecha[:16]}")
        try:
            st.image(b64, width=300)
        except Exception:
            st.info("Firma guardada (no se pudo previsualizar).")

        if st.button(f"🗑 Borrar firma '{tipo}'", key=f"borrar_{tipo}"):
            conn = conectar()
            conn.execute("""
                DELETE FROM firmas
                WHERE pedido_numero = ? AND tipo = ?
            """, (pedido_numero, tipo))
            conn.commit()
            conn.close()
            st.rerun()
        return True

    # --- Canvas para nueva firma ---
    canvas = st_canvas(
        fill_color="rgba(75, 0, 130, 0.0)",
        stroke_width=2,
        stroke_color="#4B0082",
        background_color="#FFFFFF",
        height=180,
        width=500,
        drawing_mode="freedraw",
        key=f"canvas_{tipo}_{pedido_numero}",
    )

    nombre = st.text_input(
        "Nombre del firmante",
        key=f"nombre_firma_{tipo}",
    )

    if st.button(f"💾 Guardar firma '{tipo}'", key=f"guardar_{tipo}"):
        if not nombre:
            st.error("Introduce el nombre del firmante.")
        elif canvas.image_data is None:
            st.error("Dibuja la firma antes de guardar.")
        else:
            img = Image.fromarray(canvas.image_data.astype("uint8"))
            buf = BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            guardar_firma(
                pedido_numero, tipo, nombre,
                f"data:image/png;base64,{b64}",
            )
            st.success("✔ Firma guardada.")
            st.rerun()

    return False


__all__ = [
    "guardar_firma",
    "obtener_firma",
    "tiene_firma",
    "exportar_firma_png",
    "firma_widget",
]
