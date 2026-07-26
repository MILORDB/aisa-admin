import os
import psycopg2
import urllib.parse
import sys

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_db_connection():
    """Obtiene una conexión a PostgreSQL"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL no está configurada")
    
    url = DATABASE_URL.strip()
    if not url.startswith('postgresql://') and not url.startswith('postgres://'):
        url = 'postgresql://' + url
    
    parsed = urllib.parse.urlparse(url)
    
    conn = psycopg2.connect(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/') if parsed.path else '',
        user=parsed.username or '',
        password=parsed.password or '',
        sslmode='require'
    )
    return conn

def fix_ventas_columns():
    print("🔧 AGREGANDO COLUMNAS FALTANTES A VENTAS (PostgreSQL)")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
        
        # Verificar columnas actuales
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ventas'
        """)
        columnas = cursor.fetchall()
        columnas_existentes = [col[0] for col in columnas]
        
        print("📋 Columnas existentes:", columnas_existentes)
        
        # Columnas que deben existir
        columnas_necesarias = [
            ('factura', 'TEXT'),
            ('transferencia_id', 'TEXT'),
            ('transferencia_cedula', 'TEXT'),
            ('transferencia_banco', 'TEXT'),
            ('transferencia_fecha', 'TEXT')
        ]
        
        # Agregar columnas faltantes
        columnas_agregadas = []
        for col, tipo in columnas_necesarias:
            if col not in columnas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE ventas ADD COLUMN {col} {tipo}")
                    print(f"✅ Columna '{col}' agregada correctamente")
                    columnas_agregadas.append(col)
                except psycopg2.Error as e:
                    if "duplicate column" in str(e).lower():
                        print(f"⚠️ Columna '{col}' ya existe")
                    else:
                        print(f"⚠️ Error al agregar '{col}': {e}")
            else:
                print(f"✅ Columna '{col}' ya existe")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        if columnas_agregadas:
            print(f"✅ Columnas agregadas: {', '.join(columnas_agregadas)}")
        else:
            print("✅ Todas las columnas ya existían")
        print("▶️ Reinicia el servidor y prueba nuevamente")
        
    except psycopg2.Error as e:
        print(f"❌ Error PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    fix_ventas_columns()
