"""
OZOLABS' WIZARD - Análisis y gráficos históricos
"""
import pandas as pd
from database import conectar


def serie_stock_mp():
    """Evolución temporal del stock total de MP (por código)."""
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT codigo, nombre, SUM(cantidad) AS stock, unidad
        FROM materias_primas
        GROUP BY codigo
        ORDER BY nombre
    """, conn)
    conn.close()
    return df


def serie_producciones_por_mes():
    """Producciones agrupadas por mes y producto."""
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT strftime('%Y-%m', pr.fecha) AS mes,
               p.nombre AS producto,
               SUM(pr.cantidad) AS unidades,
               SUM(pr.coste_total) AS coste
        FROM producciones pr
        JOIN productos p ON p.id = pr.producto_id
        GROUP BY mes, producto
        ORDER BY mes
    """, conn)
    conn.close()
    return df


def coste_unitario_por_producto():
    """Coste unitario real medio por producto (usando escandallos reales)."""
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT p.nombre AS producto,
               pr.lote,
               pr.cantidad,
               pr.coste_total,
               CASE WHEN pr.cantidad > 0
                    THEN pr.coste_total / pr.cantidad ELSE 0 END AS coste_unitario
        FROM producciones pr
        JOIN productos p ON p.id = pr.producto_id
        ORDER BY pr.fecha
    """, conn)
    conn.close()
    return df


def evolucion_coste_por_producto():
    """Evolución del coste unitario a lo largo del tiempo (por producto)."""
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT DATE(pr.fecha) AS fecha,
               p.nombre AS producto,
               CASE WHEN pr.cantidad > 0
                    THEN pr.coste_total / pr.cantidad ELSE 0 END AS coste_unitario
        FROM producciones pr
        JOIN productos p ON p.id = pr.producto_id
        WHERE pr.cantidad > 0
        ORDER BY fecha
    """, conn)
    conn.close()
    return df


def consumo_mp_por_mes():
    """Consumo de MP por mes (a partir de movimientos de trazabilidad)."""
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT strftime('%Y-%m', fecha) AS mes,
               materia_codigo AS mp,
               SUM(cantidad_usada) AS cantidad
        FROM trazabilidad
        GROUP BY mes, materia_codigo
        ORDER BY mes
    """, conn)
    conn.close()
    return df


def top_productos_por_volumen(limite=10):
    conn = conectar()
    df = pd.read_sql_query(f"""
        SELECT p.nombre AS producto, SUM(pr.cantidad) AS total
        FROM producciones pr
        JOIN productos p ON p.id = pr.producto_id
        GROUP BY p.nombre
        ORDER BY total DESC
        LIMIT {int(limite)}
    """, conn)
    conn.close()
    return df


def kpis_generales():
    """KPIs para el dashboard."""
    conn = conectar()
    kpis = {}

    kpis["total_producciones"] = conn.execute(
        "SELECT COUNT(*) FROM producciones"
    ).fetchone()[0]
    kpis["unidades_totales"] = conn.execute(
        "SELECT COALESCE(SUM(cantidad), 0) FROM producciones"
    ).fetchone()[0]
    kpis["coste_total"] = conn.execute(
        "SELECT COALESCE(SUM(coste_total), 0) FROM producciones"
    ).fetchone()[0]

    kpis["lotes_mp"] = conn.execute(
        "SELECT COUNT(DISTINCT codigo || '|' || lote) FROM materias_primas"
    ).fetchone()[0]
    kpis["lotes_pt"] = conn.execute(
        "SELECT COUNT(*) FROM stock_producto WHERE cantidad > 0"
    ).fetchone()[0]

    kpis["nc_abiertas"] = conn.execute(
        "SELECT COUNT(*) FROM no_conformidades WHERE estado != 'cerrada'"
    ).fetchone()[0]
    kpis["lotes_bloqueados"] = conn.execute(
        "SELECT COUNT(*) FROM liberacion_lotes "
        "WHERE estado IN ('bloqueado', 'rechazado')"
    ).fetchone()[0]

    conn.close()
    return kpis


def mermas_por_producto():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT producto_codigo AS producto,
               tipo,
               COALESCE(SUM(cantidad), 0) AS cantidad,
               COALESCE(SUM(coste_estimado), 0) AS coste
        FROM mermas
        GROUP BY producto_codigo, tipo
        ORDER BY coste DESC
    """, conn)
    conn.close()
    return df


def desviacion_media_por_mp():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT articulo_codigo AS mp,
               AVG(desviacion_pct) AS desv_media_pct,
               COUNT(*) AS veces
        FROM pesos_reales
        GROUP BY articulo_codigo
        ORDER BY ABS(AVG(desviacion_pct)) DESC
    """, conn)
    conn.close()
    return df


def pedidos_por_estado():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT estado, COUNT(*) AS cantidad,
               SUM(cantidad_planificada) AS unidades
        FROM ordenes_produccion
        GROUP BY estado
    """, conn)
    conn.close()
    return df


def compras_por_mes():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT strftime('%Y-%m', fecha_creacion) AS mes,
               COUNT(*) AS ordenes,
               SUM(total_estimado) AS total
        FROM ordenes_compra
        WHERE estado != 'cancelada'
        GROUP BY mes
        ORDER BY mes
    """, conn)
    conn.close()
    return df


def proveedores_top(limite=10):
    conn = conectar()
    df = pd.read_sql_query(f"""
        SELECT proveedor_codigo AS proveedor,
               COUNT(*) AS ordenes,
               SUM(total_estimado) AS total
        FROM ordenes_compra
        WHERE estado != 'cancelada'
        GROUP BY proveedor_codigo
        ORDER BY total DESC
        LIMIT {int(limite)}
    """, conn)
    conn.close()
    return df


def rendimiento_por_producto():
    conn = conectar()
    df = pd.read_sql_query("""
        SELECT producto_codigo AS producto,
               AVG(rendimiento_pct) AS rendimiento_medio,
               COUNT(*) AS lotes
        FROM rendimiento_lote
        GROUP BY producto_codigo
        ORDER BY rendimiento_medio
    """, conn)
    conn.close()
    return df
