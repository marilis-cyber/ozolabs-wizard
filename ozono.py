"""
OZOLABS' WIZARD - Fabricación de aceites ozonizados
=====================================================
- Registro de producciones de ozonización (parámetros del generador).
- Stock de aceite ozonizado organizado por GARRAFAS (1, 2, 5, 10 L).
- Salidas de garrafas con historial de consumo (en qué se ha gastado).
"""
from database import conectar
from datetime import datetime


# =========================================================
# PRODUCCIONES DE OZONIZACIÓN
# =========================================================
def crear_produccion_ozono(litros, reactor, aceite_codigo="",
                           aceite_nombre="", aceite_lote="", proveedor="",
                           flujo=0, presion=0, nitrogeno="", trampa_agua="",
                           emulsion="", hora_inicio="", hora_fin="",
                           observaciones="", responsable=""):
    """Registra una producción de aceite ozonizado."""
    numero = f"OZO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = conectar()
    conn.execute("""
        INSERT INTO ozono_producciones
        (numero, fecha, hora_inicio, hora_fin, litros, reactor,
         aceite_codigo, aceite_nombre, aceite_lote, proveedor,
         flujo, presion, nitrogeno, trampa_agua, emulsion,
         observaciones, responsable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (numero, datetime.now().date().isoformat(), hora_inicio, hora_fin,
          litros, reactor, aceite_codigo, aceite_nombre, aceite_lote,
          proveedor, flujo, presion, nitrogeno, trampa_agua, emulsion,
          observaciones, responsable))
    conn.commit()
    conn.close()
    print(f"✔ Producción de ozono {numero} registrada ({litros} L).")
    return numero


def listar_producciones_ozono(limite=200):
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, fecha, hora_inicio, hora_fin, litros, reactor,
               aceite_nombre, aceite_lote, proveedor, flujo, presion,
               nitrogeno, trampa_agua, emulsion, observaciones, responsable
        FROM ozono_producciones
        ORDER BY id DESC LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


# =========================================================
# GARRAFAS (stock de aceite ozonizado)
# =========================================================
def crear_garrafa(litros_capacidad, produccion_numero="", lote="",
                  producto="Aceite ozonizado", ubicacion=""):
    """
    Crea una garrafa (continente) con su capacidad de litros.
    El código se genera automáticamente: GAR-0001, GAR-0002...
    """
    conn = conectar()
    n = conn.execute("SELECT COUNT(*) FROM garrafas").fetchone()[0]
    codigo = f"GAR-{n + 1:04d}"
    conn.execute("""
        INSERT INTO garrafas
        (codigo, litros_capacidad, litros_disponibles, produccion_numero,
         lote, producto, fecha_llenado, ubicacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (codigo, litros_capacidad, litros_capacidad, produccion_numero,
          lote, producto, datetime.now().date().isoformat(), ubicacion))
    conn.commit()
    conn.close()
    print(f"✔ Garrafa {codigo} ({litros_capacidad} L) creada.")
    return codigo


def listar_garrafas():
    conn = conectar()
    rows = conn.execute("""
        SELECT codigo, litros_capacidad, litros_disponibles,
               produccion_numero, lote, producto, fecha_llenado, ubicacion
        FROM garrafas
        ORDER BY codigo
    """).fetchall()
    conn.close()
    return rows


def detalle_garrafa(codigo):
    """Devuelve los datos de una garrafa y su historial de salidas."""
    conn = conectar()
    garrafa = conn.execute("""
        SELECT codigo, litros_capacidad, litros_disponibles,
               produccion_numero, lote, producto, fecha_llenado, ubicacion
        FROM garrafas WHERE codigo = ?
    """, (codigo,)).fetchone()
    salidas = conn.execute("""
        SELECT fecha, litros, destino, comentarios, responsable
        FROM salidas_garrafa
        WHERE garrafa_codigo = ?
        ORDER BY id DESC
    """, (codigo,)).fetchall()
    conn.close()
    return garrafa, salidas


def crear_salida_garrafa(garrafa_codigo, litros, destino,
                         comentarios="", responsable=""):
    """Registra una salida de litros de una garrafa (descuenta stock)."""
    conn = conectar()
    row = conn.execute(
        "SELECT litros_disponibles FROM garrafas WHERE codigo = ?",
        (garrafa_codigo,)
    ).fetchone()
    if not row:
        conn.close()
        return False, "Garrafa no encontrada."
    if litros > row[0] + 0.001:
        conn.close()
        return False, f"Solo quedan {row[0]:.2f} L en esa garrafa."

    conn.execute("""
        INSERT INTO salidas_garrafa
        (garrafa_codigo, fecha, litros, destino, comentarios, responsable)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (garrafa_codigo, datetime.now().isoformat(), litros, destino,
          comentarios, responsable))
    conn.execute("""
        UPDATE garrafas
        SET litros_disponibles = litros_disponibles - ?
        WHERE codigo = ?
    """, (litros, garrafa_codigo))
    conn.commit()
    conn.close()
    print(f"✔ Salida de {litros} L de {garrafa_codigo} → {destino}.")
    return True, "Salida registrada."


def resumen_stock_ozono():
    """Total de litros disponibles en todas las garrafas."""
    conn = conectar()
    row = conn.execute("""
        SELECT COUNT(*), COALESCE(SUM(litros_disponibles), 0),
               COALESCE(SUM(litros_capacidad), 0)
        FROM garrafas
    """).fetchone()
    conn.close()
    return {
        "garrafas": row[0],
        "litros_disponibles": row[1],
        "litros_capacidad": row[2],
    }


__all__ = [
    "crear_produccion_ozono", "listar_producciones_ozono",
    "crear_garrafa", "listar_garrafas", "detalle_garrafa",
    "crear_salida_garrafa", "resumen_stock_ozono",
]
