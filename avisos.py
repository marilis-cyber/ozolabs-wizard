"""
OZOLABS' WIZARD - Sistema de alertas automáticas
"""
from database import conectar
from datetime import datetime, timedelta


def avisos_envases():
    avisos = []
    conn = conectar()
    rows = conn.execute("""
        SELECT codigo, nombre, lote, cantidad, unidad, stock_minimo
        FROM envases
    """).fetchall()
    agregados = {}
    for cod, nom, lote, cant, uni, smin in rows:
        agregados.setdefault(cod, {"nombre": nom, "total": 0, "smin": smin, "uni": uni})
        agregados[cod]["total"] += cant
    for cod, d in agregados.items():
        if d["smin"] and d["total"] < d["smin"]:
            avisos.append(
                f"⚠ Stock bajo de ENVASE '{d['nombre']}' ({cod}): "
                f"{d['total']:.0f} (mínimo {d['smin']})."
            )
    conn.close()
    return avisos


def avisos_ordenes_pendientes():
    avisos = []
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, fecha_prevista FROM ordenes_produccion
        WHERE estado IN ('planificado', 'en_preparacion', 'en_curso')
    """).fetchall()
    hoy = datetime.now().date()
    for numero, fprev in rows:
        if fprev:
            try:
                f = datetime.fromisoformat(fprev).date()
                if f < hoy:
                    avisos.append(f"🔴 Pedido {numero} RETRASADO (previsto {fprev}).")
                elif (f - hoy).days <= 3:
                    avisos.append(f"📅 Pedido {numero} previsto para {fprev}.")
            except Exception:
                pass
    conn.close()
    return avisos


def avisos_lotes_bloqueados():
    avisos = []
    conn = conectar()
    rows = conn.execute("""
        SELECT tipo_articulo, articulo_codigo, lote, fecha, estado
        FROM liberacion_lotes
        WHERE estado IN ('bloqueado', 'rechazado')
    """).fetchall()
    for t, c, l, f, e in rows:
        avisos.append(f"🚫 Lote {l} de {c} ({t}) está {e} (desde {f[:10]}).")
    conn.close()
    return avisos


def avisos_no_conformidades_abiertas():
    avisos = []
    conn = conectar()
    rows = conn.execute("""
        SELECT id, articulo_codigo, lote, gravedad, descripcion
        FROM no_conformidades
        WHERE estado IN ('abierta', 'en_proceso')
    """).fetchall()
    for i, c, l, g, d in rows:
        avisos.append(f"⚠ NC #{i} ({g}) {c} lote {l}: {d[:60]}")
    conn.close()
    return avisos


def avisos_pedidos_en_preparacion():
    avisos = []
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, fecha_inicio FROM ordenes_produccion
        WHERE estado = 'en_preparacion'
    """).fetchall()
    hoy = datetime.now()
    for numero, fini in rows:
        if fini:
            try:
                f = datetime.fromisoformat(fini)
                horas = (hoy - f).total_seconds() / 3600
                if horas > 48:
                    avisos.append(
                        f"⏳ Pedido {numero} lleva {horas:.0f} h en preparación. "
                        f"¿Se ha olvidado finalizarlo?"
                    )
            except Exception:
                pass
    conn.close()
    return avisos


def avisos_pedidos_en_curso():
    avisos = []
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, fecha_inicio FROM ordenes_produccion
        WHERE estado = 'en_curso'
    """).fetchall()
    hoy = datetime.now()
    for numero, fini in rows:
        if fini:
            try:
                f = datetime.fromisoformat(fini)
                horas = (hoy - f).total_seconds() / 3600
                if horas > 24:
                    avisos.append(
                        f"⏳ Pedido {numero} lleva {horas:.0f} h en curso. "
                        f"Recuerda finalizarlo."
                    )
            except Exception:
                pass
    conn.close()
    return avisos


def generar_avisos(dias_caducidad=30, dias_certificado=60):
    avisos = []
    hoy = datetime.now().date()
    limite = hoy + timedelta(days=dias_caducidad)
    limite_cert = hoy + timedelta(days=dias_certificado)

    conn = conectar()

    # Stock mínimo MP (agrupado por código)
    rows = conn.execute("""
        SELECT codigo, nombre, SUM(cantidad), unidad, MAX(stock_minimo)
        FROM materias_primas GROUP BY codigo
    """).fetchall()
    for cod, nom, total, uni, smin in rows:
        if smin and total < smin:
            avisos.append(
                f"⚠ Stock bajo de MP '{nom}' ({cod}): {total:.2f} {uni} (mínimo {smin})."
            )

    # Caducidad MP
    rows = conn.execute("""
        SELECT codigo, nombre, lote, cantidad, unidad, fecha_caducidad
        FROM materias_primas
        WHERE cantidad > 0 AND fecha_caducidad IS NOT NULL
    """).fetchall()
    for cod, nom, lote, cant, uni, fcad in rows:
        try:
            f = datetime.fromisoformat(fcad).date()
        except Exception:
            continue
        if f < hoy:
            avisos.append(f"❌ LOTE CADUCADO: {nom} lote {lote} caducó el {fcad}.")
        elif f <= limite:
            dias = (f - hoy).days
            avisos.append(f"⏰ El lote {lote} de {nom} caduca en {dias} días ({fcad}).")

    # Certificados ecológicos
    rows = conn.execute("""
        SELECT nombre, lote, certificado_eco, caducidad_certificado
        FROM materias_primas
        WHERE certificado_eco IS NOT NULL AND caducidad_certificado IS NOT NULL
    """).fetchall()
    for nom, lote, cert, fcert in rows:
        try:
            f = datetime.fromisoformat(fcert).date()
        except Exception:
            continue
        if f < hoy:
            avisos.append(f"❌ Certificado '{cert}' de {nom} (lote {lote}) CADUCADO.")
        elif f <= limite_cert:
            dias = (f - hoy).days
            avisos.append(f"📜 Certificado '{cert}' de {nom} caduca en {dias} días.")

    # Stock mínimo PT
    rows = conn.execute("""
        SELECT p.codigo, p.nombre, COALESCE(SUM(s.cantidad), 0), p.stock_minimo
        FROM productos p
        LEFT JOIN stock_producto s ON s.producto_id = p.id
        GROUP BY p.id
    """).fetchall()
    for cod, nom, total, smin in rows:
        if smin and total < smin:
            avisos.append(
                f"⚠ Stock bajo de PT '{nom}' ({cod}): {total} uds (mínimo {smin})."
            )

    conn.close()

    # Avisos ampliados
    avisos.extend(avisos_envases())
    avisos.extend(avisos_ordenes_pendientes())
    avisos.extend(avisos_lotes_bloqueados())
    avisos.extend(avisos_no_conformidades_abiertas())
    avisos.extend(avisos_pedidos_en_preparacion())
    avisos.extend(avisos_pedidos_en_curso())

    return avisos
