"""
OZOLABS' WIZARD - Versión simplificada todo-en-uno
ERP/MRP básico para materias primas, productos y producción
"""
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date

# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(page_title="OZOLABS' WIZARD", page_icon="🧙‍♂️", layout="wide")

DB = "erp.db"


# =========================================================
# BASE DE DATOS
# =========================================================
def conectar():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def crear_tablas():
    conn = conectar()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS materias_primas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT NOT NULL, nombre TEXT NOT NULL, proveedor TEXT,
        lote TEXT NOT NULL, cantidad REAL NOT NULL, unidad TEXT NOT NULL,
        fecha_recepcion TEXT, fecha_caducidad TEXT,
        certificado_eco TEXT, caducidad_certificado TEXT,
        coste_unitario REAL DEFAULT 0, ubicacion TEXT,
        stock_minimo REAL DEFAULT 0, UNIQUE(codigo, lote))""")

    c.execute("""CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL,
        formato TEXT, stock_minimo REAL DEFAULT 0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS formulas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL, materia_codigo TEXT NOT NULL,
        cantidad_por_unidad REAL NOT NULL, unidad TEXT NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE)""")

    c.execute("""CREATE TABLE IF NOT EXISTS stock_producto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL, lote TEXT NOT NULL,
        fecha_fabricacion TEXT, fecha_caducidad TEXT, cantidad REAL NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE)""")

    c.execute("""CREATE TABLE IF NOT EXISTS trazabilidad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_lote TEXT NOT NULL, producto_id INTEGER,
        materia_codigo TEXT, materia_lote TEXT, cantidad_usada REAL, fecha TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS producciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER,
        lote TEXT NOT NULL, cantidad REAL NOT NULL, fecha TEXT,
        coste_total REAL DEFAULT 0)""")
    conn.commit()
    conn.close()


# =========================================================
# MATERIAS PRIMAS
# =========================================================
def añadir_materia(cod, nom, prov, lote, cant, uni, frec, fcad,
                   eco, feco, coste, ubi, smin):
    conn = conectar()
    try:
        conn.execute("""INSERT INTO materias_primas
            (codigo,nombre,proveedor,lote,cantidad,unidad,fecha_recepcion,
             fecha_caducidad,certificado_eco,caducidad_certificado,
             coste_unitario,ubicacion,stock_minimo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cod, nom, prov, lote, cant, uni, frec, fcad, eco, feco,
             coste, ubi, smin))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False
    finally:
        conn.close()


def listar_materias():
    conn = conectar()
    rows = conn.execute("""SELECT codigo,nombre,proveedor,lote,cantidad,unidad,
                                  fecha_caducidad,ubicacion,coste_unitario
                           FROM materias_primas ORDER BY nombre, lote""").fetchall()
    conn.close()
    return rows


def stock_por_codigo(cod):
    conn = conectar()
    row = conn.execute("""SELECT COALESCE(SUM(cantidad),0), unidad
                          FROM materias_primas WHERE codigo=?
                          GROUP BY unidad""", (cod,)).fetchone()
    conn.close()
    return row if row else (0, "")


def lotes_disponibles(cod):
    conn = conectar()
    rows = conn.execute("""SELECT id,lote,cantidad,unidad,fecha_caducidad
                           FROM materias_primas WHERE codigo=? AND cantidad>0
                           ORDER BY fecha_caducidad IS NULL, fecha_caducidad""",
                        (cod,)).fetchall()
    conn.close()
    return rows


def descontar_fefo(cod, necesaria):
    lotes = lotes_disponibles(cod)
    restante = necesaria
    usados = []
    conn = conectar()
    for mid, lote, cant, uni, fcad in lotes:
        if restante <= 0:
            break
        usar = min(cant, restante)
        conn.execute("UPDATE materias_primas SET cantidad=cantidad-? WHERE id=?",
                     (usar, mid))
        usados.append((lote, usar, uni))
        restante -= usar
    conn.commit()
    conn.close()
    if restante > 0.0001:
        raise ValueError(f"Stock insuficiente de {cod}. Faltan {restante}")
    return usados


# =========================================================
# PRODUCTOS Y FÓRMULAS
# =========================================================
def añadir_producto(cod, nom, formato, smin):
    conn = conectar()
    try:
        conn.execute("INSERT INTO productos (codigo,nombre,formato,stock_minimo) VALUES (?,?,?,?)",
                     (cod, nom, formato, smin))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False
    finally:
        conn.close()


def obtener_producto(cod):
    conn = conectar()
    row = conn.execute("SELECT id,codigo,nombre,formato,stock_minimo FROM productos WHERE codigo=?",
                       (cod,)).fetchone()
    conn.close()
    return row


def añadir_ingrediente(prod_cod, mat_cod, cant, uni):
    prod = obtener_producto(prod_cod)
    if not prod:
        st.error("Producto no existe")
        return False
    conn = conectar()
    conn.execute("""INSERT INTO formulas (producto_id,materia_codigo,cantidad_por_unidad,unidad)
                    VALUES (?,?,?,?)""", (prod[0], mat_cod, cant, uni))
    conn.commit()
    conn.close()
    return True


def ver_formula(prod_cod):
    prod = obtener_producto(prod_cod)
    if not prod:
        return []
    conn = conectar()
    rows = conn.execute("""SELECT materia_codigo,cantidad_por_unidad,unidad
                           FROM formulas WHERE producto_id=?""", (prod[0],)).fetchall()
    conn.close()
    return rows


def listar_productos():
    conn = conectar()
    rows = conn.execute("SELECT codigo,nombre,formato,stock_minimo FROM productos ORDER BY nombre").fetchall()
    conn.close()
    return rows


def stock_pt(cod=None):
    conn = conectar()
    if cod:
        rows = conn.execute("""SELECT p.codigo,p.nombre,s.lote,s.cantidad,
                                      s.fecha_fabricacion,s.fecha_caducidad
                               FROM stock_producto s JOIN productos p ON p.id=s.producto_id
                               WHERE p.codigo=?""", (cod,)).fetchall()
    else:
        rows = conn.execute("""SELECT p.codigo,p.nombre,s.lote,s.cantidad,
                                      s.fecha_fabricacion,s.fecha_caducidad
                               FROM stock_producto s JOIN productos p ON p.id=s.producto_id
                               ORDER BY p.nombre""").fetchall()
    conn.close()
    return rows


# =========================================================
# PRODUCCIÓN
# =========================================================
def producir(prod_cod, cantidad, lote=None, fcad=None):
    prod = obtener_producto(prod_cod)
    if not prod:
        return False, "Producto no existe"
    formula = ver_formula(prod_cod)
    if not formula:
        return False, "El producto no tiene fórmula definida"

    # Comprobar stock
    for mat_cod, cant_u, uni in formula:
        necesaria = cant_u * cantidad
        disp, _ = stock_por_codigo(mat_cod)
        if disp < necesaria:
            return False, f"Stock insuficiente de {mat_cod}: faltan {necesaria - disp:.3f} {uni}"

    if not lote:
        lote = f"PT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Descontar y trazabilidad
    conn = conectar()
    coste_total = 0
    for mat_cod, cant_u, uni in formula:
        necesaria = cant_u * cantidad
        usados = descontar_fefo(mat_cod, necesaria)
        for lote_mp, cant_usa, _ in usados:
            conn.execute("""INSERT INTO trazabilidad
                (producto_lote,producto_id,materia_codigo,materia_lote,cantidad_usada,fecha)
                VALUES (?,?,?,?,?,?)""",
                (lote, prod[0], mat_cod, lote_mp, cant_usa, datetime.now().isoformat()))
        # Coste
        precio_row = conn.execute("""SELECT coste_unitario FROM materias_primas
                                     WHERE codigo=? ORDER BY fecha_recepcion DESC LIMIT 1""",
                                  (mat_cod,)).fetchone()
        precio = precio_row[0] if precio_row else 0
        coste_total += precio * necesaria

    conn.execute("""INSERT INTO producciones (producto_id,lote,cantidad,fecha,coste_total)
                    VALUES (?,?,?,?,?)""",
                 (prod[0], lote, cantidad, datetime.now().isoformat(), coste_total))

    conn.execute("""INSERT INTO stock_producto
                    (producto_id,lote,fecha_fabricacion,fecha_caducidad,cantidad)
                    VALUES (?,?,?,?,?)""",
                 (prod[0], lote, datetime.now().date().isoformat(), fcad, cantidad))
    conn.commit()
    conn.close()

    return True, f"Lote {lote} · Coste: {coste_total:.2f} €"


# =========================================================
# AVISOS
# =========================================================
def generar_avisos(dias_cad=30, dias_cert=60):
    avisos = []
    hoy = datetime.now().date()
    lim = hoy + timedelta(days=dias_cad)
    lim_c = hoy + timedelta(days=dias_cert)
    conn = conectar()

    # Stock bajo MP
    for cod, nom, total, uni, smin in conn.execute("""
        SELECT codigo,nombre,SUM(cantidad),unidad,MAX(stock_minimo)
        FROM materias_primas GROUP BY codigo""").fetchall():
        if smin and total < smin:
            avisos.append(f"⚠ Stock bajo de '{nom}' ({cod}): {total:.2f} {uni} (mín. {smin})")

    # Caducidad MP
    for cod, nom, lote, cant, uni, fcad in conn.execute("""
        SELECT codigo,nombre,lote,cantidad,unidad,fecha_caducidad
        FROM materias_primas WHERE cantidad>0 AND fecha_caducidad IS NOT NULL""").fetchall():
        try:
            f = datetime.fromisoformat(fcad).date()
        except Exception:
            continue
        if f < hoy:
            avisos.append(f"❌ Lote {lote} de {nom} CADUCADO ({fcad})")
        elif f <= lim:
            dias = (f - hoy).days
            avisos.append(f"⏰ Lote {lote} de {nom} caduca en {dias} días")

    # Certificados eco
    for nom, lote, cert, fcert in conn.execute("""
        SELECT nombre,lote,certificado_eco,caducidad_certificado
        FROM materias_primas
        WHERE certificado_eco IS NOT NULL AND caducidad_certificado IS NOT NULL""").fetchall():
        try:
            f = datetime.fromisoformat(fcert).date()
        except Exception:
            continue
        if f < hoy:
            avisos.append(f"❌ Certificado '{cert}' de {nom} CADUCADO")
        elif f <= lim_c:
            dias = (f - hoy).days
            avisos.append(f"📜 Certificado '{cert}' de {nom} caduca en {dias} días")

    # Stock bajo PT
    for cod, nom, total, smin in conn.execute("""
        SELECT p.codigo,p.nombre,COALESCE(SUM(s.cantidad),0),p.stock_minimo
        FROM productos p LEFT JOIN stock_producto s ON s.producto_id=p.id
        GROUP BY p.id""").fetchall():
        if smin and total < smin:
            avisos.append(f"⚠ Stock bajo de PT '{nom}': {total} uds (mín. {smin})")

    conn.close()
    return avisos


# =========================================================
# INICIALIZACIÓN
# =========================================================
crear_tablas()


# =========================================================
# INTERFAZ
# =========================================================
st.sidebar.markdown("""
<div style="text-align:center; padding:10px 0;">
    <h1 style="margin:0; color:#7B68EE;">🧙‍♂️</h1>
    <h2 style="margin:0; font-size:1.1em;">OZOLABS'</h2>
    <h1 style="margin:0; font-size:1.4em; color:#7B68EE;">WIZARD</h1>
    <p style="font-size:0.7em; opacity:0.6;">ERP / MRP</p>
</div>
""", unsafe_allow_html=True)

seccion = st.sidebar.radio("Módulo", [
    "🏠 Dashboard",
    "🌿 Materias primas",
    "📦 Productos y fórmulas",
    "⚙️ Producción",
    "📊 Avisos",
])


# =========================================================
# DASHBOARD
# =========================================================
if seccion == "🏠 Dashboard":
    st.markdown("""
    <div style="background:linear-gradient(90deg,#1e1e2f,#2d2d5a);padding:20px 30px;
                border-radius:12px;margin-bottom:20px;">
        <h1 style="margin:0;color:#fff;">🧙‍♂️ OZOLABS' <span style="color:#9B7FFF;">WIZARD</span></h1>
        <p style="margin:6px 0 0 0;color:#bbb;">Tu centro de control para materias primas y producción</p>
    </div>
    """, unsafe_allow_html=True)

    mp = listar_materias()
    pt = stock_pt()
    productos = listar_productos()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lotes de MP", len(mp))
    c2.metric("Productos", len(productos))
    c3.metric("Lotes PT en stock", len(pt))
    c4.metric("Avisos activos", len(generar_avisos()))

    st.markdown("### ⚠️ Avisos")
    avisos = generar_avisos()
    if avisos:
        for a in avisos:
            st.warning(a)
    else:
        st.success("✔ Sin avisos. Todo en orden.")

    st.markdown("### 📊 Stock materias primas")
    if mp:
        datos = {}
        for cod, nom, prov, lote, cant, uni, fcad, ubi, coste in mp:
            datos.setdefault((cod, nom, uni), 0)
            datos[(cod, nom, uni)] += cant
        df_mp = pd.DataFrame([(k[0], k[1], v, k[2]) for k, v in datos.items()],
                             columns=["Código", "Nombre", "Stock", "Unidad"])
        st.dataframe(df_mp, use_container_width=True)
        if not df_mp.empty:
            st.bar_chart(df_mp.set_index("Nombre")["Stock"])

    st.markdown("### 📦 Stock producto terminado")
    if pt:
        df_pt = pd.DataFrame(pt, columns=["Código", "Producto", "Lote", "Cantidad",
                                            "Fabricación", "Caducidad"])
        st.dataframe(df_pt, use_container_width=True)


# =========================================================
# MATERIAS PRIMAS
# =========================================================
elif seccion == "🌿 Materias primas":
    st.title("🌿 Materias primas")
    tab1, tab2, tab3 = st.tabs(["➕ Añadir", "📋 Stock", "🔍 Lotes"])

    with tab1:
        with st.form("form_mp"):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código *")
            nom = c2.text_input("Nombre *")
            prov = c1.text_input("Proveedor")
            lote = c2.text_input("Lote *")
            cant = c1.number_input("Cantidad *", min_value=0.0, step=0.1)
            uni = c2.selectbox("Unidad *", ["kg", "g", "L", "mL", "ud"])
            frec = c1.date_input("Recepción", value=date.today())
            fcad = c2.date_input("Caducidad", value=None)
            eco = c1.text_input("Certificado eco")
            feco = c2.date_input("Caduc. certificado", value=None)
            coste = c1.number_input("Coste €/ud", min_value=0.0, step=0.01)
            ubi = c2.text_input("Ubicación")
            smin = c1.number_input("Stock mínimo", min_value=0.0)

            if st.form_submit_button("Guardar"):
                if cod and nom and lote:
                    if añadir_materia(cod, nom, prov, lote, cant, uni,
                                       str(frec), str(fcad) if fcad else None,
                                       eco or None, str(feco) if feco else None,
                                       coste, ubi, smin):
                        st.success("✔ Añadida")
                        st.rerun()
                else:
                    st.error("Código, nombre y lote son obligatorios")

    with tab2:
        filas = listar_materias()
        df_mp = pd.DataFrame(filas, columns=["Código", "Nombre", "Proveedor",
                                                "Lote", "Cantidad", "Unidad",
                                                "Caducidad", "Ubicación", "€/ud"])
        st.dataframe(df_mp, use_container_width=True)

    with tab3:
        cod = st.text_input("Código MP")
        if cod:
            filas = lotes_disponibles(cod)
            df_l = pd.DataFrame(filas, columns=["ID", "Lote", "Cantidad", "Unidad", "Caducidad"])
            st.dataframe(df_l, use_container_width=True)


# =========================================================
# PRODUCTOS
# =========================================================
elif seccion == "📦 Productos y fórmulas":
    st.title("📦 Productos y fórmulas")
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Crear producto", "🧪 Añadir ingrediente",
                                        "📜 Ver fórmula", "📦 Stock PT"])

    with tab1:
        with st.form("form_prod"):
            cod = st.text_input("Código *")
            nom = st.text_input("Nombre *")
            formato = st.text_input("Formato")
            smin = st.number_input("Stock mínimo", min_value=0.0)
            if st.form_submit_button("Crear"):
                if cod and nom:
                    if añadir_producto(cod, nom, formato, smin):
                        st.success("✔ Creado")
                        st.rerun()

    with tab2:
        with st.form("form_ing"):
            pc = st.text_input("Producto")
            mc = st.text_input("Materia prima")
            cant = st.number_input("Cantidad por unidad", min_value=0.0, step=0.001, format="%.4f")
            uni = st.selectbox("Unidad", ["kg", "g", "L", "mL", "ud"])
            if st.form_submit_button("Añadir"):
                if añadir_ingrediente(pc, mc, cant, uni):
                    st.success("✔ Añadido")

    with tab3:
        pc = st.text_input("Producto", key="vf")
        if pc:
            filas = ver_formula(pc)
            if filas:
                df_f = pd.DataFrame(filas, columns=["Materia", "Cant/ud", "Unidad"])
                st.dataframe(df_f, use_container_width=True)
            else:
                st.info("Sin fórmula definida")

    with tab4:
        filas = stock_pt()
        df_pt = pd.DataFrame(filas, columns=["Código", "Producto", "Lote", "Cantidad",
                                                "Fabricación", "Caducidad"])
        st.dataframe(df_pt, use_container_width=True)


# =========================================================
# PRODUCCIÓN
# =========================================================
elif seccion == "⚙️ Producción":
    st.title("⚙️ Registrar producción")

    col1, col2 = st.columns(2)
    cod = col1.text_input("Código producto *")
    cant = col2.number_input("Cantidad a fabricar *", min_value=0.0, step=1.0)
    lote = col1.text_input("Lote PT (vacío=auto)")
    fcad = col2.date_input("Caducidad PT", value=None)

    if cod and cant > 0:
        formula = ver_formula(cod)
        if formula:
            st.markdown("### 🧪 Materias primas necesarias")
            df_n = pd.DataFrame(
                [(mc, cu * cant, u) for mc, cu, u in formula],
                columns=["Materia", "Cantidad necesaria", "Unidad"])
            st.dataframe(df_n, use_container_width=True)

    if st.button("🚀 Fabricar"):
        if not cod or cant <= 0:
            st.error("Introduce código y cantidad")
        else:
            ok, msg = producir(cod, cant, lote or None, str(fcad) if fcad else None)
            if ok:
                st.success(f"✔ {msg}")
                st.rerun()
            else:
                st.error(msg)


# =========================================================
# AVISOS
# =========================================================
elif seccion == "📊 Avisos":
    st.title("📊 Avisos automáticos")
    avisos = generar_avisos()
    if not avisos:
        st.success("✔ Sin avisos")
    else:
        for a in avisos:
            if "❌" in a:
                st.error(a)
            elif "⚠" in a or "⏰" in a:
                st.warning(a)
            else:
                st.info(a)


st.sidebar.markdown("---")
st.sidebar.caption(f"🧙‍♂️ OZOLABS' WIZARD v1.0 · {datetime.now().strftime('%d/%m/%Y')}")