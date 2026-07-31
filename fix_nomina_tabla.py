import os
import sys
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor

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

def fix_nomina_tabla():
    """Corrige la estructura de la tabla nomina"""
    print("🔧 REPARANDO TABLA NOMINA")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
        
        # Verificar columnas existentes
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'nomina'
        """)
        columnas = [col[0] for col in cursor.fetchall()]
        print(f"📋 Columnas existentes: {columnas}")
        
        # Columnas necesarias
        columnas_necesarias = {
            'salario_base': 'REAL NOT NULL DEFAULT 0',
            'dias_trabajados': 'INTEGER DEFAULT 0',
            'dias_ausencia': 'INTEGER DEFAULT 0',
            'dias_extras': 'INTEGER DEFAULT 0',
            'salario_devengado': 'REAL DEFAULT 0',
            'comisiones': 'REAL DEFAULT 0',
            'total': 'REAL DEFAULT 0'
        }
        
        # Agregar columnas faltantes
        for col, tipo in columnas_necesarias.items():
            if col not in columnas:
                try:
                    cursor.execute(f"ALTER TABLE nomina ADD COLUMN {col} {tipo}")
                    print(f"✅ Columna '{col}' agregada")
                except psycopg2.Error as e:
                    print(f"⚠️ Error al agregar '{col}': {e}")
        
        # Verificar que la tabla tenga la estructura correcta
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'nomina'
            ORDER BY ordinal_position
        """)
        columnas_final = cursor.fetchall()
        
        print("\n📋 Estructura final de la tabla nomina:")
        for col, tipo in columnas_final:
            print(f"   • {col} ({tipo})")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ TABLA NOMINA REPARADA CORRECTAMENTE")
        print("👉 Visita /negocio/nomina para probar")
        
    except psycopg2.Error as e:
        print(f"❌ Error PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    fix_nomina_tabla()
