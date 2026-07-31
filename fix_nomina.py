import os
import sys
import urllib.parse
import psycopg2
from datetime import datetime

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

def fix_nomina():
    print("🔧 REPARANDO TABLAS DE NÓMINA")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
        
        # 1. Verificar/crear tabla asistencia
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS asistencia (
            id SERIAL PRIMARY KEY,
            trabajador_id INTEGER NOT NULL,
            negocio_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            presente INTEGER DEFAULT 1,
            horas_trabajadas REAL DEFAULT 8,
            created_at TEXT NOT NULL,
            FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(trabajador_id, fecha)
        )
        ''')
        print("✅ Tabla 'asistencia' creada/verificada")
        
        # 2. Verificar/crear tabla nomina
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS nomina (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL,
            trabajador_id INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            ano INTEGER NOT NULL,
            salario_base REAL NOT NULL DEFAULT 0,
            dias_trabajados INTEGER DEFAULT 0,
            dias_ausencia INTEGER DEFAULT 0,
            dias_extras INTEGER DEFAULT 0,
            salario_devengado REAL DEFAULT 0,
            comisiones REAL DEFAULT 0,
            total REAL DEFAULT 0,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(negocio_id, trabajador_id, mes, ano)
        )
        ''')
        print("✅ Tabla 'nomina' creada/verificada")
        
        # 3. Verificar/crear tabla comisiones_trabajador
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS comisiones_trabajador (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL,
            trabajador_id INTEGER NOT NULL,
            venta_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            monto REAL NOT NULL,
            fecha TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
        )
        ''')
        print("✅ Tabla 'comisiones_trabajador' creada/verificada")
        
        # 4. Verificar columnas de productos (comision)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'comision'
        """)
        existe_comision = cursor.fetchone()
        
        if not existe_comision:
            print("🔧 Agregando columna 'comision' a productos...")
            cursor.execute("ALTER TABLE productos ADD COLUMN comision REAL DEFAULT 0")
            print("✅ Columna 'comision' agregada")
        
        # 5. Verificar columnas de nomina
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'nomina'
        """)
        columnas = [col[0] for col in cursor.fetchall()]
        
        columnas_necesarias = [
            ('salario_base', 'REAL NOT NULL DEFAULT 0'),
            ('dias_trabajados', 'INTEGER DEFAULT 0'),
            ('dias_ausencia', 'INTEGER DEFAULT 0'),
            ('dias_extras', 'INTEGER DEFAULT 0'),
            ('salario_devengado', 'REAL DEFAULT 0'),
            ('comisiones', 'REAL DEFAULT 0'),
            ('total', 'REAL DEFAULT 0')
        ]
        
        for col, tipo in columnas_necesarias:
            if col not in columnas:
                try:
                    cursor.execute(f"ALTER TABLE nomina ADD COLUMN {col} {tipo}")
                    print(f"✅ Columna '{col}' agregada")
                except Exception as e:
                    print(f"⚠️ Error al agregar '{col}': {e}")
        
        # 6. Verificar que los trabajadores tengan salario
        cursor.execute('''
            SELECT u.id, u.nombre, u.datos_negocio
            FROM usuarios u
            WHERE u.rol = 'trabajador'
        ''')
        trabajadores = cursor.fetchall()
        
        for t in trabajadores:
            datos = {}
            if t[2]:
                try:
                    import json
                    datos = json.loads(t[2]) if isinstance(t[2], str) else t[2]
                except:
                    pass
            
            if not datos.get('salario') or datos.get('salario') == 0:
                print(f"⚠️ El trabajador '{t[1]}' no tiene salario asignado")
                print(f"   Actualiza su perfil o ejecuta: UPDATE usuarios SET datos_negocio = '{{\"salario\": 1000}}' WHERE id = {t[0]}")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ REPARACIÓN COMPLETADA")
        print("👉 Ahora puedes calcular la nómina")
        print("👉 Recuerda asignar salario a los trabajadores en su perfil")
        
    except psycopg2.Error as e:
        print(f"❌ Error PostgreSQL: {e}")
        conn.rollback()
        conn.close()
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_nomina()
