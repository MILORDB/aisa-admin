import sqlite3

DB_PATH = "E:/AISA/data/usuarios.db"

def resetear_negocio():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Verificar que los módulos existen
    cursor.execute("SELECT id, nombre FROM modulos WHERE nombre IN ('inventario','servicios','tienda','trabajadores','ventas')")
    modulos = cursor.fetchall()
    
    if not modulos:
        print("❌ Los módulos de negocio no existen en la base de datos.")
        print("   Ejecuta primero: python add_modules.py")
        conn.close()
        return
    
    print("📋 Módulos encontrados:")
    for m in modulos:
        print(f"  ID:{m[0]} | {m[1]}")
    
    # 2. Obtener el usuario negocio
    username = input("Introduce el nombre de usuario negocio: ").strip()
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
    user = cursor.fetchone()
    
    if not user:
        print(f"❌ Usuario '{username}' no encontrado.")
        conn.close()
        return
    
    user_id = user[0]
    print(f"✅ Usuario encontrado: {username} (ID: {user_id})")
    
    # 3. Eliminar permisos existentes de este usuario
    cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = ?", (user_id,))
    print("🗑️ Permisos anteriores eliminados.")
    
    # 4. Asignar TODOS los módulos de negocio
    for modulo_id, nombre in modulos:
        cursor.execute('''
        INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
        VALUES (?, ?, 1, 'aprobado')
        ''', (user_id, modulo_id))
        print(f"  ✅ Asignado: {nombre}")
    
    conn.commit()
    conn.close()
    print("\n✅ Todos los módulos han sido asignados correctamente.")
    print("🔄 Recarga la página de negocio.")

if __name__ == "__main__":
    resetear_negocio()