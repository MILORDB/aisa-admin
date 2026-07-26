import os
import sys
import psycopg2
import urllib.parse

def get_db_connection():
    """Obtiene una conexión a la base de datos PostgreSQL en Render"""
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL no está configurada")
        print("   Asegúrate de que la variable de entorno esté configurada en Render")
        return None
    
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
        return None

def fix_ventas_columns():
    """Agrega las columnas faltantes a la tabla ventas"""
    print("🔧 REPARANDO TABLA VENTAS EN RENDER")
    print("=" * 50)
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL en Render")
        
        # Verificar columnas actuales
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ventas'
            ORDER BY ordinal_position
        """)
        columnas = cursor.fetchall()
        columnas_existentes = [col[0] for col in columnas]
        
        print("\n📋 Columnas existentes en 'ventas':")
        for i, col in enumerate(columnas_existentes):
            print(f"   {i+1}. {col}")
        
        # Columnas que deben existir
        columnas_necesarias = [
            ('factura', 'TEXT'),
            ('transferencia_id', 'TEXT'),
            ('transferencia_cedula', 'TEXT'),
            ('transferencia_banco', 'TEXT'),
            ('transferencia_fecha', 'TEXT')
        ]
        
        print("\n🔧 Agregando columnas faltantes...")
        columnas_agregadas = []
        errores = []
        
        for col, tipo in columnas_necesarias:
            if col not in columnas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE ventas ADD COLUMN {col} {tipo}")
                    columnas_agregadas.append(col)
                    print(f"   ✅ Columna '{col}' agregada correctamente")
                except psycopg2.Error as e:
                    if "duplicate column" in str(e).lower():
                        print(f"   ⚠️ Columna '{col}' ya existe")
                    else:
                        errores.append(f"   ❌ Error al agregar '{col}': {e}")
                        print(f"   ❌ Error al agregar '{col}': {e}")
            else:
                print(f"   ✅ Columna '{col}' ya existe")
        
        if errores:
            print("\n⚠️ Se encontraron errores al agregar algunas columnas:")
            for err in errores:
                print(err)
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        if columnas_agregadas:
            print(f"✅ Columnas agregadas: {', '.join(columnas_agregadas)}")
        else:
            print("✅ Todas las columnas ya existían")
        print("✅ Reparación completada correctamente")
        print("▶️ Reinicia el servidor o prueba la funcionalidad de ventas")
        
        return True
        
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

def verificar_ventas():
    """Verifica que la tabla ventas tenga todas las columnas necesarias"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Verificar columnas
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'ventas'
            ORDER BY ordinal_position
        """)
        columnas = cursor.fetchall()
        
        print("\n📋 ESTRUCTURA ACTUAL DE LA TABLA VENTAS:")
        print("-" * 40)
        for col, tipo in columnas:
            print(f"   {col}: {tipo}")
        print("-" * 40)
        
        # Contar filas
        cursor.execute("SELECT COUNT(*) FROM ventas")
        count = cursor.fetchone()[0]
        print(f"📊 Total de registros en ventas: {count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error al verificar: {e}")

def main():
    print("=" * 50)
    print("🛠️  REPARADOR DE VENTAS PARA RENDER")
    print("=" * 50)
    
    print("\n1. Ejecutando reparación de columnas...")
    exito = fix_ventas_columns()
    
    if exito:
        print("\n2. Verificando estructura final...")
        verificar_ventas()
        
        print("\n" + "=" * 50)
        print("✅ PROCESO COMPLETADO CON ÉXITO")
        print("👉 Ahora puedes probar el módulo de ventas")
    else:
        print("\n" + "=" * 50)
        print("❌ EL PROCESO FALLÓ")
        print("👉 Revisa los errores arriba y verifica la conexión a la base de datos")

if __name__ == "__main__":
    main()
