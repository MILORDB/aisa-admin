import sqlite3
import os

DB_PATH = "E:/AISA/data/usuarios.db"

def fix_columns():
    print("🔧 AGREGANDO COLUMNAS FALTANTES")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar columnas en productos
        cursor.execute("PRAGMA table_info(productos)")
        columnas_productos = [col[1] for col in cursor.fetchall()]
        print("📋 Columnas en productos:", columnas_productos)
        
        # Agregar columnas a productos
        columnas_faltantes_productos = []
        if 'foto_url' not in columnas_productos:
            cursor.execute("ALTER TABLE productos ADD COLUMN foto_url TEXT")
            columnas_faltantes_productos.append('foto_url')
            print("✅ Columna 'foto_url' agregada a productos")
        
        if 'foto_public_id' not in columnas_productos:
            cursor.execute("ALTER TABLE productos ADD COLUMN foto_public_id TEXT")
            columnas_faltantes_productos.append('foto_public_id')
            print("✅ Columna 'foto_public_id' agregada a productos")
        
        # Verificar columnas en ventas
        cursor.execute("PRAGMA table_info(ventas)")
        columnas_ventas = [col[1] for col in cursor.fetchall()]
        print("📋 Columnas en ventas:", columnas_ventas)
        
        # Agregar columna a ventas
        if 'factura_url' not in columnas_ventas:
            cursor.execute("ALTER TABLE ventas ADD COLUMN factura_url TEXT")
            print("✅ Columna 'factura_url' agregada a ventas")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 40)
        print("✅ Todas las columnas fueron agregadas correctamente")
        print("▶️ Reinicia el servidor y prueba nuevamente")
        
    except sqlite3.Error as e:
        print(f"❌ Error SQLite: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    fix_columns()