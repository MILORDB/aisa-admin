import sqlite3

DB_PATH = "E:/AISA/data/usuarios.db"

def fix_permisos_negocio():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Obtener el ID del usuario negocio
    username = input("Introduce el nombre de usuario negocio: ").strip()
    cursor.execute("SELECT id FROM usuarios WHERE username = ? AND tipo = 'negocio'", (username,))
    user = cursor.fetchone()
    
    if not user:
        print(f"❌ Usuario '{username}' no encontrado o no es tipo negocio.")
        return
    
    user_id = user[0]
    print(f"✅ Usuario encontrado: {username} (ID: {user_id})")

    # 2. Obtener IDs de los 5 módulos de negocio
    modulos_nombres = ['inventario', 'servicios', 'tienda', 'trabajadores', 'ventas']
    placeholders = ','.join('?' * len(modulos_nombres))
    cursor.execute(f"SELECT id, nombre FROM modulos WHERE nombre IN ({placeholders})", modulos_nombres)
    modulos = cursor.fetchall()

    if not modulos:
        print("❌ No se encontraron módulos de negocio en la base de datos.")
        return

    print("\n📋 Módulos encontrados:")
    for m in modulos:
        print(f"  ID:{m[0]} | {m[1]}")

    # 3. Asignar permisos activos para cada módulo
    for modulo_id, nombre in modulos:
        cursor.execute('''
        INSERT OR REPLACE INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
        VALUES (?, ?, 1, 'aprobado')
        ''', (user_id, modulo_id))
        print(f"  ✅ Permiso activo para: {nombre}")

    conn.commit()
    conn.close()
    print("\n✅ Todos los módulos de negocio han sido asignados correctamente.")

if __name__ == "__main__":
    fix_permisos_negocio()