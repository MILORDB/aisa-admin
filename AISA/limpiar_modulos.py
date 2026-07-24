import sqlite3

DB_PATH = "E:/AISA/data/usuarios.db"

def limpiar_modulos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Ver los módulos actuales
    cursor.execute("SELECT id, nombre FROM modulos")
    print("📋 Módulos actuales en la base de datos:")
    for row in cursor.fetchall():
        print(f"  ID:{row[0]} | {row[1]}")
    
    # 2. Eliminar TODOS los módulos
    cursor.execute("DELETE FROM modulos")
    print("\n🗑️ Todos los módulos eliminados.")
    
    # 3. Insertar SOLO los 5 módulos de negocio
    modulos = [
        ('inventario', 'Gestión de inventario y productos', 1, 'negocio'),
        ('tienda', 'Tienda online para clientes', 1, 'negocio'),
        ('trabajadores', 'Gestión de trabajadores y empleados', 1, 'negocio'),
        ('servicios', 'Gestión de servicios ofrecidos', 1, 'negocio'),
        ('ventas', 'Gestión de ventas y facturación', 1, 'negocio'),
    ]
    
    for nombre, desc, activo, tipo in modulos:
        cursor.execute('''
        INSERT INTO modulos (nombre, descripcion, activo_global, tipo_requerido)
        VALUES (?, ?, ?, ?)
        ''', (nombre, desc, activo, tipo))
        print(f"  ✅ Insertado: {nombre}")
    
    conn.commit()
    conn.close()
    print("\n✅ Base de datos limpiada. Solo quedan los 5 módulos de negocio.")

if __name__ == "__main__":
    limpiar_modulos()