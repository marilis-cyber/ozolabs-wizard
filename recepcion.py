"""
OZOLABS' WIZARD - Recepción de mercancía (versión ampliada)
Entrada directa de mercancía con todos los campos de control:
fecha, producto, lote, proveedor, uso, conforme, bio, certificado bio,
responsable.
"""
from database import conectar
from datetime import datetime


# =========================================================
# RECEPCIONES DIRECTAS
# =========================================================
def crear_recepcion_directa(producto_nombre, lote, proveedor,
                            fecha_entrada=None, uso="cosmetico",
                            conforme="conforme", bio=False,
                            caducidad_bio=None, responsable="",
                            observaciones=""):
    """
    Registra una entrada de mercancía directamente (sin necesidad de OC).

    Args:
        producto_nombre: nombre del producto/materia recibida.
        lote: lote del proveedor.
        proveedor: nombre o código del proveedor.
        fecha_entrada: fecha de entrada (ISO).
        uso: 'cosmetico' | 'alimentario' | 'ambos'.
        conforme: 'conforme' | 'no_conforme'.
        bio: True/False.
        caducidad_bio: fecha de caducidad del certificado bio.
        responsable: quién recibe.
        observaciones: notas.

    Returns:
        Número de recepción (str).
    """
    numero = f"ENT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    fecha = fecha_entrada or datetime.now().date().isoformat()
    estado = "conforme" if conforme == "conforme" else "con_incidencia"

    conn = conectar()
    conn.execute("""
        INSERT INTO recepciones
        (numero, orden_compra, proveedor_codigo, fecha, albaran_proveedor,
         usuario_receptor, observaciones, estado, uso, conforme, bio,
         caducidad_bio, responsable, producto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (numero, None, proveedor, fecha, "", responsable,
          observaciones, estado, uso, conforme, 1 if bio else 0,
          caducidad_bio, responsable, producto_nombre))
    conn.commit()
    conn.close()
    print(f"✔ Entrada {numero} registrada: {producto_nombre} lote {lote}.")
    return numero


def listar_recepciones_directas(limite=300):
    """Devuelve las recepciones directas con todos los campos."""
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, fecha, producto, proveedor_codigo, uso, conforme,
               bio, caducidad_bio, responsable, observaciones
        FROM recepciones
        ORDER BY fecha DESC, id DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


def crear_salida(producto, producto_codigo, uso, destino, lote,
                 cantidad, unidad, comentarios, responsable=""):
    """Registra una salida de producto."""
    conn = conectar()
    conn.execute("""
        INSERT INTO salidas
        (fecha, producto, producto_codigo, uso, destino, lote,
         cantidad, unidad, comentarios, responsable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), producto, producto_codigo, uso,
          destino, lote, cantidad, unidad, comentarios, responsable))
    conn.commit()
    conn.close()
    print(f"✔ Salida registrada: {producto} lote {lote} → {destino}.")


def listar_salidas(limite=500):
    """Devuelve todas las salidas, la más reciente primero."""
    conn = conectar()
    rows = conn.execute("""
        SELECT fecha, producto, producto_codigo, uso, destino, lote,
               cantidad, unidad, comentarios, responsable
        FROM salidas
        ORDER BY id DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


__all__ = [
    "crear_recepcion_directa",
    "listar_recepciones_directas",
    "crear_salida",
    "listar_salidas",
]
