import sqlite3
import os

DB_PATH = "E:/AISA/data/usuarios.db"

def fix_contratos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔧 Verificando tabla contratos...")
    
    # Verificar si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contratos'")
    tabla_existe = cursor.fetchone()
    
    if not tabla_existe:
        print("❌ La tabla contratos no existe. Creándola...")
        cursor.execute('''
        CREATE TABLE contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id INTEGER NOT NULL,
            trabajador_id INTEGER,
            empresa TEXT NOT NULL,
            numero_contrato TEXT UNIQUE NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'ventas',
            monto REAL DEFAULT 0,
            estado TEXT DEFAULT 'activo',
            descripcion TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id),
            FOREIGN KEY (trabajador_id) REFERENCES usuarios(id)
        )
        ''')
        print("✅ Tabla contratos creada correctamente")
        conn.commit()
        conn.close()
        return
    
    # Obtener columnas actuales
    cursor.execute("PRAGMA table_info(contratos)")
    columnas = cursor.fetchall()
    columnas_existentes = [col[1] for col in columnas]
    
    print("📋 Columnas existentes:", columnas_existentes)
    
    # Columnas que deben existir
    columnas_necesarias = {
        'empresa': 'TEXT NOT NULL',
        'numero_contrato': 'TEXT UNIQUE NOT NULL',
        'tipo': 'TEXT DEFAULT \'ventas\'',
        'monto': 'REAL DEFAULT 0'
    }
    
    # Agregar columnas faltantes
    for col, tipo in columnas_necesarias.items():
        if col not in columnas_existentes:
            try:
                cursor.execute(f"ALTER TABLE contratos ADD COLUMN {col} {tipo}")
                print(f"✅ Columna '{col}' agregada correctamente")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Error al agregar '{col}': {e}")
        else:
            print(f"✅ Columna '{col}' ya existe")
    
    conn.commit()
    conn.close()
    print("✅ Proceso completado")

if __name__ == "__main__":
    fix_contratos()