"""
OZOLABS' WIZARD - Módulo de reprocesos
Permite registrar y dar seguimiento a lotes que deben reprocesarse.
"""
from database import conectar
from datetime import datetime


def abrir_reproceso(lote_origen, producto_codigo, cantidad_origen,
                     motivo, descripcion="", responsable=""):
    """
    Abre un nuevo reproceso y devuelve su número.

    Args:
        lote_origen: lote del producto que se va a reprocesar.
        producto_codigo: código del producto afectado.
        cantidad_origen: cantidad de unidades afectadas.
        motivo: motivo breve (fuera de especificación, error, etc.).
        descripcion: descripción ampliada.
        responsable: persona que abre el reproceso.

    Returns:
        Número del reproceso (str), formato REP-YYYYMMDDHHMMSS.
    """
    numero = f"REP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = conectar()
    conn.execute("""
        INSERT INTO reprocesos
        (numero, lote_origen, producto_codigo, cantidad_origen, motivo,
         descripcion, estado, fecha_apertura, responsable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (numero, lote_origen, producto_codigo, cantidad_origen, motivo,
          descripcion, "abierto", datetime.now().isoformat(), responsable))
    conn.commit()
    conn.close()
    print(f"✔ Reproceso {numero} abierto.")
    return numero


def cerrar_reproceso(numero, lote_destino, resultado="conforme",
                     coste_extra=0, observaciones=""):
    """
    Cierra un reproceso indicando el lote destino y el resultado.

    Args:
        numero: número del reproceso.
        lote_destino: nuevo lote de producto terminado.
        resultado: conforme / no_conforme / descartado.
        coste_extra: coste adicional en euros.
        observaciones: notas de cierre.
    """
    conn = conectar()
    conn.execute("""
        UPDATE reprocesos
        SET estado = 'cerrado', lote_destino = ?, resultado = ?,
            fecha_cierre = ?, coste_extra = ?
        WHERE numero = ?
    """, (lote_destino, resultado, datetime.now().isoformat(),
          coste_extra, numero))

    if observaciones:
        row = conn.execute(
            "SELECT descripcion FROM reprocesos WHERE numero = ?",
            (numero,)
        ).fetchone()
        desc = (row[0] or "") + f"\n\n[CIERRE] {observaciones}"
        conn.execute(
            "UPDATE reprocesos SET descripcion = ? WHERE numero = ?",
            (desc, numero)
        )

    conn.commit()
    conn.close()
    print(f"✔ Reproceso {numero} cerrado (destino: {lote_destino}).")


def listar_reprocesos(estado=None):
    """
    Lista reprocesos, opcionalmente filtrados por estado.
    Columnas:
    (numero, lote_origen, producto_codigo, cantidad_origen, motivo,
     estado, lote_destino, fecha_apertura, fecha_cierre,
     resultado, coste_extra)
    """
    conn = conectar()
    if estado:
        rows = conn.execute("""
            SELECT numero, lote_origen, producto_codigo, cantidad_origen,
                   motivo, estado, lote_destino, fecha_apertura,
                   fecha_cierre, resultado, coste_extra
            FROM reprocesos
            WHERE estado = ?
            ORDER BY fecha_apertura DESC
        """, (estado,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT numero, lote_origen, producto_codigo, cantidad_origen,
                   motivo, estado, lote_destino, fecha_apertura,
                   fecha_cierre, resultado, coste_extra
            FROM reprocesos
            ORDER BY fecha_apertura DESC
        """).fetchall()
    conn.close()
    return rows


def ver_reproceso(numero):
    """
    Devuelve la tupla completa de un reproceso:
    (numero, lote_origen, producto_codigo, cantidad_origen, motivo,
     descripcion, estado, lote_destino, fecha_apertura, fecha_cierre,
     responsable, resultado, coste_extra)
    """
    conn = conectar()
    row = conn.execute("""
        SELECT numero, lote_origen, producto_codigo, cantidad_origen,
               motivo, descripcion, estado, lote_destino, fecha_apertura,
               fecha_cierre, responsable, resultado, coste_extra
        FROM reprocesos
        WHERE numero = ?
    """, (numero,)).fetchone()
    conn.close()
    return row


def reprocesos_de_lote(lote):
    """
    Devuelve todos los reprocesos asociados a un lote de origen.

    El orden de las columnas está fijado para encajar con
    informes.generar_informe_rendimiento:
        (numero, motivo, estado, lote_destino,
         fecha_apertura, fecha_cierre, resultado)
    """
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, motivo, estado, lote_destino,
               fecha_apertura, fecha_cierre, resultado
        FROM reprocesos
        WHERE lote_origen = ?
    """, (lote,)).fetchall()
    conn.close()
    return rows


def motivos_frecuentes():
    """
    Estadísticas de motivos de reproceso con coste acumulado.
    Devuelve tuplas: (motivo, veces, coste_total).
    """
    conn = conectar()
    rows = conn.execute("""
        SELECT motivo, COUNT(*) AS veces,
               COALESCE(SUM(coste_extra), 0) AS coste
        FROM reprocesos
        GROUP BY motivo
        ORDER BY veces DESC
    """).fetchall()
    conn.close()
    return rows


__all__ = [
    "abrir_reproceso",
    "cerrar_reproceso",
    "listar_reprocesos",
    "ver_reproceso",
    "reprocesos_de_lote",
    "motivos_frecuentes",
]
