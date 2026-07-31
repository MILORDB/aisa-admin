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

def fix_admin_permissions():
    print("🔧 REPARANDO PERMISOS DEL ADMIN")
    print("=" * 50)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("✅ Conectado a PostgreSQL")
        
        # 1. Verificar que existe el admin
        cursor.execute("SELECT * FROM usuarios WHERE rol = 'admin'")
        admin = cursor.fetchone()
        
        if not admin:
            print("❌ No hay usuario admin en la base de datos")
            print("   Ejecuta primero: python init_db_auto.py")
            conn.close()
            return
        
        admin_id = admin['id']
        print(f"✅ Admin encontrado: {admin['username']} (ID: {admin_id})")
        
        # 2. Verificar módulos existentes
        cursor.execute("SELECT * FROM modulos ORDER BY id")
        modulos = cursor.fetchall()
        
        if not modulos:
            print("⚠️ No hay módulos en la base de datos. Creándolos...")
            
            modulos_list = [
                ('voz', 'Texto a voz y reconocimiento de voz', 1, 'ambos'),
                ('control_pc', 'Control de mouse, teclado y programas', 1, 'negocio'),
                ('busqueda_web', 'Búsqueda en internet con DeepSeek', 1, 'ambos'),
                ('memoria', 'Memoria vectorial para recordar conversaciones', 1, 'ambos'),
                ('archivos', 'Lectura de archivos PDF, Word, Excel', 1, 'negocio'),
                ('contexto', 'Contexto de conversación', 1, 'ambos'),
                ('android', 'Conexión con dispositivos Android', 1, 'negocio'),
                ('inventario', 'Gestión de inventario y productos', 1, 'negocio'),
                ('tienda', 'Tienda online para clientes', 1, 'negocio'),
                ('trabajadores', 'Gestión de trabajadores y empleados', 1, 'negocio'),
                ('servicios', 'Gestión de servicios ofrecidos', 1, 'negocio'),
                ('ventas', 'Gestión de ventas y facturación', 1, 'negocio'),
                ('contratos', 'Gestión de contratos con clientes', 1, 'negocio'),
                ('nomina', 'Gestión de nómina y salarios', 1, 'negocio'),
            ]
            
            for nombre, desc, activo, tipo in modulos_list:
                cursor.execute('''
                    INSERT INTO modulos (nombre, descripcion, activo_global, tipo_requerido)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (nombre) DO NOTHING
                ''', (nombre, desc, activo, tipo))
            
            conn.commit()
            print("✅ Módulos creados")
            
            # Recargar módulos
            cursor.execute("SELECT * FROM modulos ORDER BY id")
            modulos = cursor.fetchall()
        
        print(f"📋 Módulos encontrados: {len(modulos)}")
        for m in modulos:
            print(f"   - {m['nombre']} (ID: {m['id']})")
        
        # 3. Eliminar permisos antiguos del admin
        cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (admin_id,))
        print(f"🗑️ Permisos antiguos eliminados para admin ID {admin_id}")
        
        # 4. Asignar todos los módulos al admin
        for mod in modulos:
            cursor.execute('''
                INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                VALUES (%s, %s, 1, 'aprobado')
            ''', (admin_id, mod['id']))
            print(f"   ✅ Asignado: {mod['nombre']}")
        
        conn.commit()
        print(f"✅ {len(modulos)} permisos asignados al admin")
        
        # 5. Verificar que el admin tenga rol 'admin'
        cursor.execute('''
            UPDATE usuarios 
            SET rol = 'admin', tipo = 'admin', activo = 1, aprobado = 1
            WHERE id = %s
        ''', (admin_id,))
        conn.commit()
        print("✅ Rol y tipo del admin actualizados")
        
        # 6. Verificar los permisos finales
        cursor.execute('''
            SELECT m.nombre, p.activo, p.estado_solicitud
            FROM modulos m
            LEFT JOIN permisos_usuario p ON m.id = p.modulo_id AND p.usuario_id = %s
            ORDER BY m.nombre
        ''', (admin_id,))
        
        permisos = cursor.fetchall()
        
        print("\n📋 PERMISOS FINALES DEL ADMIN:")
        print("-" * 50)
        for p in permisos:
            estado = "✅ ACTIVO" if p['activo'] == 1 else "❌ INACTIVO"
            print(f"   {p['nombre']}: {estado}")
        print("-" * 50)
        
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ PERMISOS DEL ADMIN REPARADOS")
        print("👉 Cierra sesión y vuelve a iniciar sesión para ver los cambios")
        print("👤 Usuario: admin")
        print("🔑 Contraseña: admin123")
        
    except psycopg2.Error as e:
        print(f"❌ Error PostgreSQL: {e}")
        conn.rollback()
        conn.close()
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_admin_permissions()
