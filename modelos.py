"""
OZOLABS' WIZARD - Lógica de negocio
Todas las operaciones sobre materias primas, productos, producción,
envases, proveedores, costes, pedidos, calidad y exportaciones.
"""
from database import conectar
from datetime import datetime, timedelta
import csv


# =========================================================
# MATERIAS PRIMAS
# =========================================================
def añadir_materia(codigo, nombre, proveedor, lote, cantidad, unidad,
                   fecha_recepcion, fecha_caducidad, certificado_eco=None,
                   caducidad_certificado=None, coste_unitario=0,
                   ubicacion="", stock_minimo=0):
    conn = conectar()
    try:
        conn.execute("""
            INSERT INTO materias_primas
            (codigo, nombre, proveedor, lote, cantidad, unidad, fecha_recepcion,
             fecha_caducidad, certificado_eco, caducidad_certificado,
             coste_unitario, ubicacion, stock_minimo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, proveedor, lote, cantidad, unidad, fecha_recepcion,
              fecha_caducidad, certificado_eco, caducidad_certificado,
              coste_unitario, ubicacion, stock_minimo))
        conn.commit()
        print(f"✔ Materia '{nombre}' (lote {lote}) registrada.")
        return True
    except Exception as e:
        print(f"✘ Error: {e}")
        return False
    finally:
        conn.close()


def listar_materias():
    conn = conectar()
    rows = conn.execute("""
        SELECT codigo, nombre, lote, cantidad, unidad,
               fecha_caducidad, ubicacion
        FROM materias_primas
        ORDER BY nombre, fecha_caducidad
    """).fetchall()
    conn.close()
    return rows


def stock_por_codigo(codigo):
    conn = conectar()
    row = conn.execute("""
        SELECT COALESCE(SUM(cantidad), 0), unidad
        FROM materias_primas
        WHERE codigo = ?
        GROUP BY unidad
    """, (codigo,)).fetchone()
    conn.close()
    return row if row else (0, "")


def lotes_disponibles(codigo):
    """Devuelve lotes ordenados por caducidad (FEFO)."""
    conn = conectar()
    rows = conn.execute("""
        SELECT id, lote, cantidad, unidad, fecha_caducidad
        FROM materias_primas
        WHERE codigo = ? AND cantidad > 0
        ORDER BY fecha_caducidad IS NULL, fecha_caducidad
    """, (codigo,)).fetchall()
    conn.close()
    return rows


def descontar_fefo(codigo, cantidad_necesaria, unidad=""):
    """Descuenta del stock siguiendo FEFO (First Expired, First Out).
    Devuelve lista de (lote, cantidad_usada, unidad)."""
    lotes = lotes_disponibles(codigo)
    restante = cantidad_necesaria
    usados = []
    conn = conectar()
    for mid, lote, cant, uni, fcad in lotes:
        if restante <= 0:
            break
        usar = min(cant, restante)
        conn.execute(
            "UPDATE materias_primas SET cantidad = cantidad - ? WHERE id = ?",
            (usar, mid)
        )
        usados.append((lote, usar, uni))
        restante -= usar
    conn.commit()
    conn.close()
    if restante > 0.0001:
        raise ValueError(f"Stock insuficiente de {codigo}. Faltan {restante} {unidad}")
    return usados


# Alias por compatibilidad con app.py
descontar_stock_fefo = descontar_fefo


# =========================================================
# PRODUCTOS
# =========================================================
def añadir_producto(codigo, nombre, formato="", stock_minimo=0):
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO productos (codigo, nombre, formato, stock_minimo) VALUES (?, ?, ?, ?)",
            (codigo, nombre, formato, stock_minimo)
        )
        conn.commit()
        print(f"✔ Producto '{nombre}' creado.")
        return True
    except Exception as e:
        print(f"✘ Error: {e}")
        return False
    finally:
        conn.close()


def obtener_producto(codigo):
    conn = conectar()
    row = conn.execute(
        "SELECT id, codigo, nombre, formato, stock_minimo FROM productos WHERE codigo = ?",
        (codigo,)
    ).fetchone()
    conn.close()
    return row


def añadir_ingrediente_formula(producto_codigo, materia_codigo, cantidad, unidad):
    prod = obtener_producto(producto_codigo)
    if not prod:
        print("✘ Producto no existe.")
        return False
    conn = conectar()
    conn.execute("""
        INSERT INTO formulas (producto_id, materia_codigo, cantidad_por_unidad, unidad)
        VALUES (?, ?, ?, ?)
    """, (prod[0], materia_codigo, cantidad, unidad))
    conn.commit()
    conn.close()
    print(f"✔ Ingrediente añadido a la fórmula de {producto_codigo}.")
    return True


def ver_formula(producto_codigo):
    prod = obtener_producto(producto_codigo)
    if not prod:
        return []
    conn = conectar()
    rows = conn.execute("""
        SELECT materia_codigo, cantidad_por_unidad, unidad
        FROM formulas
        WHERE producto_id = ?
    """, (prod[0],)).fetchall()
    conn.close()
    return rows


def stock_producto_terminado(codigo=None):
    conn = conectar()
    if codigo:
        rows = conn.execute("""
            SELECT p.codigo, p.nombre, s.lote, s.cantidad,
                   s.fecha_caducidad, s.fecha_fabricacion
            FROM stock_producto s
            JOIN productos p ON p.id = s.producto_id
            WHERE p.codigo = ?
            ORDER BY s.fecha_caducidad IS NULL, s.fecha_caducidad
        """, (codigo,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT p.codigo, p.nombre, s.lote, s.cantidad,
                   s.fecha_caducidad, s.fecha_fabricacion
            FROM stock_producto s
            JOIN productos p ON p.id = s.producto_id
            ORDER BY p.nombre
        """).fetchall()
    conn.close()
    return rows


def trazabilidad_lote(lote_pt):
    conn = conectar()
    rows = conn.execute("""
        SELECT materia_codigo, materia_lote, cantidad_usada, fecha
        FROM trazabilidad
        WHERE producto_lote = ?
    """, (lote_pt,)).fetchall()
    conn.close()
    return rows


# =========================================================
# PRODUCCIÓN
# =========================================================
def producir(producto_codigo, cantidad_unidades, lote_pt=None, fecha_caducidad_pt=None):
    prod = obtener_producto(producto_codigo)
    if not prod:
        print("✘ Producto no existe.")
        return False
    formula = ver_formula(producto_codigo)
    if not formula:
        print("✘ El producto no tiene fórmula definida.")
        return False

    # Comprobar stock primero
    for mat_cod, cant_u, uni in formula:
        necesaria = cant_u * cantidad_unidades
        disp, u = stock_por_codigo(mat_cod)
        if disp < necesaria:
            print(f"✘ Stock insuficiente de {mat_cod}: necesitas {necesaria} {uni}, hay {disp} {u}")
            return False

    if not lote_pt:
        lote_pt = f"PT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    conn = conectar()
    coste_total = 0.0

    # Descontar MP con FEFO y registrar trazabilidad
    for mat_cod, cant_u, uni in formula:
        necesaria = cant_u * cantidad_unidades
        usados = descontar_fefo(mat_cod, necesaria, uni)

        coste_mp = conn.execute(
            "SELECT COALESCE(coste_unitario, 0) FROM materias_primas WHERE codigo = ? LIMIT 1",
            (mat_cod,)
        ).fetchone()
        if coste_mp:
            coste_total += coste_mp[0] * necesaria

        for lote_mp, cant_usada, _ in usados:
            conn.execute("""
                INSERT INTO trazabilidad
                (producto_lote, producto_id, materia_codigo, materia_lote, cantidad_usada, fecha)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (lote_pt, prod[0], mat_cod, lote_mp, cant_usada, datetime.now().isoformat()))

    # Registrar producción
    cur = conn.execute("""
        INSERT INTO producciones (producto_id, lote, cantidad, fecha, coste_total)
        VALUES (?, ?, ?, ?, ?)
    """, (prod[0], lote_pt, cantidad_unidades, datetime.now().isoformat(), coste_total))
    produccion_id = cur.lastrowid

    # Escandallo real: guardar lote y precio exacto usado
    for mat_cod, cant_u, uni in formula:
        rows = conn.execute("""
            SELECT materia_lote, cantidad_usada
            FROM trazabilidad
            WHERE producto_lote = ? AND materia_codigo = ?
        """, (lote_pt, mat_cod)).fetchall()
        for mat_lote, cant_usada in rows:
            precio_row = conn.execute("""
                SELECT coste_unitario FROM materias_primas
                WHERE codigo = ? AND lote = ? LIMIT 1
            """, (mat_cod, mat_lote)).fetchone()
            precio = precio_row[0] if precio_row else 0
            conn.execute("""
                INSERT INTO escandallo_real
                (produccion_id, producto_lote, articulo_tipo, articulo_codigo,
                 articulo_lote, cantidad, unidad, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (produccion_id, lote_pt, "MP", mat_cod, mat_lote,
                  cant_usada, uni, precio, cant_usada * precio))

    # Añadir stock producto terminado
    conn.execute("""
        INSERT INTO stock_producto
        (producto_id, lote, fecha_fabricacion, fecha_caducidad, cantidad)
        VALUES (?, ?, ?, ?, ?)
    """, (prod[0], lote_pt, datetime.now().date().isoformat(),
          fecha_caducidad_pt, cantidad_unidades))

    conn.commit()
    conn.close()

    print(f"\n✔ Producción registrada: {cantidad_unidades} uds de {prod[2]}")
    print(f"  Lote PT: {lote_pt}")
    print(f"  Coste estimado MP: {coste_total:.2f} €")

    # Registrar rendimiento inicial al 100 %
    try:
        from rendimiento import registrar_rendimiento
        registrar_rendimiento(
            producto_lote=lote_pt,
            producto_codigo=producto_codigo,
            cantidad_teorica=cantidad_unidades,
            cantidad_real=cantidad_unidades,
            unidad="ud",
            observaciones="Registro automático al finalizar producción",
        )
    except Exception as e:
        print(f"⚠ No se pudo registrar rendimiento: {e}")

    return True


def calcular_coste_produccion(producto_codigo, cantidad_unidades):
    """Devuelve dict con desglose de costes: mp, envases, mano_obra,
    indirectos, total, coste_unitario."""
    prod = obtener_producto(producto_codigo)
    if not prod:
        return None

    conn = conectar()
    coste_mp = 0.0
    detalle_mp = []
    for mat_cod, cant_u, uni in ver_formula(producto_codigo):
        necesaria = cant_u * cantidad_unidades
        row = conn.execute("""
            SELECT coste_unitario FROM materias_primas
            WHERE codigo = ? ORDER BY fecha_recepcion DESC LIMIT 1
        """, (mat_cod,)).fetchone()
        precio = row[0] if row else 0
        subtotal = necesaria * precio
        coste_mp += subtotal
        detalle_mp.append((mat_cod, necesaria, uni, precio, subtotal))

    coste_env = 0.0
    detalle_env = []
    for env_cod, cant_u in ver_formula_envases(producto_codigo):
        necesaria = cant_u * cantidad_unidades
        row = conn.execute("""
            SELECT coste_unitario FROM envases
            WHERE codigo = ? ORDER BY fecha_recepcion DESC LIMIT 1
        """, (env_cod,)).fetchone()
        precio = row[0] if row else 0
        subtotal = necesaria * precio
        coste_env += subtotal
        detalle_env.append((env_cod, necesaria, precio, subtotal))

    tiempos = conn.execute("""
        SELECT minutos_por_lote, horas_mano_obra
        FROM tiempos_producto WHERE producto_id = ?
    """, (prod[0],)).fetchone()
    horas_mo = tiempos[1] if tiempos else 0
    minutos_lote = tiempos[0] if tiempos else 0
    horas_totales = horas_mo + (minutos_lote / 60.0)

    coste_mo = 0.0
    coste_ind = 0.0
    for cid, concepto, cph, cpu, activo in conn.execute(
        "SELECT id, concepto, coste_por_hora, coste_por_unidad, activo "
        "FROM costes_indirectos WHERE activo = 1"
    ).fetchall():
        coste_mo += cph * horas_totales
        coste_ind += cpu * cantidad_unidades

    conn.close()

    total = coste_mp + coste_env + coste_mo + coste_ind
    return {
        "mp": coste_mp,
        "envases": coste_env,
        "mano_obra": coste_mo,
        "indirectos": coste_ind,
        "total": total,
        "coste_unitario": total / cantidad_unidades if cantidad_unidades else 0,
        "detalle_mp": detalle_mp,
        "detalle_env": detalle_env,
    }


def imprimir_coste(producto_codigo, cantidad_unidades):
    c = calcular_coste_produccion(producto_codigo, cantidad_unidades)
    if not c:
        print("✘ Producto no existe.")
        return
    print(f"\n── DESGLOSE DE COSTE: {cantidad_unidades} uds de {producto_codigo} ──")
    print(f"\nMaterias primas:")
    for cod, cant, uni, precio, sub in c["detalle_mp"]:
        print(f"  {cod:<15} {cant:>8.3f} {uni:<4} x {precio:>7.4f} € = {sub:>8.2f} €")
    print(f"  Subtotal MP: {c['mp']:.2f} €")
    print(f"\nEnvases/etiquetas:")
    for cod, cant, precio, sub in c["detalle_env"]:
        print(f"  {cod:<15} {cant:>8.0f} ud x {precio:>7.4f} € = {sub:>8.2f} €")
    print(f"  Subtotal envases: {c['envases']:.2f} €")
    print(f"\nMano de obra + indirectos: {c['mano_obra'] + c['indirectos']:.2f} €")
    print(f"\nCOSTE TOTAL: {c['total']:.2f} €")
    print(f"COSTE UNITARIO: {c['coste_unitario']:.4f} €/ud")


# =========================================================
# ENVASES
# =========================================================
def añadir_envase(codigo, nombre, tipo, lote, cantidad, unidad, coste_unitario=0,
                  proveedor="", ubicacion="", stock_minimo=0, fecha_recepcion=None):
    conn = conectar()
    try:
        conn.execute("""
            INSERT INTO envases
            (codigo, nombre, tipo, lote, cantidad, unidad, coste_unitario,
             proveedor, ubicacion, stock_minimo, fecha_recepcion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, tipo, lote, cantidad, unidad, coste_unitario,
              proveedor, ubicacion, stock_minimo,
              fecha_recepcion or datetime.now().date().isoformat()))
        conn.commit()
        print(f"✔ Envase '{nombre}' (lote {lote}) añadido.")
        return True
    except Exception as e:
        print(f"✘ Error: {e}")
        return False
    finally:
        conn.close()


def listar_envases():
    conn = conectar()
    rows = conn.execute("""
        SELECT codigo, nombre, tipo, lote, cantidad, unidad, coste_unitario, stock_minimo
        FROM envases
        ORDER BY nombre, lote
    """).fetchall()
    conn.close()
    return rows


def stock_envase(codigo):
    conn = conectar()
    row = conn.execute("""
        SELECT COALESCE(SUM(cantidad), 0), unidad
        FROM envases WHERE codigo = ?
        GROUP BY unidad
    """, (codigo,)).fetchone()
    conn.close()
    return row if row else (0, "ud")


def descontar_envase_fefo(codigo, cantidad_necesaria):
    conn = conectar()
    lotes = conn.execute("""
        SELECT id, lote, cantidad FROM envases
        WHERE codigo = ? AND cantidad > 0
        ORDER BY fecha_recepcion
    """, (codigo,)).fetchall()
    restante = cantidad_necesaria
    usados = []
    for eid, lote, cant in lotes:
        if restante <= 0:
            break
        usar = min(cant, restante)
        conn.execute("UPDATE envases SET cantidad = cantidad - ? WHERE id = ?", (usar, eid))
        usados.append((lote, usar))
        restante -= usar
    conn.commit()
    conn.close()
    if restante > 0.0001:
        raise ValueError(f"Stock insuficiente de envase {codigo}. Faltan {restante}")
    return usados


def añadir_envase_a_formula(producto_codigo, envase_codigo, cantidad_por_unidad):
    prod = obtener_producto(producto_codigo)
    if not prod:
        print("✘ Producto no existe.")
        return False
    conn = conectar()
    conn.execute("""
        INSERT INTO formula_envases (producto_id, envase_codigo, cantidad_por_unidad)
        VALUES (?, ?, ?)
    """, (prod[0], envase_codigo, cantidad_por_unidad))
    conn.commit()
    conn.close()
    print("✔ Envase añadido a la fórmula.")
    return True


def ver_formula_envases(producto_codigo):
    prod = obtener_producto(producto_codigo)
    if not prod:
        return []
    conn = conectar()
    rows = conn.execute("""
        SELECT envase_codigo, cantidad_por_unidad
        FROM formula_envases
        WHERE producto_id = ?
    """, (prod[0],)).fetchall()
    conn.close()
    return rows


# =========================================================
# PROVEEDORES
# =========================================================
def añadir_proveedor(codigo, nombre, contacto="", email="", telefono="",
                     condiciones_pago="", notas=""):
    conn = conectar()
    try:
        conn.execute("""
            INSERT INTO proveedores
            (codigo, nombre, contacto, email, telefono, condiciones_pago, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, contacto, email, telefono, condiciones_pago, notas))
        conn.commit()
        print(f"✔ Proveedor '{nombre}' añadido.")
        return True
    except Exception as e:
        print(f"✘ Error: {e}")
        return False
    finally:
        conn.close()


def listar_proveedores():
    conn = conectar()
    rows = conn.execute("""
        SELECT codigo, nombre, contacto, email, telefono
        FROM proveedores ORDER BY nombre
    """).fetchall()
    conn.close()
    return rows


def registrar_precio(proveedor_codigo, articulo_codigo, tipo_articulo,
                     precio_unitario, lote=""):
    conn = conectar()
    conn.execute("""
        INSERT INTO precios_proveedor
        (proveedor_codigo, articulo_codigo, tipo_articulo, precio_unitario, fecha, lote)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (proveedor_codigo, articulo_codigo, tipo_articulo, precio_unitario,
          datetime.now().isoformat(), lote))
    conn.commit()
    conn.close()


def comparar_precios(articulo_codigo):
    conn = conectar()
    rows = conn.execute("""
        SELECT proveedor_codigo, precio_unitario, fecha
        FROM precios_proveedor
        WHERE articulo_codigo = ?
        ORDER BY fecha DESC
    """, (articulo_codigo,)).fetchall()
    conn.close()
    return rows


# =========================================================
# COSTES INDIRECTOS Y TIEMPOS
# =========================================================
def añadir_coste_indirecto(concepto, coste_por_hora=0, coste_por_unidad=0):
    conn = conectar()
    conn.execute("""
        INSERT INTO costes_indirectos (concepto, coste_por_hora, coste_por_unidad, activo)
        VALUES (?, ?, ?, 1)
    """, (concepto, coste_por_hora, coste_por_unidad))
    conn.commit()
    conn.close()
    print(f"✔ Coste indirecto '{concepto}' añadido.")


def listar_costes_indirectos():
    conn = conectar()
    rows = conn.execute("""
        SELECT id, concepto, coste_por_hora, coste_por_unidad, activo
        FROM costes_indirectos
    """).fetchall()
    conn.close()
    return rows


def definir_tiempos_producto(producto_codigo, minutos_por_lote=0, horas_mano_obra=0):
    prod = obtener_producto(producto_codigo)
    if not prod:
        print("✘ Producto no existe.")
        return False
    conn = conectar()
    conn.execute("""
        INSERT OR REPLACE INTO tiempos_producto
        (producto_id, minutos_por_lote, horas_mano_obra)
        VALUES (?, ?, ?)
    """, (prod[0], minutos_por_lote, horas_mano_obra))
    conn.commit()
    conn.close()
    print("✔ Tiempos de fabricación guardados.")
    return True


# =========================================================
# PEDIDOS / ÓRDENES DE PRODUCCIÓN
# =========================================================
def crear_orden_produccion(producto_codigo, cantidad, fecha_prevista=None,
                            observaciones="", prioridad="normal"):
    prod = obtener_producto(producto_codigo)
    if not prod:
        print("✘ Producto no existe.")
        return None
    numero = f"PED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = conectar()

    # Asegurar columnas nuevas (por compatibilidad)
    for col, tipo in [("prioridad", "TEXT DEFAULT 'normal'"),
                      ("fecha_inicio", "TEXT"),
                      ("historial", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE ordenes_produccion ADD COLUMN {col} {tipo}")
            conn.commit()
        except Exception:
            pass

    conn.execute("""
        INSERT INTO ordenes_produccion
        (numero, producto_id, cantidad_planificada, estado, fecha_creacion,
         fecha_prevista, observaciones, prioridad)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (numero, prod[0], cantidad, "planificado",
          datetime.now().isoformat(), fecha_prevista, observaciones, prioridad))
    conn.commit()
    conn.close()
    print(f"✔ Pedido {numero} creado en estado 'planificado'.")
    return numero


def listar_ordenes(estado=None):
    conn = conectar()
    campos = """o.numero, p.codigo, p.nombre, o.cantidad_planificada,
                o.cantidad_fabricada, o.estado, o.fecha_creacion,
                o.fecha_prevista, o.fecha_inicio"""
    if estado:
        rows = conn.execute(f"""
            SELECT {campos}
            FROM ordenes_produccion o
            JOIN productos p ON p.id = o.producto_id
            WHERE o.estado = ?
            ORDER BY o.fecha_creacion DESC
        """, (estado,)).fetchall()
    else:
        rows = conn.execute(f"""
            SELECT {campos}
            FROM ordenes_produccion o
            JOIN productos p ON p.id = o.producto_id
            ORDER BY o.fecha_creacion DESC
        """).fetchall()
    conn.close()
    return rows


def estado_pedido(numero):
    conn = conectar()
    row = conn.execute(
        "SELECT estado FROM ordenes_produccion WHERE numero = ?", (numero,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def _registrar_evento_pedido(numero, evento):
    conn = conectar()
    try:
        conn.execute("ALTER TABLE ordenes_produccion ADD COLUMN historial TEXT")
        conn.commit()
    except Exception:
        pass
    row = conn.execute(
        "SELECT historial FROM ordenes_produccion WHERE numero = ?", (numero,)
    ).fetchone()
    historial = (row[0] if row and row[0] else "")
    entrada = f"{datetime.now().strftime('%Y-%m-%d %H:%M')} · {evento}\n"
    historial += entrada
    conn.execute(
        "UPDATE ordenes_produccion SET historial = ? WHERE numero = ?",
        (historial, numero)
    )
    conn.commit()
    conn.close()


def poner_pedido_en_preparacion(numero):
    """Planificado → En preparación. Reserva MP y envases."""
    estado = estado_pedido(numero)
    if estado != "planificado":
        print(f"✘ El pedido {numero} está en estado '{estado}', no se puede preparar.")
        return False

    conn = conectar()
    row = conn.execute("""
        SELECT o.id, p.codigo, o.cantidad_planificada
        FROM ordenes_produccion o
        JOIN productos p ON p.id = o.producto_id
        WHERE o.numero = ?
    """, (numero,)).fetchone()
    if not row:
        conn.close()
        print("✘ Pedido no encontrado.")
        return False
    oid, prod_cod, cant = row

    faltantes = []

    # Reservar MP
    for mat_cod, cant_u, uni in ver_formula(prod_cod):
        necesaria = cant_u * cant
        disp, u = stock_por_codigo(mat_cod)
        if disp < necesaria:
            faltantes.append(f"{mat_cod}: necesita {necesaria} {uni}, hay {disp} {u}")
            continue
        conn.execute("""
            INSERT INTO reservas_stock
            (pedido_numero, tipo_articulo, articulo_codigo,
             cantidad_reservada, unidad, fecha, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (numero, "MP", mat_cod, necesaria, uni,
              datetime.now().isoformat(), "activa"))

    # Reservar ENV
    for env_cod, cant_u in ver_formula_envases(prod_cod):
        necesaria = cant_u * cant
        disp, u = stock_envase(env_cod)
        if disp < necesaria:
            faltantes.append(f"{env_cod}: necesita {necesaria} ud, hay {disp}")
            continue
        conn.execute("""
            INSERT INTO reservas_stock
            (pedido_numero, tipo_articulo, articulo_codigo,
             cantidad_reservada, unidad, fecha, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (numero, "ENV", env_cod, necesaria, "ud",
              datetime.now().isoformat(), "activa"))

    if faltantes:
        conn.rollback()
        conn.close()
        print("✘ No se puede preparar. Faltan:")
        for f in faltantes:
            print(f"   · {f}")
        return False

    conn.execute("""
        UPDATE ordenes_produccion
        SET estado = 'en_preparacion', fecha_inicio = ?
        WHERE numero = ?
    """, (datetime.now().isoformat(), numero))
    conn.commit()
    conn.close()
    _registrar_evento_pedido(numero, "Pedido en preparación · stock reservado")
    print(f"✔ Pedido {numero} en preparación. Stock reservado.")
    return True


def poner_pedido_en_curso(numero):
    """En preparación → En curso."""
    estado = estado_pedido(numero)
    if estado != "en_preparacion":
        print(f"✘ El pedido {numero} está en estado '{estado}'.")
        return False
    conn = conectar()
    conn.execute(
        "UPDATE ordenes_produccion SET estado = 'en_curso' WHERE numero = ?",
        (numero,)
    )
    conn.commit()
    conn.close()
    _registrar_evento_pedido(numero, "Producción en curso")
    print(f"✔ Pedido {numero} en curso.")
    return True


def cancelar_pedido(numero, motivo=""):
    estado = estado_pedido(numero)
    if estado in ("finalizado", "cancelado"):
        print(f"✘ El pedido {numero} ya está '{estado}'.")
        return False
    conn = conectar()
    conn.execute("""
        UPDATE reservas_stock SET estado = 'liberada'
        WHERE pedido_numero = ? AND estado = 'activa'
    """, (numero,))
    conn.execute(
        "UPDATE ordenes_produccion SET estado = 'cancelado' WHERE numero = ?",
        (numero,)
    )
    conn.commit()
    conn.close()
    _registrar_evento_pedido(numero, f"Pedido cancelado. Motivo: {motivo or '—'}")
    print(f"✔ Pedido {numero} cancelado. Reservas liberadas.")
    return True


def reservas_de_pedido(numero):
    conn = conectar()
    rows = conn.execute("""
        SELECT tipo_articulo, articulo_codigo, cantidad_reservada,
               unidad, estado, fecha
        FROM reservas_stock
        WHERE pedido_numero = ?
        ORDER BY tipo_articulo, articulo_codigo
    """, (numero,)).fetchall()
    conn.close()
    return rows


def historial_pedido(numero):
    conn = conectar()
    row = conn.execute(
        "SELECT historial FROM ordenes_produccion WHERE numero = ?", (numero,)
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] else ""


def ejecutar_orden(numero_orden, lote_pt=None, fecha_caducidad_pt=None):
    """Finaliza un pedido. Debe estar en 'en_preparacion' o 'en_curso'.
    También acepta 'planificado' (salta pasos)."""
    conn = conectar()
    row = conn.execute("""
        SELECT o.id, p.codigo, o.cantidad_planificada, o.estado
        FROM ordenes_produccion o
        JOIN productos p ON p.id = o.producto_id
        WHERE o.numero = ?
    """, (numero_orden,)).fetchone()
    if not row:
        conn.close()
        print("✘ Pedido no encontrado.")
        return False

    oid, prod_cod, cant, estado = row

    if estado == "finalizado":
        conn.close()
        print("✘ El pedido ya está finalizado.")
        return False
    if estado == "cancelado":
        conn.close()
        print("✘ El pedido está cancelado.")
        return False

    # Consumir reservas si estaba en preparación
    if estado == "en_preparacion":
        conn.execute("""
            UPDATE reservas_stock SET estado = 'consumida'
            WHERE pedido_numero = ? AND estado = 'activa'
        """, (numero_orden,))
        conn.commit()

    conn.close()

    # Ejecutar producción
    producir(prod_cod, cant, lote_pt=lote_pt or numero_orden,
             fecha_caducidad_pt=fecha_caducidad_pt)

    # Cerrar pedido
    conn = conectar()
    conn.execute("""
        UPDATE ordenes_produccion
        SET estado = 'finalizado', cantidad_fabricada = ?, fecha_finalizacion = ?
        WHERE id = ?
    """, (cant, datetime.now().isoformat(), oid))
    conn.commit()
    conn.close()
    _registrar_evento_pedido(numero_orden, "Pedido finalizado · producción registrada")
    print(f"✔ Pedido {numero_orden} finalizado.")
    return True


# =========================================================
# MOVIMIENTOS DE STOCK
# =========================================================
def registrar_movimiento(tipo_articulo, articulo_codigo, lote, tipo_movimiento,
                         cantidad, unidad, referencia="", notas=""):
    conn = conectar()
    conn.execute("""
        INSERT INTO movimientos_stock
        (fecha, tipo_articulo, articulo_codigo, lote, tipo_movimiento,
         cantidad, unidad, referencia, notas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), tipo_articulo, articulo_codigo, lote,
          tipo_movimiento, cantidad, unidad, referencia, notas))
    conn.commit()
    conn.close()


def listar_movimientos(limite=100):
    conn = conectar()
    rows = conn.execute("""
        SELECT fecha, tipo_articulo, articulo_codigo, lote,
               tipo_movimiento, cantidad, unidad, referencia
        FROM movimientos_stock
        ORDER BY id DESC LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


# =========================================================
# HISTÓRICO Y EXPORTACIÓN
# =========================================================
def historico_producciones(desde=None, hasta=None):
    conn = conectar()
    q = """
        SELECT pr.id, p.codigo, p.nombre, pr.lote, pr.cantidad, pr.fecha, pr.coste_total
        FROM producciones pr
        JOIN productos p ON p.id = pr.producto_id
    """
    params = []
    if desde and hasta:
        q += " WHERE DATE(pr.fecha) BETWEEN ? AND ?"
        params = [desde, hasta]
    q += " ORDER BY pr.fecha DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def exportar_csv(nombre_fichero, filas, cabeceras):
    with open(nombre_fichero, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cabeceras)
        w.writerows(filas)
    print(f"✔ Exportado a {nombre_fichero}")


def exportar_stock_mp():
    exportar_csv("stock_materias_primas.csv", listar_materias(),
                 ["Código", "Nombre", "Lote", "Cantidad", "Unidad",
                  "Caducidad", "Ubicación"])


def exportar_stock_pt():
    exportar_csv("stock_producto_terminado.csv", stock_producto_terminado(),
                 ["Código", "Producto", "Lote", "Cantidad", "Caducidad", "Fabricación"])


def exportar_historico():
    exportar_csv("historico_producciones.csv", historico_producciones(),
                 ["ID", "Código", "Producto", "Lote", "Cantidad", "Fecha", "Coste"])


def exportar_mrp_csv():
    filas = necesidades_mrp()
    datos = [(r["tipo"], r["codigo"], f"{r['necesaria']:.3f}",
              f"{r['disponible']:.3f}", f"{r['a_comprar']:.3f}",
              r["unidad"]) for r in filas]
    exportar_csv("planificacion_mrp.csv", datos,
                 ["Tipo", "Código", "Necesaria", "Disponible", "A_Comprar", "Unidad"])


# =========================================================
# ESCANDALLOS Y MRP
# =========================================================
def ver_escandallo_real(producto_lote):
    conn = conectar()
    rows = conn.execute("""
        SELECT articulo_tipo, articulo_codigo, articulo_lote,
               cantidad, unidad, precio_unitario, subtotal
        FROM escandallo_real
        WHERE producto_lote = ?
    """, (producto_lote,)).fetchall()
    conn.close()
    return rows


def imprimir_escandallo_real(producto_lote):
    filas = ver_escandallo_real(producto_lote)
    if not filas:
        print(f"✘ No hay escandallo registrado para el lote {producto_lote}.")
        return None
    print(f"\n── ESCANDALLO REAL DEL LOTE {producto_lote} ──\n")
    total = 0
    print(f"{'Tipo':<5}{'Artículo':<15}{'Lote':<15}{'Cant':>10} "
          f"{'Ud':<5}{'€/ud':>10}{'Subtotal':>12}")
    print("-" * 75)
    for tipo, cod, lote, cant, uni, precio, sub in filas:
        print(f"{tipo:<5}{cod:<15}{lote or '':<15}{cant:>10.4f} "
              f"{uni or '':<5}{precio:>10.4f}{sub:>12.2f}")
        total += sub
    print("-" * 75)
    print(f"{'COSTE TOTAL REAL:':<60}{total:>12.2f} €")
    return total


def stock_disponible_neto(codigo, tipo="MP"):
    """Stock disponible tras restar reservas activas."""
    conn = conectar()
    row = conn.execute("""
        SELECT COALESCE(SUM(cantidad_reservada), 0)
        FROM reservas_stock
        WHERE articulo_codigo = ? AND tipo_articulo = ? AND estado = 'activa'
    """, (codigo, tipo)).fetchone()
    reservado = row[0] if row else 0
    conn.close()

    if tipo == "MP":
        disp, uni = stock_por_codigo(codigo)
    else:
        disp, uni = stock_envase(codigo)
    return max(0, disp - reservado), uni


def necesidades_mrp(incluir_ordenes=True, stock_seguridad_pct=10):
    """Calcula necesidades de MP y ENV a partir de pedidos planificados,
    comparando con el stock disponible neto (descontando reservas)."""
    conn = conectar()
    necesidades = {}

    if incluir_ordenes:
        ordenes = conn.execute("""
            SELECT p.codigo, o.cantidad_planificada
            FROM ordenes_produccion o
            JOIN productos p ON p.id = o.producto_id
            WHERE o.estado IN ('planificado', 'en_preparacion', 'en_curso')
        """).fetchall()
        for prod_cod, cant in ordenes:
            for mat_cod, cant_u, uni in ver_formula(prod_cod):
                k = ("MP", mat_cod)
                necesidades.setdefault(k, {"necesaria": 0, "unidad": uni})
                necesidades[k]["necesaria"] += cant_u * cant
            for env_cod, cant_u in ver_formula_envases(prod_cod):
                k = ("ENV", env_cod)
                necesidades.setdefault(k, {"necesaria": 0, "unidad": "ud"})
                necesidades[k]["necesaria"] += cant_u * cant

    resultado = []
    for (tipo, codigo), d in necesidades.items():
        necesaria = d["necesaria"] * (1 + stock_seguridad_pct / 100.0)
        disponible_neto, uni = stock_disponible_neto(codigo, tipo)
        a_comprar = max(0, necesaria - disponible_neto)
        resultado.append({
            "tipo": tipo,
            "codigo": codigo,
            "necesaria": necesaria,
            "disponible": disponible_neto,
            "a_comprar": a_comprar,
            "unidad": d["unidad"] or uni,
        })
    conn.close()
    return sorted(resultado, key=lambda x: (x["tipo"], x["codigo"]))


# =========================================================
# CONTROL DE CALIDAD
# =========================================================
def registrar_control_calidad(tipo_articulo, articulo_codigo, lote,
                              parametro, valor_obtenido, valor_esperado,
                              resultado, responsable="", observaciones=""):
    conn = conectar()
    conn.execute("""
        INSERT INTO controles_calidad
        (tipo_articulo, articulo_codigo, lote, fecha, responsable, parametro,
         valor_obtenido, valor_esperado, resultado, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tipo_articulo, articulo_codigo, lote, datetime.now().isoformat(),
          responsable, parametro, valor_obtenido, valor_esperado,
          resultado, observaciones))
    conn.commit()
    conn.close()
    print(f"✔ Control de calidad registrado ({resultado}).")


def ver_controles_calidad(tipo=None, codigo=None, lote=None):
    conn = conectar()
    q = """
        SELECT id, tipo_articulo, articulo_codigo, lote, fecha, parametro,
               valor_obtenido, valor_esperado, resultado, responsable
        FROM controles_calidad WHERE 1 = 1
    """
    params = []
    if tipo:
        q += " AND tipo_articulo = ?"
        params.append(tipo)
    if codigo:
        q += " AND articulo_codigo = ?"
        params.append(codigo)
    if lote:
        q += " AND lote = ?"
        params.append(lote)
    q += " ORDER BY fecha DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def registrar_no_conformidad(tipo_articulo, articulo_codigo, lote,
                             descripcion, gravedad="leve", accion_correctiva=""):
    conn = conectar()
    conn.execute("""
        INSERT INTO no_conformidades
        (fecha, tipo_articulo, articulo_codigo, lote, descripcion, gravedad,
         accion_correctiva, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), tipo_articulo, articulo_codigo, lote,
          descripcion, gravedad, accion_correctiva, "abierta"))
    conn.commit()
    conn.close()
    print("✔ No conformidad registrada (estado: abierta).")
    # Bloquea el lote automáticamente
    cambiar_estado_lote(tipo_articulo, articulo_codigo, lote,
                        "bloqueado", motivo="NC abierta")


def listar_no_conformidades(estado=None):
    conn = conectar()
    if estado:
        rows = conn.execute("""
            SELECT id, fecha, tipo_articulo, articulo_codigo, lote,
                   descripcion, gravedad, estado
            FROM no_conformidades
            WHERE estado = ?
            ORDER BY fecha DESC
        """, (estado,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, fecha, tipo_articulo, articulo_codigo, lote,
                   descripcion, gravedad, estado
            FROM no_conformidades
            ORDER BY fecha DESC
        """).fetchall()
    conn.close()
    return rows


def cerrar_no_conformidad(nc_id, accion_correctiva=""):
    conn = conectar()
    conn.execute("""
        UPDATE no_conformidades
        SET estado = 'cerrada', fecha_cierre = ?, accion_correctiva = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), accion_correctiva, nc_id))
    conn.commit()
    conn.close()
    print(f"✔ NC #{nc_id} cerrada.")


def cambiar_estado_lote(tipo_articulo, articulo_codigo, lote, estado,
                        responsable="", motivo=""):
    """estado: pendiente / liberado / bloqueado / rechazado"""
    conn = conectar()
    conn.execute("""
        INSERT INTO liberacion_lotes
        (tipo_articulo, articulo_codigo, lote, estado, fecha, responsable)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(tipo_articulo, articulo_codigo, lote)
        DO UPDATE SET estado = excluded.estado,
                      fecha = excluded.fecha,
                      responsable = excluded.responsable
    """, (tipo_articulo, articulo_codigo, lote, estado,
          datetime.now().isoformat(), responsable))
    conn.commit()
    conn.close()
    print(f"✔ Lote {lote} de {articulo_codigo} → {estado}.")


def estado_lote(tipo_articulo, articulo_codigo, lote):
    conn = conectar()
    row = conn.execute("""
        SELECT estado FROM liberacion_lotes
        WHERE tipo_articulo = ? AND articulo_codigo = ? AND lote = ?
    """, (tipo_articulo, articulo_codigo, lote)).fetchone()
    conn.close()
    return row[0] if row else "pendiente"


def listar_lotes_por_estado(estado):
    conn = conectar()
    rows = conn.execute("""
        SELECT tipo_articulo, articulo_codigo, lote, fecha, responsable
        FROM liberacion_lotes
        WHERE estado = ?
        ORDER BY fecha DESC
    """, (estado,)).fetchall()
    conn.close()
    return rows


# =========================================================
# HELPERS PRIVADOS Y WRAPPERS
# =========================================================
def _precio_lote_mp(codigo, lote):
    conn = conectar()
    row = conn.execute("""
        SELECT coste_unitario FROM materias_primas
        WHERE codigo = ? AND lote = ? LIMIT 1
    """, (codigo, lote)).fetchone()
    conn.close()
    return row[0] if row else 0


def _precio_lote_env(codigo, lote):
    conn = conectar()
    row = conn.execute("""
        SELECT coste_unitario FROM envases
        WHERE codigo = ? AND lote = ? LIMIT 1
    """, (codigo, lote)).fetchone()
    conn.close()
    return row[0] if row else 0


def generar_hoja_pesada_pedido(numero, ruta=None):
    """Wrapper que llama a informes.generar_hoja_pesada()."""
    from informes import generar_hoja_pesada
    return generar_hoja_pesada(numero, ruta)


# Reexportar conectar para conveniencia
__all__ = [
    "conectar",
    # MP
    "añadir_materia", "listar_materias", "stock_por_codigo",
    "lotes_disponibles", "descontar_fefo", "descontar_stock_fefo",
    # Productos
    "añadir_producto", "obtener_producto", "añadir_ingrediente_formula",
    "ver_formula", "stock_producto_terminado", "trazabilidad_lote",
    # Producción
    "producir", "calcular_coste_produccion", "imprimir_coste",
    # Envases
    "añadir_envase", "listar_envases", "stock_envase", "descontar_envase_fefo",
    "añadir_envase_a_formula", "ver_formula_envases",
    # Proveedores
    "añadir_proveedor", "listar_proveedores", "registrar_precio", "comparar_precios",
    # Costes
    "añadir_coste_indirecto", "listar_costes_indirectos", "definir_tiempos_producto",
    # Pedidos
    "crear_orden_produccion", "listar_ordenes", "estado_pedido",
    "poner_pedido_en_preparacion", "poner_pedido_en_curso",
    "cancelar_pedido", "reservas_de_pedido", "historial_pedido",
    "ejecutar_orden",
    # Movimientos / histórico / export
    "registrar_movimiento", "listar_movimientos", "historico_producciones",
    "exportar_csv", "exportar_stock_mp", "exportar_stock_pt",
    "exportar_historico", "exportar_mrp_csv",
    # Escandallos / MRP
    "ver_escandallo_real", "imprimir_escandallo_real",
    "stock_disponible_neto", "necesidades_mrp",
    # Calidad
    "registrar_control_calidad", "ver_controles_calidad",
    "registrar_no_conformidad", "listar_no_conformidades",
    "cerrar_no_conformidad", "cambiar_estado_lote", "estado_lote",
    "listar_lotes_por_estado",
    # Helpers
    "generar_hoja_pesada_pedido",
]
