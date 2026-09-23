"""OZOLABS' WIZARD - Versión CLI"""
from database import crear_tablas
from modelos import (
    añadir_materia, listar_materias,
    añadir_producto, añadir_ingrediente_formula, ver_formula,
    producir, listar_ordenes, crear_orden_produccion,
)
from avisos import generar_avisos


def pausa():
    input("\nENTER para continuar...")


def menu_materias():
    while True:
        print("""
── MATERIAS PRIMAS ──
1. Añadir materia prima
2. Listar stock
0. Volver""")
        op = input("Opción: ")
        if op == "1":
            añadir_materia(
                input("Código: "),
                input("Nombre: "),
                input("Proveedor: "),
                input("Lote: "),
                float(input("Cantidad: ")),
                input("Unidad (kg/g/L/mL/ud): "),
                input("Fecha recepción (YYYY-MM-DD): "),
                input("Fecha caducidad (YYYY-MM-DD, vacío=NA): ") or None,
                input("Certificado eco (vacío=no): ") or None,
                input("Caducidad certificado (YYYY-MM-DD): ") or None,
                float(input("Coste unitario €: ") or 0),
                input("Ubicación: "),
                float(input("Stock mínimo: ") or 0),
            )
            pausa()
        elif op == "2":
            print(f"\n{'Código':<12}{'Nombre':<25}{'Lote':<15}{'Cant':>8} {'Ud':<5}{'Caduca':<12}{'Ubic.'}")
            for r in listar_materias():
                print(f"{r[0]:<12}{r[1]:<25}{r[2]:<15}{r[3]:>8.2f} "
                      f"{r[4]:<5}{str(r[5] or ''):<12}{r[6] or ''}")
            pausa()
        elif op == "0":
            break


def menu_productos():
    while True:
        print("""
── PRODUCTOS Y FÓRMULAS ──
1. Crear producto
2. Añadir ingrediente a fórmula
3. Ver fórmula
0. Volver""")
        op = input("Opción: ")
        if op == "1":
            añadir_producto(
                input("Código: "),
                input("Nombre: "),
                input("Formato: "),
                float(input("Stock mínimo: ") or 0),
            )
            pausa()
        elif op == "2":
            añadir_ingrediente_formula(
                input("Código producto: "),
                input("Código materia prima: "),
                float(input("Cantidad por unidad: ")),
                input("Unidad: "),
            )
            pausa()
        elif op == "3":
            pc = input("Código producto: ")
            print(f"\nFórmula de {pc}:")
            for r in ver_formula(pc):
                print(f"  - {r[0]}: {r[1]} {r[2]} / unidad")
            pausa()
        elif op == "0":
            break


def menu_produccion():
    print("\n── REGISTRAR PRODUCCIÓN ──")
    cod = input("Código producto: ")
    cant = float(input("Cantidad a fabricar: "))
    lote = input("Lote PT (vacío=auto): ") or None
    fcad = input("Caducidad PT (YYYY-MM-DD, vacío=NA): ") or None
    producir(cod, cant, lote, fcad)
    pausa()


def menu_pedidos():
    while True:
        print("""
── PEDIDOS DE PRODUCCIÓN ──
1. Crear pedido
2. Listar pedidos
0. Volver""")
        op = input("Opción: ")
        if op == "1":
            numero = crear_orden_produccion(
                input("Código producto: "),
                float(input("Cantidad: ")),
                input("Fecha prevista (YYYY-MM-DD, vacío=NA): ") or None,
                input("Observaciones: "),
            )
            if numero:
                print(f"✔ Pedido {numero} creado.")
            pausa()
        elif op == "2":
            for r in listar_ordenes():
                print(f"  {r[0]} | {r[1]} {r[2]} | plan:{r[3]} fab:{r[4]} | "
                      f"{r[5]} | prev:{r[6] or '-'}")
            pausa()
        elif op == "0":
            break


def menu_avisos():
    print("\n── AVISOS AUTOMÁTICOS ──")
    avisos = generar_avisos()
    if not avisos:
        print("✔ Sin avisos. Todo en orden.")
    else:
        for a in avisos:
            print(a)
    pausa()


def main():
    crear_tablas()
    banner = r"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║              O Z O L A B S '   W I Z A R D               ║
║                                                          ║
║   ERP / MRP - Gestión integral de producción             ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""
    while True:
        print(banner)
        print("""
 1. Materias primas
 2. Productos y fórmulas
 3. Registrar producción
 4. Pedidos de producción
 5. Avisos automáticos
 0. Salir
""")
        op = input("Opción: ")
        if op == "1":
            menu_materias()
        elif op == "2":
            menu_productos()
        elif op == "3":
            menu_produccion()
        elif op == "4":
            menu_pedidos()
        elif op == "5":
            menu_avisos()
        elif op == "0":
            print("\n🧙‍♂️ Hasta luego, mago. 👋\n")
            break


if __name__ == "__main__":
    main()
