"""
OZOLABS' WIZARD - Informes PDF y etiquetas térmicas
Usa reportlab para generar documentos con logo vectorial.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.graphics.shapes import Drawing, Circle, Polygon
from reportlab.pdfgen import canvas
from datetime import datetime
import os


# =========================================================
# LOGO VECTORIAL (dibujado con primitivas de reportlab)
# =========================================================
def _dibujar_logo(c, x, y, tam=25 * mm):
    """Dibuja el logo del mago con matraz usando primitivas vectoriales."""
    c.saveState()

    # Círculo de fondo morado
    c.setFillColor(colors.HexColor("#7B68EE"))
    c.circle(x + tam / 2, y - tam / 2, tam / 2, fill=1, stroke=0)

    # Sombrero (triángulo blanco)
    c.setFillColor(colors.white)
    p = c.beginPath()
    p.moveTo(x + tam * 0.20, y - tam * 0.40)
    p.lineTo(x + tam * 0.50, y - tam * 0.08)
    p.lineTo(x + tam * 0.80, y - tam * 0.40)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # Cara (círculo pequeño)
    c.setFillColor(colors.HexColor("#FFE0BD"))
    c.circle(x + tam * 0.50, y - tam * 0.50, tam * 0.06, fill=1, stroke=0)

    # Matraz (triángulo invertido)
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.white)
    c.setLineWidth(1)
    p = c.beginPath()
    p.moveTo(x + tam * 0.40, y - tam * 0.62)
    p.lineTo(x + tam * 0.40, y - tam * 0.72)
    p.lineTo(x + tam * 0.30, y - tam * 0.88)
    p.lineTo(x + tam * 0.70, y - tam * 0.88)
    p.lineTo(x + tam * 0.60, y - tam * 0.72)
    p.lineTo(x + tam * 0.60, y - tam * 0.62)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # Líquido verde
    c.setFillColor(colors.HexColor("#00E5B0"))
    p = c.beginPath()
    p.moveTo(x + tam * 0.34, y - tam * 0.82)
    p.lineTo(x + tam * 0.66, y - tam * 0.82)
    p.lineTo(x + tam * 0.70, y - tam * 0.88)
    p.lineTo(x + tam * 0.30, y - tam * 0.88)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    c.restoreState()


def _logo_drawing(tam=25 * mm):
    """Devuelve un Drawing con el logo (para usar dentro de tablas)."""
    d = Drawing(tam, tam)
    r = tam / 2

    d.add(Circle(r, r, r, fillColor=colors.HexColor("#7B68EE"), strokeColor=None))

    d.add(Polygon(
        points=[r * 0.40, r * 1.20, r, r * 1.85, r * 1.60, r * 1.20],
        fillColor=colors.white, strokeColor=None
    ))
    d.add(Circle(r, r * 0.95, r * 0.12,
                 fillColor=colors.HexColor("#FFE0BD"), strokeColor=None))

    d.add(Polygon(
        points=[r * 0.80, r * 0.75, r * 0.80, r * 0.55, r * 0.60, r * 0.25,
                r * 1.40, r * 0.25, r * 1.20, r * 0.55, r * 1.20, r * 0.75],
        fillColor=colors.white, strokeColor=None
    ))
    d.add(Polygon(
        points=[r * 0.68, r * 0.38, r * 1.32, r * 0.38, r * 1.40, r * 0.25,
                r * 0.60, r * 0.25],
        fillColor=colors.HexColor("#00E5B0"), strokeColor=None
    ))
    return d


# =========================================================
# INFORME DE PRODUCCIÓN
# =========================================================
def generar_informe_produccion(producto_lote, ruta_salida=None):
    """Genera un informe PDF completo de una producción con:
    - Cabecera con logo
    - Datos del producto y lote
    - Trazabilidad de MP consumidas
    - Trazabilidad de envases
    - Desglose de coste real
    """
    from database import conectar
    from qr_utils import generar_qr, url_informe

    if not ruta_salida:
        ruta_salida = f"informe_produccion_{producto_lote}.pdf"

    conn = conectar()
    fila = conn.execute("""
        SELECT p.codigo, p.nombre, p.formato,
               pr.lote, pr.cantidad, pr.fecha, pr.coste_total,
               sp.fecha_fabricacion, sp.fecha_caducidad
        FROM producciones pr
        JOIN productos p ON p.id = pr.producto_id
        LEFT JOIN stock_producto sp
               ON sp.producto_id = pr.producto_id AND sp.lote = pr.lote
        WHERE pr.lote = ?
        ORDER BY pr.id DESC LIMIT 1
    """, (producto_lote,)).fetchone()

    if not fila:
        conn.close()
        print(f"✘ No se encontró producción con lote {producto_lote}.")
        return None

    cod, nom, formato, lote, cantidad, fecha, coste_hist, f_fab, f_cad = fila

    escandallo = conn.execute("""
        SELECT articulo_tipo, articulo_codigo, articulo_lote,
               cantidad, unidad, precio_unitario, subtotal
        FROM escandallo_real
        WHERE producto_lote = ?
        ORDER BY articulo_tipo, articulo_codigo
    """, (producto_lote,)).fetchall()
    conn.close()

    # Construir documento
    doc = SimpleDocTemplate(
        ruta_salida, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"Informe producción {producto_lote}",
        author="OZOLABS' WIZARD",
    )

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "titulo", parent=styles["Title"],
        textColor=colors.HexColor("#4B0082"),
        fontSize=22, spaceAfter=4
    )
    estilo_sub = ParagraphStyle(
        "sub", parent=styles["Normal"],
        textColor=colors.HexColor("#7B68EE"),
        fontSize=11, alignment=2
    )
    estilo_h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"],
        textColor=colors.HexColor("#4B0082"),
        fontSize=13, spaceBefore=12, spaceAfter=6
    )
    estilo_normal = styles["Normal"]

    story = []

    # QR de trazabilidad
    url = url_informe(producto_lote)
    qr_temp = f"_tmp_qr_{producto_lote}.png"
    try:
        generar_qr(url, qr_temp, con_logo=True)
        qr_img = Image(qr_temp, width=25 * mm, height=25 * mm)
    except Exception:
        qr_img = Paragraph("", estilo_normal)

    # Cabecera con logo + QR
    logo = _logo_drawing(22 * mm)
    cabecera_tabla = Table(
        [[logo,
          Paragraph("<b>OZOLABS' WIZARD</b><br/>Informe de producción", estilo_sub),
          qr_img]],
        colWidths=[30 * mm, 120 * mm, 30 * mm],
    )
    cabecera_tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#7B68EE")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    story.append(cabecera_tabla)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Informe de producción", estilo_titulo))
    story.append(Paragraph(f"Lote: <b>{lote}</b>", estilo_normal))
    story.append(Spacer(1, 6 * mm))

    # Datos generales
    story.append(Paragraph("1. Datos del producto", estilo_h2))
    datos = [
        ["Código", cod],
        ["Producto", nom],
        ["Formato/presentación", formato or "—"],
        ["Cantidad fabricada", f"{cantidad:.0f} uds"],
        ["Fecha de fabricación", (f_fab or fecha[:10]) if fecha else "—"],
        ["Fecha de caducidad", f_cad or "—"],
    ]
    t = Table(datos, colWidths=[60 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F0FF")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#4B0082")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    # Materias primas
    story.append(Paragraph("2. Materias primas consumidas (trazabilidad)", estilo_h2))
    mp = [e for e in escandallo if e[0] == "MP"]
    env = [e for e in escandallo if e[0] == "ENV"]

    if mp:
        tabla_mp = [["Código", "Lote MP", "Cantidad", "Ud", "€/ud", "Subtotal €"]]
        for _, cod_mp, lote_mp, cant, uni, precio, sub in mp:
            tabla_mp.append([
                cod_mp, lote_mp or "—",
                f"{cant:.4f}", uni or "",
                f"{precio:.4f}", f"{sub:.2f}",
            ])
        t = Table(tabla_mp, colWidths=[35 * mm, 35 * mm, 22 * mm, 14 * mm, 28 * mm, 36 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7B68EE")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F8F7FF")]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("<i>Sin materias primas registradas.</i>", estilo_normal))

    # Envases
    story.append(Paragraph("3. Envases y etiquetas consumidos", estilo_h2))
    if env:
        tabla_env = [["Código", "Lote", "Cantidad", "€/ud", "Subtotal €"]]
        for _, cod_env, lote_env, cant, uni, precio, sub in env:
            tabla_env.append([
                cod_env, lote_env or "—",
                f"{cant:.0f}", f"{precio:.4f}", f"{sub:.2f}",
            ])
        t = Table(tabla_env, colWidths=[40 * mm, 35 * mm, 25 * mm, 30 * mm, 40 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00B894")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F0FFF8")]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("<i>Sin envases registrados.</i>", estilo_normal))

    # Resumen de costes
    story.append(Paragraph("4. Resumen de costes", estilo_h2))
    total_mp = sum(e[6] for e in mp)
    total_env = sum(e[6] for e in env)
    total = total_mp + total_env

    resumen = [
        ["Materias primas", f"{total_mp:.2f} €"],
        ["Envases y etiquetas", f"{total_env:.2f} €"],
        ["COSTE TOTAL REAL", f"{total:.2f} €"],
        ["Coste unitario", f"{total / cantidad:.4f} €/ud" if cantidad else "—"],
    ]
    t = Table(resumen, colWidths=[100 * mm, 70 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 1), colors.HexColor("#F3F0FF")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#4B0082")),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#EDE7FF")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # Pie
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"<font size=8 color='#888888'>Documento generado automáticamente por "
        f"<b>OZOLABS' WIZARD</b> el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}. "
        f"Este informe es válido como registro de trazabilidad interna.</font>",
        estilo_normal,
    ))

    doc.build(story)

    if os.path.exists(qr_temp):
        try:
            os.remove(qr_temp)
        except Exception:
            pass

    print(f"✔ Informe PDF generado: {ruta_salida}")
    return ruta_salida


# =========================================================
# ETIQUETA TÉRMICA 50x30 mm
# =========================================================
def generar_etiqueta_termica(producto_codigo, lote, cantidad_uds=1,
                              ancho_mm=50, alto_mm=30, ruta_salida=None):
    """Genera un PDF con etiquetas de tamaño real para impresora térmica."""
    from database import conectar

    if not ruta_salida:
        ruta_salida = f"etiqueta_{producto_codigo}_{lote}.pdf"

    conn = conectar()
    fila = conn.execute("""
        SELECT p.nombre, p.formato, sp.fecha_fabricacion, sp.fecha_caducidad
        FROM productos p
        LEFT JOIN stock_producto sp
               ON sp.producto_id = p.id AND sp.lote = ?
        WHERE p.codigo = ?
    """, (lote, producto_codigo)).fetchone()
    conn.close()

    if not fila:
        print("✘ Producto o lote no encontrado.")
        return None

    nombre, formato, f_fab, f_cad = fila

    ancho = ancho_mm * mm
    alto = alto_mm * mm
    c = canvas.Canvas(ruta_salida, pagesize=(ancho, alto))

    for _ in range(int(cantidad_uds)):
        _dibujar_etiqueta_termica(c, ancho, alto, nombre, formato, lote,
                                   f_fab, f_cad)
        c.showPage()

    c.save()
    print(f"✔ Etiquetas térmicas generadas: {ruta_salida}")
    return ruta_salida


def _dibujar_etiqueta_termica(c, ancho, alto, nombre, formato, lote,
                               f_fab, f_cad):
    """Dibuja una etiqueta térmica en el canvas actual."""
    margin = 2 * mm

    # Marco
    c.setStrokeColor(colors.HexColor("#7B68EE"))
    c.setLineWidth(0.6)
    c.rect(1 * mm, 1 * mm, ancho - 2 * mm, alto - 2 * mm)

    # Logo
    _dibujar_logo(c, ancho - 9 * mm, alto - 2 * mm, tam=7 * mm)

    # Nombre
    c.setFillColor(colors.HexColor("#4B0082"))
    c.setFont("Helvetica-Bold", 8)
    nombre_corto = nombre[:22] + ("…" if len(nombre) > 22 else "")
    c.drawString(margin, alto - 4 * mm, nombre_corto)

    # Formato
    c.setFillColor(colors.HexColor("#333333"))
    c.setFont("Helvetica", 6.5)
    c.drawString(margin, alto - 7 * mm, f"Formato: {formato or '—'}")

    # Línea separadora
    c.setStrokeColor(colors.HexColor("#CCCCDD"))
    c.line(margin, alto - 8.5 * mm, ancho - margin, alto - 8.5 * mm)

    # Lote
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(margin, alto - 11.5 * mm, f"Lote: {lote}")

    # Fechas
    c.setFont("Helvetica", 6)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawString(margin, alto - 14.5 * mm, f"Fab: {f_fab or '—'}")
    c.drawString(margin, alto - 17.5 * mm, f"Cad: {f_cad or '—'}")

    # Marca
    c.setFont("Helvetica-Bold", 5)
    c.setFillColor(colors.HexColor("#7B68EE"))
    c.drawString(margin, 1.8 * mm, "OZOLABS' WIZARD")


# =========================================================
# HOJA DE PESADA
# =========================================================
def generar_hoja_pesada(numero_pedido, ruta_salida=None):
    """Genera un PDF con la hoja de pesada para que el operario la rellene."""
    from database import conectar
    from qr_utils import generar_qr, url_informe

    if not ruta_salida:
        ruta_salida = f"hoja_pesada_{numero_pedido}.pdf"

    conn = conectar()
    pedido = conn.execute("""
        SELECT o.numero, o.cantidad_planificada, o.estado,
               o.fecha_creacion, o.fecha_prevista, o.observaciones,
               p.codigo, p.nombre, p.formato
        FROM ordenes_produccion o
        JOIN productos p ON p.id = o.producto_id
        WHERE o.numero = ?
    """, (numero_pedido,)).fetchone()

    if not pedido:
        conn.close()
        print(f"✘ Pedido {numero_pedido} no encontrado.")
        return None

    (num, cantidad, estado, f_creac, f_prev, obs,
     prod_cod, prod_nom, formato) = pedido

    # Fórmula MP
    formula_mp = conn.execute("""
        SELECT f.materia_codigo, mp.nombre, f.cantidad_por_unidad, f.unidad
        FROM formulas f
        JOIN productos p ON p.id = f.producto_id
        LEFT JOIN materias_primas mp ON mp.codigo = f.materia_codigo
        WHERE p.codigo = ?
        GROUP BY f.materia_codigo
    """, (prod_cod,)).fetchall()

    # Lotes FEFO asignados
    mp_con_lote = []
    for mat_cod, mat_nom, cant_u, uni in formula_mp:
        cant_total = cant_u * cantidad
        lotes = conn.execute("""
            SELECT lote, cantidad, unidad, fecha_caducidad
            FROM materias_primas
            WHERE codigo = ? AND cantidad > 0
            ORDER BY fecha_caducidad IS NULL, fecha_caducidad
        """, (mat_cod,)).fetchall()

        restante = cant_total
        asignaciones = []
        for lote, disp, uni_lote, fcad in lotes:
            if restante <= 0:
                break
            usar = min(disp, restante)
            asignaciones.append({
                "lote": lote, "cantidad": usar,
                "unidad": uni_lote, "caducidad": fcad,
            })
            restante -= usar
        mp_con_lote.append({
            "codigo": mat_cod,
            "nombre": mat_nom or mat_cod,
            "necesaria": cant_total,
            "unidad": uni,
            "asignaciones": asignaciones,
            "faltante": max(0, restante),
        })

    # Fórmula envases
    formula_env = conn.execute("""
        SELECT fe.envase_codigo, e.nombre, fe.cantidad_por_unidad
        FROM formula_envases fe
        JOIN productos p ON p.id = fe.producto_id
        LEFT JOIN envases e ON e.codigo = fe.envase_codigo
        WHERE p.codigo = ?
        GROUP BY fe.envase_codigo
    """, (prod_cod,)).fetchall()

    env_con_lote = []
    for env_cod, env_nom, cant_u in formula_env:
        cant_total = cant_u * cantidad
        lotes = conn.execute("""
            SELECT lote, cantidad FROM envases
            WHERE codigo = ? AND cantidad > 0
            ORDER BY fecha_recepcion
        """, (env_cod,)).fetchall()
        restante = cant_total
        asignaciones = []
        for lote, disp in lotes:
            if restante <= 0:
                break
            usar = min(disp, restante)
            asignaciones.append({"lote": lote, "cantidad": usar})
            restante -= usar
        env_con_lote.append({
            "codigo": env_cod,
            "nombre": env_nom or env_cod,
            "necesaria": cant_total,
            "asignaciones": asignaciones,
            "faltante": max(0, restante),
        })

    conn.close()

    # QR
    qr_temp = f"_tmp_qr_pedido_{numero_pedido}.png"
    try:
        url = url_informe(numero_pedido)
        generar_qr(url, qr_temp, con_logo=True)
    except Exception:
        qr_temp = None

    # Documento
    doc = SimpleDocTemplate(
        ruta_salida, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"Hoja de pesada {numero_pedido}",
        author="OZOLABS' WIZARD",
    )

    styles = getSampleStyleSheet()
    estilo_h1 = ParagraphStyle(
        "h1", parent=styles["Title"],
        textColor=colors.HexColor("#4B0082"),
        fontSize=18, spaceAfter=4
    )
    estilo_h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"],
        textColor=colors.HexColor("#4B0082"),
        fontSize=12, spaceBefore=10, spaceAfter=6
    )
    estilo_small = ParagraphStyle("s", parent=styles["Normal"], fontSize=9)
    estilo_sub = ParagraphStyle(
        "sub", parent=styles["Normal"],
        fontSize=10, alignment=2,
        textColor=colors.HexColor("#7B68EE")
    )

    story = []

    # Cabecera
    logo = _logo_drawing(22 * mm)
    qr_img = None
    if qr_temp and os.path.exists(qr_temp):
        try:
            qr_img = Image(qr_temp, width=22 * mm, height=22 * mm)
        except Exception:
            qr_img = None

    cabecera_datos = [[
        logo,
        Paragraph("<b>OZOLABS' WIZARD</b><br/>Hoja de pesada · Producción", estilo_sub),
        qr_img or Paragraph("", estilo_sub),
    ]]
    t = Table(cabecera_datos, colWidths=[30 * mm, 120 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#7B68EE")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(f"Hoja de pesada · Pedido {num}", estilo_h1))
    story.append(Paragraph(
        f"Estado: <b>{estado}</b> · "
        f"Creado: {f_creac[:16].replace('T', ' ') if f_creac else '—'} · "
        f"Previsto: {f_prev or '—'}",
        estilo_small,
    ))
    story.append(Spacer(1, 4 * mm))

    # Producto
    story.append(Paragraph("Producto a fabricar", estilo_h2))
    datos_prod = [
        ["Código producto", prod_cod],
        ["Nombre", prod_nom],
        ["Formato", formato or "—"],
        ["Cantidad a fabricar", f"{cantidad:.0f} uds"],
        ["Lote PT previsto", num],
    ]
    t = Table(datos_prod, colWidths=[50 * mm, 130 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F0FF")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#4B0082")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)

    # Materias primas
    story.append(Paragraph("🧪 Materias primas a pesar (FEFO)", estilo_h2))
    story.append(Paragraph(
        "<i>Usa los lotes indicados en el orden mostrado. "
        "Anota el peso real y marca OK si coincide (±2%).</i>",
        estilo_small,
    ))
    story.append(Spacer(1, 2 * mm))

    tabla_mp = [["MP", "Nombre", "Lote FEFO", "Caducidad",
                 "Cantidad teórica", "Peso real", "OK"]]
    for mp in mp_con_lote:
        if not mp["asignaciones"]:
            tabla_mp.append([
                mp["codigo"], mp["nombre"], "⚠ FALTA STOCK", "",
                f"{mp['necesaria']:.3f} {mp['unidad']}", "", "",
            ])
        else:
            for a in mp["asignaciones"]:
                tabla_mp.append([
                    mp["codigo"], mp["nombre"], a["lote"],
                    (a["caducidad"] or "—")[:10],
                    f"{a['cantidad']:.3f} {a['unidad']}",
                    "________", "☐",
                ])

    t = Table(
        tabla_mp,
        colWidths=[22 * mm, 34 * mm, 24 * mm, 22 * mm, 28 * mm, 22 * mm, 8 * mm],
        repeatRows=1,
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7B68EE")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),
        ("ALIGN", (5, 1), (6, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F8F7FF")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    # Envases
    if env_con_lote:
        story.append(Paragraph("🧴 Envases y etiquetas", estilo_h2))
        tabla_env = [["Envase", "Nombre", "Lote", "Cantidad teórica", "Real", "OK"]]
        for env in env_con_lote:
            if not env["asignaciones"]:
                tabla_env.append([
                    env["codigo"], env["nombre"], "⚠ FALTA STOCK",
                    f"{env['necesaria']:.0f}", "", "",
                ])
            else:
                for a in env["asignaciones"]:
                    tabla_env.append([
                        env["codigo"], env["nombre"], a["lote"],
                        f"{a['cantidad']:.0f}", "______", "☐",
                    ])
        t = Table(
            tabla_env,
            colWidths=[28 * mm, 46 * mm, 30 * mm, 30 * mm, 22 * mm, 8 * mm],
            repeatRows=1,
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00B894")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("ALIGN", (4, 1), (5, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F0FFF8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    # Sección de mermas / incidencias
    story.append(Paragraph("Mermas / incidencias detectadas", estilo_h2))
    mermas_tabla = [[
        "Motivo (derrame, evaporación, filtrado…)", "Artículo",
        "Cantidad", "Acción correctiva", "OK",
    ], [
        "", "", "", "", "",
    ], [
        "", "", "", "", "",
    ]]
    t = Table(
        mermas_tabla,
        colWidths=[70 * mm, 40 * mm, 22 * mm, 40 * mm, 8 * mm],
        rowHeights=[6 * mm, 8 * mm, 8 * mm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFB6C1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    # Observaciones
    story.append(Paragraph("Observaciones", estilo_h2))
    obs_tabla = [[Paragraph(
        f"<br/><br/>{obs or ''}<br/><br/><br/><br/>",
        estilo_small,
    )]]
    t = Table(obs_tabla, colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCDD")),
    ]))
    story.append(t)
    story.append(Spacer(1, 8 * mm))

    # Firmas (con imagen digital si existe)
    story.append(Paragraph("Firmas", estilo_h2))

    firma_prep_path = f"_tmp_firma_prep_{numero_pedido}.png"
    firma_ver_path = f"_tmp_firma_ver_{numero_pedido}.png"

    try:
        from firmas import exportar_firma_png, obtener_firma
        firma_prep_path = exportar_firma_png(numero_pedido, "preparado", firma_prep_path)
        firma_ver_path = exportar_firma_png(numero_pedido, "verificado", firma_ver_path)
    except Exception:
        firma_prep_path = None
        firma_ver_path = None

    def _celda_firma(tipo, ruta):
        if ruta and os.path.exists(ruta):
            try:
                img = Image(ruta, width=40 * mm, height=14 * mm)
                try:
                    from firmas import obtener_firma
                    firma = obtener_firma(numero_pedido, tipo)
                    nombre = firma[0] if firma else ""
                    fecha = firma[2][:16] if firma else ""
                    pie = Paragraph(
                        f"<font size=8>{nombre}<br/>{fecha}</font>",
                        estilo_small,
                    )
                except Exception:
                    pie = Paragraph("", estilo_small)
                return [img, pie]
            except Exception:
                pass
        return [
            Paragraph(
                "<br/><br/><br/>________________________<br/>"
                "<font size=8>Nombre y firma</font>",
                estilo_small,
            ),
            Paragraph("", estilo_small),
        ]

    firma_prep = _celda_firma("preparado", firma_prep_path)
    firma_ver = _celda_firma("verificado", firma_ver_path)

    firmas_tabla = [[
        Paragraph("<b>Preparado por:</b>", estilo_small),
        Paragraph("<b>Verificado por:</b>", estilo_small),
        Paragraph("<b>Fecha:</b>", estilo_small),
    ], [
        firma_prep[0],
        firma_ver[0],
        Paragraph(
            f"<br/><br/><br/>"
            f"<font size=9>{datetime.now().strftime('%d/%m/%Y')}</font>",
            estilo_small,
        ),
    ]]
    t = Table(firmas_tabla, colWidths=[60 * mm, 60 * mm, 60 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCDD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#EEEEEE")),
    ]))
    story.append(t)

    # Pie
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"<font size=7 color='#888888'>Documento generado por OZOLABS' WIZARD · "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')} · "
        f"Pedido {num}</font>",
        estilo_small,
    ))

    doc.build(story)

    # Limpiar temporales
    for ruta_tmp in [qr_temp, firma_prep_path, firma_ver_path]:
        if ruta_tmp and os.path.exists(ruta_tmp):
            try:
                os.remove(ruta_tmp)
            except Exception:
                pass

    print(f"✔ Hoja de pesada generada: {ruta_salida}")
    return ruta_salida


# =========================================================
# INFORME DE RENDIMIENTO POR LOTE
# =========================================================
def generar_informe_rendimiento(producto_lote, ruta_salida=None):
    """Informe PDF: comparativa teórico vs. real, mermas y reprocesos."""
    from database import conectar
    from rendimiento import rendimiento_de_lote, rendimiento_medio_producto
    from mermas import pesos_de_pedido, resumen_merma_pedido
    from reprocesos import reprocesos_de_lote

    if not ruta_salida:
        ruta_salida = f"informe_rendimiento_{producto_lote}.pdf"

    rend = rendimiento_de_lote(producto_lote)
    if not rend:
        print(f"✘ No hay rendimiento para {producto_lote}.")
        return None

    (prod_cod, cant_teor, cant_real, unidad, rend_pct,
     peso_final, peso_obj, fecha, obs) = rend

    rend_medio = rendimiento_medio_producto(prod_cod)
    pesos = pesos_de_pedido(producto_lote)
    resumen = resumen_merma_pedido(producto_lote)
    repros = reprocesos_de_lote(producto_lote)

    doc = SimpleDocTemplate(
        ruta_salida, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Rendimiento {producto_lote}",
        author="OZOLABS' WIZARD",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1", parent=styles["Title"],
        textColor=colors.HexColor("#4B0082"),
        fontSize=18, spaceAfter=6,
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"],
        textColor=colors.HexColor("#4B0082"),
        fontSize=12, spaceBefore=10, spaceAfter=6,
    )
    sm = ParagraphStyle("sm", parent=styles["Normal"], fontSize=9)

    story = []

    # Cabecera
    logo = _logo_drawing(20 * mm)
    t = Table(
        [[logo, Paragraph(
            "<b>OZOLABS' WIZARD</b><br/>Informe de rendimiento", sm)]],
        colWidths=[30 * mm, 150 * mm],
    )
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#7B68EE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(f"Rendimiento lote {producto_lote}", h1))

    # KPIs
    story.append(Paragraph("Resumen", h2))
    kpi = [
        ["Producto", prod_cod],
        ["Fecha", fecha[:16].replace("T", " ") if fecha else "—"],
        ["Cantidad teórica", f"{cant_teor:.2f} {unidad}"],
        ["Cantidad real", f"{cant_real:.2f} {unidad}"],
        ["Rendimiento", f"{rend_pct:.2f}%"],
        ["Rendimiento medio producto",
         f"{rend_medio['media']:.2f}% (n={rend_medio['n']})"
         if rend_medio else "—"],
        ["Peso final / objetivo",
         f"{peso_final:.3f} / {peso_obj:.3f}" if peso_obj else "—"],
    ]
    t = Table(kpi, colWidths=[70 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F0FF")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t)

    # Desviación de pesos
    if pesos:
        story.append(Paragraph("Desviación de pesos reales", h2))
        data = [["Artículo", "Lote", "Teórica", "Real", "Desv.", "%"]]
        for (_, art, lote, teo, real, ud, desv, pct, _, _, _) in pesos:
            data.append([
                art, lote or "—", f"{teo:.3f}", f"{real:.3f}",
                f"{desv:+.3f}", f"{pct:+.2f}%",
            ])
        t = Table(
            data,
            colWidths=[30 * mm, 30 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm],
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7B68EE")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCDD")),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ]))
        story.append(t)

        # Resumen de merma
        story.append(Paragraph("Resumen de merma", h2))
        res = [
            ["Peso teórico total", f"{resumen['teorica']:.3f}"],
            ["Peso real total", f"{resumen['real']:.3f}"],
            ["Desviación", f"{resumen['desviacion']:+.3f} "
                            f"({resumen['desviacion_pct']:+.2f}%)"],
        ]
        t = Table(res, colWidths=[70 * mm, 110 * mm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCDD")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(t)

    # Reprocesos
    if repros:
        story.append(Paragraph("Reprocesos asociados", h2))
        data = [["Nº", "Motivo", "Estado", "Lote destino", "Resultado"]]
        for (num, motivo, estado, ld, fa, fc, res) in repros:
            data.append([num, motivo, estado, ld or "—", res or "—"])
        t = Table(
            data,
            colWidths=[30 * mm, 40 * mm, 25 * mm, 40 * mm, 35 * mm],
        )
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E67E22")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCDD")),
        ]))
        story.append(t)

    # Observaciones
    if obs:
        story.append(Paragraph("Observaciones", h2))
        story.append(Paragraph(obs, sm))

    # Pie
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"<font size=7 color='#888888'>Generado por OZOLABS' WIZARD · "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}</font>",
        sm,
    ))

    doc.build(story)
    print(f"✔ Informe de rendimiento generado: {ruta_salida}")
    return ruta_salida
