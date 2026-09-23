"""
OZOLABS' WIZARD - Capa de base de datos
"""
import sqlite3
import os
from datetime import datetime
from shutil import copyfile

DB_PATH = "erp.db"


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def crear_tablas():
    conn = conectar()
    c = conn.cursor()

    # ---------- FASE 1 ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS materias_primas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT NOT NULL,
        nombre TEXT NOT NULL,
        proveedor TEXT,
        lote TEXT NOT NULL,
        cantidad REAL NOT NULL,
        unidad TEXT NOT NULL,
        fecha_recepcion TEXT,
        fecha_caducidad TEXT,
        certificado_eco TEXT,
        caducidad_certificado TEXT,
        coste_unitario REAL DEFAULT 0,
        ubicacion TEXT,
        stock_minimo REAL DEFAULT 0,
        UNIQUE(codigo, lote)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        formato TEXT,
        stock_minimo REAL DEFAULT 0
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS formulas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        materia_codigo TEXT NOT NULL,
        cantidad_por_unidad REAL NOT NULL,
        unidad TEXT NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS stock_producto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        lote TEXT NOT NULL,
        fecha_fabricacion TEXT,
        fecha_caducidad TEXT,
        cantidad REAL NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS trazabilidad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_lote TEXT NOT NULL,
        producto_id INTEGER,
        materia_codigo TEXT,
        materia_lote TEXT,
        cantidad_usada REAL,
        fecha TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS producciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER,
        lote TEXT NOT NULL,
        cantidad REAL NOT NULL,
        fecha TEXT,
        coste_total REAL DEFAULT 0,
        orden_id INTEGER
    )""")

    # ---------- FASE 2 ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        contacto TEXT,
        email TEXT,
        telefono TEXT,
        condiciones_pago TEXT,
        notas TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS envases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT NOT NULL,
        nombre TEXT NOT NULL,
        tipo TEXT,
        lote TEXT,
        cantidad REAL NOT NULL,
        unidad TEXT NOT NULL,
        coste_unitario REAL DEFAULT 0,
        proveedor TEXT,
        ubicacion TEXT,
        stock_minimo REAL DEFAULT 0,
        fecha_recepcion TEXT,
        UNIQUE(codigo, lote)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS formula_envases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        envase_codigo TEXT NOT NULL,
        cantidad_por_unidad REAL NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS costes_indirectos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concepto TEXT NOT NULL,
        coste_por_hora REAL DEFAULT 0,
        coste_por_unidad REAL DEFAULT 0,
        activo INTEGER DEFAULT 1
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS tiempos_producto (
        producto_id INTEGER PRIMARY KEY,
        minutos_por_lote REAL DEFAULT 0,
        horas_mano_obra REAL DEFAULT 0,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        producto_id INTEGER NOT NULL,
        cantidad_planificada REAL NOT NULL,
        cantidad_fabricada REAL DEFAULT 0,
        estado TEXT DEFAULT 'planificado',
        fecha_creacion TEXT,
        fecha_prevista TEXT,
        fecha_finalizacion TEXT,
        fecha_inicio TEXT,
        observaciones TEXT,
        prioridad TEXT DEFAULT 'normal',
        historial TEXT,
        FOREIGN KEY(producto_id) REFERENCES productos(id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS movimientos_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        tipo_articulo TEXT NOT NULL,
        articulo_codigo TEXT NOT NULL,
        lote TEXT,
        tipo_movimiento TEXT NOT NULL,
        cantidad REAL NOT NULL,
        unidad TEXT,
        referencia TEXT,
        notas TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS precios_proveedor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_codigo TEXT,
        articulo_codigo TEXT,
        tipo_articulo TEXT,
        precio_unitario REAL,
        fecha TEXT,
        lote TEXT
    )""")

    # ---------- FASE 3 ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS escandallo_real (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produccion_id INTEGER,
        producto_lote TEXT,
        articulo_tipo TEXT,
        articulo_codigo TEXT,
        articulo_lote TEXT,
        cantidad REAL,
        unidad TEXT,
        precio_unitario REAL,
        subtotal REAL,
        FOREIGN KEY(produccion_id) REFERENCES producciones(id) ON DELETE CASCADE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS controles_calidad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_articulo TEXT NOT NULL,
        articulo_codigo TEXT NOT NULL,
        lote TEXT NOT NULL,
        fecha TEXT NOT NULL,
        responsable TEXT,
        parametro TEXT,
        valor_obtenido TEXT,
        valor_esperado TEXT,
        resultado TEXT,
        observaciones TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS no_conformidades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        tipo_articulo TEXT,
        articulo_codigo TEXT,
        lote TEXT,
        descripcion TEXT NOT NULL,
        gravedad TEXT,
        accion_correctiva TEXT,
        estado TEXT DEFAULT 'abierta',
        fecha_cierre TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS liberacion_lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_articulo TEXT NOT NULL,
        articulo_codigo TEXT NOT NULL,
        lote TEXT NOT NULL,
        estado TEXT DEFAULT 'pendiente',
        fecha TEXT,
        responsable TEXT,
        UNIQUE(tipo_articulo, articulo_codigo, lote)
    )""")

    # ---------- FASE 8: RESERVAS ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS reservas_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_numero TEXT NOT NULL,
        tipo_articulo TEXT NOT NULL,
        articulo_codigo TEXT NOT NULL,
        cantidad_reservada REAL NOT NULL,
        unidad TEXT,
        fecha TEXT,
        estado TEXT DEFAULT 'activa'
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_reservas_pedido ON reservas_stock(pedido_numero)")

    # ---------- FASE 10 ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS pesos_reales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_numero TEXT NOT NULL,
        tipo_articulo TEXT NOT NULL,
        articulo_codigo TEXT NOT NULL,
        articulo_lote TEXT,
        cantidad_teorica REAL,
        cantidad_real REAL,
        unidad TEXT,
        desviacion REAL,
        desviacion_pct REAL,
        operario TEXT,
        fecha TEXT,
        notas TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS mermas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_numero TEXT NOT NULL,
        producto_codigo TEXT,
        tipo TEXT,
        motivo TEXT,
        articulo_codigo TEXT,
        articulo_lote TEXT,
        cantidad REAL,
        unidad TEXT,
        coste_estimado REAL,
        accion_correctiva TEXT,
        fecha TEXT,
        responsable TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS firmas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_numero TEXT NOT NULL,
        tipo TEXT,
        nombre TEXT,
        imagen_base64 TEXT,
        fecha TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS subproductos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_numero TEXT,
        codigo TEXT NOT NULL,
        nombre TEXT,
        lote TEXT,
        cantidad REAL,
        unidad TEXT,
        destino TEXT,
        coste_unitario REAL DEFAULT 0,
        fecha TEXT
    )""")

    c.execute("CREATE INDEX IF NOT EXISTS idx_pesos_pedido ON pesos_reales(pedido_numero)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_mermas_pedido ON mermas(pedido_numero)")

    # ---------- FASE 11: COMPRAS ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_compra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        proveedor_codigo TEXT NOT NULL,
        estado TEXT DEFAULT 'borrador',
        fecha_creacion TEXT,
        fecha_envio TEXT,
        fecha_prevista TEXT,
        fecha_recepcion TEXT,
        observaciones TEXT,
        condiciones_pago TEXT,
        total_estimado REAL DEFAULT 0,
        usuario_creador TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS lineas_compra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orden_numero TEXT NOT NULL,
        tipo_articulo TEXT NOT NULL,
        articulo_codigo TEXT NOT NULL,
        articulo_nombre TEXT,
        cantidad_pedida REAL NOT NULL,
        cantidad_recibida REAL DEFAULT 0,
        unidad TEXT NOT NULL,
        precio_unitario REAL DEFAULT 0,
        subtotal REAL DEFAULT 0,
        notas TEXT,
        FOREIGN KEY(orden_numero) REFERENCES ordenes_compra(numero) ON DELETE CASCADE
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS recepciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        orden_compra TEXT,
        proveedor_codigo TEXT,
        fecha TEXT,
        albaran_proveedor TEXT,
        usuario_receptor TEXT,
        observaciones TEXT,
        estado TEXT DEFAULT 'pendiente_qc'
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS lineas_recepcion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recepcion_numero TEXT NOT NULL,
        tipo_articulo TEXT,
        articulo_codigo TEXT,
        lote_proveedor TEXT,
        lote_interno TEXT,
        cantidad_recibida REAL,
        unidad TEXT,
        fecha_caducidad TEXT,
        certificado_eco TEXT,
        caducidad_certificado TEXT,
        coste_unitario REAL,
        ubicacion TEXT,
        estado_qc TEXT DEFAULT 'pendiente'
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS rendimiento_lote (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_lote TEXT NOT NULL,
        producto_codigo TEXT,
        cantidad_teorica REAL,
        cantidad_real REAL,
        unidad TEXT,
        rendimiento_pct REAL,
        peso_final REAL,
        peso_objetivo REAL,
        fecha TEXT,
        observaciones TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS reprocesos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        lote_origen TEXT NOT NULL,
        producto_codigo TEXT,
        cantidad_origen REAL,
        motivo TEXT,
        descripcion TEXT,
        estado TEXT DEFAULT 'abierto',
        lote_destino TEXT,
        fecha_apertura TEXT,
        fecha_cierre TEXT,
        responsable TEXT,
        coste_extra REAL DEFAULT 0,
        resultado TEXT
    )""")

    # ---------- USUARIOS Y AUDITORÍA ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        email TEXT,
        password_hash TEXT NOT NULL,
        rol TEXT NOT NULL,
        activo INTEGER DEFAULT 1,
        fecha_creacion TEXT,
        ultimo_acceso TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        usuario TEXT,
        accion TEXT,
        detalle TEXT
    )""")

    c.execute("CREATE INDEX IF NOT EXISTS idx_lineas_compra ON lineas_compra(orden_numero)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_recepciones_oc ON recepciones(orden_compra)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_rendimiento_lote ON rendimiento_lote(producto_lote)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_reprocesos_origen ON reprocesos(lote_origen)")

    conn.commit()
    conn.close()
    print("✔ OZOLABS' WIZARD · Base de datos lista.")


def backup_db():
    if not os.path.exists(DB_PATH):
        return
    carpeta = "backups"
    os.makedirs(carpeta, exist_ok=True)
    nombre = f"ozolabs_wizard_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    copyfile(DB_PATH, os.path.join(carpeta, nombre))
    print(f"✔ Backup OZOLABS' WIZARD creado: {nombre}")
