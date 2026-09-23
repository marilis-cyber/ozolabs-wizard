"""
OZOLABS' WIZARD - Rendimiento real vs. teórico por lote
"""
from database import conectar
from datetime import datetime


def registrar_rendimiento(producto_lote, producto_codigo, cantidad_teorica,
                          cantidad_real, unidad="ud", peso_final=None,
                          peso_objetivo=None, observaciones=""):
    """
    Registra el rendimiento real de un lote.

    Args:
        producto_lote: identificador del lote de producto terminado.
        producto_codigo: código del producto.
        cantidad_teorica: cantidad esperada (uds).
        cantidad_real: cantidad real obtenida (uds).
        unidad: unidad de medida (por defecto "ud").
        peso_final: peso real final (opcional, para líquidos/polvos).
        peso_objetivo: peso objetivo (opcional).
        observaciones: notas libres.

    Returns:
        El rendimiento calculado en % (float).
    """
    rendimiento_pct = (cantidad_real / cantidad_teorica * 100) if cantidad_teorica else 0

    conn = conectar()
    conn.execute("""
        INSERT INTO rendimiento_lote
        (producto_lote, producto_codigo, cantidad_teorica, cantidad_real,
         unidad, rendimiento_pct, peso_final, peso_objetivo, fecha, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (producto_lote, producto_codigo, cantidad_teorica, cantidad_real,
          unidad, rendimiento_pct,
          peso_final if peso_final is not None else 0,
          peso_objetivo if peso_objetivo is not None else 0,
          datetime.now().isoformat(), observaciones))
    conn.commit()
    conn.close()
    print(f"✔ Rendimiento {rendimiento_pct:.2f}% registrado para {producto_lote}.")
    return rendimiento_pct


def rendimiento_de_lote(producto_lote):
    """
    Devuelve la tupla:
    (producto_codigo, cantidad_teorica, cantidad_real, unidad,
     rendimiento_pct, peso_final, peso_objetivo, fecha, observaciones)
    o None si no existe.
    """
    conn = conectar()
    row = conn.execute("""
        SELECT producto_codigo, cantidad_teorica, cantidad_real,
               unidad, rendimiento_pct, peso_final, peso_objetivo,
               fecha, observaciones
        FROM rendimiento_lote
        WHERE producto_lote = ?
        ORDER BY id DESC LIMIT 1
    """, (producto_lote,)).fetchone()
    conn.close()
    return row


def rendimiento_medio_producto(producto_codigo):
    """
    Devuelve dict {media, min, max, n} o None si no hay datos.
    """
    conn = conectar()
    row = conn.execute("""
        SELECT AVG(rendimiento_pct), MIN(rendimiento_pct),
               MAX(rendimiento_pct), COUNT(*)
        FROM rendimiento_lote
        WHERE producto_codigo = ?
    """, (producto_codigo,)).fetchone()
    conn.close()
    if row and row[3]:
        return {
            "media": row[0],
            "min": row[1],
            "max": row[2],
            "n": row[3],
        }
    return None


def historico_rendimiento(producto_codigo=None, limite=200):
    """
    Devuelve el histórico de rendimientos, opcionalmente filtrado por producto.
    """
    conn = conectar()
    q = """
        SELECT producto_lote, producto_codigo, cantidad_teorica,
               cantidad_real, unidad, rendimiento_pct, fecha
        FROM rendimiento_lote WHERE 1 = 1
    """
    params = []
    if producto_codigo:
        q += " AND producto_codigo = ?"
        params.append(producto_codigo)
    q += " ORDER BY fecha DESC LIMIT ?"
    params.append(limite)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


__all__ = [
    "registrar_rendimiento",
    "rendimiento_de_lote",
    "rendimiento_medio_producto",
    "historico_rendimiento",
]
