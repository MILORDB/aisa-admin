import sqlite3

DB_PATH = "E:/AISA/data/usuarios.db"

def asignar_negocio():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Ver usuarios tipo negocio
    cursor.execute("SELECT id, username FROM usuarios WHERE tipo = 'negocio'")
    negocios = cursor.fetchall()
    
    if not negocios:
        print("❌ No hay usuarios de tipo 'negocio'.")
        print("   Usa: UPDATE usuarios SET tipo = 'negocio' WHERE username = 'tu_usuario'")
        conn.close()
        return
    
    print("👥 Usuarios tipo negocio:")
    for n in negocios:
        print(f"  ID:{n[0]} | {n[1]}")
    
    # 2. Seleccionar usuario
    user_id = input("\nIntroduce el ID del usuario: ").strip()
    cursor.execute("SELECT username FROM usuarios WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        print("❌ Usuario no encontrado")
        conn.close()
        return
    
    print(f"✅ Usuario seleccionado: {user[0]}")
    
    # 3. Eliminar permisos antiguos
    cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = ?", (user_id,))
    print("🗑️ Permisos antiguos eliminados.")
    
    # 4. Asignar los 5 módulos
    cursor.execute("SELECT id, nombre FROM modulos")
    modulos = cursor.fetchall()
    
    for mod_id, nombre in modulos:
        cursor.execute('''
        INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
        VALUES (?, ?, 1, 'aprobado')
        ''', (user_id, mod_id))
        print(f"  ✅ Asignado: {nombre}")
    
    conn.commit()
    conn.close()
    print("\n✅ Todos los módulos asignados correctamente.")
    print("🔄 Recarga la página de negocio.")

if __name__ == "__main__":
    asignar_negocio()