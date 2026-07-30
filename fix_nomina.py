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
    print("🔧 CREANDO TABLAS PARA NÓMINA")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
        
        # Crear tabla asistencia
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
        
        # Crear tabla nomina
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS nomina (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL,
            trabajador_id INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            ano INTEGER NOT NULL,
            salario_base REAL NOT NULL,
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
        
        # Crear tabla comisiones_trabajador
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
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ TABLAS CREADAS CORRECTAMENTE")
        print("👉 Ahora puedes usar el módulo de nómina")
        
    except psycopg2.Error as e:
        print(f"❌ Error PostgreSQL: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    fix_nomina()
