"""
OZOLABS' WIZARD - Usuarios, roles, permisos y auditoría
"""
from database import conectar, ConexionTurso as _ConexionTurso
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import os

# Contexto de hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Clave secreta para JWT (en producción usar variable de entorno)
SECRET_KEY = os.environ.get("OZOLABS_SECRET", "ozolabs-wizard-secret-change-me")
ALGORITHM = "HS256"
TOKEN_HORAS = 12

# Roles disponibles
ROLES = {
    "admin": {
        "descripcion": "Acceso total. Gestiona usuarios, config y datos maestros.",
        "modulos": "*",
    },
    "produccion": {
        "descripcion": "Fabricar, pedidos, materias primas y producto terminado.",
        "modulos": [
            "🏠 Dashboard", "🌿 Materias primas", "📦 Productos y fórmulas",
            "⚙️ Producción", "📋 Pedidos de producción", "🧴 Envases y etiquetas",
            "🔬 Escandallos reales", "📐 Planificación MRP", "🏷️ Etiquetado",
            "🖨️ Etiqueta térmica", "📊 Avisos", "📈 Histórico y exportación",
            "📄 Informes PDF", "📊 Análisis y gráficos", "🔲 Códigos QR",
            "⚖️ Pesos reales", "📉 Mermas", "🖊️ Firmas digitales",
            "📈 Rendimiento", "🔄 Reprocesos",
        ],
    },
    "calidad": {
        "descripcion": "Control de calidad, no conformidades y liberación de lotes.",
        "modulos": [
            "🏠 Dashboard", "✅ Control de calidad", "🔬 Escandallos reales",
            "📄 Informes PDF", "📊 Avisos", "📊 Análisis y gráficos",
            "🏷️ Etiquetado", "🖨️ Etiqueta térmica", "📥 Recepción de mercancía",
            "📈 Rendimiento", "🔄 Reprocesos", "⚖️ Pesos reales", "📉 Mermas",
        ],
    },
    "compras": {
        "descripcion": "Proveedores, materias primas, envases y planificación MRP.",
        "modulos": [
            "🏠 Dashboard", "🚚 Proveedores", "🌿 Materias primas",
            "🧴 Envases y etiquetas", "📐 Planificación MRP", "📊 Avisos",
            "💰 Costes", "📈 Histórico y exportación",
            "🛒 Órdenes de compra", "📥 Recepción de mercancía",
        ],
    },
    "consulta": {
        "descripcion": "Solo lectura. Dashboard, stock, avisos e históricos.",
        "modulos": [
            "🏠 Dashboard", "🌿 Materias primas", "📦 Productos y fórmulas",
            "📊 Avisos", "📈 Histórico y exportación", "📊 Análisis y gráficos",
        ],
    },
}


# =========================================================
# HASHING
# =========================================================
def hash_password(password):
    """Devuelve el hash bcrypt de una contraseña."""
    return pwd_context.hash(password)


def verificar_password(password, hash_guardado):
    """Comprueba si una contraseña coincide con su hash."""
    try:
        return pwd_context.verify(password, hash_guardado)
    except Exception:
        return False


# =========================================================
# TABLAS
# =========================================================
def crear_tabla_usuarios():
    """Crea las tablas de usuarios y auditoría si no existen."""
    conn = conectar()
    sqls = [
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
    if isinstance(conn, _ConexionTurso):
        try:
            conn.execute_lote(sqls)
        except Exception as e:
            print(f"⚠ Error creando tablas de usuarios: {e}")
    else:
        for sql in sqls:
            conn.execute(sql)
        conn.commit()
    conn.close()


def crear_admin_inicial():
    """Crea el usuario admin/admin si no existe ningún usuario."""
    conn = conectar()
    n = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    conn.close()
    if n == 0:
        ok = crear_usuario("admin", "Administrador", "admin", "admin",
                           email="admin@ozolabs.local")
        if ok:
            print("⚠ Usuario inicial creado: admin / admin (cámbialo en el primer login)")
        else:
            print("✘ NO se pudo crear el usuario admin inicial. "
                  "¿Está passlib/bcrypt bien instalado?")
        return ok
    return True


def reset_admin():
    """Borra y recrea el usuario admin/admin. Útil si el hash quedó corrupto."""
    conn = conectar()
    conn.execute("DELETE FROM usuarios WHERE usuario = 'admin'")
    conn.commit()
    conn.close()
    ok = crear_usuario("admin", "Administrador", "admin", "admin",
                       email="admin@ozolabs.local")
    print("✔ admin/admin recreado." if ok else "✘ Error recreando admin.")
    return ok


# =========================================================
# CRUD USUARIOS
# =========================================================
def crear_usuario(usuario, nombre, password, rol, email=""):
    if rol not in ROLES:
        print(f"✘ Rol inválido. Válidos: {list(ROLES.keys())}")
        return False
    try:
        h = hash_password(password)
    except Exception as e:
        print(f"✘ Error al hashear la contraseña (passlib/bcrypt): {e}")
        return False
    conn = conectar()
    try:
        conn.execute("""
            INSERT INTO usuarios
            (usuario, nombre, email, password_hash, rol, activo, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (usuario, nombre, email, h, rol, datetime.now().isoformat()))
        conn.commit()
        print(f"✔ Usuario '{usuario}' creado con rol '{rol}'.")
        return True
    except Exception as e:
        print(f"✘ Error: {e}")
        return False
    finally:
        conn.close()


def listar_usuarios():
    conn = conectar()
    rows = conn.execute("""
        SELECT usuario, nombre, email, rol, activo, fecha_creacion, ultimo_acceso
        FROM usuarios
        ORDER BY usuario
    """).fetchall()
    conn.close()
    return rows


def cambiar_rol(usuario, nuevo_rol):
    if nuevo_rol not in ROLES:
        return False
    conn = conectar()
    conn.execute("UPDATE usuarios SET rol = ? WHERE usuario = ?",
                 (nuevo_rol, usuario))
    conn.commit()
    conn.close()
    return True


def activar_desactivar(usuario, activo):
    conn = conectar()
    conn.execute("UPDATE usuarios SET activo = ? WHERE usuario = ?",
                 (1 if activo else 0, usuario))
    conn.commit()
    conn.close()


def cambiar_password(usuario, nueva):
    conn = conectar()
    h = hash_password(nueva)
    conn.execute("UPDATE usuarios SET password_hash = ? WHERE usuario = ?",
                 (h, usuario))
    conn.commit()
    conn.close()


# =========================================================
# AUTENTICACIÓN
# =========================================================
def autenticar(usuario, password):
    """Devuelve dict con datos del usuario o None si falla."""
    conn = conectar()
    row = conn.execute("""
        SELECT id, nombre, password_hash, rol, activo
        FROM usuarios WHERE usuario = ?
    """, (usuario,)).fetchone()
    if not row:
        conn.close()
        return None
    uid, nombre, h, rol, activo = row
    if not activo:
        conn.close()
        return None
    if not verificar_password(password, h):
        conn.close()
        return None
    conn.execute("UPDATE usuarios SET ultimo_acceso = ? WHERE id = ?",
                 (datetime.now().isoformat(), uid))
    conn.execute("""
        INSERT INTO auditoria (fecha, usuario, accion, detalle)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().isoformat(), usuario, "login", "Acceso correcto"))
    conn.commit()
    conn.close()
    return {"id": uid, "usuario": usuario, "nombre": nombre, "rol": rol}


# =========================================================
# TOKENS JWT
# =========================================================
def generar_token(usuario, rol, horas=TOKEN_HORAS):
    payload = {
        "sub": usuario,
        "rol": rol,
        "exp": datetime.utcnow() + timedelta(hours=horas),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except Exception:
        return None


# =========================================================
# PERMISOS
# =========================================================
def puede_acceder(rol, modulo):
    if rol not in ROLES:
        return False
    mods = ROLES[rol]["modulos"]
    if mods == "*":
        return True
    return modulo in mods


# =========================================================
# AUDITORÍA
# =========================================================
def registrar_auditoria(usuario, accion, detalle=""):
    conn = conectar()
    conn.execute("""
        INSERT INTO auditoria (fecha, usuario, accion, detalle)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().isoformat(), usuario, accion, detalle))
    conn.commit()
    conn.close()


def ver_auditoria(limite=200):
    conn = conectar()
    rows = conn.execute("""
        SELECT fecha, usuario, accion, detalle
        FROM auditoria
        ORDER BY id DESC LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return rows


# =========================================================
# EXPORT
# =========================================================
__all__ = [
    "ROLES",
    "pwd_context", "SECRET_KEY", "ALGORITHM", "TOKEN_HORAS",
    "hash_password", "verificar_password",
    "crear_tabla_usuarios", "crear_admin_inicial",
    "crear_usuario", "listar_usuarios", "cambiar_rol",
    "activar_desactivar", "cambiar_password",
    "autenticar", "generar_token", "verificar_token",
    "puede_acceder",
    "registrar_auditoria", "ver_auditoria",
]
