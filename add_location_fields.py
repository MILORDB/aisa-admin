import os
import urllib.parse
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def add_location_fields():
    print("🔧 AGREGANDO CAMPOS DE UBICACIÓN A LA TABLA USUARIOS")
    print("=" * 60)
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL no está configurada")
        return
    
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
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
        
        # Verificar y agregar columna latitud
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'latitud'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN latitud REAL")
            print("✅ Columna 'latitud' agregada")
        else:
            print("✅ Columna 'latitud' ya existe")
        
        # Verificar y agregar columna longitud
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'longitud'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN longitud REAL")
            print("✅ Columna 'longitud' agregada")
        else:
            print("✅ Columna 'longitud' ya existe")
        
        # Verificar y agregar columna ubicacion_actualizada
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'ubicacion_actualizada'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN ubicacion_actualizada TEXT")
            print("✅ Columna 'ubicacion_actualizada' agregada")
        else:
            print("✅ Columna 'ubicacion_actualizada' ya existe")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ CAMPOS DE UBICACIÓN AGREGADOS CORRECTAMENTE")
        print("👉 Ahora puedes guardar ubicaciones en el mapa")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_location_fields()
