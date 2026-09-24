"""
OZOLABS' WIZARD - Aplicación web principal (Streamlit)
Versión multiarchivo completa.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import base64

from database import crear_tablas, backup_db, conectar
from modelos import (
    añadir_materia, listar_materias, stock_por_codigo, lotes_disponibles,
    añadir_producto, obtener_producto, añadir_ingrediente_formula,
    ver_formula, stock_producto_terminado, trazabilidad_lote,
    producir, calcular_coste_produccion,
    añadir_envase, listar_envases, stock_envase,
    añadir_envase_a_formula, ver_formula_envases,
    añadir_proveedor, listar_proveedores, comparar_precios,
    añadir_coste_indirecto, listar_costes_indirectos,
    definir_tiempos_producto,
    crear_orden_produccion, listar_ordenes, ejecutar_orden,
    poner_pedido_en_preparacion, poner_pedido_en_curso,
    cancelar_pedido, reservas_de_pedido, estado_pedido,
    historico_producciones, listar_movimientos,
    exportar_stock_mp, exportar_stock_pt, exportar_historico,
    exportar_mrp_csv,
    ver_escandallo_real, necesidades_mrp,
    registrar_control_calidad, ver_controles_calidad,
    registrar_no_conformidad, listar_no_conformidades,
    cerrar_no_conformidad, cambiar_estado_lote,
    listar_lotes_por_estado,
)
from avisos import generar_avisos
from usuarios import (
    autenticar, crear_usuario, listar_usuarios, cambiar_rol,
    activar_desactivar, cambiar_password, ver_auditoria,
    crear_admin_inicial, crear_tabla_usuarios, ROLES, puede_acceder,
)
from analytics import (
    kpis_generales, serie_stock_mp, serie_producciones_por_mes,
    coste_unitario_por_producto, evolucion_coste_por_producto,
    consumo_mp_por_mes, top_productos_por_volumen,
    mermas_por_producto, desviacion_media_por_mp,
    pedidos_por_estado, compras_por_mes, proveedores_top,
    rendimiento_por_producto,
)
from informes import (
    generar_informe_produccion, generar_etiqueta_termica,
    generar_hoja_pesada, generar_informe_rendimiento,
)
from qr_utils import generar_qr, url_informe
from emailer import enviar_informe_email, enviar_alerta_stock
from firmas import firma_widget, tiene_firma, obtener_firma
from mermas import (
    registrar_peso_real, pesos_de_pedido, resumen_merma_pedido,
    registrar_merma, listar_mermas, resumen_mermas_producto,
    registrar_subproducto, listar_subproductos, coste_real_ajustado,
)
from rendimiento import (
    registrar_rendimiento, rendimiento_de_lote,
    rendimiento_medio_producto, historico_rendimiento,
)
from reprocesos import (
    abrir_reproceso, cerrar_reproceso, listar_reprocesos,
    ver_reproceso, reprocesos_de_lote, motivos_frecuentes,
)
from compras import (
    crear_orden_compra, listar_ordenes_compra, ver_orden_compra,
    cambiar_estado_orden_compra, calcular_necesidad_compra_mrp,
    crear_recepcion, añadir_linea_recepcion,
    confirmar_recepcion_y_entrar_stock, lineas_recepcion,
    marcar_linea_qc, listar_recepciones,
)

import plotly.express as px


# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(
    page_title="OZOLABS' WIZARD",
    page_icon="🧙‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# LOGO OZOLABS' WIZARD
# =========================================================
def logo_base64(ruta="assets/logo.svg"):
    try:
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""


# =========================================================
# INICIALIZACIÓN
# =========================================================
if "db_inicializada" not in st.session_state:
    crear_tablas()
    crear_tabla_usuarios()
    crear_admin_inicial()
    st.session_state.db_inicializada = True


def df(filas, columnas):
    return pd.DataFrame(filas, columns=columnas) if filas else pd.DataFrame(columns=columnas)


def descargar_df(dataframe, nombre, etiqueta="⬇ Descargar CSV"):
    csv = dataframe.to_csv(index=False, sep=";").encode("utf-8")
    st.download_button(etiqueta, csv, file_name=nombre, mime="text/csv")


def pausa_visual():
    st.markdown("")


# =========================================================
# LOGIN
# =========================================================
if "usuario" not in st.session_state:
    st.session_state.usuario = None


def pantalla_login():
    st.markdown(
        """
        <div style="max-width:420px; margin:60px auto 0 auto; text-align:center;">
            <h1 style="color:#7B68EE; letter-spacing:3px;">OZOLABS' WIZARD</h1>
            <p style="opacity:0.6;">Accede con tus credenciales</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar", use_container_width=True):
            datos = autenticar(u, p)
            if datos:
                st.session_state.usuario = datos
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

    # --- Diagnóstico y rescate ---
    with st.expander("🔧 ¿No puedes entrar? Diagnóstico"):
        from database import conectar as _conn
        c = _conn()
        n = c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        filas = c.execute(
            "SELECT usuario, rol, activo FROM usuarios ORDER BY usuario"
        ).fetchall()
        c.close()
        st.write(f"Usuarios en la base de datos: **{n}**")
        if filas:
            st.dataframe(
                pd.DataFrame(filas, columns=["Usuario", "Rol", "Activo"]),
                use_container_width=True,
            )
        else:
            st.warning(
                "No hay ningún usuario. Pulsa el botón de abajo para crear "
                "el usuario **admin / admin**."
            )
        if st.button("🔄 Crear / restaurar admin (admin/admin)"):
            from usuarios import reset_admin
            if reset_admin():
                st.success("✔ admin/admin creado. Ya puedes entrar.")
            else:
                st.error(
                    "✘ No se pudo crear. Falta o falla `passlib`/`bcrypt`. "
                    "Revisa los logs del Space."
                )


if not st.session_state.usuario:
    pantalla_login()
    st.stop()


user = st.session_state.usuario
rol = user["rol"]


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.markdown(
    f"""
    <div style="text-align:center; padding: 12px 0 4px 0;">
        <img src="data:image/svg+xml;base64,{logo_base64()}"
             style="width:100px; height:100px; display:block; margin:0 auto 6px auto;"/>
        <h2 style="margin:0; font-size: 1.1em;">OZOLABS'</h2>
        <h1 style="margin:0; font-size: 1.4em; color:#7B68EE;">WIZARD</h1>
        <p style="margin:6px 0 0 0; font-size:0.7em; opacity:0.6;">
            {user['nombre']} · <b>{rol}</b>
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")

TODOS_LOS_MODULOS = [
    "🏠 Dashboard", "🌿 Materias primas", "📦 Productos y fórmulas",
    "⚙️ Producción", "📋 Pedidos de producción", "🧴 Envases y etiquetas",
    "🚚 Proveedores", "💰 Costes", "📊 Avisos", "📤 Salidas",
    "🔬 Escandallos reales", "📐 Planificación MRP", "✅ Control de calidad",
    "🏷️ Etiquetado", "📄 Informes PDF", "🖨️ Etiqueta térmica",
    "📖 Manual de uso", "📊 Análisis y gráficos", "📧 Envío de informes",
    "🔲 Códigos QR", "⚖️ Pesos reales", "📉 Mermas", "🖊️ Firmas digitales",
    "📈 Rendimiento", "🔄 Reprocesos", "🛒 Órdenes de compra",
    "📥 Recepción de mercancía",
]

if rol == "admin":
    MODULOS_VISIBLES = TODOS_LOS_MODULOS + ["👥 Usuarios", "📜 Auditoría", "ℹ️ Acerca de"]
else:
    MODULOS_VISIBLES = [m for m in TODOS_LOS_MODULOS if puede_acceder(rol, m)]
    MODULOS_VISIBLES.append("ℹ️ Acerca de")

seccion = st.sidebar.radio("Módulo", MODULOS_VISIBLES, label_visibility="collapsed")

st.sidebar.markdown("---")
if st.sidebar.button("💾 Hacer backup BD", use_container_width=True):
    backup_db()
    st.sidebar.success("Backup creado en /backups")

if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
    st.session_state.usuario = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(f"🧙‍♂️ OZOLABS' WIZARD v1.0 · {datetime.now().strftime('%d/%m/%Y')}")


# =========================================================
# 🏠 DASHBOARD
# =========================================================
if seccion == "🏠 Dashboard":
    st.markdown(
        f"""
        <div style="
            display:flex; align-items:center; gap:20px;
            background: linear-gradient(90deg, #1e1e2f 0%, #2d2d5a 100%);
            padding: 20px 30px; border-radius: 12px; margin-bottom: 20px;
        ">
            <img src="data:image/svg+xml;base64,{logo_base64()}"
                 style="width:80px; height:80px; flex-shrink:0;"/>
            <div>
                <h1 style="margin:0; color:#fff; letter-spacing:2px;">
                    OZOLABS' <span style="color:#9B7FFF;">WIZARD</span>
                </h1>
                <p style="margin:6px 0 0 0; color:#bbb;">
                    Tu centro de control para materias primas, producción y calidad.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mp = listar_materias()
    pt = stock_producto_terminado()
    env = listar_envases()
    ordenes = listar_ordenes()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lotes de MP", len(mp))
    c2.metric("Lotes de PT", len(pt))
    c3.metric("Lotes de envases", len(env))
    c4.metric("Pedidos activos",
              sum(1 for o in ordenes if o[5] in ("planificado", "en_preparacion", "en_curso")))

    st.markdown("### ⚠️ Avisos")
    avisos = generar_avisos()
    if avisos:
        for a in avisos:
            st.warning(a)
    else:
        st.success("✔ Sin avisos. Todo en orden.")

    st.markdown("### 📊 Stock global de materias primas")
    if mp:
        datos = {}
        for cod, nom, lote, cant, uni, fcad, ubi in mp:
            datos.setdefault((cod, nom, uni), 0)
            datos[(cod, nom, uni)] += cant
        df_mp = pd.DataFrame(
            [(k[0], k[1], v, k[2]) for k, v in datos.items()],
            columns=["Código", "Nombre", "Stock total", "Unidad"],
        )
        st.dataframe(df_mp, use_container_width=True)
        st.bar_chart(df_mp.set_index("Nombre")["Stock total"])

    st.markdown("### 📦 Stock producto terminado")
    if pt:
        df_pt = df(pt, ["Código", "Producto", "Lote", "Cantidad", "Caducidad", "Fabricación"])
        st.dataframe(df_pt, use_container_width=True)


# =========================================================
# 🌿 MATERIAS PRIMAS
# =========================================================
elif seccion == "🌿 Materias primas":
    st.title("🌿 Materias primas")
    tab1, tab2, tab3 = st.tabs(["➕ Añadir lote", "📋 Stock actual", "🔍 Lotes de un código"])

    with tab1:
        with st.form("form_mp"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código *")
            nombre = c2.text_input("Nombre *")
            proveedor = c1.text_input("Proveedor")
            lote = c2.text_input("Lote *")
            cantidad = c1.number_input("Cantidad *", min_value=0.0, step=0.1)
            unidad = c2.selectbox("Unidad *", ["kg", "g", "L", "mL", "ud"])
            frec = c1.date_input("Fecha recepción", value=date.today())
            fcad = c2.date_input("Fecha caducidad", value=None)
            eco = c1.text_input("Certificado ecológico")
            feco = c2.date_input("Caducidad certificado", value=None)
            coste = c1.number_input("Coste unitario (€)", min_value=0.0, step=0.01)
            ubi = c2.text_input("Ubicación")
            smin = c1.number_input("Stock mínimo", min_value=0.0, step=0.1)

            if st.form_submit_button("Guardar"):
                if not codigo or not nombre or not lote:
                    st.error("Código, nombre y lote son obligatorios.")
                else:
                    añadir_materia(
                        codigo, nombre, proveedor, lote, cantidad, unidad,
                        str(frec), str(fcad) if fcad else None,
                        eco or None, str(feco) if feco else None,
                        coste, ubi, smin,
                    )
                    st.success("✔ Materia prima añadida.")
                    st.rerun()

    with tab2:
        filas = listar_materias()
        df_mp = df(filas, ["Código", "Nombre", "Lote", "Cantidad", "Unidad", "Caducidad", "Ubicación"])
        st.dataframe(df_mp, use_container_width=True)
        descargar_df(df_mp, "stock_materias_primas.csv")

    with tab3:
        cod = st.text_input("Código MP")
        if cod:
            filas = lotes_disponibles(cod)
            df_l = df(filas, ["ID", "Lote", "Cantidad", "Unidad", "Caducidad"])
            st.dataframe(df_l, use_container_width=True)


# =========================================================
# 📦 PRODUCTOS Y FÓRMULAS
# =========================================================
elif seccion == "📦 Productos y fórmulas":
    from modelos import (ver_formula_detallada, actualizar_producto,
                         borrar_ingrediente_formula, producto_por_nombre)
    st.title("📦 Productos y fórmulas")

    conn = conectar()
    prods = conn.execute(
        "SELECT codigo, nombre FROM productos ORDER BY nombre"
    ).fetchall()
    conn.close()
    opciones_prod = [f"{c} · {n}" for c, n in prods]

    tab1, tab2, tab3, tab4 = st.tabs([
        "➕ Nuevo producto", "🧪 Editar fórmula", "📜 Ver fórmulas",
        "📦 Stock producto terminado",
    ])

    # ---------- TAB 1: crear / editar producto ----------
    with tab1:
        st.markdown("### Datos del producto")
        with st.form("form_prod"):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código *")
            nom = c2.text_input("Nombre *")
            c3, c4 = st.columns(2)
            tamano = c3.number_input("Tamaño por unidad *", min_value=0.0,
                                      step=1.0, value=50.0)
            uni_tam = c4.selectbox("Unidad del tamaño", ["mL", "g"])
            c5, c6 = st.columns(2)
            uso = c5.selectbox("Uso", ["cosmetico", "alimentario", "ambos"])
            formato = c6.text_input("Formato/presentación")
            c7, c8 = st.columns(2)
            env_cod = c7.text_input("Código envase (opcional)")
            cad_meses = c8.number_input("Caducidad (meses)", min_value=0,
                                         step=1, value=0)
            smin = st.number_input("Stock mínimo (uds)", min_value=0.0)

            if st.form_submit_button("💾 Guardar producto"):
                if not cod or not nom:
                    st.error("Código y nombre son obligatorios.")
                else:
                    existente = obtener_producto(cod)
                    if existente:
                        actualizar_producto(cod, nom, formato, smin, tamano,
                                            uni_tam, uso, env_cod, int(cad_meses))
                        st.success(f"✔ Producto '{nom}' actualizado.")
                    else:
                        añadir_producto(cod, nom, formato, smin, tamano,
                                        uni_tam, uso, env_cod, int(cad_meses))
                        st.success(f"✔ Producto '{nom}' creado.")
                    st.rerun()

        if prods:
            st.markdown("---")
            st.markdown("### Editar un producto existente")
            sel_ed = st.selectbox("Producto a editar", opciones_prod,
                                   key="sel_editar")
            cod_ed = sel_ed.split(" · ")[0]
            p = obtener_producto(cod_ed)
            if p:
                st.info(
                    f"**{p[2]}** · Tamaño: {p[5]} {p[6]} · Uso: {p[7]} "
                    f"· Stock mín: {p[4]}"
                )
                st.caption("Para modificarlo, escribe su código arriba y "
                           "vuelve a guardar.")

    # ---------- TAB 2: editar fórmula (% + cantidad) ----------
    with tab2:
        if not prods:
            st.info("Crea primero un producto.")
        else:
            sel = st.selectbox("Producto", opciones_prod, key="sel_formula")
            prod_cod = sel.split(" · ")[0]
            prod_nom = sel.split(" · ")[1]
            p = obtener_producto(prod_cod)
            tamano = p[5] if p else 0
            uni_tam = p[6] if p else "mL"

            st.markdown(
                f"**{prod_nom}** · Tamaño por unidad: **{tamano} {uni_tam}**"
            )
            st.caption("Introduce cada ingrediente en **%**. Se calcula "
                       "automáticamente la cantidad por unidad.")

            # Fórmula actual
            formula = ver_formula_detallada(prod_cod)
            if formula:
                filas_f = []
                total_pct = 0
                total_coste = 0
                for cod_mp, nom_mp, cant, uni, pct, precio, sub in formula:
                    filas_f.append([nom_mp, f"{pct:.1f} %", f"{cant:.3f}",
                                    uni, f"{precio:.3f} €", f"{sub:.3f} €"])
                    total_pct += pct
                    total_coste += sub
                df_f = pd.DataFrame(filas_f, columns=["Ingrediente", "%",
                                                       "Cantidad/ud", "Unidad",
                                                       "€/unidad", "Coste/ud"])
                st.dataframe(df_f, use_container_width=True)
                cc1, cc2 = st.columns(2)
                cc1.metric("Suma de %", f"{total_pct:.1f} %",
                           delta="OK" if abs(total_pct - 100) < 0.5 else "Revisar")
                cc2.metric("Coste MP/unidad", f"{total_coste:.4f} €")
            else:
                st.info("Sin fórmula definida todavía.")

            st.markdown("---")
            st.markdown("### Añadir ingrediente")
            with st.form("form_ing_porc"):
                c1, c2 = st.columns(2)
                mp_cod = c1.text_input("Código de materia prima *")
                pct = c2.number_input("% del ingrediente", min_value=0.0,
                                       max_value=100.0, step=0.1, value=0.0)
                modo = st.radio(
                    "¿Cómo quieres introducirlo?",
                    ["Solo %  (calcula cantidad)", "Solo cantidad  (calcula %)"],
                    horizontal=True,
                )
                if modo.startswith("Solo cantidad"):
                    cant_manual = st.number_input(
                        f"Cantidad por unidad ({uni_tam})", min_value=0.0,
                        step=0.001, format="%.4f")
                else:
                    cant_manual = 0.0

                if st.form_submit_button("➕ Añadir a la fórmula"):
                    if not mp_cod:
                        st.error("Indica el código de la materia prima.")
                    else:
                        mp = obtener_producto(mp_cod)  # comprobar
                        conn2 = conectar()
                        existe = conn2.execute(
                            "SELECT nombre FROM materias_primas WHERE codigo = ? LIMIT 1",
                            (mp_cod,)).fetchone()
                        conn2.close()
                        if not existe:
                            st.error(f"No existe la materia prima '{mp_cod}'.")
                        else:
                            if modo.startswith("Solo cantidad") and tamano > 0:
                                cant = cant_manual
                                pct_calc = (cant / tamano * 100) if tamano else 0
                            else:
                                cant = tamano * pct / 100.0
                                pct_calc = pct
                            añadir_ingrediente_formula(prod_cod, mp_cod, cant,
                                                       uni_tam, pct_calc)
                            st.success("✔ Ingrediente añadido.")
                            st.rerun()

            # Borrar ingrediente
            if formula:
                st.markdown("### Eliminar ingrediente")
                nombres = [f[1] for f in formula]
                del_sel = st.selectbox("Ingrediente a eliminar", nombres,
                                        key="del_ing")
                if st.button("🗑 Eliminar de la fórmula"):
                    for f in formula:
                        if f[1] == del_sel:
                            borrar_ingrediente_formula(prod_cod, f[0])
                            st.success("✔ Eliminado.")
                            st.rerun()

    # ---------- TAB 3: ver fórmulas ----------
    with tab3:
        if not prods:
            st.info("No hay productos.")
        else:
            sel_v = st.selectbox("Elige un producto por su nombre",
                                 opciones_prod, key="sel_ver")
            prod_cod = sel_v.split(" · ")[0]
            prod_nom = sel_v.split(" · ")[1]
            formula = ver_formula_detallada(prod_cod)
            if formula:
                st.markdown(f"### Fórmula de **{prod_nom}**")
                filas_f = []
                for cod_mp, nom_mp, cant, uni, pct, precio, sub in formula:
                    filas_f.append([nom_mp, f"{pct:.1f} %", f"{cant:.3f}",
                                    uni, f"{precio:.3f} €", f"{sub:.3f} €"])
                df_f = pd.DataFrame(filas_f, columns=["Ingrediente", "%",
                                                       "Cantidad/ud", "Unidad",
                                                       "€/unidad", "Coste/ud"])
                st.dataframe(df_f, use_container_width=True)
            else:
                st.info("Este producto no tiene fórmula todavía.")

    # ---------- TAB 4: stock producto terminado ----------
    with tab4:
        st.markdown("### Stock de producto terminado (PT)")
        st.caption("Aquí se ven los lotes de producto ya fabricados.")
        filas = stock_producto_terminado()
        df_pt = df(filas, ["Código", "Producto", "Lote", "Cantidad",
                            "Caducidad", "Fabricación"])
        st.dataframe(df_pt, use_container_width=True)
        descargar_df(df_pt, "stock_producto_terminado.csv")

        st.markdown("### 🔎 Trazabilidad de un lote")
        lote = st.text_input("Lote PT", key="traz_pt")
        if lote:
            filas_t = trazabilidad_lote(lote)
            df_t = df(filas_t, ["MP", "Lote MP", "Cantidad usada", "Fecha"])
            st.dataframe(df_t, use_container_width=True)


# =========================================================
# ⚙️ PRODUCCIÓN
# =========================================================
elif seccion == "⚙️ Producción":
    st.title("⚙️ Registrar producción")

    col1, col2 = st.columns(2)
    cod = col1.text_input("Código producto *")
    cant = col2.number_input("Cantidad a fabricar *", min_value=0.0, step=1.0)
    lote = col1.text_input("Lote PT (vacío=auto)")
    fcad = col2.date_input("Caducidad PT", value=None)

    if cod and cant > 0:
        coste = calcular_coste_produccion(cod, cant)
        if coste:
            st.markdown("### 💰 Previsión de coste")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Materias primas", f"{coste['mp']:.2f} €")
            c2.metric("Envases", f"{coste['envases']:.2f} €")
            c3.metric("Mano de obra + ind.", f"{coste['mano_obra'] + coste['indirectos']:.2f} €")
            c4.metric("Coste unitario", f"{coste['coste_unitario']:.4f} €/ud")

            with st.expander("Ver desglose"):
                st.write("**Materias primas**")
                st.dataframe(
                    pd.DataFrame(coste["detalle_mp"],
                                 columns=["Código", "Cantidad", "Unidad", "€/ud", "Subtotal"]),
                    use_container_width=True,
                )
                if coste["detalle_env"]:
                    st.write("**Envases**")
                    st.dataframe(
                        pd.DataFrame(coste["detalle_env"],
                                     columns=["Código", "Cantidad", "€/ud", "Subtotal"]),
                        use_container_width=True,
                    )

    if st.button("🚀 Fabricar"):
        if not cod or cant <= 0:
            st.error("Introduce código y cantidad.")
        else:
            try:
                producir(cod, cant, lote or None, str(fcad) if fcad else None)
                st.success("✔ Producción registrada. Stock descontado (FEFO) y trazabilidad guardada.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")


# =========================================================
# 📋 PEDIDOS DE PRODUCCIÓN
# =========================================================
elif seccion == "📋 Pedidos de producción":
    st.title("📋 Pedidos de producción")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "➕ Crear pedido", "📄 Listar pedidos", "🔄 Ciclo de vida",
        "▶️ Ejecutar pedido", "📜 Historial de un pedido", "📄 Hoja de pesada",
    ])

    with tab1:
        with st.form("form_pedido"):
            cod = st.text_input("Código producto")
            cant = st.number_input("Cantidad", min_value=0.0)
            fprev = st.date_input("Fecha prevista", value=None)
            prioridad = st.selectbox("Prioridad", ["normal", "alta", "urgente"])
            obs = st.text_area("Observaciones")
            if st.form_submit_button("Crear pedido"):
                numero = crear_orden_produccion(
                    cod, cant, str(fprev) if fprev else None, obs, prioridad,
                )
                if numero:
                    st.success(f"✔ Pedido {numero} creado.")
                    st.rerun()

    with tab2:
        est = st.selectbox(
            "Filtrar estado",
            ["(todos)", "planificado", "en_preparacion", "en_curso", "finalizado", "cancelado"],
        )
        filas = listar_ordenes(None if est == "(todos)" else est)
        df_op = df(filas, [
            "Nº pedido", "Código", "Producto", "Planif.", "Fabricado",
            "Estado", "Creado", "Previsto", "Iniciado",
        ])
        st.dataframe(df_op, use_container_width=True)

    with tab3:
        st.markdown("### Cambiar estado de un pedido")
        conn = conectar()
        pedidos_activos = conn.execute("""
            SELECT numero, estado FROM ordenes_produccion
            WHERE estado IN ('planificado','en_preparacion','en_curso')
            ORDER BY fecha_creacion DESC
        """).fetchall()
        conn.close()

        if not pedidos_activos:
            st.info("No hay pedidos activos.")
        else:
            opciones = [f"{n} · {e}" for n, e in pedidos_activos]
            sel = st.selectbox("Pedido activo", opciones)
            numero_sel = sel.split(" · ")[0]
            estado_actual = sel.split(" · ")[1]
            st.caption(f"Estado actual: **{estado_actual}**")

            col1, col2 = st.columns(2)
            with col1:
                if estado_actual == "planificado":
                    if st.button("📦 Poner en preparación"):
                        if poner_pedido_en_preparacion(numero_sel):
                            st.success("✔ Reservas creadas.")
                            st.rerun()
                        else:
                            st.error("No se pudo reservar.")
            with col2:
                if estado_actual == "en_preparacion":
                    if st.button("🔥 Empezar producción"):
                        if poner_pedido_en_curso(numero_sel):
                            st.success("✔ En curso.")
                            st.rerun()

            if estado_actual == "en_preparacion":
                st.markdown("#### 🔒 Reservas activas")
                res = reservas_de_pedido(numero_sel)
                if res:
                    df_res = pd.DataFrame(res, columns=["Tipo", "Código", "Cantidad",
                                                          "Ud", "Estado", "Fecha"])
                    st.dataframe(df_res, use_container_width=True)

            st.markdown("---")
            with st.expander("🚫 Cancelar pedido"):
                motivo = st.text_input("Motivo de cancelación")
                if st.button("Cancelar pedido"):
                    if cancelar_pedido(numero_sel, motivo):
                        st.success("✔ Cancelado.")
                        st.rerun()

    with tab4:
        num = st.text_input("Nº pedido a finalizar")
        lote = st.text_input("Lote PT (vacío=nº pedido)")
        fcad = st.date_input("Caducidad PT", value=None)
        if st.button("✅ Finalizar pedido"):
            if num:
                ejecutar_orden(num, lote or None, str(fcad) if fcad else None)
                st.success(f"✔ Pedido {num} finalizado.")
                st.rerun()

    with tab5:
        num = st.text_input("Nº pedido", key="hist_ped")
        if num:
            from modelos import conectar as _c
            c = conectar()
            row = c.execute("SELECT historial FROM ordenes_produccion WHERE numero=?",
                            (num,)).fetchone()
            c.close()
            if row and row[0]:
                st.text_area("Historial", row[0], height=250, disabled=True)
            res = reservas_de_pedido(num)
            if res:
                st.markdown("**Reservas:**")
                st.dataframe(pd.DataFrame(res, columns=["Tipo", "Código", "Cantidad",
                                                          "Ud", "Estado", "Fecha"]),
                             use_container_width=True)

    with tab6:
        st.markdown("### 📄 Generar hoja de pesada")
        num = st.text_input("Nº pedido", key="hp")
        if st.button("📄 Generar PDF"):
            if num:
                ruta = f"hoja_pesada_{num}.pdf"
                r = generar_hoja_pesada(num, ruta)
                if r and os.path.exists(ruta):
                    with open(ruta, "rb") as f:
                        st.download_button("⬇ Descargar", f.read(),
                                            file_name=ruta, mime="application/pdf")


# =========================================================
# 🧴 ENVASES
# =========================================================
elif seccion == "🧴 Envases y etiquetas":
    st.title("🧴 Envases y etiquetas")
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Añadir", "📋 Stock", "🧪 Fórmula envases", "📜 Ver fórmula"])

    with tab1:
        with st.form("form_env"):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código *")
            nom = c2.text_input("Nombre *")
            tipo = c1.selectbox("Tipo", ["tarro", "bomba", "tubo", "caja", "etiqueta", "bolsa", "otro"])
            lote = c2.text_input("Lote *")
            cant = c1.number_input("Cantidad *", min_value=0.0)
            uni = c2.text_input("Unidad", value="ud")
            coste = c1.number_input("Coste unitario €", min_value=0.0, step=0.001, format="%.4f")
            prov = c2.text_input("Proveedor")
            ubi = c1.text_input("Ubicación")
            smin = c2.number_input("Stock mínimo", min_value=0.0)
            if st.form_submit_button("Guardar"):
                añadir_envase(cod, nom, tipo, lote, cant, uni, coste, prov, ubi, smin)
                st.success("✔ Envase añadido.")
                st.rerun()

    with tab2:
        filas = listar_envases()
        df_e = df(filas, ["Código", "Nombre", "Tipo", "Lote", "Cantidad", "Unidad", "€/ud", "Stock mín."])
        st.dataframe(df_e, use_container_width=True)
        descargar_df(df_e, "stock_envases.csv")

    with tab3:
        with st.form("form_env_formula"):
            pc = st.text_input("Código producto")
            ec = st.text_input("Código envase")
            cpu = st.number_input("Cantidad por unidad", min_value=0.0, step=0.001, format="%.4f")
            if st.form_submit_button("Añadir a fórmula"):
                añadir_envase_a_formula(pc, ec, cpu)
                st.success("✔ Añadido.")
                st.rerun()

    with tab4:
        pc = st.text_input("Código producto", key="vfe")
        if pc:
            filas = ver_formula_envases(pc)
            df_f = df(filas, ["Envase", "Cantidad/ud"])
            st.dataframe(df_f, use_container_width=True)


# =========================================================
# 🚚 PROVEEDORES
# =========================================================
elif seccion == "🚚 Proveedores":
    st.title("🚚 Proveedores")
    tab1, tab2, tab3 = st.tabs(["➕ Añadir", "📋 Listar", "💲 Comparar precios"])

    with tab1:
        with st.form("form_prov"):
            cod = st.text_input("Código *")
            nom = st.text_input("Nombre *")
            cont = st.text_input("Contacto")
            email = st.text_input("Email")
            tel = st.text_input("Teléfono")
            pago = st.text_input("Condiciones de pago")
            notas = st.text_area("Notas")
            if st.form_submit_button("Guardar"):
                añadir_proveedor(cod, nom, cont, email, tel, pago, notas)
                st.success("✔ Proveedor añadido.")
                st.rerun()

    with tab2:
        filas = listar_proveedores()
        df_p = df(filas, ["Código", "Nombre", "Contacto", "Email", "Teléfono"])
        st.dataframe(df_p, use_container_width=True)

    with tab3:
        cod = st.text_input("Código artículo")
        if cod:
            filas = comparar_precios(cod)
            df_c = df(filas, ["Proveedor", "Precio €", "Fecha"])
            st.dataframe(df_c, use_container_width=True)


# =========================================================
# 💰 COSTES
# =========================================================
elif seccion == "💰 Costes":
    st.title("💰 Costes")
    tab1, tab2, tab3, tab4 = st.tabs(
        ["➕ Coste indirecto", "📋 Listar indirectos", "⏱️ Tiempos producto", "🧮 Calcular coste"]
    )

    with tab1:
        with st.form("form_ci"):
            concepto = st.text_input("Concepto")
            cph = st.number_input("€/hora", min_value=0.0, step=0.01)
            cpu = st.number_input("€/unidad", min_value=0.0, step=0.001, format="%.4f")
            if st.form_submit_button("Añadir"):
                añadir_coste_indirecto(concepto, cph, cpu)
                st.success("✔ Añadido.")
                st.rerun()

    with tab2:
        filas = listar_costes_indirectos()
        df_ci = df(filas, ["ID", "Concepto", "€/hora", "€/unidad", "Activo"])
        st.dataframe(df_ci, use_container_width=True)

    with tab3:
        with st.form("form_tp"):
            pc = st.text_input("Código producto")
            min_lote = st.number_input("Minutos por lote", min_value=0.0)
            horas_mo = st.number_input("Horas mano de obra", min_value=0.0)
            if st.form_submit_button("Guardar"):
                definir_tiempos_producto(pc, min_lote, horas_mo)
                st.success("✔ Guardado.")
                st.rerun()

    with tab4:
        pc = st.text_input("Código producto", key="cc")
        cant = st.number_input("Cantidad uds", min_value=1.0, value=100.0)
        if pc and st.button("Calcular"):
            c = calcular_coste_produccion(pc, cant)
            if not c:
                st.error("Producto no encontrado.")
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("MP", f"{c['mp']:.2f} €")
                c2.metric("Envases", f"{c['envases']:.2f} €")
                c3.metric("MO + ind.", f"{c['mano_obra'] + c['indirectos']:.2f} €")
                c4.metric("Total", f"{c['total']:.2f} €")
                st.metric("Coste unitario", f"{c['coste_unitario']:.4f} €/ud")


# =========================================================
# 📊 AVISOS
# =========================================================
elif seccion == "📊 Avisos":
    st.title("📊 Avisos automáticos")
    if st.button("🔄 Recalcular"):
        st.rerun()
    avisos = generar_avisos()
    if not avisos:
        st.success("✔ Sin avisos.")
    else:
        for a in avisos:
            if "❌" in a or "🚫" in a or "🔴" in a:
                st.error(a)
            elif "⚠" in a or "⏰" in a:
                st.warning(a)
            else:
                st.info(a)


# =========================================================
# 📈 HISTÓRICO
# =========================================================
elif seccion == "📈 Histórico y exportación":
    st.title("📈 Histórico y exportación")
    tab1, tab2, tab3 = st.tabs(["📜 Producciones", "🔁 Movimientos", "⬇️ Exportar"])

    with tab1:
        c1, c2 = st.columns(2)
        desde = c1.date_input("Desde", value=None)
        hasta = c2.date_input("Hasta", value=None)
        filas = historico_producciones(
            str(desde) if desde else None,
            str(hasta) if hasta else None,
        )
        df_h = df(filas, ["ID", "Código", "Producto", "Lote", "Cantidad", "Fecha", "Coste"])
        st.dataframe(df_h, use_container_width=True)
        if not df_h.empty:
            st.bar_chart(df_h.set_index("Producto")["Cantidad"])

    with tab2:
        filas = listar_movimientos(200)
        df_m = df(filas, ["Fecha", "Tipo art.", "Código", "Lote", "Movimiento", "Cant.", "Ud", "Ref."])
        st.dataframe(df_m, use_container_width=True)

    with tab3:
        col1, col2, col3 = st.columns(3)
        if col1.button("Exportar stock MP"):
            exportar_stock_mp(); st.success("Generado stock_materias_primas.csv")
        if col2.button("Exportar stock PT"):
            exportar_stock_pt(); st.success("Generado stock_producto_terminado.csv")
        if col3.button("Exportar histórico"):
            exportar_historico(); st.success("Generado historico_producciones.csv")


# =========================================================
# 🔬 ESCANDALLOS REALES
# =========================================================
elif seccion == "🔬 Escandallos reales":
    st.title("🔬 Escandallos reales por lote")
    lote = st.text_input("Lote PT")
    if lote:
        filas = ver_escandallo_real(lote)
        if not filas:
            st.info("Sin escandallo.")
        else:
            df_e = pd.DataFrame(filas, columns=["Tipo", "Código", "Lote", "Cantidad",
                                                  "Unidad", "€/ud", "Subtotal"])
            st.dataframe(df_e, use_container_width=True)
            st.metric("COSTE TOTAL REAL", f"{df_e['Subtotal'].sum():.2f} €")
            st.bar_chart(df_e.set_index("Código")["Subtotal"])


# =========================================================
# 📐 PLANIFICACIÓN MRP
# =========================================================
elif seccion == "📐 Planificación MRP":
    st.title("📐 Planificación MRP")
    st.caption("Necesidades con 10% de stock de seguridad.")
    filas = necesidades_mrp()
    df_m = pd.DataFrame(filas, columns=["Tipo", "Código", "Necesaria", "Disponible",
                                          "A comprar", "Unidad"]) if filas else pd.DataFrame(
        columns=["Tipo", "Código", "Necesaria", "Disponible", "A comprar", "Unidad"])
    st.dataframe(df_m, use_container_width=True)
    if not df_m.empty:
        st.bar_chart(df_m.set_index("Código")["A comprar"])
    if st.button("Exportar MRP"):
        exportar_mrp_csv(); st.success("Generado planificacion_mrp.csv")


# =========================================================
# ✅ CONTROL DE CALIDAD
# =========================================================
elif seccion == "✅ Control de calidad":
    st.title("✅ Control de calidad")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["➕ Análisis", "📋 Controles", "🚫 No conformidad", "📄 Listar NC", "🔓 Liberar lote"])

    with tab1:
        with st.form("form_qc"):
            c1, c2 = st.columns(2)
            tipo = c1.selectbox("Tipo", ["MP", "PT"])
            cod = c2.text_input("Código")
            lote = c1.text_input("Lote")
            param = c2.text_input("Parámetro")
            vobt = c1.text_input("Valor obtenido")
            vesp = c2.text_input("Valor esperado")
            res = c1.selectbox("Resultado", ["APTO", "NO_APTO", "PENDIENTE"])
            resp = c2.text_input("Responsable")
            obs = st.text_area("Observaciones")
            if st.form_submit_button("Registrar"):
                registrar_control_calidad(tipo, cod, lote, param, vobt, vesp, res, resp, obs)
                st.success("✔ Control registrado.")
                st.rerun()

    with tab2:
        tipo = st.selectbox("Tipo", ["(todos)", "MP", "PT"])
        filas = ver_controles_calidad(None if tipo == "(todos)" else tipo)
        df_c = df(filas, ["ID", "Tipo", "Código", "Lote", "Fecha", "Parámetro",
                            "Valor", "Esperado", "Resultado", "Resp."])
        st.dataframe(df_c, use_container_width=True)

    with tab3:
        with st.form("form_nc"):
            tipo = st.selectbox("Tipo", ["MP", "PT", "ENV"])
            cod = st.text_input("Código")
            lote = st.text_input("Lote")
            desc = st.text_area("Descripción")
            grav = st.selectbox("Gravedad", ["leve", "grave", "crítica"])
            acc = st.text_area("Acción correctiva")
            if st.form_submit_button("Registrar NC (bloquea lote)"):
                registrar_no_conformidad(tipo, cod, lote, desc, grav, acc)
                st.success("✔ NC registrada. Lote bloqueado.")
                st.rerun()

    with tab4:
        est = st.selectbox("Estado", ["(todas)", "abierta", "en_proceso", "cerrada"])
        filas = listar_no_conformidades(None if est == "(todas)" else est)
        df_nc = df(filas, ["ID", "Fecha", "Tipo", "Código", "Lote", "Descripción",
                             "Gravedad", "Estado"])
        st.dataframe(df_nc, use_container_width=True)
        nc_id = st.number_input("ID NC a cerrar", min_value=0, step=1)
        acc = st.text_input("Acción correctiva")
        if st.button("Cerrar NC"):
            if nc_id:
                cerrar_no_conformidad(int(nc_id), acc)
                st.success("✔ Cerrada.")
                st.rerun()

    with tab5:
        with st.form("form_lib"):
            tipo = st.selectbox("Tipo", ["MP", "PT"])
            cod = st.text_input("Código")
            lote = st.text_input("Lote")
            estado = st.selectbox("Estado", ["pendiente", "liberado", "bloqueado", "rechazado"])
            resp = st.text_input("Responsable")
            if st.form_submit_button("Cambiar estado"):
                cambiar_estado_lote(tipo, cod, lote, estado, resp)
                st.success("✔ Estado cambiado.")
                st.rerun()

        st.markdown("**Lotes bloqueados/rechazados:**")
        for est in ["bloqueado", "rechazado"]:
            for r in listar_lotes_por_estado(est):
                st.warning(f"{r[0]} {r[1]} lote {r[2]} → {est}")


# =========================================================
# 🏷️ ETIQUETADO
# =========================================================
elif seccion == "🏷️ Etiquetado":
    st.title("🏷️ Etiquetado automático")
    tab1, tab2 = st.tabs(["🖨️ Individual", "📄 Masivas"])

    with tab1:
        cod = st.text_input("Código producto")
        lote = st.text_input("Lote PT")
        formato = st.selectbox("Formato", ["pdf", "html", "txt"])
        if st.button("Generar"):
            if cod and lote:
                from informes import generar_etiqueta_termica
                ruta = f"etiqueta_{cod}_{lote}.pdf"
                r = generar_etiqueta_termica(cod, lote, 1, 50, 30, ruta)
                if r and os.path.exists(ruta):
                    with open(ruta, "rb") as f:
                        st.download_button("⬇ Descargar", f.read(),
                                            file_name=ruta, mime="application/pdf")

    with tab2:
        cod = st.text_input("Código producto", key="mas")
        lote = st.text_input("Lote PT", key="mas2")
        n = st.number_input("Nº etiquetas", min_value=1, value=10)
        if st.button("Generar etiquetas"):
            ruta = f"etiquetas_{cod}_{lote}_x{n}.pdf"
            r = generar_etiqueta_termica(cod, lote, int(n), 50, 30, ruta)
            if r and os.path.exists(ruta):
                with open(ruta, "rb") as f:
                    st.download_button("⬇ Descargar PDF", f.read(),
                                        file_name=ruta, mime="application/pdf")


# =========================================================
# 📄 INFORMES PDF
# =========================================================
elif seccion == "📄 Informes PDF":
    st.title("📄 Informe de producción en PDF")
    lote = st.text_input("Lote PT")
    if st.button("🧾 Generar informe PDF"):
        if not lote:
            st.error("Introduce un lote.")
        else:
            ruta = f"informe_produccion_{lote}.pdf"
            r = generar_informe_produccion(lote, ruta_salida=ruta)
            if r and os.path.exists(ruta):
                with open(ruta, "rb") as f:
                    st.download_button("⬇ Descargar PDF", f.read(),
                                        file_name=ruta, mime="application/pdf")
                with open(ruta, "rb") as f:
                    pdf_b64 = base64.b64encode(f.read()).decode()
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{pdf_b64}" '
                    f'width="100%" height="800px" style="border:1px solid #ccc;"></iframe>',
                    unsafe_allow_html=True,
                )


# =========================================================
# 🖨️ ETIQUETA TÉRMICA
# =========================================================
elif seccion == "🖨️ Etiqueta térmica":
    st.title("🖨️ Etiqueta térmica (50×30 mm)")
    col1, col2 = st.columns(2)
    cod = col1.text_input("Código producto")
    lote = col2.text_input("Lote PT")
    col3, col4, col5 = st.columns(3)
    ancho = col3.number_input("Ancho (mm)", 30, 100, 50)
    alto = col4.number_input("Alto (mm)", 20, 80, 30)
    n = col5.number_input("Nº etiquetas", 1, 500, 1)
    if st.button("🖨️ Generar PDF"):
        if cod and lote:
            ruta = f"etiqueta_termica_{cod}_{lote}.pdf"
            r = generar_etiqueta_termica(cod, lote, int(n), int(ancho), int(alto), ruta)
            if r and os.path.exists(ruta):
                with open(ruta, "rb") as f:
                    st.download_button("⬇ Descargar", f.read(),
                                        file_name=ruta, mime="application/pdf")


# =========================================================
# 📊 ANÁLISIS Y GRÁFICOS
# =========================================================
elif seccion == "📊 Análisis y gráficos":
    st.title("📊 Análisis y gráficos históricos")
    kpis = kpis_generales()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Producciones", kpis["total_producciones"])
    c2.metric("Unidades", f"{kpis['unidades_totales']:.0f}")
    c3.metric("Coste total", f"{kpis['coste_total']:.2f} €")
    c4.metric("NC abiertas", kpis["nc_abiertas"])

    st.markdown("### 📈 Producciones por mes y producto")
    df_mes = serie_producciones_por_mes()
    if not df_mes.empty:
        fig = px.bar(df_mes, x="mes", y="unidades", color="producto",
                     barmode="stack", color_discrete_sequence=px.colors.qualitative.Purple)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📉 Evolución del coste unitario")
    df_ev = evolucion_coste_por_producto()
    if not df_ev.empty:
        fig = px.line(df_ev, x="fecha", y="coste_unitario", color="producto",
                      markers=True, color_discrete_sequence=px.colors.qualitative.Purple)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🌿 Consumo de MP por mes")
    df_mp = consumo_mp_por_mes()
    if not df_mp.empty:
        fig = px.area(df_mp, x="mes", y="cantidad", color="mp",
                      color_discrete_sequence=px.colors.qualitative.Purple)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📉 Mermas por producto")
    df_merm = mermas_por_producto()
    if not df_merm.empty:
        fig = px.bar(df_merm, x="producto", y="coste", color="tipo", barmode="stack")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📋 Pedidos por estado")
    df_pe = pedidos_por_estado()
    if not df_pe.empty:
        fig = px.bar(df_pe, x="estado", y="cantidad", color="estado", text="cantidad")
        st.plotly_chart(fig, use_container_width=True)


# =========================================================
# 📧 ENVÍO DE INFORMES
# =========================================================
elif seccion == "📧 Envío de informes":
    st.title("📧 Envío de informes por email")
    from config import EMAIL_CONFIG
    if not EMAIL_CONFIG.get("activo"):
        st.warning("⚠ El envío está desactivado. Edita `config.py`.")
    lote = st.text_input("Lote PT")
    destinatarios_txt = st.text_input("Destinatarios (separados por coma)")
    if st.button("📧 Enviar"):
        if lote:
            ruta = f"informe_produccion_{lote}.pdf"
            if not os.path.exists(ruta):
                generar_informe_produccion(lote, ruta)
            destinatarios = [d.strip() for d in destinatarios_txt.split(",") if d.strip()] or None
            if enviar_informe_email(ruta, lote, "(producto)", destinatarios=destinatarios):
                st.success("✔ Enviado.")
            else:
                st.error("No se pudo enviar.")


# =========================================================
# 🔲 CÓDIGOS QR
# =========================================================
elif seccion == "🔲 Códigos QR":
    st.title("🔲 Generador de códigos QR")
    lote = st.text_input("Lote PT")
    if st.button("Generar QR"):
        if lote:
            url = url_informe(lote)
            ruta = f"qr_{lote}.png"
            generar_qr(url, ruta, con_logo=True)
            if os.path.exists(ruta):
                st.image(ruta, width=250)
                with open(ruta, "rb") as f:
                    st.download_button("⬇ Descargar", f.read(),
                                        file_name=ruta, mime="image/png")


# =========================================================
# ⚖️ PESOS REALES
# =========================================================
elif seccion == "⚖️ Pesos reales":
    st.title("⚖️ Registro de pesos reales")
    conn = conectar()
    pedidos = conn.execute("""SELECT numero FROM ordenes_produccion
                              WHERE estado IN ('en_preparacion','en_curso','finalizado')
                              ORDER BY fecha_creacion DESC LIMIT 50""").fetchall()
    conn.close()
    if not pedidos:
        st.info("No hay pedidos.")
    else:
        sel = st.selectbox("Pedido", [p[0] for p in pedidos])
        res = resumen_merma_pedido(sel)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Teórico", f"{res['teorica']:.2f}")
        c2.metric("Real", f"{res['real']:.2f}")
        c3.metric("Desv.", f"{res['desviacion']:+.2f}")
        c4.metric("%", f"{res['desviacion_pct']:+.2f}%")
        filas = pesos_de_pedido(sel)
        if filas:
            df_p = pd.DataFrame(filas, columns=["Tipo", "Artículo", "Lote", "Teórico",
                                                  "Real", "Ud", "Desv.", "%", "Operario",
                                                  "Fecha", "Notas"])
            st.dataframe(df_p, use_container_width=True)


# =========================================================
# 📉 MERMAS
# =========================================================
elif seccion == "📉 Mermas":
    st.title("📉 Mermas y subproductos")
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Merma", "➕ Subproducto", "📋 Listar", "📊 Estadísticas"])

    with tab1:
        with st.form("form_merma"):
            conn = conectar()
            pedidos = conn.execute("""SELECT numero FROM ordenes_produccion
                                       ORDER BY fecha_creacion DESC LIMIT 50""").fetchall()
            conn.close()
            opciones = [p[0] for p in pedidos] or ["(sin pedidos)"]
            pedido = st.selectbox("Pedido", opciones)
            producto = st.text_input("Producto")
            tipo = st.selectbox("Tipo", ["merma", "subproducto", "pérdida"])
            motivo = st.selectbox("Motivo", ["derrame", "evaporación", "filtrado", "envasado",
                                              "adherencia", "caducidad", "error de pesada",
                                              "rotura", "otro"])
            col1, col2 = st.columns(2)
            art = col1.text_input("Artículo")
            lote = col2.text_input("Lote")
            col3, col4 = st.columns(2)
            cant = col3.number_input("Cantidad", min_value=0.0, step=0.001, format="%.3f")
            uni = col4.selectbox("Unidad", ["kg", "g", "L", "mL", "ud"])
            coste = st.number_input("Coste estimado €", min_value=0.0, step=0.01)
            resp = st.text_input("Responsable")
            if st.form_submit_button("Registrar"):
                registrar_merma(pedido, producto, tipo, motivo, art, lote, cant, uni, coste, "", resp)
                st.success("✔ Registrada.")
                st.rerun()

    with tab2:
        with st.form("form_sub"):
            conn = conectar()
            pedidos = conn.execute("SELECT numero FROM ordenes_produccion ORDER BY fecha_creacion DESC LIMIT 50").fetchall()
            conn.close()
            opciones = [p[0] for p in pedidos] or ["(sin pedidos)"]
            pedido = st.selectbox("Pedido", opciones, key="sub_ped")
            codigo = st.text_input("Código subproducto")
            nombre = st.text_input("Nombre")
            lote = st.text_input("Lote")
            cant = st.number_input("Cantidad", min_value=0.0)
            uni = st.text_input("Unidad", value="kg")
            destino = st.selectbox("Destino", ["reutilización", "venta", "residuo", "donación"])
            coste = st.number_input("Coste/valor unitario €", min_value=0.0)
            if st.form_submit_button("Registrar subproducto"):
                registrar_subproducto(pedido, codigo, nombre, lote, cant, uni, destino, coste)
                st.success("✔ Registrado.")
                st.rerun()

    with tab3:
        pedido = st.text_input("Filtrar por pedido (vacío=todos)")
        tipo = st.selectbox("Filtrar por tipo", ["(todos)", "merma", "subproducto", "pérdida"])
        filas = listar_mermas(pedido or None, None if tipo == "(todos)" else tipo)
        df_m = pd.DataFrame(filas, columns=["ID", "Pedido", "Producto", "Tipo", "Motivo",
                                              "Artículo", "Lote", "Cantidad", "Ud", "Coste €",
                                              "Fecha", "Responsable"])
        st.dataframe(df_m, use_container_width=True)

    with tab4:
        producto = st.text_input("Código producto")
        if producto:
            resumen = resumen_mermas_producto(producto)
            if resumen:
                df_r = pd.DataFrame(resumen, columns=["Tipo", "Motivo", "Veces",
                                                        "Cantidad total", "Coste €"])
                st.dataframe(df_r, use_container_width=True)


# =========================================================
# 🖊️ FIRMAS DIGITALES
# =========================================================
elif seccion == "🖊️ Firmas digitales":
    st.title("🖊️ Firmas digitales")
    conn = conectar()
    pedidos = conn.execute("""SELECT numero FROM ordenes_produccion
                              ORDER BY fecha_creacion DESC LIMIT 50""").fetchall()
    conn.close()
    if not pedidos:
        st.info("No hay pedidos.")
    else:
        sel = st.selectbox("Pedido", [p[0] for p in pedidos])
        col1, col2 = st.columns(2)
        with col1:
            firma_widget(sel, "preparado", "Firma del operario")
        with col2:
            firma_widget(sel, "verificado", "Firma del verificador")


# =========================================================
# 📈 RENDIMIENTO
# =========================================================
elif seccion == "📈 Rendimiento":
    st.title("📈 Rendimiento real vs. teórico")
    tab1, tab2, tab3 = st.tabs(["📋 Por lote", "📊 Histórico", "📈 Estadísticas"])

    with tab1:
        lote = st.text_input("Lote PT")
        if lote:
            rend = rendimiento_de_lote(lote)
            if rend:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Producto", rend[0])
                c2.metric("Teórico", f"{rend[1]:.2f}")
                c3.metric("Real", f"{rend[2]:.2f}")
                c4.metric("Rendimiento", f"{rend[4]:.2f}%")
                if st.button("📄 Informe PDF"):
                    ruta = f"informe_rendimiento_{lote}.pdf"
                    r = generar_informe_rendimiento(lote, ruta)
                    if r and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            st.download_button("⬇ Descargar", f.read(),
                                                file_name=ruta, mime="application/pdf")

    with tab2:
        prod = st.text_input("Filtrar por producto")
        filas = historico_rendimiento(prod or None)
        if filas:
            df_h = pd.DataFrame(filas, columns=["Lote", "Producto", "Teórico", "Real",
                                                  "Ud", "Rendimiento %", "Fecha"])
            st.dataframe(df_h, use_container_width=True)

    with tab3:
        prod = st.text_input("Producto para estadísticas")
        if prod:
            stats = rendimiento_medio_producto(prod)
            if stats:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Media", f"{stats['media']:.2f}%")
                c2.metric("Mín", f"{stats['min']:.2f}%")
                c3.metric("Máx", f"{stats['max']:.2f}%")
                c4.metric("Nº lotes", stats["n"])


# =========================================================
# 🔄 REPROCESOS
# =========================================================
elif seccion == "🔄 Reprocesos":
    st.title("🔄 Reprocesos")
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Abrir", "📋 Listar", "✔️ Cerrar", "📊 Estadísticas"])

    with tab1:
        with st.form("form_rep"):
            lote = st.text_input("Lote origen")
            prod = st.text_input("Producto")
            cant = st.number_input("Cantidad origen", min_value=0.0)
            motivo = st.selectbox("Motivo", ["fuera de especificación", "olor/textura",
                                              "error de dosificación", "contaminación",
                                              "envase defectuoso", "caducidad próxima",
                                              "reclamación cliente", "otro"])
            desc = st.text_area("Descripción")
            resp = st.text_input("Responsable")
            if st.form_submit_button("Abrir reproceso"):
                numero = abrir_reproceso(lote, prod, cant, motivo, desc, resp)
                st.success(f"✔ Reproceso {numero} abierto.")
                st.rerun()

    with tab2:
        est = st.selectbox("Estado", ["(todos)", "abierto", "en_proceso", "cerrado", "descartado"])
        filas = listar_reprocesos(None if est == "(todos)" else est)
        df_r = df(filas, ["Número", "Lote origen", "Producto", "Cantidad", "Motivo",
                            "Estado", "Lote destino", "Apertura", "Cierre",
                            "Resultado", "Coste extra"])
        st.dataframe(df_r, use_container_width=True)

    with tab3:
        num = st.text_input("Número de reproceso")
        if num:
            rep = ver_reproceso(num)
            if rep:
                with st.form("form_cerrar"):
                    lote_dest = st.text_input("Lote destino")
                    resultado = st.selectbox("Resultado", ["conforme", "no_conforme", "descartado"])
                    coste = st.number_input("Coste extra €", min_value=0.0)
                    obs = st.text_area("Observaciones")
                    if st.form_submit_button("Cerrar"):
                        cerrar_reproceso(num, lote_dest, resultado, coste, obs)
                        st.success("✔ Cerrado.")
                        st.rerun()

    with tab4:
        filas = motivos_frecuentes()
        if filas:
            df_m = pd.DataFrame(filas, columns=["Motivo", "Veces", "Coste €"])
            st.dataframe(df_m, use_container_width=True)


# =========================================================
# 🛒 ÓRDENES DE COMPRA
# =========================================================
elif seccion == "🛒 Órdenes de compra":
    st.title("🛒 Órdenes de compra")
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Crear", "📋 Listar", "👁️ Ver", "💡 MRP"])

    with tab1:
        conn = conectar()
        proveedores = conn.execute("SELECT codigo,nombre FROM proveedores ORDER BY nombre").fetchall()
        conn.close()
        if not proveedores:
            st.warning("No hay proveedores.")
        else:
            opciones_prov = [f"{c} · {n}" for c, n in proveedores]
            prov_sel = st.selectbox("Proveedor", opciones_prov)
            prov_cod = prov_sel.split(" · ")[0]
            st.markdown("**Líneas**")
            if "lineas_oc_tmp" not in st.session_state:
                st.session_state.lineas_oc_tmp = []
            with st.form("form_linea_oc"):
                c1, c2, c3 = st.columns(3)
                tipo = c1.selectbox("Tipo", ["MP", "ENV"])
                cod = c2.text_input("Código")
                nombre = c3.text_input("Nombre")
                c4, c5, c6 = st.columns(3)
                cant = c4.number_input("Cantidad", min_value=0.0)
                uni = c5.selectbox("Unidad", ["kg", "g", "L", "mL", "ud"])
                precio = c6.number_input("€/ud", min_value=0.0, step=0.01)
                if st.form_submit_button("➕ Añadir línea"):
                    if cod and cant > 0:
                        st.session_state.lineas_oc_tmp.append({
                            "tipo_articulo": tipo, "articulo_codigo": cod,
                            "articulo_nombre": nombre, "cantidad": cant,
                            "unidad": uni, "precio_unitario": precio, "notas": "",
                        })
                        st.rerun()
            if st.session_state.lineas_oc_tmp:
                st.dataframe(pd.DataFrame(st.session_state.lineas_oc_tmp), use_container_width=True)
                if st.button("✅ Crear orden de compra"):
                    numero = crear_orden_compra(
                        prov_cod, st.session_state.lineas_oc_tmp,
                        None, "", "", user["usuario"],
                    )
                    st.session_state.lineas_oc_tmp = []
                    st.success(f"✔ OC {numero} creada.")
                    st.rerun()

    with tab2:
        est = st.selectbox("Filtrar estado", ["(todas)", "borrador", "enviada",
                                                "confirmada", "recibida_parcial",
                                                "recibida", "cancelada"])
        filas = listar_ordenes_compra(None if est == "(todas)" else est)
        df_oc = df(filas, ["Número", "Proveedor", "Estado", "Creada",
                             "Prevista", "Recibida", "Total €"])
        st.dataframe(df_oc, use_container_width=True)

    with tab3:
        numero = st.text_input("Nº OC")
        if numero:
            cab, lineas = ver_orden_compra(numero)
            if cab:
                st.markdown(f"### {cab[0]} · {cab[1]} · **{cab[2]}**")
                df_l = pd.DataFrame(lineas, columns=["ID", "Tipo", "Código", "Nombre",
                                                       "Pedida", "Recibida", "Ud", "€/ud",
                                                       "Subtotal", "Notas"])
                st.dataframe(df_l, use_container_width=True)
                st.metric("Total", f"{cab[8]:.2f} €")

    with tab4:
        st.markdown("### Sugerencias por proveedor")
        grupos = calcular_necesidad_compra_mrp()
        if not grupos:
            st.success("✔ Sin necesidades.")
        else:
            for proveedor, items in grupos.items():
                with st.expander(f"🚚 {proveedor}"):
                    st.dataframe(pd.DataFrame(items), use_container_width=True)


# =========================================================
# 📥 RECEPCIÓN (versión ampliada)
# =========================================================
elif seccion == "📥 Recepción de mercancía":
    from recepcion import (crear_recepcion_directa,
                           listar_recepciones_directas)
    st.title("📥 Recepción de mercancía")
    tab1, tab2 = st.tabs(["➕ Nueva entrada", "📋 Listado"])

    with tab1:
        with st.form("form_recepcion_directa"):
            c1, c2 = st.columns(2)
            fecha_entrada = c1.date_input("Fecha de entrada",
                                          value=date.today())
            producto = c2.text_input("Producto *")
            lote = c1.text_input("Lote *")
            proveedor = c2.text_input("Proveedor")
            uso = c1.selectbox("Uso", ["cosmetico", "alimentario", "ambos"])
            conforme = c2.selectbox("Conformidad",
                                    ["conforme", "no_conforme"])
            bio = c1.checkbox("Bio")
            caducidad_bio = c2.date_input("Caducidad certificado bio",
                                           value=None)
            responsable = c1.text_input("Responsable")
            observaciones = st.text_area("Observaciones")

            if st.form_submit_button("Guardar entrada"):
                if not producto or not lote:
                    st.error("Producto y lote son obligatorios.")
                else:
                    num = crear_recepcion_directa(
                        producto, lote, proveedor,
                        str(fecha_entrada), uso, conforme, bio,
                        str(caducidad_bio) if caducidad_bio else None,
                        responsable, observaciones,
                    )
                    st.success(f"✔ Entrada {num} registrada.")
                    st.rerun()

    with tab2:
        filas = listar_recepciones_directas()
        df_r = df(filas, ["Número", "Fecha", "Producto", "Proveedor",
                          "Uso", "Conformidad", "Bio", "Caduc. bio",
                          "Responsable", "Observaciones"])
        st.dataframe(df_r, use_container_width=True)
        descargar_df(df_r, "recepciones.csv")


# =========================================================
# 📤 SALIDAS
# =========================================================
elif seccion == "📤 Salidas":
    from recepcion import crear_salida, listar_salidas
    st.title("📤 Salidas de producto")
    tab1, tab2 = st.tabs(["➕ Nueva salida", "📋 Listado"])

    with tab1:
        conn = conectar()
        productos = conn.execute(
            "SELECT codigo, nombre FROM productos ORDER BY nombre"
        ).fetchall()
        conn.close()

        if productos:
            opciones = [f"{c} · {n}" for c, n in productos]
            sel = st.selectbox("Producto", opciones)
            prod_cod = sel.split(" · ")[0]
            prod_nom = sel.split(" · ")[1]
        else:
            st.info("No hay productos. Añádelos en Productos y fórmulas.")
            prod_cod = ""
            prod_nom = st.text_input("Producto")

        with st.form("form_salida"):
            c1, c2 = st.columns(2)
            uso = c1.selectbox("Uso", ["cosmetico", "alimentario", "ambos"])
            destino = c2.text_input("Destino *")
            lote = c1.text_input("Lote *")
            cantidad = c2.number_input("Cantidad", min_value=0.0, step=0.1)
            unidad = c1.selectbox("Unidad", ["ud", "kg", "g", "L", "mL"])
            responsable = c2.text_input("Responsable")
            comentarios = st.text_area(
                "Comentarios",
                placeholder="Ej: envío de aceite a Natural Solter "
                            "para producción de crema J",
            )
            if st.form_submit_button("Registrar salida"):
                if not prod_nom or not destino or not lote:
                    st.error("Producto, destino y lote son obligatorios.")
                else:
                    crear_salida(prod_nom, prod_cod, uso, destino, lote,
                                 cantidad, unidad, comentarios, responsable)
                    st.success("✔ Salida registrada.")
                    st.rerun()

    with tab2:
        filas = listar_salidas()
        df_s = df(filas, ["Fecha", "Producto", "Código", "Uso", "Destino",
                          "Lote", "Cantidad", "Unidad", "Comentarios",
                          "Responsable"])
        st.dataframe(df_s, use_container_width=True)
        descargar_df(df_s, "salidas.csv")

        # Gasto por lote
        st.markdown("### 🔎 Consumo por lote")
        if not df_s.empty:
            lotes = sorted(set(df_s["Lote"].dropna()))
            lote_sel = st.selectbox("Ver movimientos del lote", ["(todos)"] + lotes)
            if lote_sel != "(todos)":
                df_lote = df_s[df_s["Lote"] == lote_sel]
                st.dataframe(df_lote, use_container_width=True)
                total = df_lote["Cantidad"].sum()
                st.metric("Total salido de este lote", f"{total:.2f}")


# =========================================================
# 📖 MANUAL
# =========================================================
elif seccion == "📖 Manual de uso":
    st.title("📖 Manual de uso")
    st.markdown("""
    # 🧙‍♂️ OZOLABS' WIZARD

    ## Orden recomendado
    1. **🚚 Proveedores** → alta de proveedores.
    2. **🌿 Materias primas** → alta de lotes con caducidad y certificados.
    3. **🧴 Envases y etiquetas** → tarros, bombas, etiquetas.
    4. **📦 Productos y fórmulas** → BOM.
    5. **💰 Costes** → costes indirectos y tiempos.

    ## Producción
    - Directa: **⚙️ Producción**.
    - Planificada: **📋 Pedidos de producción** → Crear → Preparar → En curso → Finalizar.

    ## Trazabilidad
    - **🔬 Escandallos reales** por lote.
    - **📄 Informes PDF**.
    - **🖨️ Etiquetas térmicas** con QR.
    """)
    manual_md = "# Manual OZOLABS' WIZARD\n\nConsulta los módulos en el menú lateral."
    st.download_button("⬇ Descargar manual (MD)", manual_md.encode("utf-8"),
                        file_name="manual_ozolabs_wizard.md", mime="text/markdown")


# =========================================================
# 👥 USUARIOS (solo admin)
# =========================================================
elif seccion == "👥 Usuarios":
    if rol != "admin":
        st.error("Solo admins.")
        st.stop()
    st.title("👥 Usuarios")
    tab1, tab2, tab3 = st.tabs(["➕ Crear", "📋 Listar", "🔑 Contraseña"])
    with tab1:
        with st.form("form_user"):
            u = st.text_input("Usuario")
            n = st.text_input("Nombre")
            e = st.text_input("Email")
            p = st.text_input("Contraseña", type="password")
            r = st.selectbox("Rol", list(ROLES.keys()))
            if st.form_submit_button("Crear"):
                if crear_usuario(u, n, p, r, e):
                    st.success("✔ Creado.")
                    st.rerun()
    with tab2:
        filas = listar_usuarios()
        df_u = pd.DataFrame(filas, columns=["Usuario", "Nombre", "Email", "Rol",
                                              "Activo", "Creado", "Último acceso"])
        st.dataframe(df_u, use_container_width=True)
    with tab3:
        with st.form("form_pwd"):
            usuario_sel = st.selectbox("Usuario", [f[0] for f in filas])
            nueva = st.text_input("Nueva contraseña", type="password")
            if st.form_submit_button("Cambiar"):
                if usuario_sel and nueva:
                    cambiar_password(usuario_sel, nueva)
                    st.success("✔ Actualizada.")


# =========================================================
# 📜 AUDITORÍA (solo admin)
# =========================================================
elif seccion == "📜 Auditoría":
    if rol != "admin":
        st.error("Solo admins.")
        st.stop()
    st.title("📜 Auditoría")
    filas = ver_auditoria(500)
    df_a = pd.DataFrame(filas, columns=["Fecha", "Usuario", "Acción", "Detalle"])
    st.dataframe(df_a, use_container_width=True)


# =========================================================
# ℹ️ ACERCA DE
# =========================================================
elif seccion == "ℹ️ Acerca de":
    st.markdown(
        f"""
        <div style="text-align:center;">
            <img src="data:image/svg+xml;base64,{logo_base64()}" style="width:220px;"/>
            <h1 style="letter-spacing:3px;">OZOLABS' <span style="color:#7B68EE;">WIZARD</span></h1>
            <p style="opacity:0.7;">ERP / MRP artesanal · v1.0</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown("### 📦 Descargar logo")
    try:
        with open("assets/logo.svg", "rb") as f:
            st.download_button("⬇ logo.svg", f.read(),
                                file_name="ozolabs_wizard_logo.svg", mime="image/svg+xml")
    except Exception:
        pass
