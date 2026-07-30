import os
import sys
import urllib.parse
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL no está configurada")
    
    url = DATABASE_URL.strip()
    if not url.startswith('postgresql://') and not url.startswith('postgres://'):
        url = 'postgresql://' + url
    
    parsed = urllib.parse.urlparse(url)
    
    try:
        conn = psycopg2.connect(
            host=parsed.hostname or 'localhost',
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/') if parsed.path else '',
            user=parsed.username or '',
            password=parsed.password or '',
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        raise

def fix_comision():
    print("🔧 AGREGANDO COLUMNA 'comision' A LA TABLA productos")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
        
        # Verificar si la columna existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'comision'
        """)
        existe = cursor.fetchone()
        
        if not existe:
            print("🔧 Agregando columna 'comision'...")
            cursor.execute("ALTER TABLE productos ADD COLUMN comision REAL DEFAULT 0")
            conn.commit()
            print("✅ Columna 'comision' agregada correctamente")
        else:
            print("✅ La columna 'comision' ya existe")
        
        # Actualizar productos con comision NULL a 0
        cursor.execute("UPDATE productos SET comision = 0 WHERE comision IS NULL")
        filas = cursor.rowcount
        conn.commit()
        
        if filas > 0:
            print(f"✅ {filas} productos actualizados con comisión = 0")
        
        # Mostrar columnas
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'productos'
            ORDER BY ordinal_position
        """)
        columnas = cursor.fetchall()
        
        print("\n📋 Columnas en 'productos':")
        for col, tipo in columnas:
            print(f"   • {col} ({tipo})")
        
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ PROCESO COMPLETADO")
        print("👉 Ahora puedes usar el campo 'comisión' en el inventario")
        
    except psycopg2.Error as e:
        print(f"❌ Error PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    fix_comision()
