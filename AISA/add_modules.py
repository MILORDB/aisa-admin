import sqlite3

DB_PATH = "E:/AISA/data/usuarios.db"

def add_modules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    modulos = [
        ('inventario', 'Gestión de inventario y productos', 1, 'negocio'),
        ('tienda', 'Tienda online para clientes', 1, 'negocio'),
        ('trabajadores', 'Gestión de trabajadores y empleados', 1, 'negocio'),
        ('servicios', 'Gestión de servicios ofrecidos', 1, 'negocio'),
        ('ventas', 'Gestión de ventas y facturación', 1, 'negocio'),
    ]
    
    for nombre, desc, activo, tipo in modulos:
        cursor.execute('''
        INSERT OR IGNORE INTO modulos (nombre, descripcion, activo_global, tipo_requerido)
        VALUES (?, ?, ?, ?)
        ''', (nombre, desc, activo, tipo))
    
    conn.commit()
    conn.close()
    print("✅ Módulos de negocio agregados a la base de datos")

if __name__ == "__main__":
    add_modules()