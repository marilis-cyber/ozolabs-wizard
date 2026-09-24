"""
OZOLABS' WIZARD - Capa de base de datos
=========================================================
Soporta DOS modos automáticamente:

  • Turso (nube, persistente)  → si hay credenciales en st.secrets["turso"]
                                 o en las variables de entorno TURSO_URL /
                                 TURSO_TOKEN.
  • SQLite local (erp.db)      → si no hay credenciales (uso en tu Mac).

El resto del código sigue usando la misma API de siempre:
    conn = conectar()
    conn.execute(...).fetchone()
    conn.commit()
"""
import os
import json
import urllib.request
import urllib.error

DB_PATH = "erp.db"


# =========================================================
# DETECCIÓN DE TURSO
# =========================================================
def _limpiar(valor):
    """Quita espacios, saltos de línea y comillas que se cuelan al pegar."""
    if not valor:
        return valor
    v = str(valor).strip()
    v = v.replace("\n", "").replace("\r", "").replace(" ", "")
    v = v.strip('"').strip("'")
    return v


def _credenciales_turso():
    """
    Devuelve (url, token) si hay credenciales de Turso, o (None, None).
    Es muy tolerante: busca en st.secrets de varias formas y también en
    variables de entorno.
    """
    # 1) Streamlit secrets
    try:
        import streamlit as st
        sec = st.secrets

        # Recolectar TODAS las claves conocidas, en cualquier sección
        def _buscar_clave(nombres):
            """Busca una clave por varios nombres, en raíz y en [turso]/[secrets]."""
            for nombre in nombres:
                try:
                    if nombre in sec:
                        v = sec[nombre]
                        if v:
                            return str(v)
                except Exception:
                    pass
            # Buscar dentro de las secciones habituales
            for seccion in ("turso", "secrets"):
                try:
                    if seccion in sec:
                        sub = sec[seccion]
                        for nombre in nombres:
                            if nombre in sub:
                                v = sub[nombre]
                                if v:
                                    return str(v)
                except Exception:
                    pass
            return None

        # URL
        url = _buscar_clave(["turso_url", "url", "TURSO_URL"])
        # Token: entero o en trozos
        token = _buscar_clave(["turso_token", "auth_token", "token",
                               "TURSO_TOKEN"])
        if not token:
            t1 = _buscar_clave(["turso_t1", "t1"]) or ""
            t2 = _buscar_clave(["turso_t2", "t2"]) or ""
            t3 = _buscar_clave(["turso_t3", "t3"]) or ""
            if t1:
                token = t1 + t2 + t3
        if url and token:
            return _limpiar(url), _limpiar(token)
    except Exception:
        pass

    # 2) Variables de entorno
    url = os.environ.get("TURSO_URL")
    token = os.environ.get("TURSO_TOKEN")
    if url and token:
        return _limpiar(url), _limpiar(token)

    return None, None


def usando_turso():
    url, token = _credenciales_turso()
    return bool(url and token)


# =========================================================
# ADAPTADOR TURSO (habla el protocolo HTTP /v2/pipeline)
# =========================================================
def _tipo_arg(valor):
    """Convierte un valor Python al formato de argumento de Turso."""
    if valor is None:
        return {"type": "null"}
    if isinstance(valor, bool):
        return {"type": "integer", "value": "1" if valor else "0"}
    if isinstance(valor, int):
        return {"type": "integer", "value": str(valor)}
    if isinstance(valor, float):
        # Turso espera el float como NÚMERO, no como string
        return {"type": "float", "value": valor}
    return {"type": "text", "value": str(valor)}


def _valor_celda(celda):
    """Extrae el valor Python de una celda de respuesta de Turso."""
    if not isinstance(celda, dict):
        return celda
    t = celda.get("type")
    v = celda.get("value")
    if t == "null":
        return None
    if t == "integer":
        try:
            return int(v)
        except (TypeError, ValueError):
            return v
    if t == "float":
        try:
            return float(v)
        except (TypeError, ValueError):
            return v
    return v


class _CursorTurso:
    """
    Cursor compatible con el de sqlite3, pero por HTTP contra Turso.
    Implementa lo que usa el proyecto:
        .execute(sql, params)  → devuelve self
        .fetchone() / .fetchall()
        .lastrowid
    """

    def __init__(self, conexion):
        self._conn = conexion
        self._filas = []
        self._columnas = []
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=()):
        payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": sql,
                        "args": [_tipo_arg(p) for p in (params or ())],
                    },
                },
                {"type": "close"},
            ]
        }
        respuesta = self._conn._peticion(payload)
        resultados = respuesta.get("results", [])

        if not resultados or resultados[0].get("type") != "ok":
            # Extraer mensaje de error si lo hay
            err = resultados[0].get("error", {}) if resultados else {}
            msg = err.get("message", "Error desconocido en Turso")
            raise Exception(f"Turso: {msg}")

        res = resultados[0]["response"]["result"]
        self._columnas = [c["name"] for c in res.get("cols", [])]
        self._filas = [
            tuple(_valor_celda(c) for c in fila)
            for fila in res.get("rows", [])
        ]
        self.rowcount = res.get("affected_row_count", 0)
        self.lastrowid = res.get("last_insert_rowid")
        return self

    def fetchone(self):
        return self._filas[0] if self._filas else None

    def fetchall(self):
        return list(self._filas)

    def __iter__(self):
        return iter(self._filas)


class _ConexionTurso:

    def __init__(self, url, token):
        # Normaliza la URL a https:// para el protocolo HTTP
        self._url = url.replace("libsql://", "https://").rstrip("/")
        self._token = token

    def _peticion(self, payload):
        datos = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        # Reintentar hasta 3 veces ante fallos transitorios (429, 5xx, red)
        import time as _time
        ultimo_error = None
        for intento in range(3):
            req = urllib.request.Request(
                f"{self._url}/v2/pipeline",
                data=datos, headers=headers, method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                try:
                    cuerpo = e.read().decode("utf-8", errors="replace")
                except Exception:
                    cuerpo = "(sin cuerpo)"
                ultimo_error = (f"Turso HTTP {e.code} · {e.reason} · "
                                f"url={self._url} · resp={cuerpo[:400]}")
                # Error de servidor / rate limit → esperar y reintentar
                if e.code in (429, 500, 502, 503, 504) and intento < 2:
                    _time.sleep(1.5 * (intento + 1))
                    continue
                raise Exception(ultimo_error)
            except urllib.error.URLError as e:
                ultimo_error = f"Turso conexion: {e}"
                if intento < 2:
                    _time.sleep(1.5 * (intento + 1))
                    continue
                raise Exception(ultimo_error)
        raise Exception(ultimo_error or "Turso: error desconocido")

    def execute(self, sql, params=()):
        # PRAGMA foreign_keys no aplica en Turso; se ignora sin error
        if sql.strip().upper().startswith("PRAGMA"):
            return _CursorTurso(self)
        return _CursorTurso(self).execute(sql, params)

    def execute_lote(self, sentencias):
        """Ejecuta varias sentencias SQL en UNA sola petición HTTP.
        Mucho más rápido y fiable que una petición por sentencia."""
        peticiones = [
            {"type": "execute", "stmt": {"sql": sql, "args": []}}
            for sql in sentencias
        ]
        peticiones.append({"type": "close"})
        respuesta = self._peticion({"requests": peticiones})
        errores = [
            r.get("error", {}).get("message", "?")
            for r in respuesta.get("results", [])
            if r.get("type") == "error"
        ]
        if errores:
            raise Exception("; ".join(errores[:3]))
        return True

    def cursor(self):
        return _CursorTurso(self)

    def commit(self):
        # Turso por HTTP hace autocommit de cada sentencia.
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# =========================================================
# CONEXIÓN (pública)
# =========================================================
def conectar():
    """
    Devuelve una conexión a Turso (si hay credenciales) o a SQLite local.
    """
    url, token = _credenciales_turso()
    if url and token:
        return _ConexionTurso(url, token)

    # SQLite local
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# ESQUEMA DE TABLAS
# =========================================================
def _tablas_sql():
    """Lista de sentencias CREATE TABLE (idénticas para Turso y SQLite)."""
    return [
        """CREATE TABLE IF NOT EXISTS materias_primas (
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
        )""",
        """CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            formato TEXT,
            stock_minimo REAL DEFAULT 0,
            tamano_unidad REAL DEFAULT 0,
            unidad_tamano TEXT DEFAULT 'mL',
            uso TEXT DEFAULT 'cosmetico',
            envase_codigo TEXT,
            caducidad_meses INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS formulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            materia_codigo TEXT NOT NULL,
            cantidad_por_unidad REAL NOT NULL,
            unidad TEXT NOT NULL,
            porcentaje REAL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS stock_producto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            lote TEXT NOT NULL,
            fecha_fabricacion TEXT,
            fecha_caducidad TEXT,
            cantidad REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS trazabilidad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_lote TEXT NOT NULL,
            producto_id INTEGER,
            materia_codigo TEXT,
            materia_lote TEXT,
            cantidad_usada REAL,
            fecha TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS producciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER,
            lote TEXT NOT NULL,
            cantidad REAL NOT NULL,
            fecha TEXT,
            coste_total REAL DEFAULT 0,
            orden_id INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            contacto TEXT,
            email TEXT,
            telefono TEXT,
            condiciones_pago TEXT,
            notas TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS envases (
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
        )""",
        """CREATE TABLE IF NOT EXISTS formula_envases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            envase_codigo TEXT NOT NULL,
            cantidad_por_unidad REAL NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS costes_indirectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT NOT NULL,
            coste_por_hora REAL DEFAULT 0,
            coste_por_unidad REAL DEFAULT 0,
            activo INTEGER DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS tiempos_producto (
            producto_id INTEGER PRIMARY KEY,
            minutos_por_lote REAL DEFAULT 0,
            horas_mano_obra REAL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS ordenes_produccion (
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
            historial TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS movimientos_stock (
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
        )""",
        """CREATE TABLE IF NOT EXISTS precios_proveedor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_codigo TEXT,
            articulo_codigo TEXT,
            tipo_articulo TEXT,
            precio_unitario REAL,
            fecha TEXT,
            lote TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS escandallo_real (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produccion_id INTEGER,
            producto_lote TEXT,
            articulo_tipo TEXT,
            articulo_codigo TEXT,
            articulo_lote TEXT,
            cantidad REAL,
            unidad TEXT,
            precio_unitario REAL,
            subtotal REAL
        )""",
        """CREATE TABLE IF NOT EXISTS controles_calidad (
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
        )""",
        """CREATE TABLE IF NOT EXISTS no_conformidades (
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
        )""",
        """CREATE TABLE IF NOT EXISTS liberacion_lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_articulo TEXT NOT NULL,
            articulo_codigo TEXT NOT NULL,
            lote TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            fecha TEXT,
            responsable TEXT,
            UNIQUE(tipo_articulo, articulo_codigo, lote)
        )""",
        """CREATE TABLE IF NOT EXISTS reservas_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_numero TEXT NOT NULL,
            tipo_articulo TEXT NOT NULL,
            articulo_codigo TEXT NOT NULL,
            cantidad_reservada REAL NOT NULL,
            unidad TEXT,
            fecha TEXT,
            estado TEXT DEFAULT 'activa'
        )""",
        """CREATE TABLE IF NOT EXISTS pesos_reales (
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
        )""",
        """CREATE TABLE IF NOT EXISTS mermas (
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
        )""",
        """CREATE TABLE IF NOT EXISTS firmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_numero TEXT NOT NULL,
            tipo TEXT,
            nombre TEXT,
            imagen_base64 TEXT,
            fecha TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS subproductos (
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
        )""",
        """CREATE TABLE IF NOT EXISTS ordenes_compra (
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
        )""",
        """CREATE TABLE IF NOT EXISTS lineas_compra (
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
            notas TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS recepciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            orden_compra TEXT,
            proveedor_codigo TEXT,
            fecha TEXT,
            albaran_proveedor TEXT,
            usuario_receptor TEXT,
            observaciones TEXT,
            estado TEXT DEFAULT 'pendiente_qc',
            uso TEXT DEFAULT 'cosmetico',
            conforme TEXT DEFAULT 'conforme',
            bio INTEGER DEFAULT 0,
            caducidad_bio TEXT,
            responsable TEXT,
            producto TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS lineas_recepcion (
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
        )""",
        """CREATE TABLE IF NOT EXISTS rendimiento_lote (
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
        )""",
        """CREATE TABLE IF NOT EXISTS reprocesos (
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
        )""",
        """CREATE TABLE IF NOT EXISTS salidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            producto TEXT,
            producto_codigo TEXT,
            uso TEXT DEFAULT 'cosmetico',
            destino TEXT,
            lote TEXT,
            cantidad REAL DEFAULT 0,
            unidad TEXT,
            comentarios TEXT,
            responsable TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS ozono_producciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            fecha TEXT,
            hora_inicio TEXT,
            hora_fin TEXT,
            litros REAL DEFAULT 0,
            reactor TEXT,
            aceite_codigo TEXT,
            aceite_nombre TEXT,
            aceite_lote TEXT,
            proveedor TEXT,
            flujo REAL DEFAULT 0,
            presion REAL DEFAULT 0,
            nitrogeno TEXT,
            trampa_agua TEXT,
            emulsion TEXT,
            observaciones TEXT,
            responsable TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS garrafas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            litros_capacidad REAL DEFAULT 0,
            litros_disponibles REAL DEFAULT 0,
            produccion_numero TEXT,
            lote TEXT,
            producto TEXT,
            fecha_llenado TEXT,
            ubicacion TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS salidas_garrafa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            garrafa_codigo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            litros REAL DEFAULT 0,
            destino TEXT,
            comentarios TEXT,
            responsable TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS etiquetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_codigo TEXT NOT NULL,
            producto_nombre TEXT,
            version INTEGER DEFAULT 1,
            nombre_fichero TEXT,
            contenido_base64 TEXT,
            fecha TEXT,
            comentarios TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT,
            ultimo_acceso TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            usuario TEXT,
            accion TEXT,
            detalle TEXT
        )""",
    ]


def crear_tablas():
    conn = conectar()
    sentencias = _tablas_sql()
    # En Turso, lanzamos todas las sentencias en UNA sola petición
    # (mucho más rápido y fiable que 36 peticiones HTTP seguidas).
    if isinstance(conn, _ConexionTurso):
        try:
            conn.execute_lote(sentencias)
        except Exception as e:
            print(f"⚠ Error creando tablas en lote, probando una a una: {e}")
            for sql in sentencias:
                try:
                    conn.execute(sql)
                except Exception as e2:
                    print(f"⚠ Error creando tabla: {e2}")
    else:
        for sql in sentencias:
            try:
                conn.execute(sql)
            except Exception as e:
                print(f"⚠ Error creando tabla: {e}")
    try:
        _migrar_columnas(conn)
    except Exception as e:
        print(f"⚠ Error en migraciones: {e}")
    conn.commit()
    conn.close()
    print("✔ OZOLABS' WIZARD · Base de datos lista.")


def _migrar_columnas(conn):
    """Añade columnas nuevas a tablas existentes (migración sin perder datos)."""
    migraciones = [
        ("recepciones", "uso", "TEXT DEFAULT 'cosmetico'"),
        ("recepciones", "conforme", "TEXT DEFAULT 'conforme'"),
        ("recepciones", "bio", "INTEGER DEFAULT 0"),
        ("recepciones", "caducidad_bio", "TEXT"),
        ("recepciones", "responsable", "TEXT"),
        ("recepciones", "producto", "TEXT"),
        ("materias_primas", "uso", "TEXT DEFAULT 'cosmetico'"),
        ("materias_primas", "bio", "INTEGER DEFAULT 0"),
        ("materias_primas", "caducidad_bio", "TEXT"),
        ("materias_primas", "proveedor_lote", "TEXT"),
        ("productos", "tamano_unidad", "REAL DEFAULT 0"),
        ("productos", "unidad_tamano", "TEXT DEFAULT 'mL'"),
        ("productos", "uso", "TEXT DEFAULT 'cosmetico'"),
        ("productos", "envase_codigo", "TEXT"),
        ("productos", "caducidad_meses", "INTEGER DEFAULT 0"),
        ("formulas", "porcentaje", "REAL DEFAULT 0"),
    ]
    for tabla, columna, tipo in migraciones:
        try:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        except Exception:
            pass  # La columna ya existe


def backup_db():
    """Backup solo tiene sentido con SQLite local."""
    if usando_turso():
        print("ℹ Turso: el backup lo gestiona la nube automáticamente.")
        return
    import os as _os
    from datetime import datetime as _dt
    from shutil import copyfile
    if not _os.path.exists(DB_PATH):
        return
    carpeta = "backups"
    _os.makedirs(carpeta, exist_ok=True)
    nombre = f"ozolabs_wizard_backup_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db"
    copyfile(DB_PATH, _os.path.join(carpeta, nombre))
    print(f"✔ Backup OZOLABS' WIZARD creado: {nombre}")


# Alias público para comprobar el tipo de conexión desde otros módulos
ConexionTurso = _ConexionTurso
