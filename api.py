"""OZOLABS' WIZARD - API REST FastAPI
Ejecutar: uvicorn api:app --reload --port 8000"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import crear_tablas
from usuarios import (
    autenticar, generar_token, verificar_token, puede_acceder,
    crear_tabla_usuarios, registrar_auditoria,
)
import analytics as ana


# =========================================================
# MODELOS PYDANTIC
# =========================================================
class LoginIn(BaseModel):
    usuario: str
    password: str


class LoginOut(BaseModel):
    token: str
    usuario: str
    rol: str
    nombre: str


class MateriaPrimaIn(BaseModel):
    codigo: str
    nombre: str
    proveedor: Optional[str] = None
    lote: str
    cantidad: float
    unidad: str
    fecha_recepcion: Optional[str] = None
    fecha_caducidad: Optional[str] = None
    certificado_eco: Optional[str] = None
    caducidad_certificado: Optional[str] = None
    coste_unitario: float = 0
    ubicacion: Optional[str] = None
    stock_minimo: float = 0


class ProduccionIn(BaseModel):
    producto_codigo: str
    cantidad: float
    lote: Optional[str] = None
    fecha_caducidad: Optional[str] = None


# =========================================================
# APP
# =========================================================
app = FastAPI(
    title="OZOLABS' WIZARD API",
    description="API REST para integración con sistemas externos. "
                "Usa /auth/login para obtener un token JWT.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def arranque():
    crear_tablas()
    crear_tabla_usuarios()


# =========================================================
# SEGURIDAD
# =========================================================
def usuario_actual(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Falta token Bearer")
    token = authorization.split(" ", 1)[1]
    datos = verificar_token(token)
    if not datos:
        raise HTTPException(401, "Token inválido o expirado")
    return datos


def requiere_modulo(modulo: str):
    def dep(user=Depends(usuario_actual)):
        if not puede_acceder(user["rol"], modulo):
            raise HTTPException(
                403, f"El rol '{user['rol']}' no puede acceder a {modulo}"
            )
        return user
    return dep


# =========================================================
# AUTENTICACIÓN
# =========================================================
@app.post("/auth/login", response_model=LoginOut, tags=["Auth"])
def login(datos: LoginIn):
    u = autenticar(datos.usuario, datos.password)
    if not u:
        raise HTTPException(401, "Credenciales incorrectas")
    token = generar_token(u["usuario"], u["rol"])
    return {
        "token": token,
        "usuario": u["usuario"],
        "rol": u["rol"],
        "nombre": u["nombre"],
    }


@app.get("/auth/yo", tags=["Auth"])
def yo(user=Depends(usuario_actual)):
    return user


# =========================================================
# STOCK
# =========================================================
@app.get("/stock/mp", tags=["Stock"])
def stock_mp(user=Depends(requiere_modulo("🌿 Materias primas"))):
    from database import conectar
    conn = conectar()
    rows = conn.execute("""
        SELECT codigo, nombre, lote, cantidad, unidad,
               fecha_caducidad, ubicacion
        FROM materias_primas ORDER BY nombre
    """).fetchall()
    conn.close()
    return [
        {"codigo": r[0], "nombre": r[1], "lote": r[2], "cantidad": r[3],
         "unidad": r[4], "caducidad": r[5], "ubicacion": r[6]}
        for r in rows
    ]


@app.get("/stock/mp/{codigo}", tags=["Stock"])
def stock_mp_codigo(codigo: str,
                    user=Depends(requiere_modulo("🌿 Materias primas"))):
    from database import conectar
    conn = conectar()
    row = conn.execute("""
        SELECT COALESCE(SUM(cantidad), 0), unidad
        FROM materias_primas WHERE codigo = ? GROUP BY unidad
    """, (codigo,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Materia prima no encontrada")
    return {"codigo": codigo, "stock": row[0], "unidad": row[1]}


@app.get("/stock/pt", tags=["Stock"])
def stock_pt(user=Depends(requiere_modulo("🏠 Dashboard"))):
    from database import conectar
    conn = conectar()
    rows = conn.execute("""
        SELECT p.codigo, p.nombre, s.lote, s.cantidad,
               s.fecha_caducidad, s.fecha_fabricacion
        FROM stock_producto s
        JOIN productos p ON p.id = s.producto_id
        ORDER BY p.nombre
    """).fetchall()
    conn.close()
    return [
        {"codigo": r[0], "producto": r[1], "lote": r[2], "cantidad": r[3],
         "caducidad": r[4], "fabricacion": r[5]}
        for r in rows
    ]


# =========================================================
# MATERIAS PRIMAS (escritura)
# =========================================================
@app.post("/mp", tags=["Materias primas"])
def crear_mp(datos: MateriaPrimaIn,
             user=Depends(requiere_modulo("🌿 Materias primas"))):
    from modelos import añadir_materia
    try:
        añadir_materia(
            datos.codigo, datos.nombre, datos.proveedor, datos.lote,
            datos.cantidad, datos.unidad, datos.fecha_recepcion,
            datos.fecha_caducidad, datos.certificado_eco,
            datos.caducidad_certificado, datos.coste_unitario,
            datos.ubicacion, datos.stock_minimo,
        )
        registrar_auditoria(user["usuario"], "crear_mp",
                            f"{datos.codigo} lote {datos.lote}")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


# =========================================================
# PRODUCCIÓN
# =========================================================
@app.post("/produccion", tags=["Producción"])
def crear_produccion(datos: ProduccionIn,
                     user=Depends(requiere_modulo("⚙️ Producción"))):
    from modelos import producir
    try:
        producir(datos.producto_codigo, datos.cantidad,
                 datos.lote, datos.fecha_caducidad)
        registrar_auditoria(user["usuario"], "produccion",
                            f"{datos.producto_codigo} x{datos.cantidad}")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


# =========================================================
# AVISOS
# =========================================================
@app.get("/avisos", tags=["Avisos"])
def avisos(user=Depends(requiere_modulo("📊 Avisos"))):
    from avisos import generar_avisos
    return {"avisos": generar_avisos()}


# =========================================================
# ANALYTICS
# =========================================================
@app.get("/analytics/kpis", tags=["Analytics"])
def kpis(user=Depends(requiere_modulo("📊 Análisis y gráficos"))):
    return ana.kpis_generales()


@app.get("/analytics/producciones", tags=["Analytics"])
def producciones(user=Depends(requiere_modulo("📊 Análisis y gráficos"))):
    df = ana.serie_producciones_por_mes()
    return df.to_dict(orient="records")


# =========================================================
# TRAZABILIDAD
# =========================================================
@app.get("/trazabilidad/{lote}", tags=["Trazabilidad"])
def trazabilidad(lote: str, user=Depends(requiere_modulo("🏠 Dashboard"))):
    from database import conectar
    conn = conectar()
    rows = conn.execute("""
        SELECT materia_codigo, materia_lote, cantidad_usada, fecha
        FROM trazabilidad WHERE producto_lote = ?
    """, (lote,)).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(404, "Lote no encontrado")
    return {
        "lote": lote,
        "componentes": [
            {"mp": r[0], "lote_mp": r[1], "cantidad": r[2], "fecha": r[3]}
            for r in rows
        ],
    }


# =========================================================
# ROOT
# =========================================================
@app.get("/", tags=["Root"])
def root():
    return {
        "app": "OZOLABS' WIZARD API",
        "version": "1.0.0",
        "docs": "/docs",
        "estado": "ok",
    }
