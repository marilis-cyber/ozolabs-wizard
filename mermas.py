"""
OZOLABS' WIZARD - Mermas, pesos reales y subproductos
"""
from database import conectar
from datetime import datetime


# =========================================================
# PESOS REALES
# =========================================================
def registrar_peso_real(pedido_numero, tipo_articulo, articulo_codigo,
                        articulo_lote, cantidad_teorica, cantidad_real,
                        unidad, operario="", notas=""):
    """Guarda el peso real pesado por el operario y calcula la desviación."""
    desviacion = cantidad_real - cantidad_teorica
    desviacion_pct = (desviacion / cantidad_teorica * 100) if cantidad_teorica else 0

    conn = conectar()
    conn.execute("""
        INSERT INTO pesos_reales
        (pedido_numero, tipo_articulo, articulo_codigo, articulo_lote,
         cantidad_teorica, cantidad_real, unidad, desviacion, desviacion_pct,
         operario, fecha, notas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pedido_numero, tipo_articulo, articulo_codigo, articulo_lote,
          cantidad_teorica, cantidad_real, unidad, desviacion, desviacion_pct,
          operario, datetime.now().isoformat(), notas))
    conn.commit()
    conn.close()
    return desviacion, desviacion_pct


def pesos_de_pedido(pedido_numero):
    """Devuelve todos los pesos reales registrados para un pedido."""
    conn = conectar()
    rows = conn.execute("""
        SELECT tipo_articulo, articulo_codigo, articulo_lote,
               cantidad_teorica, cantidad_real, unidad,
               desviacion, desviacion_pct, operario, fecha, notas
        FROM pesos_reales
        WHERE pedido_numero = ?
        ORDER BY articulo_codigo
    """, (pedido_numero,)).fetchall()
    conn.close()
    return rows


def resumen_merma_pedido(pedido_numero):
    """Devuelve totales: peso teórico, real, desviación total y %."""
    conn = conectar()
    row = conn.execute("""
        SELECT COALESCE(SUM(cantidad_teorica), 0),
               COALESCE(SUM(cantidad_real), 0),
               COALESCE(SUM(desviacion), 0)
        FROM pesos_reales
        WHERE pedido_numero = ?
    """, (pedido_numero,)).fetchone()
    conn.close()

    teorica, real, desv = row if row else (0, 0, 0)
    pct = (desv / teorica * 100) if teorica else 0
    return {
        "teorica": teorica,
        "real": real,
        "desviacion": desv,
        "desviacion_pct": pct,
    }


# =========================================================
# MERMAS
# =========================================================
def registrar_merma(pedido_numero, producto_codigo, tipo, motivo,
                    articulo_codigo="", articulo_lote="",
                    cantidad=0, unidad="", coste_estimado=0,
                    accion_correctiva="", responsable=""):
    """Registra una merma, subproducto o pérdida."""
    conn = conectar()
    conn.execute("""
        INSERT INTO mermas
        (pedido_numero, producto_codigo, tipo, motivo, articulo_codigo,
         articulo_lote, cantidad, unidad, coste_estimado, accion_correctiva,
         fecha, responsable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pedido_numero, producto_codigo, tipo, motivo, articulo_codigo,
          articulo_lote, cantidad, unidad, coste_estimado, accion_correctiva,
          datetime.now().isoformat(), responsable))
    conn.commit()
    conn.close()
    print(f"✔ {tipo.capitalize()} registrada: {motivo} ({cantidad} {unidad}).")


def listar_mermas(pedido_numero=None, tipo=None):
    """Lista mermas filtradas por pedido y/o tipo."""
    conn = conectar()
    q = """
        SELECT id, pedido_numero, producto_codigo, tipo, motivo,
               articulo_codigo, articulo_lote, cantidad, unidad,
               coste_estimado, fecha, responsable
        FROM mermas WHERE 1 = 1
    """
    params = []
    if pedido_numero:
        q += " AND pedido_numero = ?"
        params.append(pedido_numero)
    if tipo:
        q += " AND tipo = ?"
        params.append(tipo)
    q += " ORDER BY fecha DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def resumen_mermas_producto(producto_codigo):
    """Estadísticas de mermas agrupadas por tipo y motivo para un producto."""
    conn = conectar()
    rows = conn.execute("""
        SELECT tipo, motivo, COUNT(*) AS veces,
               COALESCE(SUM(cantidad), 0) AS total_cant,
               COALESCE(SUM(coste_estimado), 0) AS coste
        FROM mermas
        WHERE producto_codigo = ?
        GROUP BY tipo, motivo
        ORDER BY coste DESC
    """, (producto_codigo,)).fetchall()
    conn.close()
    return rows


# =========================================================
# SUBPRODUCTOS
# =========================================================
def registrar_subproducto(pedido_numero, codigo, nombre, lote,
                          cantidad, unidad, destino="reutilización",
                          coste_unitario=0):
    """Registra un subproducto aprovechable generado en una producción."""
    conn = conectar()
    conn.execute("""
        INSERT INTO subproductos
        (pedido_numero, codigo, nombre, lote, cantidad, unidad, destino,
         coste_unitario, fecha)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pedido_numero, codigo, nombre, lote, cantidad, unidad,
          destino, coste_unitario, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"✔ Subproducto '{nombre}' registrado ({cantidad} {unidad}).")


def listar_subproductos(pedido_numero=None):
    """Lista subproductos, opcionalmente filtrados por pedido."""
    conn = conectar()
    if pedido_numero:
        rows = conn.execute("""
            SELECT id, codigo, nombre, lote, cantidad, unidad,
                   destino, coste_unitario, fecha
            FROM subproductos
            WHERE pedido_numero = ?
            ORDER BY fecha DESC
        """, (pedido_numero,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, codigo, nombre, lote, cantidad, unidad,
                   destino, coste_unitario, fecha
            FROM subproductos
            ORDER BY fecha DESC
        """).fetchall()
    conn.close()
    return rows


# =========================================================
# COSTE REAL AJUSTADO
# =========================================================
def coste_real_ajustado(pedido_numero):
    """
    Coste real del pedido teniendo en cuenta:
      - Consumo real de MP (si hay pesos reales)
      - Mermas registradas
      - Subproductos aprovechados

    Devuelve dict con desglose:
      coste_teorico, ajuste_pesos, coste_mermas,
      ahorro_subproductos, coste_real
    """
    conn = conectar()

    # Coste teórico desde escandallo_real
    row = conn.execute("""
        SELECT COALESCE(SUM(subtotal), 0)
        FROM escandallo_real
        WHERE producto_lote = ?
    """, (pedido_numero,)).fetchone()
    coste_teorico = row[0] if row else 0

    # Ajuste por desviación de peso real
    pesos = conn.execute("""
        SELECT articulo_codigo, articulo_lote,
               cantidad_teorica, cantidad_real
        FROM pesos_reales
        WHERE pedido_numero = ?
    """, (pedido_numero,)).fetchall()

    ajuste_pesos = 0
    for cod, lote, teor, real in pesos:
        if not teor:
            continue
        precio_row = conn.execute("""
            SELECT coste_unitario FROM materias_primas
            WHERE codigo = ? AND lote = ? LIMIT 1
        """, (cod, lote)).fetchone()
        precio = precio_row[0] if precio_row else 0
        ajuste_pesos += (real - teor) * precio

    # Coste de mermas
    row = conn.execute("""
        SELECT COALESCE(SUM(coste_estimado), 0)
        FROM mermas
        WHERE pedido_numero = ?
    """, (pedido_numero,)).fetchone()
    coste_mermas = row[0] if row else 0

    # Ahorro por subproductos
    row = conn.execute("""
        SELECT COALESCE(SUM(cantidad * coste_unitario), 0)
        FROM subproductos
        WHERE pedido_numero = ?
    """, (pedido_numero,)).fetchone()
    ahorro_subproductos = row[0] if row else 0

    conn.close()

    coste_real = coste_teorico + ajuste_pesos + coste_mermas - ahorro_subproductos

    return {
        "coste_teorico": coste_teorico,
        "ajuste_pesos": ajuste_pesos,
        "coste_mermas": coste_mermas,
        "ahorro_subproductos": ahorro_subproductos,
        "coste_real": coste_real,
    }


__all__ = [
    "registrar_peso_real",
    "pesos_de_pedido",
    "resumen_merma_pedido",
    "registrar_merma",
    "listar_mermas",
    "resumen_mermas_producto",
    "registrar_subproducto",
    "listar_subproductos",
    "coste_real_ajustado",
]
