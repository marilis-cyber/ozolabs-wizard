"""
OZOLABS' WIZARD - Gestión de etiquetas
=======================================
Permite subir la etiqueta final de cada producto (PDF), guardar
versiones y descargar la última.
"""
from database import conectar
from datetime import datetime
import base64


def subir_etiqueta(producto_codigo, producto_nombre, nombre_fichero,
                   contenido_bytes, comentarios=""):
    """Guarda una nueva versión de etiqueta para un producto."""
    conn = conectar()
    row = conn.execute("""
        SELECT COALESCE(MAX(version), 0) FROM etiquetas
        WHERE producto_codigo = ?
    """, (producto_codigo,)).fetchone()
    version = (row[0] if row else 0) + 1

    b64 = base64.b64encode(contenido_bytes).decode("utf-8")
    conn.execute("""
        INSERT INTO etiquetas
        (producto_codigo, producto_nombre, version, nombre_fichero,
         contenido_base64, fecha, comentarios)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (producto_codigo, producto_nombre, version, nombre_fichero,
          b64, datetime.now().isoformat(), comentarios))
    conn.commit()
    conn.close()
    print(f"✔ Etiqueta v{version} subida para {producto_nombre}.")
    return version


def listar_etiquetas(producto_codigo=None):
    """Lista las etiquetas (sin el contenido, para mostrar)."""
    conn = conectar()
    if producto_codigo:
        rows = conn.execute("""
            SELECT id, producto_codigo, producto_nombre, version,
                   nombre_fichero, fecha, comentarios
            FROM etiquetas WHERE producto_codigo = ?
            ORDER BY version DESC
        """, (producto_codigo,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, producto_codigo, producto_nombre, version,
                   nombre_fichero, fecha, comentarios
            FROM etiquetas
            ORDER BY producto_nombre, version DESC
        """).fetchall()
    conn.close()
    return rows


def obtener_etiqueta(etiqueta_id):
    """Devuelve (nombre_fichero, contenido_bytes) de una etiqueta."""
    conn = conectar()
    row = conn.execute("""
        SELECT nombre_fichero, contenido_base64
        FROM etiquetas WHERE id = ?
    """, (etiqueta_id,)).fetchone()
    conn.close()
    if not row:
        return None, None
    return row[0], base64.b64decode(row[1])


def ultima_etiqueta(producto_codigo):
    """Devuelve (id, nombre_fichero, contenido_bytes) de la última versión."""
    conn = conectar()
    row = conn.execute("""
        SELECT id, nombre_fichero, contenido_base64
        FROM etiquetas WHERE producto_codigo = ?
        ORDER BY version DESC LIMIT 1
    """, (producto_codigo,)).fetchone()
    conn.close()
    if not row:
        return None, None, None
    return row[0], row[1], base64.b64decode(row[2])


__all__ = [
    "subir_etiqueta", "listar_etiquetas", "obtener_etiqueta",
    "ultima_etiqueta",
]
