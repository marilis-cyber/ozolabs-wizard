"""
OZOLABS' WIZARD - Gestión de inventario, expediciones, biblioteca de fórmulas
y hojas de fabricación.
====================================================================
Este módulo implementa:
  1. Registro de ENTRADAS de materias primas (con histórico y documentos).
  2. Registro de EXPEDICIONES / SALIDAS multi-línea (varios productos por
     movimiento), con descuento automático de stock de producto terminado.
  3. BIBLIOTECA DE FÓRMULAS independiente del inventario, con versiones,
     ingredientes libres, procedimiento, parámetros y documentos.
  4. HOJAS DE FABRICACIÓN que vinculan la fórmula con materias primas reales
     y lotes en el momento de fabricar.
"""
from database import conectar
from datetime import datetime


# =========================================================
# FORMATO DE FECHA (DD/MM/AAAA)
# =========================================================
def fmt_fecha(valor):
    """Convierte una fecha ISO (YYYY-MM-DD o ISO completo) a DD/MM/AAAA.
    Si ya está en DD/MM/AAAA la devuelve sin cambios."""
    if not valor:
        return ""
    s = str(valor).strip()
    if not s:
        return ""
    # Si ya viene en DD/MM/AAAA (o similar), la devolvemos tal cual
    if "/" in s[:6] and len(s.split("/")[0]) <= 2:
        return s.split(" ")[0]
    # Normalizar: quedarnos con la parte de fecha (10 primeros caracteres)
    d = s[:10]
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return s


def _ahora():
    return datetime.now().isoformat()


# =========================================================
# 1. ENTRADAS DE MATERIAS PRIMAS
# =========================================================
def registrar_entrada_mp(fecha, materia_codigo, materia_nombre, lote_interno,
                         lote_proveedor, proveedor, uso, cantidad, unidad,
                         fecha_caducidad=None, documento_fichero=None,
                         documento_base64=None, documento_tipo=None,
                         observaciones="", usuario=""):
    """Registra una entrada de materia prima en el histórico y la suma al stock."""
    conn = conectar()
    try:
        # 1) Guardar el histórico de la entrada
        conn.execute("""
            INSERT INTO entradas_mp
            (fecha, materia_codigo, materia_nombre, lote_interno, lote_proveedor,
             proveedor, uso, cantidad, unidad, fecha_caducidad, documento_fichero,
             documento_base64, documento_tipo, observaciones, usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fecha, materia_codigo, materia_nombre, lote_interno, lote_proveedor,
              proveedor, uso, cantidad, unidad, fecha_caducidad, documento_fichero,
              documento_base64, documento_tipo, observaciones, usuario))

        # 2) Incorporar al stock de materias_primas (upsert por codigo+lote)
        existente = conn.execute("""
            SELECT id FROM materias_primas WHERE codigo = ? AND lote = ?
        """, (materia_codigo, lote_interno)).fetchone()
        if existente:
            conn.execute("""
                UPDATE materias_primas
                SET cantidad = cantidad + ?,
                    proveedor = COALESCE(?, proveedor),
                    uso = COALESCE(?, uso),
                    proveedor_lote = COALESCE(?, proveedor_lote),
                    fecha_caducidad = COALESCE(?, fecha_caducidad),
                    fecha_recepcion = ?
                WHERE id = ?
            """, (cantidad, proveedor, uso, lote_proveedor, fecha_caducidad,
                  fecha, existente[0]))
        else:
            conn.execute("""
                INSERT INTO materias_primas
                (codigo, nombre, proveedor, lote, cantidad, unidad,
                 fecha_recepcion, fecha_caducidad, coste_unitario, ubicacion,
                 stock_minimo, uso, proveedor_lote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '', 0, ?, ?)
            """, (materia_codigo, materia_nombre, proveedor, lote_interno,
                  cantidad, unidad, fecha, fecha_caducidad, uso, lote_proveedor))

        # 3) Registrar el movimiento en el histórico general de stock
        conn.execute("""
            INSERT INTO movimientos_stock
            (fecha, tipo_articulo, articulo_codigo, lote, tipo_movimiento,
             cantidad, unidad, referencia, notas)
            VALUES (?, 'MP', ?, ?, 'entrada', ?, ?, ?, ?)
        """, (fecha, materia_codigo, lote_interno, cantidad, unidad,
              f"Entrada {materia_codigo}/{lote_interno}", observaciones or ""))

        conn.commit()
        return True
    except Exception as e:
        print(f"✘ Error registrando entrada MP: {e}")
        return False
    finally:
        conn.close()


def listar_entradas_mp(limite=500):
    conn = conectar()
    rows = conn.execute("""
        SELECT id, fecha, materia_codigo, materia_nombre, lote_interno,
               lote_proveedor, proveedor, uso, cantidad, unidad,
               fecha_caducidad, documento_fichero, documento_tipo,
               observaciones, usuario
        FROM entradas_mp
        ORDER BY fecha DESC, id DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


def obtener_documento_entrada(entrada_id):
    """Devuelve (nombre_fichero, contenido_base64) del documento de una entrada."""
    conn = conectar()
    row = conn.execute("""
        SELECT documento_fichero, documento_base64
        FROM entradas_mp WHERE id = ?
    """, (entrada_id,)).fetchone()
    conn.close()
    return row if row else (None, None)


def resumen_lotes_mp(codigo=None):
    """Devuelve: codigo, lote, stock actual, unidad, proveedor, fecha_recepcion,
    fecha_caducidad, total_recibido (suma de entradas de ese lote)."""
    conn = conectar()
    q = """
        SELECT m.codigo, m.lote, m.cantidad, m.unidad, m.proveedor,
               m.fecha_recepcion, m.fecha_caducidad,
               COALESCE((SELECT SUM(e.cantidad) FROM entradas_mp e
                          WHERE e.materia_codigo = m.codigo
                            AND e.lote_interno = m.lote), m.cantidad) AS recibido
        FROM materias_primas m
    """
    params = []
    if codigo:
        q += " WHERE m.codigo = ?"
        params.append(codigo)
    q += " ORDER BY m.fecha_caducidad IS NULL, m.fecha_caducidad"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


# =========================================================
# CATÁLOGO DE MATERIAS PRIMAS (lista maestra)
# =========================================================
def importar_catalogo_mp(items):
    """Importa una lista de materias primas {codigo, nombre, proveedor, uso}.
    Devuelve (importados, existentes)."""
    conn = conectar()
    importados = 0
    existentes = 0
    try:
        for it in items:
            cod = (it.get("codigo") or "").strip()
            nom = (it.get("nombre") or "").strip()
            if not cod or not nom:
                continue
            row = conn.execute(
                "SELECT id FROM catalogo_mp WHERE codigo = ?", (cod,)
            ).fetchone()
            if row:
                existentes += 1
            else:
                conn.execute("""
                    INSERT INTO catalogo_mp (codigo, nombre, inci, proveedor, uso)
                    VALUES (?, ?, ?, ?, ?)
                """, (cod, nom, it.get("inci", "") or "",
                      it.get("proveedor", "") or "",
                      it.get("uso", "cosmetico") or "cosmetico"))
                importados += 1
        conn.commit()
    except Exception as e:
        print(f"✘ Error importando catálogo: {e}")
        return 0, 0
    finally:
        conn.close()
    return importados, existentes


def listar_catalogo_mp(limite=2000):
    conn = conectar()
    rows = conn.execute("""
        SELECT id, codigo, nombre, inci, proveedor, uso
        FROM catalogo_mp ORDER BY nombre LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


def actualizar_proveedor_catalogo(catalogo_id, proveedor, uso=None):
    conn = conectar()
    if uso:
        conn.execute(
            "UPDATE catalogo_mp SET proveedor = ?, uso = ? WHERE id = ?",
            (proveedor, uso, catalogo_id))
    else:
        conn.execute(
            "UPDATE catalogo_mp SET proveedor = ? WHERE id = ?",
            (proveedor, catalogo_id))
    conn.commit()
    conn.close()
    return True


# =========================================================
# 2. EXPEDICIONES / SALIDAS MULTI-LÍNEA
# =========================================================
def descontar_stock_pt(conn, producto_codigo, lote, cantidad):
    """Descuenta stock de producto terminado por lote concreto."""
    row = conn.execute(
        "SELECT id FROM productos WHERE codigo = ?", (producto_codigo,)
    ).fetchone()
    if not row:
        raise ValueError(f"Producto '{producto_codigo}' no existe")
    pid = row[0]
    lote_row = conn.execute("""
        SELECT id, cantidad FROM stock_producto
        WHERE producto_id = ? AND lote = ?
    """, (pid, lote)).fetchone()
    if not lote_row:
        raise ValueError(f"Sin stock del producto '{producto_codigo}' lote {lote}")
    sid, disponible = lote_row
    if disponible < cantidad:
        raise ValueError(
            f"Stock insuficiente de '{producto_codigo}' lote {lote}: "
            f"hay {disponible}, salen {cantidad}")
    conn.execute(
        "UPDATE stock_producto SET cantidad = cantidad - ? WHERE id = ?",
        (cantidad, sid))


def crear_expedicion(fecha, destino, cliente="", pedido_factura="",
                     observaciones="", usuario="", lineas=None):
    """Crea un movimiento de expedición con varias líneas de producto.
    lineas = lista de dicts: {producto_codigo, producto_nombre, lote, cantidad, unidad}"""
    numero = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = conectar()
    try:
        conn.execute("""
            INSERT INTO expediciones
            (numero, fecha, destino, cliente, pedido_factura, observaciones, usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (numero, fecha, destino, cliente, pedido_factura, observaciones, usuario))

        for l in (lineas or []):
            conn.execute("""
                INSERT INTO expedicion_lineas
                (expedicion_numero, producto_codigo, producto_nombre, lote,
                 cantidad, unidad)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (numero, l.get("producto_codigo", ""), l.get("producto_nombre", ""),
                  l.get("lote", ""), l.get("cantidad", 0), l.get("unidad", "")))

            # Descontar stock de producto terminado
            descontar_stock_pt(conn, l.get("producto_codigo", ""),
                               l.get("lote", ""), l.get("cantidad", 0))

            # Movimiento general de stock
            conn.execute("""
                INSERT INTO movimientos_stock
                (fecha, tipo_articulo, articulo_codigo, lote, tipo_movimiento,
                 cantidad, unidad, referencia, notas)
                VALUES (?, 'PT', ?, ?, 'salida', ?, ?, ?, ?)
            """, (fecha, l.get("producto_codigo", ""), l.get("lote", ""),
                  l.get("cantidad", 0), l.get("unidad", ""), numero, destino))

        conn.commit()
        return numero
    except Exception as e:
        print(f"✘ Error creando expedición: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_expediciones(limite=500):
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, fecha, destino, cliente, pedido_factura,
               observaciones, usuario
        FROM expediciones
        ORDER BY fecha DESC, id DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


def lineas_expedicion(numero):
    conn = conectar()
    rows = conn.execute("""
        SELECT producto_codigo, producto_nombre, lote, cantidad, unidad
        FROM expedicion_lineas
        WHERE expedicion_numero = ?
        ORDER BY id
    """, (numero,)).fetchall()
    conn.close()
    return rows


def todas_lineas_expediciones(limite=1000):
    """Vista plana de todas las líneas de expedición (para filtrar/buscar)."""
    conn = conectar()
    rows = conn.execute("""
        SELECT e.numero, e.fecha, e.destino, e.cliente, e.pedido_factura,
               l.producto_codigo, l.producto_nombre, l.lote, l.cantidad, l.unidad
        FROM expediciones e
        JOIN expedicion_lineas l ON l.expedicion_numero = e.numero
        ORDER BY e.fecha DESC, e.id DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


# =========================================================
# 3. BIBLIOTECA DE FÓRMULAS (independiente del inventario)
# =========================================================
def crear_formula(codigo, nombre, ingredientes, procedimiento="", parametros="",
                  observaciones="", documento_fichero=None, documento_base64=None,
                  usuario=""):
    """Crea una fórmula nueva (versión 1).
    ingredientes = lista de dicts:
        {ingrediente, porcentaje, cantidad, unidad, funcion}"""
    conn = conectar()
    try:
        ahora = _ahora()
        cur = conn.execute("""
            INSERT INTO formulas_biblioteca
            (codigo, nombre, version, estado, fecha_creacion, fecha_modificacion,
             procedimiento, parametros, observaciones, documento_fichero,
             documento_base64)
            VALUES (?, ?, 1, 'activa', ?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, ahora, ahora, procedimiento, parametros,
              observaciones, documento_fichero, documento_base64))
        fid = cur.lastrowid
        _guardar_ingredientes(conn, fid, ingredientes)
        conn.commit()
        return fid
    except Exception as e:
        print(f"✘ Error creando fórmula: {e}")
        return None
    finally:
        conn.close()


def _guardar_ingredientes(conn, formula_id, ingredientes):
    for i, ing in enumerate(ingredientes or []):
        conn.execute("""
            INSERT INTO formulas_biblioteca_ingredientes
            (formula_id, ingrediente, codigo, ecologico, porcentaje, cantidad,
             unidad, funcion, orden)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (formula_id, ing.get("ingrediente", ""), ing.get("codigo", ""),
              1 if ing.get("ecologico") else 0,
              ing.get("porcentaje", 0), ing.get("cantidad", 0),
              ing.get("unidad", ""), ing.get("funcion", ""), i))


def nueva_version_formula(codigo, ingredientes, procedimiento="", parametros="",
                          observaciones="", documento_fichero=None,
                          documento_base64=None):
    """Crea una versión nueva manteniendo el historial (la anterior pasa a 'historica')."""
    conn = conectar()
    try:
        ultima = conn.execute("""
            SELECT id, nombre, version FROM formulas_biblioteca
            WHERE codigo = ? AND estado = 'activa'
            ORDER BY version DESC LIMIT 1
        """, (codigo,)).fetchone()
        if not ultima:
            return None
        fid_old, nombre, version = ultima
        conn.execute(
            "UPDATE formulas_biblioteca SET estado = 'historica' WHERE id = ?",
            (fid_old,))
        nueva_version = version + 1
        ahora = _ahora()
        cur = conn.execute("""
            INSERT INTO formulas_biblioteca
            (codigo, nombre, version, estado, fecha_creacion, fecha_modificacion,
             procedimiento, parametros, observaciones, documento_fichero,
             documento_base64)
            VALUES (?, ?, ?, 'activa', ?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, nueva_version, ahora, ahora, procedimiento,
              parametros, observaciones, documento_fichero, documento_base64))
        fid = cur.lastrowid
        _guardar_ingredientes(conn, fid, ingredientes)
        conn.commit()
        return fid
    except Exception as e:
        print(f"✘ Error creando versión: {e}")
        return None
    finally:
        conn.close()


def listar_formulas(solo_activas=True, limite=500):
    conn = conectar()
    q = """
        SELECT id, codigo, nombre, version, estado, fecha_creacion,
               fecha_modificacion, observaciones
        FROM formulas_biblioteca
    """
    if solo_activas:
        q += " WHERE estado = 'activa'"
    q += " ORDER BY codigo, version DESC LIMIT ?"
    rows = conn.execute(q, (limite,)).fetchall()
    conn.close()
    return rows


def buscar_formulas(texto, solo_activas=True):
    conn = conectar()
    like = f"%{texto}%"
    q = """
        SELECT DISTINCT f.id, f.codigo, f.nombre, f.version, f.estado,
               f.fecha_creacion, f.fecha_modificacion, f.observaciones
        FROM formulas_biblioteca f
        LEFT JOIN formulas_biblioteca_ingredientes i ON i.formula_id = f.id
        WHERE (f.codigo LIKE ? OR f.nombre LIKE ? OR i.ingrediente LIKE ?)
    """
    params = [like, like, like]
    if solo_activas:
        q += " AND f.estado = 'activa'"
    q += " ORDER BY f.codigo, f.version DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def obtener_formula(formula_id):
    """Devuelve (cabecera, ingredientes).
    cabecera = (id, codigo, nombre, version, estado, fecha_creacion,
                fecha_modificacion, procedimiento, parametros, observaciones,
                documento_fichero, documento_base64)"""
    conn = conectar()
    cab = conn.execute("""
        SELECT id, codigo, nombre, version, estado, fecha_creacion,
               fecha_modificacion, procedimiento, parametros, observaciones,
               documento_fichero, documento_base64
        FROM formulas_biblioteca WHERE id = ?
    """, (formula_id,)).fetchone()
    if not cab:
        conn.close()
        return None
    ings = conn.execute("""
        SELECT ingrediente, codigo, ecologico, porcentaje, cantidad, unidad, funcion
        FROM formulas_biblioteca_ingredientes
        WHERE formula_id = ?
        ORDER BY orden, id
    """, (formula_id,)).fetchall()
    conn.close()
    return cab, ings


def duplicar_formula(formula_id, nuevo_codigo, nuevo_nombre):
    cab, ings = obtener_formula(formula_id)
    if not cab:
        return None
    return crear_formula(
        nuevo_codigo, nuevo_nombre,
        [{"ingrediente": i[0], "codigo": i[1], "ecologico": i[2],
          "porcentaje": i[3], "cantidad": i[4], "unidad": i[5],
          "funcion": i[6]} for i in ings],
        cab[7], cab[8],
        f"Duplicada de {cab[1]} v{cab[3]}. {cab[9] or ''}",
        cab[10], cab[11])


def eliminar_formula(formula_id):
    conn = conectar()
    try:
        conn.execute("DELETE FROM formulas_biblioteca_ingredientes WHERE formula_id = ?",
                     (formula_id,))
        conn.execute("DELETE FROM formulas_biblioteca WHERE id = ?", (formula_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"✘ Error eliminando fórmula: {e}")
        return False
    finally:
        conn.close()


def importar_formulas(items):
    """Importa varias fórmulas desde una lista plana de filas.
    items = lista de dicts: {formula_codigo, formula_nombre, ingrediente,
                             codigo, porcentaje, cantidad, unidad, funcion}.
    Agrupa por formula_codigo y crea una fórmula por grupo.
    Devuelve (creadas, rechazadas)."""
    grupos = {}
    orden = []
    for it in items:
        fc = (it.get("formula_codigo") or "").strip()
        if not fc:
            continue
        if fc not in grupos:
            grupos[fc] = {
                "nombre": (it.get("formula_nombre") or "").strip(),
                "ingredientes": [],
            }
            orden.append(fc)
        grupos[fc]["ingredientes"].append({
            "ingrediente": (it.get("ingrediente") or "").strip(),
            "codigo": (it.get("codigo") or "").strip(),
            "ecologico": 1 if it.get("ecologico") in ("1", "sí", "si", "eco", "bio", True, 1) else 0,
            "porcentaje": float(it.get("porcentaje") or 0),
            "cantidad": float(it.get("cantidad") or 0),
            "unidad": (it.get("unidad") or "").strip(),
            "funcion": (it.get("funcion") or "").strip(),
        })
    creadas = 0
    rechazadas = 0
    for fc in orden:
        g = grupos[fc]
        if not g["nombre"] or not any(i["ingrediente"] for i in g["ingredientes"]):
            rechazadas += 1
            continue
        fid = crear_formula(fc, g["nombre"], g["ingredientes"])
        if fid:
            creadas += 1
        else:
            rechazadas += 1
    return creadas, rechazadas


# =========================================================
# 4. HOJAS DE FABRICACIÓN
# =========================================================
def calcular_cantidades_formula(formula_id, cantidad_objetivo):
    """Calcula las cantidades teóricas de cada ingrediente a partir del %.
    Si el % es 0, usa la cantidad definida en la fórmula como referencia."""
    cab, ings = obtener_formula(formula_id)
    if not cab:
        return []
    resultado = []
    for ing, codigo, eco, pct, cant, uni, funcion in ings:
        if pct and pct > 0:
            teorica = cantidad_objetivo * pct / 100.0
        else:
            teorica = cant
        resultado.append({
            "ingrediente": ing, "codigo": codigo, "ecologico": eco,
            "porcentaje": pct, "cantidad_teorica": teorica,
            "unidad": uni, "funcion": funcion,
        })
    return resultado


def crear_hoja_fabricacion(formula_id, producto_codigo, producto_nombre,
                           lote_pt, cantidad_objetivo, unidad_objetivo,
                           fecha, observaciones="", usuario="", asignaciones=None):
    """Crea una hoja de fabricación en estado 'borrador' a partir de una fórmula.
    asignaciones = lista (alineada con los ingredientes) de dicts:
        {materia_codigo, materia_lote}"""
    cab, ings = obtener_formula(formula_id)
    if not cab:
        return None, "Fórmula no encontrada"
    numero = f"HDF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = conectar()
    try:
        conn.execute("""
            INSERT INTO hojas_fabricacion
            (numero, formula_id, formula_codigo, formula_nombre, formula_version,
             producto_codigo, producto_nombre, lote_pt, cantidad_objetivo,
             unidad_objetivo, fecha, estado, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', ?)
        """, (numero, formula_id, cab[1], cab[2], cab[3], producto_codigo,
              producto_nombre, lote_pt, cantidad_objetivo, unidad_objetivo,
              fecha, observaciones))
        for idx, (ing, codigo, eco, pct, cant, uni, funcion) in enumerate(ings):
            teorica = (cantidad_objetivo * pct / 100.0) if pct else cant
            mp_cod = ""
            mp_lote = ""
            if asignaciones and idx < len(asignaciones):
                mp_cod = (asignaciones[idx].get("materia_codigo") or "").strip()
                mp_lote = (asignaciones[idx].get("materia_lote") or "").strip()
            if not mp_cod:
                mp_cod = codigo or ""
            conn.execute("""
                INSERT INTO hojas_fabricacion_lineas
                (hoja_numero, ingrediente, porcentaje, cantidad_teorica, unidad,
                 materia_codigo, materia_lote, cantidad_real, unidad_real)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, '')
            """, (numero, ing, pct, teorica, uni, mp_cod, mp_lote))
        conn.commit()
        return numero, None
    except Exception as e:
        print(f"✘ Error creando hoja: {e}")
        return None, str(e)
    finally:
        conn.close()


def listar_hojas_fabricacion(limite=300):
    conn = conectar()
    rows = conn.execute("""
        SELECT numero, formula_codigo, formula_nombre, formula_version,
               producto_codigo, producto_nombre, lote_pt, cantidad_objetivo,
               unidad_objetivo, fecha, estado, observaciones
        FROM hojas_fabricacion
        ORDER BY fecha DESC, id DESC LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


def lineas_hoja(numero):
    conn = conectar()
    rows = conn.execute("""
        SELECT id, ingrediente, porcentaje, cantidad_teorica, unidad,
               materia_codigo, materia_lote, cantidad_real, unidad_real
        FROM hojas_fabricacion_lineas
        WHERE hoja_numero = ?
        ORDER BY id
    """, (numero,)).fetchall()
    conn.close()
    return rows


def descontar_mp_lote(conn, materia_codigo, lote, cantidad):
    """Descuenta stock de una materia prima por lote concreto."""
    row = conn.execute("""
        SELECT id, cantidad FROM materias_primas
        WHERE codigo = ? AND lote = ?
    """, (materia_codigo, lote)).fetchone()
    if not row:
        raise ValueError(f"Sin stock de '{materia_codigo}' lote {lote}")
    mid, disponible = row
    if disponible < cantidad:
        raise ValueError(
            f"Stock insuficiente de '{materia_codigo}' lote {lote}: "
            f"hay {disponible}, necesita {cantidad}")
    conn.execute(
        "UPDATE materias_primas SET cantidad = cantidad - ? WHERE id = ?",
        (cantidad, mid))


def confirmar_hoja_fabricacion(numero, lineas):
    """Confirma una hoja: descuenta las cantidades reales de MP por lote,
    registra producción, stock PT y trazabilidad. Devuelve (ok, mensaje).
    lineas = lista de dicts: {id, materia_codigo, materia_lote,
                              cantidad_real, unidad_real}"""
    conn = conectar()
    try:
        cab = conn.execute("""
            SELECT numero, producto_codigo, producto_nombre, lote_pt,
                   cantidad_objetivo, unidad_objetivo, estado
            FROM hojas_fabricacion WHERE numero = ?
        """, (numero,)).fetchone()
        if not cab:
            return False, "Hoja no encontrada"
        if cab[6] == "confirmada":
            return False, "La hoja ya está confirmada"

        # Pre-validación: comprobar stock de TODOS los lotes antes de descontar
        # (evita descuentos parciales si una línea falla)
        errores = []
        for l in lineas:
            cod = l.get("materia_codigo", "") or ""
            lote = l.get("materia_lote", "") or ""
            cant = l.get("cantidad_real", 0) or 0
            if not cod or not lote or cant <= 0:
                continue
            row = conn.execute("""
                SELECT cantidad FROM materias_primas
                WHERE codigo = ? AND lote = ?
            """, (cod, lote)).fetchone()
            if not row:
                errores.append(f"Sin stock de '{cod}' lote {lote}")
            elif row[0] < cant:
                errores.append(
                    f"Stock insuficiente de '{cod}' lote {lote}: "
                    f"hay {row[0]}, necesita {cant}")
        if errores:
            return False, "; ".join(errores)

        fecha_hoy = datetime.now().date().isoformat()
        prod = conn.execute(
            "SELECT id FROM productos WHERE codigo = ?", (cab[1],)
        ).fetchone()
        pid = prod[0] if prod else None

        # 1) Guardar líneas y descontar MP por lote concreto
        for l in lineas:
            conn.execute("""
                UPDATE hojas_fabricacion_lineas
                SET materia_codigo = ?, materia_lote = ?, cantidad_real = ?,
                    unidad_real = ?
                WHERE id = ?
            """, (l.get("materia_codigo", ""), l.get("materia_lote", ""),
                  l.get("cantidad_real", 0), l.get("unidad_real", ""),
                  l.get("id")))
            if l.get("cantidad_real") and l["cantidad_real"] > 0:
                descontar_mp_lote(conn, l["materia_codigo"], l["materia_lote"],
                                  l["cantidad_real"])
                conn.execute("""
                    INSERT INTO trazabilidad
                    (producto_lote, producto_id, materia_codigo, materia_lote,
                     cantidad_usada, fecha)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cab[3], pid, l["materia_codigo"], l["materia_lote"],
                      l["cantidad_real"], fecha_hoy))
                conn.execute("""
                    INSERT INTO movimientos_stock
                    (fecha, tipo_articulo, articulo_codigo, lote,
                     tipo_movimiento, cantidad, unidad, referencia, notas)
                    VALUES (?, 'MP', ?, ?, 'consumo', ?, ?, ?, ?)
                """, (fecha_hoy, l["materia_codigo"], l["materia_lote"],
                      l["cantidad_real"], l.get("unidad_real", ""), numero,
                      f"Fabricación {cab[3]}"))

        # 2) Registrar producción y stock de producto terminado
        if pid:
            conn.execute("""
                INSERT INTO producciones (producto_id, lote, cantidad, fecha, coste_total)
                VALUES (?, ?, ?, ?, 0)
            """, (pid, cab[3], cab[4], fecha_hoy))
            conn.execute("""
                INSERT INTO stock_producto
                (producto_id, lote, fecha_fabricacion, fecha_caducidad, cantidad)
                VALUES (?, ?, ?, NULL, ?)
            """, (pid, cab[3], fecha_hoy, cab[4]))

        # 3) Marcar como confirmada
        conn.execute(
            "UPDATE hojas_fabricacion SET estado = 'confirmada' WHERE numero = ?",
            (numero,))
        conn.commit()
        return True, f"Hoja {numero} confirmada. Producción y stock actualizados."
    except Exception as e:
        print(f"✘ Error confirmando hoja: {e}")
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# =========================================================
# EXPORT
# =========================================================
__all__ = [
    "fmt_fecha",
    # Entradas MP
    "registrar_entrada_mp", "listar_entradas_mp", "resumen_lotes_mp",
    "obtener_documento_entrada",
    # Catálogo MP
    "importar_catalogo_mp", "listar_catalogo_mp",
    "actualizar_proveedor_catalogo",
    # Expediciones / salidas
    "crear_expedicion", "listar_expediciones", "lineas_expedicion",
    "todas_lineas_expediciones",
    # Biblioteca de fórmulas
    "crear_formula", "nueva_version_formula", "listar_formulas",
    "buscar_formulas", "obtener_formula", "duplicar_formula", "eliminar_formula",
    "importar_formulas",
    # Hojas de fabricación
    "calcular_cantidades_formula", "crear_hoja_fabricacion",
    "listar_hojas_fabricacion", "lineas_hoja", "confirmar_hoja_fabricacion",
]
