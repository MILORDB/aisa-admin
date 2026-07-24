import sqlite3
import os

DB_PATH = "E:/AISA/data/usuarios.db"

def fix_ventas():
    print("🔧 REPARANDO TABLA VENTAS")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar columnas actuales
        cursor.execute("PRAGMA table_info(ventas)")
        columnas = cursor.fetchall()
        columnas_existentes = [col[1] for col in columnas]
        
        print("📋 Columnas existentes:", columnas_existentes)
        
        # Columnas que deben existir
        columnas_necesarias = {
            'empresa': 'TEXT',
            'tipo': "TEXT DEFAULT 'producto'"
        }
        
        # Agregar columnas faltantes
        for col, tipo in columnas_necesarias.items():
            if col not in columnas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE ventas ADD COLUMN {col} {tipo}")
                    print(f"✅ Columna '{col}' agregada correctamente")
                except sqlite3.OperationalError as e:
                    print(f"⚠️ Error al agregar '{col}': {e}")
            else:
                print(f"✅ Columna '{col}' ya existe")
        
        conn.commit()
        conn.close()
        print("\n✅ Tabla ventas reparada correctamente")
        print("▶️ Reinicia el servidor y prueba nuevamente")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_ventas()