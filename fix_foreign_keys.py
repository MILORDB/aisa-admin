# fix_foreign_keys.py
import os
import psycopg2
import urllib.parse

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def fix_foreign_keys():
    """Recrea las tablas con ON DELETE CASCADE"""
    if not DATABASE_URL:
        print("❌ DATABASE_URL no está configurada")
        return False
    
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
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False
    
    try:
        # 1. Eliminar la restricción existente
        print("🔧 Eliminando restricción antigua...")
        cursor.execute("""
            ALTER TABLE sesiones DROP CONSTRAINT IF EXISTS sesiones_usuario_id_fkey;
        """)
        
        # 2. Agregar la nueva restricción con ON DELETE CASCADE
        print("🔧 Agregando nueva restricción con ON DELETE CASCADE...")
        cursor.execute("""
            ALTER TABLE sesiones 
            ADD CONSTRAINT sesiones_usuario_id_fkey 
            FOREIGN KEY (usuario_id) 
            REFERENCES usuarios(id) 
            ON DELETE CASCADE;
        """)
        
        # 3. Verificar que la restricción se aplicó correctamente
        cursor.execute("""
            SELECT conname, confdeltype 
            FROM pg_constraint 
            WHERE conname = 'sesiones_usuario_id_fkey';
        """)
        resultado = cursor.fetchone()
        
        if resultado:
            print(f"✅ Restricción aplicada correctamente: {resultado[0]} (Tipo: {resultado[1]})")
        else:
            print("⚠️ No se pudo verificar la restricción")
        
        conn.commit()
        conn.close()
        print("✅ Base de datos corregida correctamente")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Error SQL: {e}")
        conn.rollback()
        conn.close()
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    fix_foreign_keys()
