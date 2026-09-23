"""
OZOLABS' WIZARD - Compras y recepción de mercancía
"""
from database import conectar
from datetime import datetime


# =========================================================
# ÓRDENES DE COMPRA
# =========================================================
def crear_orden_compra(proveedor_codigo, lineas, fecha_prevista=None,
                       observaciones="", condiciones_pago="",
                       usuario_creador=""):
    """
    Crea una orden de compra.
    lineas = lista de dicts con:
        {tipo_articulo, articulo_codigo, articulo_nombre,
         cantidad, unidad, precio_unitario, notas}
    """
    numero = f"OC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total = sum(l["cantidad"] * l["precio_unitario"] for l in lineas)

    conn = conectar()
    conn.execute("""
        INSERT INTO ordenes_compra
        (numero, proveedor_codigo, estado, fecha_creacion, fecha_prevista,
         observaciones, condiciones_pago, total_estimado, usuario_creador)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (numero, proveedor_codigo, "borrador",
          datetime.now().isoformat(), fecha_prevista,
          observaciones, condiciones_pago, total, usuario_creador))

    for l in lineas:
        subtotal = l["cantidad"] * l["precio_unitario"]
        conn.execute("""
            INSERT INTO lineas_compra
            (orden_numero, tipo_articulo, articulo_codigo, articulo_nombre,
             cantidad_pedida, unidad, precio_unitario, subtotal, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (numero, l["tipo_articulo"], l["articulo_codigo"],
              l.get("articulo_nombre", ""), l["cantidad"], l["unidad"],
              l["precio_unitario"], subtotal, l.get("notas", "")))

    conn.commit()
    conn.close()
    print(f"✔ Orden de compra {numero} creada. Total: {total:.2f} €")
    return numero


def listar_ordenes_compra(estado=None, proveedor=None):
    conn = conectar()
    q = """
        SELECT numero, proveedor_codigo, estado, fecha_creacion,
               fecha_prevista, fecha_recepcion, total_estimado
        FROM ordenes_compra WHERE 1 = 1
    """
    params = []
    if estado:
        q += " AND estado = ?"
        params.append(estado)
    if proveedor:
        q += " AND proveedor_codigo = ?"
        params.append(proveedor)
    q += " ORDER BY fecha_creacion DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def ver_orden_compra(numero):
    """
    Devuelve (cabecera, lineas) de una OC.
    cabecera = (numero, proveedor_codigo, estado, fecha_creacion,
                fecha_prevista, fecha_recepcion, observaciones,
                condiciones_pago, total_estimado)
    lineas   = lista de tuplas con todos los campos de cada línea.
    """
    conn = conectar()
    cabecera = conn.execute("""
        SELECT numero, proveedor_codigo, estado, fecha_creacion,
               fecha_prevista, fecha_recepcion, observaciones,
               condiciones_pago, total_estimado
        FROM ordenes_compra WHERE numero = ?
    """, (numero,)).fetchone()

    lineas = conn.execute("""
        SELECT id, tipo_articulo, articulo_codigo, articulo_nombre,
               cantidad_pedida, cantidad_recibida, unidad,
               precio_unitario, subtotal, notas
        FROM lineas_compra
        WHERE orden_numero = ?
    """, (numero,)).fetchall()
    conn.close()
    return cabecera, lineas


def cambiar_estado_orden_compra(numero, nuevo_estado):
    conn = conectar()
    if nuevo_estado == "enviada":
        conn.execute("""
            UPDATE ordenes_compra
            SET estado = ?, fecha_envio = ?
            WHERE numero = ?
        """, (nuevo_estado, datetime.now().isoformat(), numero))
    else:
        conn.execute(
            "UPDATE ordenes_compra SET estado = ? WHERE numero = ?",
            (nuevo_estado, numero)
        )
    conn.commit()
    conn.close()
    print(f"✔ Orden {numero} → {nuevo_estado}")


def calcular_necesidad_compra_mrp():
    """
    A partir de las necesidades MRP, sugiere agrupar por proveedor
    las MP/envases que hay que comprar.
    Devuelve dict {proveedor: [items]}.
    """
    from modelos import necesidades_mrp
    necesidades = necesidades_mrp()

    conn = conectar()
    sugerencias = []
    for n in necesidades:
        if n["a_comprar"] <= 0:
            continue
        if n["tipo"] == "MP":
            row = conn.execute("""
                SELECT proveedor FROM materias_primas
                WHERE codigo = ? AND proveedor IS NOT NULL
                ORDER BY fecha_recepcion DESC LIMIT 1
            """, (n["codigo"],)).fetchone()
            precio_row = conn.execute("""
                SELECT coste_unitario FROM materias_primas
                WHERE codigo = ?
                ORDER BY fecha_recepcion DESC LIMIT 1
            """, (n["codigo"],)).fetchone()
        else:
            row = conn.execute("""
                SELECT proveedor FROM envases
                WHERE codigo = ? AND proveedor IS NOT NULL
                ORDER BY fecha_recepcion DESC LIMIT 1
            """, (n["codigo"],)).fetchone()
            precio_row = conn.execute("""
                SELECT coste_unitario FROM envases
                WHERE codigo = ?
                ORDER BY fecha_recepcion DESC LIMIT 1
            """, (n["codigo"],)).fetchone()

        proveedor = row[0] if row else "(sin proveedor)"
        precio = precio_row[0] if precio_row else 0

        sugerencias.append({
            "tipo": n["tipo"],
            "codigo": n["codigo"],
            "cantidad": n["a_comprar"],
            "unidad": n["unidad"],
            "proveedor": proveedor,
            "precio": precio,
            "subtotal": n["a_comprar"] * precio,
        })

    conn.close()

    # Agrupar por proveedor
    grupos = {}
    for s in sugerencias:
        grupos.setdefault(s["proveedor"], []).append(s)
    return grupos


# =========================================================
# RECEPCIONES
# =========================================================
def crear_recepcion(orden_compra, albaran_proveedor="",
                    usuario_receptor="", observaciones=""):
    numero = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    conn = conectar()
    oc = conn.execute("""
        SELECT proveedor_codigo FROM ordenes_compra WHERE numero = ?
    """, (orden_compra,)).fetchone()
    proveedor = oc[0] if oc else None

    conn.execute("""
        INSERT INTO recepciones
        (numero, orden_compra, proveedor_codigo, fecha, albaran_proveedor,
         usuario_receptor, observaciones, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (numero, orden_compra, proveedor, datetime.now().isoformat(),
          albaran_proveedor, usuario_receptor, observaciones, "pendiente_qc"))
    conn.commit()
    conn.close()
    print(f"✔ Recepción {numero} creada.")
    return numero


def añadir_linea_recepcion(recepcion_numero, tipo_articulo, articulo_codigo,
                            lote_proveedor, cantidad, unidad,
                            fecha_caducidad=None, certificado_eco=None,
                            caducidad_certificado=None, coste_unitario=0,
                            ubicacion=""):
    """Añade una línea y la marca como pendiente de QC."""
    lote_interno = f"{articulo_codigo}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    conn = conectar()
    conn.execute("""
        INSERT INTO lineas_recepcion
        (recepcion_numero, tipo_articulo, articulo_codigo, lote_proveedor,
         lote_interno, cantidad_recibida, unidad, fecha_caducidad,
         certificado_eco, caducidad_certificado, coste_unitario, ubicacion,
         estado_qc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (recepcion_numero, tipo_articulo, articulo_codigo, lote_proveedor,
          lote_interno, cantidad, unidad, fecha_caducidad,
          certificado_eco, caducidad_certificado, coste_unitario, ubicacion,
          "pendiente"))
    conn.commit()
    conn.close()
    return lote_interno


def confirmar_recepcion_y_entrar_stock(recepcion_numero, usuario=""):
    """
    Mete las líneas conformes al stock. Las que no estén aptas no entran.
    Actualiza la OC con las cantidades recibidas.
    """
    from modelos import añadir_materia, añadir_envase

    conn = conectar()
    lineas = conn.execute("""
        SELECT id, tipo_articulo, articulo_codigo, lote_proveedor,
               lote_interno, cantidad_recibida, unidad, fecha_caducidad,
               certificado_eco, caducidad_certificado, coste_unitario,
               ubicacion, estado_qc
        FROM lineas_recepcion
        WHERE recepcion_numero = ?
    """, (recepcion_numero,)).fetchall()

    cab = conn.execute(
        "SELECT orden_compra FROM recepciones WHERE numero = ?",
        (recepcion_numero,)
    ).fetchone()
    oc_numero = cab[0] if cab else None
    conn.close()

    total_lineas = 0
    for (lid, tipo, cod, lote_prov, lote_int, cant, uni, fcad, eco,
         feco, coste, ubi, qc) in lineas:
        if qc != "apto":
            continue

        if tipo == "MP":
            añadir_materia(cod, cod, None, lote_int, cant, uni,
                           datetime.now().date().isoformat(), fcad,
                           eco, feco, coste, ubi, 0)
        elif tipo == "ENV":
            añadir_envase(cod, cod, "otro", lote_int, cant, uni,
                          coste, "", ubi, 0)
        total_lineas += 1

        # Actualizar línea de OC
        if oc_numero:
            conn2 = conectar()
            conn2.execute("""
                UPDATE lineas_compra
                SET cantidad_recibida = cantidad_recibida + ?
                WHERE orden_numero = ? AND articulo_codigo = ?
            """, (cant, oc_numero, cod))
            conn2.commit()
            conn2.close()

    # Actualizar estado OC
    if oc_numero:
        conn3 = conectar()
        lineas_oc = conn3.execute("""
            SELECT cantidad_pedida, cantidad_recibida
            FROM lineas_compra WHERE orden_numero = ?
        """, (oc_numero,)).fetchall()
        completa = all(r[1] >= r[0] for r in lineas_oc)
        parcial = any(r[1] > 0 for r in lineas_oc)
        estado = "recibida" if completa else (
            "recibida_parcial" if parcial else "confirmada"
        )
        conn3.execute("""
            UPDATE ordenes_compra
            SET estado = ?, fecha_recepcion = ?
            WHERE numero = ?
        """, (estado, datetime.now().isoformat(), oc_numero))
        conn3.commit()
        conn3.close()

    # Actualizar estado recepción
    conn4 = conectar()
    conn4.execute(
        "UPDATE recepciones SET estado = 'conforme' WHERE numero = ?",
        (recepcion_numero,)
    )
    conn4.commit()
    conn4.close()

    print(f"✔ Recepción {recepcion_numero}: {total_lineas} líneas al stock.")
    return total_lineas


def lineas_recepcion(recepcion_numero):
    conn = conectar()
    rows = conn.execute("""
        SELECT id, tipo_articulo, articulo_codigo, lote_proveedor,
               lote_interno, cantidad_recibida, unidad, fecha_caducidad,
               coste_unitario, ubicacion, estado_qc
        FROM lineas_recepcion
        WHERE recepcion_numero = ?
    """, (recepcion_numero,)).fetchall()
    conn.close()
    return rows


def marcar_linea_qc(linea_id, resultado):
    """resultado: pendiente / apto / no_apto"""
    conn = conectar()
    conn.execute(
        "UPDATE lineas_recepcion SET estado_qc = ? WHERE id = ?",
        (resultado, linea_id)
    )
    conn.commit()
    conn.close()


def listar_recepciones(estado=None):
    conn = conectar()
    if estado:
        rows = conn.execute("""
            SELECT numero, orden_compra, proveedor_codigo, fecha,
                   albaran_proveedor, estado
            FROM recepciones
            WHERE estado = ?
            ORDER BY fecha DESC
        """, (estado,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT numero, orden_compra, proveedor_codigo, fecha,
                   albaran_proveedor, estado
            FROM recepciones
            ORDER BY fecha DESC
        """).fetchall()
    conn.close()
    return rows


__all__ = [
    "crear_orden_compra",
    "listar_ordenes_compra",
    "ver_orden_compra",
    "cambiar_estado_orden_compra",
    "calcular_necesidad_compra_mrp",
    "crear_recepcion",
    "añadir_linea_recepcion",
    "confirmar_recepcion_y_entrar_stock",
    "lineas_recepcion",
    "marcar_linea_qc",
    "listar_recepciones",
]
