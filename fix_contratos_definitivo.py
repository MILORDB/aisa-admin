import sqlite3
import os

DB_PATH = "E:/AISA/data/usuarios.db"

def recreate_contratos():
    print("🔧 SOLUCIÓN DEFINITIVA PARA CONTRATOS")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("1. Eliminando tabla contratos si existe...")
        cursor.execute("DROP TABLE IF EXISTS contratos")
        
        print("2. Creando tabla contratos con estructura correcta...")
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
        
        conn.commit()
        print("✅ Tabla contratos creada correctamente")
        
        print("\n3. Verificando estructura de la tabla...")
        cursor.execute("PRAGMA table_info(contratos)")
        columnas = cursor.fetchall()
        print("\n📋 Columnas de la tabla contratos:")
        for col in columnas:
            print(f"   - {col[1]} ({col[2]})")
        
        conn.close()
        print("\n✅ SOLUCIÓN APLICADA CON ÉXITO")
        print("▶️ Reinicia el servidor y prueba nuevamente")
        
    except sqlite3.Error as e:
        print(f"❌ Error SQLite: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    recreate_contratos()