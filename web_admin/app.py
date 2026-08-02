from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from flask_cors import CORS
import os
import sys
import logging
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import traceback
import time
from datetime import datetime, timedelta
import io
from functools import wraps

# ============================================
# CONFIGURACIÓN DE LOGGING
# ============================================
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN DE RUTAS
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ============================================
# CREAR CARPETAS PARA ARCHIVOS ESTÁTICOS
# ============================================
try:
    os.makedirs(os.path.join(BASE_DIR, 'static/uploads/productos'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static/uploads/facturas'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static/img'), exist_ok=True)
    print("📁 Carpetas de almacenamiento creadas/verificadas")
except Exception as e:
    print(f"⚠️ Error creando carpetas: {e}")

# ============================================
# IMPORTAR FUNCIONES DE LA BASE DE DATOS
# ============================================
try:
    from database import (
        init_db, crear_usuario, obtener_usuario_por_username,
        obtener_usuario_por_id, obtener_todos_usuarios,
        obtener_negocios, eliminar_usuario,
        obtener_trabajadores_por_empresa, obtener_trabajador_por_id,
        verify_password, actualizar_ultimo_acceso,
        toggle_usuario, actualizar_rol_usuario, actualizar_tipo_usuario,
        obtener_modulos, obtener_permisos_usuario,
        asignar_permiso_usuario, toggle_modulo_global,
        registrar_log, obtener_logs,
        solicitar_modulo, obtener_solicitudes_pendientes,
        aprobar_solicitud, rechazar_solicitud,
        actualizar_datos_negocio, get_db,
        hash_password,
        crear_producto, obtener_productos, actualizar_producto, eliminar_producto,
        obtener_todos_productos, obtener_productos_con_stock, actualizar_stock_producto,
        obtener_productos_tienda,
        agregar_producto_tienda, toggle_destacado_tienda, eliminar_producto_tienda,
        crear_venta, obtener_ventas, obtener_todas_ventas, obtener_estadisticas_ventas, 
        eliminar_venta_con_reintegro,
        actualizar_estado_venta,
        crear_servicio, obtener_servicios, obtener_todos_servicios, toggle_servicio, eliminar_servicio,
        obtener_estadisticas_trabajador,
        crear_trabajador_negocio, toggle_trabajador_negocio, actualizar_trabajador_negocio,
        obtener_trabajadores_pendientes, aprobar_trabajador, rechazar_trabajador,
        actualizar_foto_producto, eliminar_foto_producto,
        crear_contrato, obtener_contratos, obtener_todos_contratos, 
        actualizar_contrato, actualizar_estado_contrato, eliminar_contrato,
        obtener_ultimo_numero_contrato, obtener_datos_negocio,
        obtener_estadisticas_productos,
        obtener_nomina_mes, calcular_nomina, obtener_nomina_trabajador,
        obtener_comisiones_trabajador_mes, obtener_comisiones_negocio_mes,
        registrar_comision, obtener_resumen_nomina,
        obtener_negocio_de_trabajador,
        obtener_dias_trabajados_mes, obtener_dias_ausencia_mes, obtener_dias_extras_mes,
        obtener_total_comisiones_mes,
        obtener_modulos_negocio, obtener_modulos_trabajador,
        actualizar_ubicacion_usuario, obtener_ubicacion_usuario, obtener_negocios_con_ubicacion
    )
    from auth import crear_sesion, verificar_sesion, obtener_usuario_sesion
    from storage import get_storage_manager
    from reportes import GeneradorReportes
    print("✅ Módulos importados correctamente")
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    traceback.print_exc()
    try:
        from web_admin.database import *
        from web_admin.auth import crear_sesion, verificar_sesion, obtener_usuario_sesion
        from web_admin.storage import get_storage_manager
        from web_admin.reportes import GeneradorReportes
        print("✅ Módulos importados desde web_admin")
    except ImportError as e2:
        print(f"❌ Error importando desde web_admin: {e2}")
        traceback.print_exc()

# ============================================
# CREAR APLICACIÓN FLASK
# ============================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
CORS(app)

# ============================================
# CONFIGURACIÓN DE CACHÉ (ANTI-CACHÉ)
# ============================================
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ============================================
# DECORADORES
# ============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect(url_for('login'))
        try:
            usuario = obtener_usuario_sesion(token)
            if not usuario:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ Error en login_required: {e}")
            return redirect(url_for('login'))
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect(url_for('login'))
        try:
            usuario = obtener_usuario_sesion(token)
            if not usuario or usuario.get('rol') != 'admin':
                return jsonify({'error': 'Acceso denegado'}), 403
            return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ Error en admin_required: {e}")
            return jsonify({'error': 'Error de autenticación'}), 401
    return decorated_function

# ============================================
# ENDPOINT PARA REPARAR ADMIN (URL DIRECTA)
# ============================================
@app.route('/fix-admin', methods=['GET'])
def fix_admin_endpoint():
    """Endpoint para reparar el admin - URL directa /fix-admin"""
    try:
        import urllib.parse
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import bcrypt
        from datetime import datetime
        
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        if not DATABASE_URL:
            return "<h1 style='color:#ff6b6b;'>❌ DATABASE_URL no está configurada</h1>", 500
        
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
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("✅ Conectado a PostgreSQL - Reparando admin...")
        
        mensajes = []
        
        # 1. Verificar/Crear admin
        cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
        admin = cursor.fetchone()
        
        if admin:
            mensajes.append(f"✅ Admin encontrado: {admin['username']} (ID: {admin['id']})")
            admin_id = admin['id']
        else:
            mensajes.append("⚠️ Admin no encontrado, creándolo...")
            password = "admin123"
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            fecha = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1)
                RETURNING id
            ''', ('admin', 'admin@aisa.com', password_hash, 'Administrador', 'admin', 'admin', fecha))
            
            admin_id = cursor.fetchone()['id']
            conn.commit()
            mensajes.append(f"✅ Admin creado con ID: {admin_id}")
        
        # 2. FORZAR rol y tipo a 'admin'
        cursor.execute('''
            UPDATE usuarios 
            SET rol = 'admin', tipo = 'admin', activo = 1, aprobado = 1
            WHERE id = %s
        ''', (admin_id,))
        conn.commit()
        mensajes.append("✅ Rol y tipo forzados a 'admin'")
        
        # 3. Verificar módulos
        cursor.execute("SELECT * FROM modulos")
        modulos = cursor.fetchall()
        
        if not modulos:
            mensajes.append("⚠️ No hay módulos. Creándolos...")
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
                ('mapa', 'Ubicación en mapa interactivo', 1, 'negocio'),
            ]
            
            for nombre, desc, activo, tipo in modulos_list:
                cursor.execute('''
                    INSERT INTO modulos (nombre, descripcion, activo_global, tipo_requerido)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (nombre) DO NOTHING
                ''', (nombre, desc, activo, tipo))
            
            conn.commit()
            mensajes.append("✅ Módulos creados")
            
            cursor.execute("SELECT * FROM modulos")
            modulos = cursor.fetchall()
        
        mensajes.append(f"📋 Módulos encontrados: {len(modulos)}")
        
        # 4. Eliminar permisos antiguos
        cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (admin_id,))
        mensajes.append("🗑️ Permisos antiguos eliminados")
        
        # 5. Asignar todos los módulos al admin
        for mod in modulos:
            cursor.execute('''
                INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                VALUES (%s, %s, 1, 'aprobado')
            ''', (admin_id, mod['id']))
        
        conn.commit()
        mensajes.append(f"✅ {len(modulos)} permisos asignados al admin")
        
        # 6. Verificar final
        cursor.execute("SELECT id, username, rol, tipo, activo FROM usuarios WHERE id = %s", (admin_id,))
        admin_final = cursor.fetchone()
        
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        
        return f"""
        <html>
            <head>
                <title>Admin Reparado</title>
                <style>
                    body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                    .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                    .success {{ color: #6bff6b; }}
                    .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                    .btn-primary {{ background: #6c3ce0; color: #fff; }}
                    .btn-primary:hover {{ background: #5a2ec0; }}
                    .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                    .btn-secondary:hover {{ background: #3a3a4e; }}
                    .result-box {{ background: #0f0f1a; border-radius: 8px; padding: 12px; border: 1px solid #2a2a3e; margin-top: 12px; }}
                    .result-box .row {{ display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #1a1a2e; }}
                    .result-box .row:last-child {{ border-bottom: none; }}
                    .result-box .label {{ color: #888; }}
                    .result-box .value {{ color: #fff; font-weight: 600; }}
                    .result-box .value.ok {{ color: #6bff6b; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Admin</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        {html_mensajes}
                    </div>
                    
                    <div class="card">
                        <h3>📋 Datos del Admin</h3>
                        <div class="result-box">
                            <div class="row">
                                <span class="label">👤 Usuario</span>
                                <span class="value ok">{admin_final['username']}</span>
                            </div>
                            <div class="row">
                                <span class="label">🔑 Rol</span>
                                <span class="value ok">{admin_final['rol']}</span>
                            </div>
                            <div class="row">
                                <span class="label">📋 Tipo</span>
                                <span class="value ok">{admin_final['tipo']}</span>
                            </div>
                            <div class="row">
                                <span class="label">✅ Activo</span>
                                <span class="value ok">{'Sí' if admin_final['activo'] == 1 else 'No'}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div>
                        <a href="/logout" class="btn btn-primary">🚪 Cerrar sesión</a>
                        <a href="/login" class="btn btn-secondary">🔑 Iniciar sesión</a>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 16px; background: #0f0f1a; border-radius: 8px; border: 1px solid #2a2a3e;">
                        <p style="color: #888;">👤 Usuario: <strong style="color:#6c3ce0;">admin</strong></p>
                        <p style="color: #888;">🔑 Contraseña: <strong style="color:#6c3ce0;">admin123</strong></p>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/login" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Login</a>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINT PARA REPARAR UBICACIÓN (VIA WEB)
# ============================================
@app.route('/fix-ubicacion', methods=['GET'])
def fix_ubicacion():
    """Endpoint para agregar campos de ubicación a la tabla usuarios"""
    try:
        import urllib.parse
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        if not DATABASE_URL:
            return "<h1 style='color:#ff6b6b;'>❌ DATABASE_URL no está configurada</h1>", 500
        
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
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL - Agregando campos de ubicación...")
        
        mensajes = []
        
        # Verificar y agregar columna latitud
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'latitud'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN latitud REAL")
            mensajes.append("✅ Columna 'latitud' agregada")
        else:
            mensajes.append("✅ Columna 'latitud' ya existe")
        
        # Verificar y agregar columna longitud
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'longitud'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN longitud REAL")
            mensajes.append("✅ Columna 'longitud' agregada")
        else:
            mensajes.append("✅ Columna 'longitud' ya existe")
        
        # Verificar y agregar columna ubicacion_actualizada
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'ubicacion_actualizada'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN ubicacion_actualizada TEXT")
            mensajes.append("✅ Columna 'ubicacion_actualizada' agregada")
        else:
            mensajes.append("✅ Columna 'ubicacion_actualizada' ya existe")
        
        conn.commit()
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        
        return f"""
        <html>
            <head>
                <title>Campos de Ubicación Agregados</title>
                <style>
                    body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                    .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                    .success {{ color: #6bff6b; }}
                    .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                    .btn-primary {{ background: #6c3ce0; color: #fff; }}
                    .btn-primary:hover {{ background: #5a2ec0; }}
                    .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                    .btn-secondary:hover {{ background: #3a3a4e; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Campos de Ubicación</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        {html_mensajes}
                    </div>
                    
                    <div>
                        <a href="/negocio/mapa" class="btn btn-primary">🗺️ Ir al Mapa</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINT PARA REPARAR MÓDULOS (VIA WEB)
# ============================================
@app.route('/fix-modulos-web', methods=['GET'])
def fix_modulos_web():
    """Endpoint para reparar módulos desde el navegador"""
    try:
        import urllib.parse
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        if not DATABASE_URL:
            return "<h1 style='color:#ff6b6b;'>❌ DATABASE_URL no está configurada</h1>", 500
        
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
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("✅ Conectado a PostgreSQL - Reparando módulos...")
        
        mensajes = []
        acciones = []
        
        # 1. Verificar/Crear módulo mapa
        cursor.execute("SELECT * FROM modulos WHERE nombre = 'mapa'")
        mapa = cursor.fetchone()
        
        if not mapa:
            cursor.execute('''
                INSERT INTO modulos (nombre, descripcion, activo_global, tipo_requerido)
                VALUES ('mapa', 'Ubicación en mapa interactivo', 1, 'negocio')
                RETURNING id
            ''')
            mapa_id = cursor.fetchone()['id']
            mensajes.append("✅ Módulo 'mapa' creado")
            acciones.append("creado")
        else:
            mapa_id = mapa['id']
            mensajes.append("✅ Módulo 'mapa' ya existe")
            acciones.append("existente")
        
        # 2. Activar globalmente
        cursor.execute("UPDATE modulos SET activo_global = 1 WHERE id = %s", (mapa_id,))
        mensajes.append("✅ Módulo 'mapa' activado globalmente")
        
        # 3. Asignar a todos los usuarios
        cursor.execute("SELECT id, username, rol, tipo FROM usuarios")
        usuarios = cursor.fetchall()
        
        asignados = 0
        for u in usuarios:
            cursor.execute("SELECT id FROM permisos_usuario WHERE usuario_id = %s AND modulo_id = %s", (u['id'], mapa_id))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                    VALUES (%s, %s, 1, 'aprobado')
                ''', (u['id'], mapa_id))
                asignados += 1
        
        conn.commit()
        mensajes.append(f"✅ Módulo 'mapa' asignado a {asignados} usuarios")
        
        # 4. Verificar módulos existentes
        cursor.execute("SELECT * FROM modulos ORDER BY nombre")
        modulos = cursor.fetchall()
        
        # 5. Verificar permisos totales
        cursor.execute("SELECT COUNT(*) FROM permisos_usuario WHERE modulo_id = %s", (mapa_id,))
        total_permisos = cursor.fetchone()['count']
        
        conn.close()
        
        html_modulos = ""
        for m in modulos:
            activo = "✅ Activo" if m['activo_global'] == 1 else "❌ Inactivo"
            html_modulos += f"<li><strong>{m['nombre']}</strong> - {m['descripcion']} - {activo}</li>"
        
        return f"""
        <html>
            <head>
                <title>Módulos Reparados</title>
                <style>
                    body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                    .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                    .success {{ color: #6bff6b; }}
                    .warning {{ color: #ffbb33; }}
                    .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                    .btn-primary {{ background: #6c3ce0; color: #fff; }}
                    .btn-primary:hover {{ background: #5a2ec0; }}
                    .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                    .btn-secondary:hover {{ background: #3a3a4e; }}
                    .btn-success {{ background: #4caf50; color: #fff; }}
                    .btn-success:hover {{ background: #3d8b40; }}
                    ul {{ list-style: none; padding: 0; }}
                    ul li {{ padding: 4px 0; border-bottom: 1px solid #1a1a2e; }}
                    .result-box {{ background: #0f0f1a; border-radius: 8px; padding: 12px; border: 1px solid #2a2a3e; margin-top: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Módulos</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        <ul>
                            {''.join([f'<li>✅ {m}</li>' for m in mensajes])}
                        </ul>
                        <div class="result-box">
                            <p>📊 Total de permisos para 'mapa': <strong>{total_permisos}</strong></p>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h3>📋 Todos los Módulos del Sistema</h3>
                        <ul>
                            {html_modulos}
                        </ul>
                    </div>
                    
                    <div>
                        <a href="/admin/db" class="btn btn-primary">🗄️ Ir al Gestor DB</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 16px; background: #0f0f1a; border-radius: 8px; border: 1px solid #2a2a3e;">
                        <p style="color: #888;">ℹ️ Si el módulo 'mapa' sigue sin aparecer, recarga la página (Ctrl+F5)</p>
                        <p style="color: #888;">🔍 Visita <a href="/debug/mis-modulos" style="color:#6c3ce0;">/debug/mis-modulos</a> para ver tus permisos</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINT PARA DEBUG DE MÓDULOS DEL USUARIO
# ============================================
@app.route('/debug/mis-modulos', methods=['GET'])
@login_required
def debug_mis_modulos():
    """Endpoint para depurar módulos del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Todos los módulos
    cursor.execute("SELECT * FROM modulos ORDER BY nombre")
    todos_modulos = cursor.fetchall()
    
    # Módulos con permisos del usuario
    cursor.execute('''
        SELECT m.id, m.nombre, m.descripcion, m.activo_global, p.activo as permiso_activo
        FROM modulos m
        LEFT JOIN permisos_usuario p ON m.id = p.modulo_id AND p.usuario_id = %s
        ORDER BY m.nombre
    ''', (usuario['id'],))
    mis_modulos = cursor.fetchall()
    
    conn.close()
    
    # Generar HTML para mostrar
    html = """
    <html>
        <head>
            <title>Mis Módulos - Debug</title>
            <style>
                body { background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }
                .container { max-width: 800px; margin: 0 auto; }
                .card { background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }
                .card h3 { color: #aaa; margin-bottom: 10px; }
                .success { color: #6bff6b; }
                .danger { color: #ff6b6b; }
                .warning { color: #ffbb33; }
                .modulo-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1a1a2e; }
                .modulo-item .nombre { font-weight: 600; }
                .modulo-item .estado { font-size: 12px; padding: 2px 10px; border-radius: 10px; }
                .modulo-item .estado.activo { background: #224422; color: #6bff6b; }
                .modulo-item .estado.inactivo { background: #442222; color: #ff6b6b; }
                .btn { display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }
                .btn-primary { background: #6c3ce0; color: #fff; }
                .btn-primary:hover { background: #5a2ec0; }
                .btn-secondary { background: #2a2a3e; color: #fff; }
                .btn-secondary:hover { background: #3a3a4e; }
                .usuario-info { background: #0f0f1a; border-radius: 8px; padding: 12px; border: 1px solid #2a2a3e; margin-bottom: 16px; }
                .usuario-info .row { display: flex; justify-content: space-between; padding: 4px 0; }
                .usuario-info .label { color: #888; }
                .usuario-info .value { font-weight: 600; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 style="color:#6c3ce0;">🔍 Mis Módulos</h1>
                
                <div class="card">
                    <h3>👤 Información del Usuario</h3>
                    <div class="usuario-info">
                        <div class="row">
                            <span class="label">ID</span>
                            <span class="value">{usuario_id}</span>
                        </div>
                        <div class="row">
                            <span class="label">Usuario</span>
                            <span class="value">{username}</span>
                        </div>
                        <div class="row">
                            <span class="label">Rol</span>
                            <span class="value">{rol}</span>
                        </div>
                        <div class="row">
                            <span class="label">Tipo</span>
                            <span class="value">{tipo}</span>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📋 Mis Módulos</h3>
                    <div id="modulosList">
    """.format(
        usuario_id=usuario['id'],
        username=usuario['username'],
        rol=usuario['rol'],
        tipo=usuario['tipo']
    )
    
    for m in mis_modulos:
        estado = "activo" if m.get('permiso_activo') == 1 else "inactivo"
        estado_text = "✅ Activo" if m.get('permiso_activo') == 1 else "❌ Inactivo"
        global_text = "🌍 Global: " + ("✅" if m['activo_global'] == 1 else "❌")
        
        html += f"""
        <div class="modulo-item">
            <span class="nombre">{m['nombre']} <span style="font-size:10px;color:#888;">{m['descripcion'] or ''}</span></span>
            <div>
                <span style="font-size:10px;color:#666;margin-right:10px;">{global_text}</span>
                <span class="estado {estado}">{estado_text}</span>
            </div>
        </div>
        """
    
    html += """
                    </div>
                </div>
                
                <div class="card">
                    <h3>🔧 Acciones</h3>
                    <div>
                        <a href="/fix-modulos-web" class="btn btn-primary">🔧 Reparar Módulos</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                </div>
                
                <div style="margin-top: 20px; padding: 16px; background: #0f0f1a; border-radius: 8px; border: 1px solid #2a2a3e;">
                    <p style="color: #888;">📌 Si el módulo 'mapa' no aparece como activo, visita:</p>
                    <p style="color: #6c3ce0;"><a href="/fix-modulos-web" style="color:#6c3ce0;">/fix-modulos-web</a></p>
                </div>
            </div>
        </body>
    </html>
    """
    
    return html

# ============================================
# ENDPOINT PARA REPARAR MÓDULOS
# ============================================
@app.route('/fix-modulos', methods=['GET'])
def fix_modulos_endpoint():
    """Endpoint para reparar los módulos de todos los usuarios"""
    try:
        import urllib.parse
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        if not DATABASE_URL:
            return "<h1 style='color:#ff6b6b;'>❌ DATABASE_URL no está configurada</h1>", 500
        
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
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("✅ Conectado a PostgreSQL - Reparando módulos...")
        
        mensajes = []
        
        # 1. Verificar módulos
        cursor.execute("SELECT * FROM modulos")
        modulos = cursor.fetchall()
        
        if not modulos:
            mensajes.append("⚠️ No hay módulos. Creándolos...")
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
                ('mapa', 'Ubicación en mapa interactivo', 1, 'negocio'),
            ]
            
            for nombre, desc, activo, tipo in modulos_list:
                cursor.execute('''
                    INSERT INTO modulos (nombre, descripcion, activo_global, tipo_requerido)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (nombre) DO NOTHING
                ''', (nombre, desc, activo, tipo))
            
            conn.commit()
            mensajes.append("✅ Módulos creados")
            
            cursor.execute("SELECT * FROM modulos")
            modulos = cursor.fetchall()
        
        mensajes.append(f"📋 Módulos encontrados: {len(modulos)}")
        
        # 2. Asignar permisos a cada usuario según su tipo
        cursor.execute("SELECT id, username, rol, tipo FROM usuarios")
        usuarios = cursor.fetchall()
        
        mensajes.append(f"👥 Usuarios encontrados: {len(usuarios)}")
        
        for u in usuarios:
            if u['rol'] == 'admin':
                # Admin tiene todos los módulos
                cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (u['id'],))
                for modulo in modulos:
                    cursor.execute('''
                        INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                        VALUES (%s, %s, 1, 'aprobado')
                    ''', (u['id'], modulo['id']))
                mensajes.append(f"✅ Admin {u['username']} - TODOS los módulos activos")
            elif u['tipo'] == 'negocio':
                # Negocios tienen módulos de negocio (INCLUYE MAPA)
                modulos_negocio = ['inventario', 'tienda', 'trabajadores', 'servicios', 'ventas', 'contratos', 'nomina', 'mapa']
                cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (u['id'],))
                for modulo in modulos:
                    activo = 1 if modulo['nombre'] in modulos_negocio else 0
                    cursor.execute('''
                        INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                        VALUES (%s, %s, %s, 'aprobado')
                    ''', (u['id'], modulo['id'], activo))
                mensajes.append(f"✅ Negocio {u['username']} - Módulos de negocio activos (incluye mapa)")
            elif u['rol'] == 'trabajador':
                # Trabajadores tienen acceso limitado
                modulos_trabajador = ['ventas', 'servicios']
                cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (u['id'],))
                for modulo in modulos:
                    activo = 1 if modulo['nombre'] in modulos_trabajador else 0
                    cursor.execute('''
                        INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                        VALUES (%s, %s, %s, 'aprobado')
                    ''', (u['id'], modulo['id'], activo))
                mensajes.append(f"✅ Trabajador {u['username']} - Módulos: ventas, servicios")
            else:
                # Clientes tienen acceso básico
                modulos_cliente = ['tienda']
                cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (u['id'],))
                for modulo in modulos:
                    activo = 1 if modulo['nombre'] in modulos_cliente else 0
                    cursor.execute('''
                        INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                        VALUES (%s, %s, %s, 'aprobado')
                    ''', (u['id'], modulo['id'], activo))
                mensajes.append(f"✅ Cliente {u['username']} - Módulo: tienda")
        
        conn.commit()
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        
        return f"""
        <html>
            <head><title>Módulos Reparados</title>
            <style>
                body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                .btn-primary {{ background: #6c3ce0; color: #fff; }}
                .btn-primary:hover {{ background: #5a2ec0; }}
                .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                .btn-secondary:hover {{ background: #3a3a4e; }}
            </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Módulos</h1>
                    <div class="card"><h3>📊 Resultado</h3>{html_mensajes}</div>
                    <div>
                        <a href="/admin/db" class="btn btn-primary">🗄️ Ir al Gestor DB</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINT PARA INICIALIZAR BD MANUALMENTE
# ============================================
@app.route('/init-db', methods=['GET'])
def init_db_route():
    """Endpoint para inicializar la base de datos manualmente"""
    try:
        init_db()
        return """
        <html>
            <head><title>Base de Datos Inicializada</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#6c3ce0;">✅ Base de Datos Inicializada</h1>
                <p>Usuario: <strong>admin</strong></p>
                <p>Contraseña: <strong>admin123</strong></p>
                <br>
                <a href="/login" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Ir al Login</a>
            </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error al inicializar la base de datos</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/login" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Ir al Login</a>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINT PARA REPARAR TABLA NOMINA
# ============================================
@app.route('/fix-nomina-tabla', methods=['GET'])
def fix_nomina_tabla_endpoint():
    try:
        import urllib.parse
        import psycopg2
        
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        if not DATABASE_URL:
            return "<h1 style='color:#ff6b6b;'>❌ DATABASE_URL no está configurada</h1>", 500
        
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
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
        
        mensajes = []
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'nomina'
            )
        """)
        tabla_existe = cursor.fetchone()[0]
        
        if not tabla_existe:
            mensajes.append("⚠️ La tabla 'nomina' no existe. Creándola...")
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
            conn.commit()
            mensajes.append("✅ Tabla 'nomina' creada correctamente")
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'nomina'
        """)
        columnas = [col[0] for col in cursor.fetchall()]
        mensajes.append(f"📋 Columnas existentes: {', '.join(columnas)}")
        
        columnas_necesarias = {
            'salario_base': 'REAL NOT NULL DEFAULT 0',
            'dias_trabajados': 'INTEGER DEFAULT 0',
            'dias_ausencia': 'INTEGER DEFAULT 0',
            'dias_extras': 'INTEGER DEFAULT 0',
            'salario_devengado': 'REAL DEFAULT 0',
            'comisiones': 'REAL DEFAULT 0',
            'total': 'REAL DEFAULT 0'
        }
        
        for col, tipo in columnas_necesarias.items():
            if col not in columnas:
                try:
                    cursor.execute(f"ALTER TABLE nomina ADD COLUMN {col} {tipo}")
                    mensajes.append(f"✅ Columna '{col}' agregada")
                    print(f"✅ Columna '{col}' agregada")
                except psycopg2.Error as e:
                    if "duplicate column" not in str(e).lower():
                        mensajes.append(f"⚠️ Error al agregar '{col}': {e}")
                        print(f"⚠️ Error al agregar '{col}': {e}")
                except Exception as e:
                    mensajes.append(f"⚠️ Error al agregar '{col}': {e}")
                    print(f"⚠️ Error al agregar '{col}': {e}")
            else:
                mensajes.append(f"✅ Columna '{col}' ya existe")
        
        conn.commit()
        
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'nomina'
            ORDER BY ordinal_position
        """)
        columnas_final = cursor.fetchall()
        
        html_columnas = ""
        for col, tipo in columnas_final:
            html_columnas += f"• <strong>{col}</strong> ({tipo})<br>"
        
        cursor.execute("SELECT COUNT(*) FROM nomina")
        total_registros = cursor.fetchone()[0]
        
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        
        return f"""
        <html>
            <head><title>Tabla Nómina Reparada</title>
            <style>
                body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                .success {{ color: #6bff6b; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                .btn-primary {{ background: #6c3ce0; color: #fff; }}
                .btn-primary:hover {{ background: #5a2ec0; }}
                .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                .btn-secondary:hover {{ background: #3a3a4e; }}
            </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Tabla Nómina</h1>
                    <div class="card"><h3>📊 Resultado</h3>{html_mensajes}</div>
                    <div class="card"><h3>📋 Estructura final de la tabla 'nomina'</h3>{html_columnas}</div>
                    <div class="card"><h3>📊 Estadísticas</h3><p>Total de registros en nómina: <strong>{total_registros}</strong></p></div>
                    <div>
                        <a href="/negocio/nomina" class="btn btn-primary">📊 Ir a Nómina</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                </div>
            </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error al reparar tabla</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
            </body>
        </html>
        """, 500

# ============================================
# RUTAS PRINCIPALES
# ============================================
@app.route('/')
def index():
    token = request.cookies.get('token')
    if token:
        try:
            usuario = obtener_usuario_sesion(token)
            if usuario:
                return redirect(url_for('dashboard'))
        except:
            pass
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type debe ser application/json'}), 415
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos inválidos'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Usuario y contraseña son requeridos'}), 400
        
        usuario = obtener_usuario_por_username(username)
        
        if not usuario:
            return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
        
        if usuario.get('activo') != 1:
            return jsonify({'error': 'Usuario desactivado'}), 401
        
        if not verify_password(password, usuario.get('password_hash')):
            return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
        
        token = crear_sesion(usuario.get('id'))
        actualizar_ultimo_acceso(usuario.get('id'))
        registrar_log(usuario.get('id'), 'login', 'Inicio de sesión')
        
        response = jsonify({
            'success': True,
            'usuario': {
                'id': usuario.get('id'),
                'username': usuario.get('username'),
                'nombre': usuario.get('nombre'),
                'rol': usuario.get('rol'),
                'tipo': usuario.get('tipo')
            }
        })
        response.set_cookie('token', token, httponly=True, max_age=604800)
        return response
        
    except Exception as e:
        print(f"❌ Error en login: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos inválidos'}), 400
        
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        nombre = data.get('nombre')
        tipo = data.get('tipo', 'cliente')
        datos_negocio = data.get('datos_negocio')
        
        if not username or not email or not password:
            return jsonify({'error': 'Todos los campos son requeridos'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
        
        if obtener_usuario_por_username(username):
            return jsonify({'error': 'El nombre de usuario ya está en uso'}), 400
        
        user_id = crear_usuario(username, email, password, nombre, 'usuario', tipo, datos_negocio)
        
        if not user_id:
            return jsonify({'error': 'Error al crear el usuario'}), 500
        
        registrar_log(user_id, 'registro', f'Usuario registrado: {username} (tipo: {tipo})')
        
        return jsonify({
            'success': True, 
            'message': 'Usuario registrado correctamente',
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"❌ Error en register: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/dashboard')
@login_required
def dashboard():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return redirect(url_for('login'))
    
    try:
        print(f"🔍 Dashboard - Usuario: {usuario.get('username')}, Rol: {usuario.get('rol')}, Tipo: {usuario.get('tipo')}")
        
        if usuario.get('rol') == 'admin':
            print("✅ Mostrando dashboard de ADMIN")
            return render_template('admin/dashboard.html', usuario=usuario)
        elif usuario.get('rol') == 'trabajador':
            print("✅ Mostrando dashboard de TRABAJADOR")
            return render_template('trabajador/dashboard.html', usuario=usuario)
        elif usuario.get('tipo') == 'negocio':
            print("✅ Mostrando dashboard de NEGOCIO")
            return render_template('negocio/dashboard.html', usuario=usuario)
        else:
            print("✅ Mostrando dashboard de CLIENTE")
            return render_template('cliente/dashboard.html', usuario=usuario)
    except Exception as e:
        print(f"❌ Error en dashboard: {e}")
        return render_template('login.html')

@app.route('/perfil')
@login_required
def perfil_usuario():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return redirect(url_for('login'))
    
    return render_template('perfil.html', usuario=usuario)

@app.route('/logout')
def logout():
    response = redirect(url_for('login'))
    response.delete_cookie('token')
    return response

# ============================================
# ADMIN - PERFIL Y GESTOR DB
# ============================================
@app.route('/admin/perfil')
@admin_required
def admin_perfil():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('admin/perfil.html', usuario=usuario)

@app.route('/admin/db')
@admin_required
def admin_db():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('admin/db_manager.html', usuario=usuario)

@app.route('/admin/trabajadores/pendientes')
@admin_required
def admin_trabajadores_pendientes():
    return render_template('admin/trabajadores_pendientes.html')

# ============================================
# RUTAS DE MÓDULOS DE NEGOCIO
# ============================================
@app.route('/negocio/inventario')
@login_required
def negocio_inventario():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/inventario.html', usuario=usuario, version=int(time.time()))

@app.route('/negocio/tienda')
@login_required
def negocio_tienda():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/tienda.html', usuario=usuario, version=int(time.time()))

@app.route('/negocio/trabajadores')
@login_required
def negocio_trabajadores():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/trabajadores.html', usuario=usuario, version=int(time.time()))

@app.route('/negocio/servicios')
@login_required
def negocio_servicios():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/servicios.html', usuario=usuario, version=int(time.time()))

@app.route('/negocio/ventas')
@login_required
def negocio_ventas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/ventas.html', usuario=usuario, version=int(time.time()))

@app.route('/negocio/contratos')
@login_required
def negocio_contratos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/contratos.html', usuario=usuario, version=int(time.time()))

@app.route('/negocio/nomina')
@login_required
def negocio_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/nomina.html', usuario=usuario, version=int(time.time()))

@app.route('/negocio/mapa')
@login_required
def negocio_mapa():
    """Página del mapa de ubicación"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/mapa.html', usuario=usuario, version=int(time.time()))

# ============================================
# API - PERFIL DE USUARIO
# ============================================
@app.route('/api/usuario/perfil', methods=['GET'])
@login_required
def api_obtener_perfil_usuario():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    datos_negocio = {}
    if usuario.get('datos_negocio'):
        try:
            datos_negocio = json.loads(usuario['datos_negocio']) if isinstance(usuario['datos_negocio'], str) else usuario['datos_negocio']
        except:
            datos_negocio = {}
    
    return jsonify({
        'success': True,
        'usuario': {
            'id': usuario.get('id'),
            'username': usuario.get('username'),
            'email': usuario.get('email'),
            'nombre': usuario.get('nombre'),
            'rol': usuario.get('rol'),
            'tipo': usuario.get('tipo'),
            'fecha_registro': usuario.get('fecha_registro'),
            'telefono': datos_negocio.get('telefono', ''),
            'provincia': datos_negocio.get('provincia', ''),
            'municipio': datos_negocio.get('municipio', ''),
            'direccion': datos_negocio.get('direccion', ''),
            'nombre_negocio': datos_negocio.get('nombre_negocio', ''),
            'ruc': datos_negocio.get('ruc', ''),
            'descripcion': datos_negocio.get('descripcion', ''),
            'salario': datos_negocio.get('salario', 0)
        }
    })

@app.route('/api/usuario/perfil', methods=['PUT'])
@login_required
def api_actualizar_perfil_usuario():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    
    nombre = data.get('nombre')
    email = data.get('email')
    telefono = data.get('telefono')
    provincia = data.get('provincia')
    municipio = data.get('municipio')
    direccion = data.get('direccion')
    nombre_negocio = data.get('nombre_negocio')
    ruc = data.get('ruc')
    descripcion = data.get('descripcion')
    salario = data.get('salario', 0)
    
    if not nombre:
        return jsonify({'error': 'El nombre es obligatorio'}), 400
    
    if not telefono:
        return jsonify({'error': 'El teléfono es obligatorio'}), 400
    
    if not provincia or not municipio:
        return jsonify({'error': 'Provincia y municipio son obligatorios'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT datos_negocio FROM usuarios WHERE id = %s', (usuario['id'],))
    result = cursor.fetchone()
    
    datos_negocio = {}
    if result and result[0]:
        try:
            datos_negocio = json.loads(result[0]) if isinstance(result[0], str) else result[0]
        except:
            datos_negocio = {}
    
    datos_negocio.update({
        'telefono': telefono,
        'provincia': provincia,
        'municipio': municipio,
        'direccion': direccion or '',
        'salario': salario
    })
    
    if usuario.get('tipo') == 'negocio':
        datos_negocio.update({
            'nombre_negocio': nombre_negocio or datos_negocio.get('nombre_negocio', ''),
            'ruc': ruc or datos_negocio.get('ruc', ''),
            'descripcion': descripcion or datos_negocio.get('descripcion', '')
        })
    
    cursor.execute('''
        UPDATE usuarios 
        SET nombre = %s, email = %s, datos_negocio = %s
        WHERE id = %s
    ''', (nombre, email, json.dumps(datos_negocio, ensure_ascii=False), usuario['id']))
    
    conn.commit()
    conn.close()
    
    registrar_log(usuario['id'], 'perfil_actualizado', 'Perfil de usuario actualizado')
    
    return jsonify({
        'success': True,
        'message': 'Perfil actualizado correctamente'
    })

@app.route('/api/usuario/ubicacion', methods=['GET'])
@login_required
def api_obtener_ubicacion_usuario():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    datos = obtener_datos_negocio(usuario['id'])
    
    return jsonify({
        'success': True,
        'provincia': datos.get('provincia', ''),
        'municipio': datos.get('municipio', ''),
        'tiene_ubicacion': bool(datos.get('provincia') and datos.get('municipio'))
    })

@app.route('/api/perfil')
@admin_required
def api_perfil():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return jsonify({
        'success': True,
        'usuario': {
            'id': usuario.get('id'),
            'username': usuario.get('username'),
            'email': usuario.get('email'),
            'nombre': usuario.get('nombre'),
            'rol': usuario.get('rol'),
            'fecha_registro': usuario.get('fecha_registro')
        }
    })

@app.route('/api/perfil/password', methods=['POST'])
@admin_required
def api_perfil_password():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Todos los campos son requeridos'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
    
    if not verify_password(current_password, usuario.get('password_hash')):
        return jsonify({'error': 'Contraseña actual incorrecta'}), 401
    
    new_hash = hash_password(new_password)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET password_hash = %s WHERE id = %s', (new_hash, usuario['id']))
    conn.commit()
    conn.close()
    
    registrar_log(usuario['id'], 'cambio_password', 'Contraseña actualizada')
    
    return jsonify({'success': True, 'message': 'Contraseña actualizada correctamente'})

# ============================================
# API - SQL QUERY
# ============================================
@app.route('/api/sql', methods=['POST'])
@admin_required
def api_sql():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'La consulta SQL está vacía'}), 400
    
    if not query.lower().startswith('select'):
        return jsonify({'error': 'Solo se permiten consultas SELECT'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(query)
        
        column_names = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            result.append(dict(zip(column_names, row)))
        
        return jsonify({'result': result})
    except psycopg2.Error as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# API - ESTADÍSTICAS
# ============================================
@app.route('/api/estadisticas')
@admin_required
def api_estadisticas():
    usuarios = obtener_todos_usuarios()
    logs = obtener_logs(100)
    
    total = len(usuarios)
    activos = len([u for u in usuarios if u.get('activo') == 1])
    trabajadores = len([u for u in usuarios if u.get('rol') == 'trabajador'])
    
    hoy = datetime.now().date()
    registros_hoy = 0
    for l in logs:
        try:
            if datetime.fromisoformat(l.get('fecha', '')).date() == hoy:
                registros_hoy += 1
        except:
            pass
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM productos')
    total_productos = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM ventas')
    total_ventas = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM servicios')
    total_servicios = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM contratos')
    total_contratos = cursor.fetchone()[0]
    conn.close()
    
    return jsonify({
        'total_usuarios': total,
        'usuarios_activos': activos,
        'total_trabajadores': trabajadores,
        'registros_hoy': registros_hoy,
        'total_logs': len(logs),
        'total_productos': total_productos,
        'total_ventas': total_ventas,
        'total_servicios': total_servicios,
        'total_contratos': total_contratos
    })

# ============================================
# API - VERIFICAR USUARIO (DEBUG)
# ============================================
@app.route('/api/verificar-usuario/<username>', methods=['GET'])
@admin_required
def verificar_usuario(username):
    usuario = obtener_usuario_por_username(username)
    if usuario:
        return jsonify({
            'exists': True,
            'usuario': {
                'id': usuario.get('id'),
                'username': usuario.get('username'),
                'email': usuario.get('email'),
                'tipo': usuario.get('tipo'),
                'rol': usuario.get('rol')
            }
        })
    return jsonify({'exists': False, 'message': 'Usuario no encontrado'})

# ============================================
# API - USUARIOS
# ============================================
@app.route('/api/usuarios')
@admin_required
def api_usuarios():
    usuarios = obtener_todos_usuarios()
    return jsonify([dict(u) for u in usuarios])

@app.route('/api/usuario/<int:user_id>')
@admin_required
def api_usuario(user_id):
    usuario = obtener_usuario_por_id(user_id)
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    permisos = obtener_permisos_usuario(user_id)
    return jsonify({
        'usuario': dict(usuario),
        'permisos': [dict(p) for p in permisos]
    })

@app.route('/api/usuario/<int:user_id>/toggle', methods=['POST'])
@admin_required
def api_toggle_usuario(user_id):
    data = request.get_json()
    activo = data.get('activo', 1)
    toggle_usuario(user_id, activo)
    registrar_log(None, 'usuario_toggle', f'Usuario {user_id} activo={activo}')
    return jsonify({'success': True})

@app.route('/api/usuario/<int:user_id>/rol', methods=['POST'])
@admin_required
def api_actualizar_rol(user_id):
    data = request.get_json()
    rol = data.get('rol', 'usuario')
    if rol not in ['usuario', 'admin', 'trabajador']:
        return jsonify({'error': 'Rol inválido'}), 400
    actualizar_rol_usuario(user_id, rol)
    registrar_log(None, 'usuario_rol', f'Usuario {user_id} rol={rol}')
    return jsonify({'success': True})

@app.route('/api/usuario/<int:user_id>/tipo', methods=['POST'])
@admin_required
def api_actualizar_tipo(user_id):
    data = request.get_json()
    tipo = data.get('tipo', 'cliente')
    if tipo not in ['cliente', 'negocio']:
        return jsonify({'error': 'Tipo inválido'}), 400
    actualizar_tipo_usuario(user_id, tipo)
    registrar_log(None, 'usuario_tipo', f'Usuario {user_id} tipo={tipo}')
    return jsonify({'success': True})

@app.route('/api/usuario/<int:user_id>', methods=['DELETE'])
@admin_required
def api_eliminar_usuario(user_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if usuario.get('id') == user_id:
        return jsonify({'error': 'No puedes eliminar tu propio usuario'}), 400
    
    user = obtener_usuario_por_id(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    exito = eliminar_usuario(user_id)
    
    if not exito:
        return jsonify({'error': 'Error al eliminar el usuario'}), 500
    
    registrar_log(usuario.get('id'), 'usuario_eliminado', f'Usuario {user_id} eliminado')
    
    return jsonify({'success': True, 'message': 'Usuario eliminado correctamente'})

@app.route('/api/usuario/<int:user_id>/permisos')
@login_required
def api_permisos_usuario(user_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    if not usuario or (usuario.get('id') != user_id and usuario.get('rol') != 'admin'):
        return jsonify({'error': 'No autorizado'}), 403
    
    permisos = obtener_permisos_usuario(user_id)
    return jsonify([dict(p) for p in permisos])

@app.route('/api/usuario/<int:user_id>/permiso/<int:modulo_id>', methods=['POST'])
@admin_required
def api_asignar_permiso(user_id, modulo_id):
    data = request.get_json()
    activo = data.get('activo', 1)
    asignar_permiso_usuario(user_id, modulo_id, activo)
    registrar_log(None, 'permiso_usuario', f'Usuario {user_id} módulo {modulo_id} activo={activo}')
    return jsonify({'success': True})

# ============================================
# API - MÓDULOS (GLOBAL)
# ============================================
@app.route('/api/modulo/<int:modulo_id>/toggle', methods=['POST'])
@admin_required
def api_toggle_modulo_global(modulo_id):
    """Activa o desactiva un módulo globalmente"""
    try:
        data = request.get_json()
        activo = data.get('activo', 1)
        
        exito = toggle_modulo_global(modulo_id, activo)
        
        if exito:
            registrar_log(None, 'modulo_global', f'Módulo {modulo_id} activo={activo}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al actualizar el módulo'}), 500
            
    except Exception as e:
        print(f"❌ Error en toggle_modulo_global: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# API - MÓDULOS
# ============================================
@app.route('/api/modulos')
@login_required
def api_modulos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        if usuario.get('rol') == 'admin':
            modulos = obtener_modulos()
        else:
            tipo_usuario = usuario.get('tipo') if usuario else 'cliente'
            modulos = obtener_modulos(tipo_usuario)
        
        # Convertir a diccionario para JSON
        resultado = []
        for m in modulos:
            resultado.append({
                'id': m.get('id'),
                'nombre': m.get('nombre'),
                'descripcion': m.get('descripcion'),
                'activo_global': m.get('activo_global'),
                'tipo_requerido': m.get('tipo_requerido')
            })
        
        return jsonify(resultado)
    except Exception as e:
        print(f"❌ Error en api_modulos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - NEGOCIOS
# ============================================
@app.route('/api/negocios')
@admin_required
def api_negocios():
    negocios = obtener_negocios()
    return jsonify([dict(n) for n in negocios])

@app.route('/api/negocios/cercanos', methods=['GET'])
@login_required
def api_negocios_cercanos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        datos_usuario = obtener_datos_negocio(usuario['id'])
        provincia = datos_usuario.get('provincia')
        municipio = datos_usuario.get('municipio')
        
        if not provincia or not municipio:
            return jsonify({
                'success': True,
                'negocios': [],
                'message': 'Actualiza tu ubicación en el perfil para ver negocios cercanos'
            })
        
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT id, username, nombre, datos_negocio, activo, fecha_registro
            FROM usuarios 
            WHERE tipo = 'negocio' 
            AND activo = 1
            AND datos_negocio IS NOT NULL
            AND datos_negocio LIKE %s
            AND datos_negocio LIKE %s
            ORDER BY id DESC
        ''', (f'%"provincia": "{provincia}"%', f'%"municipio": "{municipio}"%'))
        
        negocios = cursor.fetchall()
        conn.close()
        
        resultado = []
        for n in negocios:
            datos = {}
            if n.get('datos_negocio'):
                try:
                    datos = json.loads(n['datos_negocio']) if isinstance(n['datos_negocio'], str) else n['datos_negocio']
                except:
                    pass
            
            resultado.append({
                'id': n.get('id'),
                'username': n.get('username'),
                'nombre': n.get('nombre') or datos.get('nombre_negocio', n.get('username')),
                'telefono': datos.get('telefono', ''),
                'direccion': datos.get('direccion', ''),
                'descripcion': datos.get('descripcion', ''),
                'activo': n.get('activo')
            })
        
        return jsonify({
            'success': True,
            'negocios': resultado,
            'provincia': provincia,
            'municipio': municipio,
            'total': len(resultado)
        })
        
    except Exception as e:
        print(f"❌ Error en api_negocios_cercanos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - NEGOCIOS CON UBICACIÓN PARA MAPA
# ============================================
@app.route('/api/negocios/mapa', methods=['GET'])
@login_required
def api_negocios_mapa():
    """Obtiene todos los negocios con ubicación para el mapa"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    # Obtener el negocio del usuario si es trabajador
    negocio_id = None
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
    
    # Si es negocio, obtener solo su ubicación
    if usuario.get('tipo') == 'negocio':
        negocios = obtener_negocios_con_ubicacion(usuario['id'])
    else:
        negocios = obtener_negocios_con_ubicacion()
    
    return jsonify({
        'success': True,
        'negocios': negocios
    })

# ============================================
# API - UBICACIÓN
# ============================================
@app.route('/api/ubicacion/actualizar', methods=['POST'])
@login_required
def api_actualizar_ubicacion():
    """Actualiza la ubicación del usuario en el mapa"""
    try:
        token = request.cookies.get('token')
        usuario = obtener_usuario_sesion(token)
        
        if not usuario:
            return jsonify({'error': 'No autorizado'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos inválidos'}), 400
        
        latitud = data.get('latitud')
        longitud = data.get('longitud')
        
        if latitud is None or longitud is None:
            return jsonify({'error': 'Latitud y longitud son requeridas'}), 400
        
        try:
            latitud = float(latitud)
            longitud = float(longitud)
        except (ValueError, TypeError):
            return jsonify({'error': 'Coordenadas inválidas'}), 400
        
        if not (-90 <= latitud <= 90) or not (-180 <= longitud <= 180):
            return jsonify({'error': 'Coordenadas fuera de rango'}), 400
        
        exito = actualizar_ubicacion_usuario(usuario['id'], latitud, longitud)
        
        if exito:
            registrar_log(usuario['id'], 'ubicacion_actualizada', f'Lat: {latitud}, Lng: {longitud}')
            return jsonify({'success': True, 'message': 'Ubicación actualizada correctamente'})
        else:
            return jsonify({'error': 'Error al actualizar la ubicación'}), 500
            
    except Exception as e:
        print(f"❌ Error en api_actualizar_ubicacion: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ubicacion/obtener', methods=['GET'])
@login_required
def api_obtener_ubicacion():
    """Obtiene la ubicación del usuario actual"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    ubicacion = obtener_ubicacion_usuario(usuario['id'])
    
    return jsonify({
        'success': True,
        'ubicacion': {
            'latitud': ubicacion.get('latitud') if ubicacion else None,
            'longitud': ubicacion.get('longitud') if ubicacion else None,
            'actualizada': ubicacion.get('ubicacion_actualizada') if ubicacion else None,
            'tiene_ubicacion': ubicacion and ubicacion.get('latitud') is not None
        }
    })

# ============================================
# API - TODOS LOS PRODUCTOS (para admin)
# ============================================
@app.route('/api/todos/productos')
@admin_required
def api_todos_productos():
    productos = obtener_todos_productos()
    return jsonify([dict(p) for p in productos])

# ============================================
# API - TODAS LAS VENTAS (para admin)
# ============================================
@app.route('/api/todos/ventas')
@admin_required
def api_todos_ventas():
    ventas = obtener_todas_ventas()
    return jsonify([dict(v) for v in ventas])

# ============================================
# API - TODOS LOS SERVICIOS (para admin)
# ============================================
@app.route('/api/todos/servicios')
@admin_required
def api_todos_servicios():
    servicios = obtener_todos_servicios()
    return jsonify([dict(s) for s in servicios])

# ============================================
# API - NEGOCIO - TRABAJADORES
# ============================================
@app.route('/api/negocio/trabajadores')
@login_required
def api_obtener_trabajadores():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT u.id, u.username, u.email, u.nombre, u.activo, 
               u.datos_negocio, u.fecha_registro
        FROM trabajadores_negocio tn
        JOIN usuarios u ON tn.trabajador_id = u.id
        WHERE tn.negocio_id = %s AND tn.activo = 1
        ORDER BY u.id DESC
        ''', (usuario['id'],))
        
        rows = cursor.fetchall()
        conn.close()
        
        resultado = []
        for row in rows:
            datos = json.loads(row[5]) if row[5] else {}
            resultado.append({
                'id': row[0],
                'username': row[1],
                'email': row[2] or '',
                'nombre': datos.get('nombre', row[3] or ''),
                'apellidos': datos.get('apellidos', ''),
                'ci': datos.get('ci', ''),
                'movil': datos.get('movil', ''),
                'direccion': datos.get('direccion', ''),
                'frecuencia': datos.get('frecuencia', 'diaria'),
                'salario': datos.get('salario', 0),
                'activo': row[4],
                'fecha_registro': row[6],
                'modulos': datos.get('modulos', [])
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error en api_obtener_trabajadores: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/negocio/trabajador/crear', methods=['POST'])
@login_required
def api_crear_trabajador():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    
    nombre = data.get('nombre')
    apellidos = data.get('apellidos')
    ci = data.get('ci')
    movil = data.get('movil', '')
    direccion = data.get('direccion', '')
    frecuencia = data.get('frecuencia', 'diaria')
    salario = data.get('salario', 0)
    email = data.get('email', '')
    username = data.get('usuario')
    password = data.get('password')
    modulos = data.get('modulos', ['inventario', 'tienda', 'servicios', 'ventas'])
    
    if not nombre:
        return jsonify({'error': 'El nombre es obligatorio'}), 400
    if not apellidos:
        return jsonify({'error': 'Los apellidos son obligatorios'}), 400
    if not ci:
        return jsonify({'error': 'El carnet de identidad es obligatorio'}), 400
    if not username:
        return jsonify({'error': 'El nombre de usuario es obligatorio'}), 400
    if not password:
        return jsonify({'error': 'La contraseña es obligatoria'}), 400
    if len(password) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
    
    if obtener_usuario_por_username(username):
        return jsonify({'error': 'El nombre de usuario ya está en uso'}), 400
    
    datos_negocio = {
        'nombre': nombre,
        'apellidos': apellidos,
        'ci': ci,
        'movil': movil,
        'direccion': direccion,
        'frecuencia': frecuencia,
        'salario': salario,
        'empresa_id': usuario['id'],
        'modulos': modulos
    }
    
    user_id = crear_usuario(
        username=username,
        email=email or f"{username}@trabajador.local",
        password=password,
        nombre=f"{nombre} {apellidos}",
        rol='trabajador',
        tipo='negocio',
        datos_negocio=datos_negocio
    )
    
    if not user_id:
        return jsonify({'error': 'Error al crear el trabajador'}), 500
    
    crear_trabajador_negocio(usuario['id'], user_id, 'Trabajador', salario)
    
    for modulo_nombre in modulos:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM modulos WHERE nombre = %s", (modulo_nombre,))
        mod = cursor.fetchone()
        conn.close()
        if mod:
            asignar_permiso_usuario(user_id, mod[0], 1)
    
    registrar_log(usuario['id'], 'crear_trabajador', f'Creó trabajador: {nombre} {apellidos} (CI: {ci})')
    
    return jsonify({
        'success': True,
        'message': 'Trabajador creado correctamente',
        'user_id': user_id
    })

@app.route('/api/negocio/trabajador/<int:trabajador_id>', methods=['PUT'])
@login_required
def api_actualizar_trabajador(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    
    nombre = data.get('nombre')
    apellidos = data.get('apellidos')
    ci = data.get('ci')
    movil = data.get('movil', '')
    direccion = data.get('direccion', '')
    frecuencia = data.get('frecuencia', 'diaria')
    salario = data.get('salario', 0)
    email = data.get('email', '')
    modulos = data.get('modulos', [])
    
    if not nombre:
        return jsonify({'error': 'El nombre es obligatorio'}), 400
    if not apellidos:
        return jsonify({'error': 'Los apellidos son obligatorios'}), 400
    if not ci:
        return jsonify({'error': 'El carnet de identidad es obligatorio'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT datos_negocio FROM usuarios WHERE id = %s', (trabajador_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return jsonify({'error': 'Trabajador no encontrado'}), 404
    
    datos_actuales = json.loads(result[0]) if result[0] else {}
    
    datos_actuales.update({
        'nombre': nombre,
        'apellidos': apellidos,
        'ci': ci,
        'movil': movil,
        'direccion': direccion,
        'frecuencia': frecuencia,
        'salario': salario,
        'modulos': modulos
    })
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM permisos_usuario 
        WHERE usuario_id = %s
    ''', (trabajador_id,))
    
    for modulo_nombre in modulos:
        cursor.execute("SELECT id FROM modulos WHERE nombre = %s", (modulo_nombre,))
        mod = cursor.fetchone()
        if mod:
            cursor.execute('''
            INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
            VALUES (%s, %s, 1, 'aprobado')
            ''', (trabajador_id, mod[0]))
    
    cursor.execute('''
        UPDATE usuarios 
        SET nombre = %s, email = %s, datos_negocio = %s
        WHERE id = %s
    ''', (f"{nombre} {apellidos}", email, json.dumps(datos_actuales), trabajador_id))
    
    conn.commit()
    conn.close()
    
    registrar_log(usuario['id'], 'actualizar_trabajador', f'Actualizó trabajador: {nombre} {apellidos} (ID: {trabajador_id})')
    
    return jsonify({
        'success': True,
        'message': 'Trabajador actualizado correctamente'
    })

@app.route('/api/negocio/trabajador/<int:trabajador_id>', methods=['DELETE'])
@login_required
def api_eliminar_trabajador(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.nombre, u.datos_negocio
            FROM trabajadores_negocio tn
            JOIN usuarios u ON tn.trabajador_id = u.id
            WHERE tn.negocio_id = %s AND tn.trabajador_id = %s
        ''', (usuario['id'], trabajador_id))
        
        trabajador = cursor.fetchone()
        
        if not trabajador:
            conn.close()
            return jsonify({'error': 'Trabajador no encontrado o no pertenece a tu negocio'}), 404
        
        nombre_trabajador = trabajador[2] or trabajador[1] or 'Desconocido'
        
        cursor.execute('DELETE FROM sesiones WHERE usuario_id = %s', (trabajador_id,))
        cursor.execute('DELETE FROM permisos_usuario WHERE usuario_id = %s', (trabajador_id,))
        cursor.execute('''
            DELETE FROM trabajadores_negocio 
            WHERE negocio_id = %s AND trabajador_id = %s
        ''', (usuario['id'], trabajador_id))
        cursor.execute('DELETE FROM logs WHERE usuario_id = %s', (trabajador_id,))
        cursor.execute('DELETE FROM usuarios WHERE id = %s', (trabajador_id,))
        
        conn.commit()
        conn.close()
        
        registrar_log(usuario['id'], 'trabajador_eliminado', 
                     f'Eliminó trabajador: {nombre_trabajador} (ID: {trabajador_id})')
        
        return jsonify({
            'success': True,
            'message': f'Trabajador eliminado correctamente'
        })
        
    except psycopg2.Error as e:
        print(f"❌ Error SQL eliminando trabajador: {e}")
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500
    except Exception as e:
        print(f"❌ Error eliminando trabajador: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/negocio/trabajador/<int:trabajador_id>/toggle', methods=['POST'])
@login_required
def api_toggle_trabajador_negocio(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    activo = data.get('activo', 1)
    
    toggle_trabajador_negocio(usuario['id'], trabajador_id, activo)
    registrar_log(usuario['id'], 'trabajador_toggle', f'Trabajador {trabajador_id} activo={activo}')
    
    return jsonify({'success': True})

# ============================================
# API - PRODUCTOS
# ============================================
@app.route('/api/productos', methods=['GET', 'POST'])
@login_required
def api_productos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    negocio_id = usuario['id']
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    if request.method == 'GET':
        productos = obtener_productos(negocio_id)
        return jsonify([dict(p) for p in productos])
    
    if usuario.get('rol') == 'trabajador':
        return jsonify({'error': 'No tienes permisos para crear productos'}), 403
    
    data = request.get_json()
    nombre = data.get('nombre')
    categoria = data.get('categoria')
    precio = data.get('precio')
    costo = data.get('costo', 0)
    comision = data.get('comision', 0)
    stock = data.get('stock', 0)
    stock_minimo = data.get('stock_minimo', 3)
    
    if not nombre or precio is None:
        return jsonify({'error': 'Nombre y precio son requeridos'}), 400
    
    producto_id = crear_producto(negocio_id, nombre, categoria, precio, costo, comision, stock, stock_minimo)
    registrar_log(usuario['id'], 'producto_creado', f'Producto: {nombre} (Costo: ${costo}, Comisión: ${comision})')
    
    return jsonify({'success': True, 'id': producto_id})

@app.route('/api/producto/<int:producto_id>', methods=['PUT', 'DELETE'])
@login_required
def api_producto(producto_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    negocio_id = usuario['id']
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    if request.method == 'DELETE':
        try:
            print(f"🗑️ Intentando eliminar producto ID: {producto_id}")
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT negocio_id, nombre FROM productos WHERE id = %s', (producto_id,))
            producto = cursor.fetchone()
            conn.close()
            
            if not producto:
                print(f"❌ Producto {producto_id} no encontrado")
                return jsonify({'error': 'Producto no encontrado'}), 404
            
            if producto[0] != negocio_id:
                print(f"❌ Producto {producto_id} no pertenece al negocio")
                return jsonify({'error': 'No autorizado'}), 403
            
            exito = eliminar_producto(producto_id)
            
            if exito:
                registrar_log(usuario['id'], 'producto_eliminado', 
                            f'Producto: {producto[1]} (ID: {producto_id})')
                print(f"✅ Producto {producto_id} eliminado correctamente")
                return jsonify({
                    'success': True,
                    'message': f'Producto "{producto[1]}" eliminado correctamente',
                    'producto_id': producto_id
                })
            else:
                print(f"❌ Error al eliminar producto {producto_id}")
                return jsonify({
                    'error': 'No se pudo eliminar el producto. Verifica que no tenga ventas asociadas.'
                }), 500
                
        except Exception as e:
            print(f"❌ Error eliminando producto: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    if usuario.get('rol') == 'trabajador':
        return jsonify({'error': 'No tienes permisos para editar productos'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos inválidos'}), 400
            
        nombre = data.get('nombre')
        categoria = data.get('categoria')
        precio = data.get('precio')
        costo = data.get('costo', 0)
        comision = data.get('comision', 0)
        stock = data.get('stock', 0)
        stock_minimo = data.get('stock_minimo', 3)
        
        if not nombre or precio is None:
            return jsonify({'error': 'Nombre y precio son requeridos'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT negocio_id FROM productos WHERE id = %s', (producto_id,))
        producto = cursor.fetchone()
        conn.close()
        
        if not producto or producto[0] != negocio_id:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        actualizar_producto(producto_id, nombre, categoria, precio, costo, comision, stock, stock_minimo)
        registrar_log(usuario['id'], 'producto_actualizado', f'ID: {producto_id} (Costo: ${costo}, Comisión: ${comision})')
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Error actualizando producto: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/stock')
@login_required
def api_productos_stock():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    negocio_id = usuario['id']
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    productos = obtener_productos_con_stock(negocio_id)
    return jsonify([dict(p) for p in productos])

# ============================================
# API - FOTOS DE PRODUCTOS
# ============================================
@app.route('/api/producto/<int:producto_id>/foto', methods=['POST'])
@login_required
def api_subir_foto_producto(producto_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT negocio_id FROM productos WHERE id = %s', (producto_id,))
    producto = cursor.fetchone()
    conn.close()
    
    if not producto or producto[0] != usuario['id']:
        return jsonify({'error': 'Producto no encontrado'}), 404
    
    if 'foto' not in request.files:
        return jsonify({'error': 'No se envió ninguna foto'}), 400
    
    archivo = request.files['foto']
    if archivo.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    storage = get_storage_manager()
    
    import uuid
    timestamp = int(time.time())
    nombre_base = f"foto_{timestamp}_{uuid.uuid4().hex[:8]}"
    extension = archivo.filename.rsplit('.', 1)[1].lower() if '.' in archivo.filename else 'jpg'
    filename = f"{nombre_base}.{extension}"
    
    exito = storage.subir_foto_producto(usuario['id'], producto_id, archivo, filename)
    
    if not exito:
        return jsonify({'error': 'Error al subir la foto'}), 500
    
    url = storage.obtener_url_foto(usuario['id'], producto_id, filename)
    actualizar_foto_producto(producto_id, url, filename)
    
    registrar_log(usuario['id'], 'foto_subida', f'Producto {producto_id} - {filename}')
    
    return jsonify({
        'success': True, 
        'url': url,
        'filename': filename,
        'message': 'Foto subida correctamente'
    })

@app.route('/api/producto/<int:producto_id>/foto', methods=['DELETE'])
@login_required
def api_eliminar_foto_producto(producto_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT negocio_id, foto_public_id FROM productos WHERE id = %s', (producto_id,))
    producto = cursor.fetchone()
    conn.close()
    
    if not producto or producto[0] != usuario['id']:
        return jsonify({'error': 'Producto no encontrado'}), 404
    
    if not producto[1]:
        return jsonify({'error': 'El producto no tiene foto'}), 400
    
    storage = get_storage_manager()
    exito = storage.eliminar_foto_producto(usuario['id'], producto_id, producto[1])
    
    eliminar_foto_producto(producto_id)
    
    if exito:
        registrar_log(usuario['id'], 'foto_eliminada', f'Producto {producto_id}')
        return jsonify({'success': True, 'message': 'Foto eliminada correctamente'})
    else:
        return jsonify({'success': True, 'message': 'Foto eliminada de la base de datos'})

# ============================================
# API - TIENDA (NEGOCIO)
# ============================================
@app.route('/api/tienda/productos', methods=['GET'])
@login_required
def api_tienda_productos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT pt.id, pt.destacado, pt.created_at,
               p.id as producto_id, p.nombre, p.categoria, p.precio, p.stock, p.foto_url
        FROM productos_tienda pt
        JOIN productos p ON pt.producto_id = p.id
        WHERE pt.negocio_id = %s
        ORDER BY pt.destacado DESC, pt.created_at DESC
        ''', (usuario['id'],))
        
        rows = cursor.fetchall()
        conn.close()
        
        resultado = []
        for row in rows:
            resultado.append({
                'id': row[0],
                'destacado': row[1],
                'created_at': row[2],
                'producto_id': row[3],
                'nombre': row[4],
                'categoria': row[5] or '',
                'precio': float(row[6]),
                'stock': row[7],
                'foto_url': row[8]
            })
        
        print(f"📦 Productos en tienda encontrados: {len(resultado)}")
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error en api_tienda_productos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/agregar', methods=['POST'])
@login_required
def api_tienda_agregar_producto():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    producto_id = data.get('producto_id')
    destacado = data.get('destacado', 0)
    
    if not producto_id:
        return jsonify({'error': 'ID de producto requerido'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, nombre FROM productos WHERE id = %s AND negocio_id = %s', (producto_id, usuario['id']))
        producto = cursor.fetchone()
        
        if not producto:
            conn.close()
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        cursor.execute('SELECT id FROM productos_tienda WHERE producto_id = %s AND negocio_id = %s', (producto_id, usuario['id']))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'El producto ya está en la tienda'}), 400
        
        from datetime import datetime
        fecha = datetime.now().isoformat()
        cursor.execute('''
        INSERT INTO productos_tienda (negocio_id, producto_id, destacado, created_at)
        VALUES (%s, %s, %s, %s)
        ''', (usuario['id'], producto_id, destacado, fecha))
        conn.commit()
        conn.close()
        
        registrar_log(usuario['id'], 'tienda_agregar', f'Producto {producto_id} agregado a la tienda')
        
        return jsonify({'success': True, 'message': 'Producto agregado a la tienda'})
        
    except Exception as e:
        print(f"❌ Error en api_tienda_agregar_producto: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/<int:tienda_id>/destacar', methods=['POST'])
@login_required
def api_tienda_destacar_producto(tienda_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    destacado = data.get('destacado', 1)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE productos_tienda SET destacado = %s
        WHERE id = %s AND negocio_id = %s
        ''', (destacado, tienda_id, usuario['id']))
        conn.commit()
        conn.close()
        
        registrar_log(usuario['id'], 'tienda_destacar', f'Producto tienda {tienda_id} destacado={destacado}')
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Error en api_tienda_destacar_producto: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/<int:tienda_id>', methods=['DELETE'])
@login_required
def api_tienda_eliminar_producto(tienda_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM productos_tienda WHERE id = %s AND negocio_id = %s', (tienda_id, usuario['id']))
        conn.commit()
        conn.close()
        
        registrar_log(usuario['id'], 'tienda_eliminar', f'Producto tienda {tienda_id} eliminado')
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Error en api_tienda_eliminar_producto: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# API - TIENDA PÚBLICA FILTRADA POR UBICACIÓN
# ============================================
@app.route('/api/tienda/public', methods=['GET'])
def api_tienda_public():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        token = request.cookies.get('token')
        usuario = None
        provincia_filtro = None
        municipio_filtro = None
        
        if token:
            try:
                usuario = obtener_usuario_sesion(token)
                if usuario:
                    datos_negocio = obtener_datos_negocio(usuario.get('id'))
                    provincia_filtro = datos_negocio.get('provincia')
                    municipio_filtro = datos_negocio.get('municipio')
            except:
                pass
        
        query = '''
            SELECT p.id, p.nombre, p.categoria, p.precio, p.stock, p.foto_url,
                   u.id as negocio_id, u.nombre as negocio_nombre, u.username as negocio_username,
                   u.datos_negocio
            FROM productos_tienda pt
            JOIN productos p ON pt.producto_id = p.id
            JOIN usuarios u ON pt.negocio_id = u.id
            WHERE p.stock > 0 AND u.activo = 1
        '''
        
        params = []
        
        if provincia_filtro and municipio_filtro:
            query += '''
                AND (
                    u.datos_negocio IS NOT NULL 
                    AND u.datos_negocio LIKE %s 
                    AND u.datos_negocio LIKE %s
                )
            '''
            params.extend([f'%"provincia": "{provincia_filtro}"%', f'%"municipio": "{municipio_filtro}"%'])
        elif provincia_filtro:
            query += '''
                AND (
                    u.datos_negocio IS NOT NULL 
                    AND u.datos_negocio LIKE %s
                )
            '''
            params.append(f'%"provincia": "{provincia_filtro}"%')
        
        query += ' ORDER BY pt.destacado DESC, pt.created_at DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        resultado = []
        for row in rows:
            datos_negocio = {}
            if row[8]:
                try:
                    datos_negocio = json.loads(row[8]) if isinstance(row[8], str) else row[8]
                except:
                    pass
            
            resultado.append({
                'id': row[0],
                'nombre': row[1],
                'categoria': row[2] or '',
                'precio': float(row[3]),
                'stock': row[4],
                'foto_url': row[5],
                'negocio_id': row[6],
                'negocio_nombre': row[7] or row[9] or 'Negocio',
                'negocio_username': row[9],
                'provincia': datos_negocio.get('provincia', ''),
                'municipio': datos_negocio.get('municipio', '')
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error en tienda pública: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - VENTAS
# ============================================
@app.route('/api/ventas', methods=['GET', 'POST'])
@login_required
def api_ventas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    negocio_id = usuario['id']
    trabajador_id = None
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
        trabajador_id = usuario['id']
    
    if request.method == 'GET':
        if usuario.get('rol') == 'trabajador':
            ventas = obtener_ventas(negocio_id, trabajador_id)
        else:
            trabajador_id_param = request.args.get('trabajador_id')
            ventas = obtener_ventas(negocio_id, trabajador_id_param)
        return jsonify([dict(v) for v in ventas])
    
    data = request.get_json()
    print("📥 Datos recibidos en POST:", data)
    
    cliente = data.get('cliente')
    producto = data.get('producto')
    producto_id = data.get('producto_id')
    cantidad = data.get('cantidad', 1)
    precio = data.get('precio')
    total = data.get('total', precio * cantidad if precio else 0)
    if usuario.get('rol') == 'trabajador':
        trabajador_id = usuario['id']
    else:
        trabajador_id = data.get('trabajador_id')
    estado = data.get('estado', 'pagado')
    empresa = data.get('empresa')
    tipo = data.get('tipo', 'producto')
    factura_url = data.get('factura_url')
    factura = data.get('factura')
    transferencia_id = data.get('transferencia_id')
    transferencia_cedula = data.get('transferencia_cedula')
    transferencia_banco = data.get('transferencia_banco')
    transferencia_fecha = data.get('transferencia_fecha')
    
    if not cliente or not producto or precio is None:
        return jsonify({'error': 'Cliente, producto y precio son requeridos'}), 400
    
    if not producto_id:
        return jsonify({'error': 'ID de producto requerido para productos'}), 400
    
    if tipo == 'producto' and producto_id:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT stock FROM productos WHERE id = %s AND negocio_id = %s', (producto_id, negocio_id))
        stock_actual = cursor.fetchone()
        conn.close()
        
        if not stock_actual:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        if stock_actual[0] < cantidad:
            return jsonify({'error': f'Stock insuficiente. Disponible: {stock_actual[0]} unidades'}), 400
    
    venta_id = crear_venta(
        negocio_id, trabajador_id, cliente, producto, 
        producto_id, cantidad, precio, total, estado, 
        empresa, tipo, factura_url, factura,
        transferencia_id, transferencia_cedula,
        transferencia_banco, transferencia_fecha
    )
    
    if tipo == 'producto' and producto_id and estado != 'oferta':
        actualizar_stock_producto(producto_id, cantidad)
    
    if trabajador_id and tipo == 'producto':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT comision FROM productos WHERE id = %s', (producto_id,))
        comision_data = cursor.fetchone()
        conn.close()
        if comision_data and comision_data[0] > 0:
            comision = comision_data[0] * cantidad
            registrar_comision(negocio_id, trabajador_id, venta_id, producto_id, comision)
    
    registrar_log(usuario['id'], 'venta_creada', 
                  f'Venta: {producto} - Cliente: {cliente} - Cantidad: {cantidad} - Estado: {estado}')
    
    return jsonify({'success': True, 'id': venta_id, 'stock_actualizado': tipo == 'producto' and estado != 'oferta'})

@app.route('/api/ventas/estadisticas')
@login_required
def api_ventas_estadisticas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    trabajador_id = request.args.get('trabajador_id')
    stats = obtener_estadisticas_ventas(usuario['id'], trabajador_id)
    
    return jsonify({
        'total': stats[0] if stats else 0,
        'ingresos': stats[1] if stats else 0
    })

@app.route('/api/venta/<int:venta_id>/estado', methods=['PUT'])
@login_required
def api_actualizar_estado_venta(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    estado = data.get('estado')
    
    if estado not in ['pagado', 'pendiente', 'cancelado', 'transferencia', 'oferta']:
        return jsonify({'error': 'Estado inválido'}), 400
    
    exito = actualizar_estado_venta(venta_id, usuario['id'], estado)
    
    if not exito:
        return jsonify({'error': 'Venta no encontrada'}), 404
    
    registrar_log(usuario['id'], 'venta_estado', f'Venta {venta_id} estado={estado}')
    
    return jsonify({'success': True})

@app.route('/api/venta/<int:venta_id>', methods=['DELETE'])
@login_required
def api_eliminar_venta(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT estado, producto_id FROM ventas WHERE id = %s AND negocio_id = %s', (venta_id, usuario['id']))
        venta = cursor.fetchone()
        conn.close()
        
        if not venta:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        if venta[0] == 'oferta':
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ventas WHERE id = %s AND negocio_id = %s', (venta_id, usuario['id']))
            conn.commit()
            conn.close()
            registrar_log(usuario['id'], 'oferta_eliminada', f'Oferta #{venta_id} eliminada')
            return jsonify({
                'success': True,
                'message': 'Oferta eliminada correctamente'
            })
        
        exito, resultado = eliminar_venta_con_reintegro(venta_id, usuario['id'])
        
        if not exito:
            return jsonify({'error': resultado}), 400
        
        registrar_log(usuario['id'], 'venta_eliminada', 
                      f'Venta #{venta_id} eliminada. Producto: {resultado["producto"]} - Cantidad: {resultado["cantidad"]}')
        
        return jsonify({
            'success': True,
            'message': 'Venta eliminada y stock reintegrado correctamente',
            'producto': resultado.get('producto'),
            'cantidad': resultado.get('cantidad'),
            'cliente': resultado.get('cliente'),
            'total': resultado.get('total')
        })
        
    except psycopg2.Error as e:
        print(f"❌ Error SQL eliminando venta: {e}")
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500
    except Exception as e:
        print(f"❌ Error eliminando venta: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - FACTURAS Y OFERTAS
# ============================================
@app.route('/api/venta/<int:venta_id>/factura', methods=['GET'])
@login_required
def api_generar_factura(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    es_oferta = request.args.get('oferta', 'false').lower() == 'true'
    
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT v.*, u.nombre as atendido_por_nombre
            FROM ventas v
            LEFT JOIN usuarios u ON v.trabajador_id = u.id
            WHERE v.id = %s AND v.negocio_id = %s
        ''', (venta_id, usuario['id']))
        venta = cursor.fetchone()
        conn.close()
        
        if not venta:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        items = []
        producto_str = venta.get('producto', '')
        
        if ',' in producto_str:
            productos_separados = [p.strip() for p in producto_str.split(',')]
            if len(productos_separados) > 1:
                for nombre in productos_separados:
                    conn = get_db()
                    cursor2 = conn.cursor()
                    cursor2.execute('SELECT precio FROM productos WHERE nombre = %s AND negocio_id = %s', 
                                   (nombre, usuario['id']))
                    prod = cursor2.fetchone()
                    conn.close()
                    
                    precio = prod[0] if prod else venta.get('precio', 0)
                    
                    items.append({
                        'nombre': nombre,
                        'cantidad': 1,
                        'precio': precio,
                        'subtotal': precio
                    })
            else:
                items.append({
                    'nombre': producto_str,
                    'cantidad': venta.get('cantidad', 1),
                    'precio': venta.get('precio', 0),
                    'subtotal': venta.get('total', 0)
                })
        else:
            if venta.get('producto_id'):
                conn = get_db()
                cursor2 = conn.cursor()
                cursor2.execute('SELECT nombre, precio FROM productos WHERE id = %s', (venta['producto_id'],))
                prod = cursor2.fetchone()
                conn.close()
                
                if prod:
                    items.append({
                        'nombre': prod[0] or producto_str,
                        'cantidad': venta.get('cantidad', 1),
                        'precio': prod[1] or venta.get('precio', 0),
                        'subtotal': venta.get('total', 0)
                    })
                else:
                    items.append({
                        'nombre': producto_str,
                        'cantidad': venta.get('cantidad', 1),
                        'precio': venta.get('precio', 0),
                        'subtotal': venta.get('total', 0)
                    })
            else:
                items.append({
                    'nombre': producto_str,
                    'cantidad': venta.get('cantidad', 1),
                    'precio': venta.get('precio', 0),
                    'subtotal': venta.get('total', 0)
                })
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT nombre, datos_negocio FROM usuarios WHERE id = %s', (usuario['id'],))
        negocio = cursor.fetchone()
        conn.close()
        
        negocio_nombre = negocio[0] or 'Mi Negocio'
        datos_negocio = json.loads(negocio[1]) if negocio[1] else {}
        negocio_telefono = datos_negocio.get('telefono', '')
        negocio_direccion = datos_negocio.get('direccion', '')
        
        atendido_por = venta.get('atendido_por_nombre') or usuario.get('nombre') or usuario.get('username') or 'Admin'
        
        venta_data = {
            'id': venta.get('id'),
            'factura': venta.get('factura', f"FAC-{venta.get('id')}"),
            'fecha': venta.get('fecha'),
            'cliente': venta.get('cliente'),
            'empresa': venta.get('empresa', ''),
            'estado': venta.get('estado'),
            'total': venta.get('total'),
            'atendido_por': atendido_por
        }
        
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono,
            negocio_direccion=negocio_direccion,
            atendido_por=atendido_por
        )
        
        pdf_bytes = generador.generar_factura_venta(
            venta_data,
            items,
            es_oferta=es_oferta
        )
        
        tipo = 'oferta' if es_oferta else 'factura'
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={tipo}_{venta_id}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        registrar_log(usuario['id'], 'factura_generada', f'Factura {tipo} #{venta_id}')
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando factura: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - CONTRATOS
# ============================================
@app.route('/api/contratos/ultimo_numero', methods=['GET'])
@login_required
def api_ultimo_numero_contrato():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    ultimo = obtener_ultimo_numero_contrato(usuario['id'])
    return jsonify({'ultimo_numero': ultimo})

@app.route('/api/contratos', methods=['GET', 'POST'])
@login_required
def api_contratos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    negocio_id = usuario['id']
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    if request.method == 'GET':
        trabajador_id = request.args.get('trabajador_id')
        contratos = obtener_contratos(negocio_id, trabajador_id)
        return jsonify([dict(c) for c in contratos])
    
    if usuario.get('rol') == 'trabajador':
        return jsonify({'error': 'No tienes permisos para crear contratos'}), 403
    
    data = request.get_json()
    print("📥 Datos recibidos en POST:", data)
    
    empresa = data.get('empresa')
    numero_contrato = data.get('numero_contrato')
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    tipo = data.get('tipo')
    monto = data.get('monto', 0)
    estado = data.get('estado', 'activo')
    descripcion = data.get('descripcion', '')
    
    if not empresa or not numero_contrato or not fecha_inicio or not fecha_fin or not tipo:
        return jsonify({'error': 'Empresa, número de contrato, fechas y tipo son requeridos'}), 400
    
    if tipo not in ['ventas', 'servicios', 'ambos']:
        return jsonify({'error': 'Tipo inválido. Debe ser: ventas, servicios o ambos'}), 400
    
    contrato_id = crear_contrato(
        negocio_id, None, empresa, numero_contrato,
        fecha_inicio, fecha_fin, tipo, monto, estado, descripcion
    )
    registrar_log(usuario['id'], 'contrato_creado', f'Contrato: {numero_contrato} - {empresa}')
    
    return jsonify({'success': True, 'id': contrato_id})

@app.route('/api/contrato/<int:contrato_id>', methods=['PUT'])
@login_required
def api_actualizar_contrato(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    print("📥 Datos recibidos en PUT:", data)
    
    empresa = data.get('empresa')
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    tipo = data.get('tipo')
    monto = data.get('monto', 0)
    estado = data.get('estado', 'activo')
    descripcion = data.get('descripcion', '')
    
    if not empresa or not fecha_inicio or not fecha_fin or not tipo:
        return jsonify({'error': 'Empresa, fechas y tipo son requeridos'}), 400
    
    if tipo not in ['ventas', 'servicios', 'ambos']:
        return jsonify({'error': 'Tipo inválido. Debe ser: ventas, servicios o ambos'}), 400
    
    actualizar_contrato(contrato_id, empresa, fecha_inicio, fecha_fin, tipo, monto, estado, descripcion)
    registrar_log(usuario['id'], 'contrato_actualizado', f'Contrato {contrato_id} actualizado')
    
    return jsonify({'success': True})

@app.route('/api/contrato/<int:contrato_id>/estado', methods=['PUT'])
@login_required
def api_contrato_estado(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    estado = data.get('estado')
    
    if estado not in ['activo', 'pendiente', 'finalizado', 'cancelado']:
        return jsonify({'error': 'Estado inválido'}), 400
    
    actualizar_estado_contrato(contrato_id, estado)
    registrar_log(usuario['id'], 'contrato_estado', f'Contrato {contrato_id} estado={estado}')
    
    return jsonify({'success': True})

@app.route('/api/contrato/<int:contrato_id>', methods=['DELETE'])
@login_required
def api_eliminar_contrato(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    eliminar_contrato(contrato_id)
    registrar_log(usuario['id'], 'contrato_eliminado', f'Contrato {contrato_id} eliminado')
    
    return jsonify({'success': True})

# ============================================
# API - OBTENER EMPRESAS CON CONTRATOS ACTIVOS
# ============================================
@app.route('/api/contratos/empresas', methods=['GET'])
@login_required
def api_obtener_empresas_con_contratos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    negocio_id = usuario['id']
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT empresa, numero_contrato, tipo, fecha_fin
            FROM contratos 
            WHERE negocio_id = %s AND estado = 'activo'
            ORDER BY empresa ASC
        ''', (negocio_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        empresas = []
        for row in rows:
            empresas.append({
                'empresa': row[0],
                'numero_contrato': row[1],
                'tipo': row[2],
                'fecha_fin': row[3]
            })
        
        return jsonify(empresas)
        
    except Exception as e:
        print(f"❌ Error obteniendo empresas con contratos: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# API - SERVICIOS
# ============================================
@app.route('/api/servicios', methods=['GET', 'POST'])
@login_required
def api_servicios():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    negocio_id = usuario['id']
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    if request.method == 'GET':
        trabajador_id = request.args.get('trabajador_id')
        if usuario.get('rol') == 'trabajador':
            servicios = obtener_servicios(negocio_id, usuario['id'])
        else:
            servicios = obtener_servicios(negocio_id, trabajador_id)
        return jsonify([dict(s) for s in servicios])
    
    if usuario.get('rol') == 'trabajador':
        return jsonify({'error': 'No tienes permisos para crear servicios'}), 403
    
    data = request.get_json()
    nombre = data.get('nombre')
    categoria = data.get('categoria')
    precio = data.get('precio')
    duracion = data.get('duracion', 60)
    descripcion = data.get('descripcion', '')
    trabajador_id = data.get('trabajador_id')
    
    if not nombre or precio is None:
        return jsonify({'error': 'Nombre y precio son requeridos'}), 400
    
    servicio_id = crear_servicio(negocio_id, trabajador_id, nombre, categoria, precio, duracion, 1, descripcion)
    registrar_log(usuario['id'], 'servicio_creado', f'Servicio: {nombre}')
    
    return jsonify({'success': True, 'id': servicio_id})

@app.route('/api/servicio/<int:servicio_id>/toggle', methods=['POST'])
@login_required
def api_toggle_servicio(servicio_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    activo = data.get('activo', 1)
    toggle_servicio(servicio_id, activo)
    registrar_log(usuario['id'], 'servicio_toggle', f'ID: {servicio_id} - Activo: {activo}')
    
    return jsonify({'success': True})

@app.route('/api/servicio/<int:servicio_id>', methods=['DELETE'])
@login_required
def api_eliminar_servicio(servicio_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    eliminar_servicio(servicio_id)
    registrar_log(usuario['id'], 'servicio_eliminado', f'ID: {servicio_id}')
    
    return jsonify({'success': True})

# ============================================
# API - TRABAJADOR: ESTADÍSTICAS
# ============================================
@app.route('/api/trabajador/estadisticas', methods=['GET'])
@login_required
def api_trabajador_estadisticas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
        
        stats = obtener_estadisticas_trabajador(usuario['id'])
        
        return jsonify({
            'ventas': stats.get('ventas', 0),
            'clientes': stats.get('clientes', 0),
            'ingresos': stats.get('ingresos', 0),
            'servicios': stats.get('servicios', 0)
        })
        
    except Exception as e:
        print(f"❌ Error en api_trabajador_estadisticas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - REPORTES
# ============================================
@app.route('/api/reportes/contratos/resumen', methods=['GET'])
@login_required
def api_reportes_contratos_resumen():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT estado, monto FROM contratos WHERE negocio_id = %s', (usuario['id'],))
        rows = cursor.fetchall()
        conn.close()
        
        total = len(rows)
        activos = 0
        vencidos = 0
        total_gastos = 0
        
        for estado, monto in rows:
            total_gastos += monto or 0
            if estado in ('activo', 'pendiente'):
                activos += 1
            elif estado == 'vencido':
                vencidos += 1
        
        return jsonify({
            'total': total,
            'activos': activos,
            'vencidos': vencidos,
            'total_gastos': total_gastos,
            'tiene_contratos': total > 0
        })
        
    except Exception as e:
        print(f"❌ Error en api_reportes_contratos_resumen: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/ingresos/resumen', methods=['GET'])
@login_required
def api_reportes_ingresos_resumen():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        hoy = datetime.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_mes = hoy.replace(day=1)
        
        cursor.execute('SELECT fecha, total FROM ventas WHERE negocio_id = %s', (usuario['id'],))
        rows = cursor.fetchall()
        conn.close()
        
        total_ingresos = 0
        ingresos_hoy = 0
        ingresos_semana = 0
        ingresos_mes = 0
        ventas_hoy = 0
        
        hoy_str = hoy.isoformat()
        
        for fecha_str, total in rows:
            try:
                fecha = datetime.fromisoformat(fecha_str).date()
                total_ingresos += total or 0
                
                if fecha == hoy:
                    ingresos_hoy += total or 0
                    ventas_hoy += 1
                if fecha >= inicio_semana:
                    ingresos_semana += total or 0
                if fecha >= inicio_mes:
                    ingresos_mes += total or 0
            except:
                pass
        
        return jsonify({
            'total_ingresos': total_ingresos,
            'ingresos_hoy': ingresos_hoy,
            'ingresos_semana': ingresos_semana,
            'ingresos_mes': ingresos_mes,
            'ventas_hoy': ventas_hoy,
            'tiene_ventas': total_ingresos > 0
        })
        
    except Exception as e:
        print(f"❌ Error en api_reportes_ingresos_resumen: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/productos/resumen', methods=['GET'])
@login_required
def api_reportes_productos_resumen():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        stats = obtener_estadisticas_productos(usuario['id'])
        
        tiene_productos = stats.get('total', 0) > 0
        
        return jsonify({
            'total': stats.get('total', 0),
            'stock_bajo': stats.get('stock_bajo', 0),
            'stock_agotado': stats.get('agotados', 0),
            'valor_total': stats.get('valor_total', 0),
            'tiene_productos': tiene_productos
        })
        
    except Exception as e:
        print(f"❌ Error en api_reportes_productos_resumen: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/contratos', methods=['GET'])
@login_required
def api_reporte_contratos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    tipo_reporte = request.args.get('tipo', 'todos')
    
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = 'SELECT * FROM contratos WHERE negocio_id = %s'
        params = [usuario['id']]
        
        if tipo_reporte == 'activos':
            query += " AND estado IN ('activo', 'pendiente')"
        elif tipo_reporte == 'vencidos':
            query += " AND estado = 'vencido'"
        
        query += ' ORDER BY id DESC'
        
        cursor.execute(query, params)
        contratos = cursor.fetchall()
        conn.close()
        
        if not contratos:
            return jsonify({'error': 'No hay contratos para generar el reporte'}), 404
        
        negocio_data = obtener_datos_negocio(usuario['id'])
        negocio_nombre = negocio_data.get('nombre_negocio') or usuario.get('nombre') or usuario.get('username')
        negocio_telefono = negocio_data.get('telefono', '')
        
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono
        )
        
        pdf_bytes = generador.generar_reporte_contratos(contratos, tipo_reporte)
        
        filename = f'reporte_contratos_{tipo_reporte}_{datetime.now().strftime("%Y%m%d")}.pdf'
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de contratos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/ingresos', methods=['GET'])
@login_required
def api_reporte_ingresos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    tipo_reporte = request.args.get('tipo', 'hoy')
    
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = 'SELECT * FROM ventas WHERE negocio_id = %s'
        params = [usuario['id']]
        
        hoy = datetime.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_mes = hoy.replace(day=1)
        
        if tipo_reporte == 'hoy':
            query += " AND fecha = %s"
            params.append(hoy.isoformat())
        elif tipo_reporte == 'semana':
            query += " AND fecha >= %s"
            params.append(inicio_semana.isoformat())
        elif tipo_reporte == 'mes':
            query += " AND fecha >= %s"
            params.append(inicio_mes.isoformat())
        
        query += ' ORDER BY fecha DESC'
        
        cursor.execute(query, params)
        ventas = cursor.fetchall()
        conn.close()
        
        if not ventas:
            return jsonify({'error': 'No hay ventas para generar el reporte'}), 404
        
        total_ingresos = sum(v.get('total', 0) for v in ventas)
        
        negocio_data = obtener_datos_negocio(usuario['id'])
        negocio_nombre = negocio_data.get('nombre_negocio') or usuario.get('nombre') or usuario.get('username')
        negocio_telefono = negocio_data.get('telefono', '')
        
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono
        )
        
        periodo = {
            'hoy': 'Hoy',
            'semana': 'Esta semana',
            'mes': 'Este mes',
            'todos': 'Todos'
        }.get(tipo_reporte, '')
        
        pdf_bytes = generador.generar_reporte_ingresos(ventas, total_ingresos, len(ventas), periodo)
        
        filename = f'reporte_ingresos_{tipo_reporte}_{datetime.now().strftime("%Y%m%d")}.pdf'
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de ingresos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/productos', methods=['GET'])
@login_required
def api_reporte_productos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        productos = obtener_productos(usuario['id'])
        
        if not productos:
            return jsonify({'error': 'No hay productos para generar el reporte'}), 404
        
        negocio_data = obtener_datos_negocio(usuario['id'])
        negocio_nombre = negocio_data.get('nombre_negocio') or usuario.get('nombre') or usuario.get('username')
        negocio_telefono = negocio_data.get('telefono', '')
        
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono
        )
        
        pdf_bytes = generador.generar_reporte_productos(productos)
        
        filename = f'reporte_inventario_{datetime.now().strftime("%Y%m%d")}.pdf'
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de productos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - NÓMINA
# ============================================
@app.route('/api/nomina', methods=['GET'])
@login_required
def api_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    
    if not mes or not ano:
        return jsonify({'error': 'Mes y año son requeridos'}), 400
    
    try:
        nomina = obtener_nomina_mes(usuario['id'], mes, ano)
        return jsonify({
            'success': True,
            'nominas': nomina
        })
    except Exception as e:
        print(f"❌ Error en api_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/calcular', methods=['POST'])
@login_required
def api_calcular_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    mes = data.get('mes', type=int)
    ano = data.get('ano', type=int)
    
    if not mes or not ano:
        return jsonify({'error': 'Mes y año son requeridos'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tn.trabajador_id, u.nombre, u.datos_negocio
            FROM trabajadores_negocio tn
            JOIN usuarios u ON tn.trabajador_id = u.id
            WHERE tn.negocio_id = %s AND tn.activo = 1
        ''', (usuario['id'],))
        trabajadores = cursor.fetchall()
        conn.close()
        
        if not trabajadores:
            return jsonify({
                'success': True,
                'message': 'No hay trabajadores activos',
                'trabajadores': 0
            })
        
        contador = 0
        errores = []
        
        for t in trabajadores:
            trabajador_id = t[0]
            nombre = t[1] or 'Trabajador'
            try:
                resultado = calcular_nomina(usuario['id'], trabajador_id, mes, ano)
                if resultado:
                    contador += 1
                    print(f"✅ Nómina calculada para {nombre}")
                else:
                    errores.append(f"⚠️ No se pudo calcular nómina para {nombre}")
            except Exception as e:
                errores.append(f"❌ Error calculando nómina para {nombre}: {str(e)}")
                print(f"❌ Error calculando nómina para {nombre}: {e}")
        
        mensaje = f'Nómina calculada para {contador} trabajadores'
        if errores:
            mensaje += f' | {len(errores)} errores'
            print(f"⚠️ Errores: {errores}")
        
        return jsonify({
            'success': True,
            'message': mensaje,
            'trabajadores': contador,
            'errores': errores
        })
        
    except Exception as e:
        print(f"❌ Error en api_calcular_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/detalle', methods=['GET'])
@login_required
def api_nomina_detalle():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    trabajador_id = request.args.get('trabajador_id', type=int)
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    
    if not trabajador_id or not mes or not ano:
        return jsonify({'error': 'Trabajador, mes y año son requeridos'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT u.id, u.nombre, u.datos_negocio
            FROM usuarios u
            WHERE u.id = %s
        ''', (trabajador_id,))
        trabajador = cursor.fetchone()
        conn.close()
        
        if not trabajador:
            return jsonify({'error': 'Trabajador no encontrado'}), 404
        
        datos = {}
        if trabajador.get('datos_negocio'):
            try:
                datos = json.loads(trabajador['datos_negocio']) if isinstance(trabajador['datos_negocio'], str) else trabajador['datos_negocio']
            except:
                datos = {}
        
        salario_base = datos.get('salario', 0)
        
        import calendar
        _, dias_mes = calendar.monthrange(ano, mes)
        
        dias_trabajados = obtener_dias_trabajados_mes(trabajador_id, mes, ano)
        dias_ausencia = obtener_dias_ausencia_mes(trabajador_id, mes, ano)
        dias_extras = obtener_dias_extras_mes(trabajador_id, mes, ano)
        
        if dias_trabajados == 0:
            dias_trabajados = dias_mes
        
        salario_diario = salario_base / dias_mes if dias_mes > 0 else 0
        salario_devengado = salario_diario * dias_trabajados
        
        comisiones_list = obtener_comisiones_trabajador_mes(trabajador_id, mes, ano)
        comisiones_total = sum(c.get('monto', 0) for c in comisiones_list) if comisiones_list else 0
        
        total = salario_devengado + comisiones_total
        
        return jsonify({
            'success': True,
            'detalle': {
                'trabajador_id': trabajador_id,
                'nombre': trabajador.get('nombre') or datos.get('nombre', 'Trabajador'),
                'salario_base': salario_base,
                'dias_mes': dias_mes,
                'dias_trabajados': dias_trabajados,
                'dias_ausencia': dias_ausencia,
                'dias_extras': dias_extras,
                'salario_diario': salario_diario,
                'salario_devengado': salario_devengado,
                'comisiones': comisiones_total,
                'total': total,
                'comisiones_list': comisiones_list or []
            }
        })
        
    except Exception as e:
        print(f"❌ Error en api_nomina_detalle: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/reporte', methods=['GET'])
@login_required
def api_nomina_reporte():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario.get('tipo') != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    
    if not mes or not ano:
        return jsonify({'error': 'Mes y año son requeridos'}), 400
    
    try:
        nomina = obtener_nomina_mes(usuario['id'], mes, ano)
        
        if not nomina:
            return jsonify({'error': 'No hay datos de nómina para generar el reporte'}), 404
        
        negocio_data = obtener_datos_negocio(usuario['id'])
        negocio_nombre = negocio_data.get('nombre_negocio') or usuario.get('nombre') or usuario.get('username')
        negocio_telefono = negocio_data.get('telefono', '')
        
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
        from reportlab.lib import colors
        import io
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )
        
        styles = getSampleStyleSheet()
        elementos = []
        
        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        nombre_mes = meses[mes - 1] if 1 <= mes <= 12 else str(mes)
        
        estilo_titulo = ParagraphStyle(
            'Titulo',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#6c3ce0'),
            alignment=TA_CENTER,
            spaceAfter=4
        )
        
        estilo_subtitulo = ParagraphStyle(
            'Subtitulo',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#888888'),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        elementos.append(Paragraph(f"📊 REPORTE DE NÓMINA - {nombre_mes} de {ano}", estilo_titulo))
        elementos.append(Paragraph(f"{negocio_nombre} | Total: ${sum(n.get('total', 0) for n in nomina):,.2f}", estilo_subtitulo))
        elementos.append(Spacer(1, 0.5*cm))
        
        tabla_datos = [
            ["Trabajador", "Salario Base", "Días Trab.", "Ausencias", "Salario Dev.", "Comisiones", "Total"]
        ]
        
        total_comisiones = 0
        total_nomina = 0
        
        for n in nomina:
            nombre = n.get('nombre', 'Trabajador')
            salario_base = n.get('salario_base', 0)
            dias_trabajados = n.get('dias_trabajados', 0)
            dias_ausencia = n.get('dias_ausencia', 0)
            salario_devengado = n.get('salario_devengado', 0)
            comisiones = n.get('comisiones', 0)
            total = n.get('total', 0)
            
            total_comisiones += comisiones
            total_nomina += total
            
            tabla_datos.append([
                Paragraph(nombre, styles['Normal']),
                f"${salario_base:,.2f}",
                str(dias_trabajados),
                str(dias_ausencia),
                f"${salario_devengado:,.2f}",
                f"${comisiones:,.2f}",
                f"${total:,.2f}"
            ])
        
        tabla_datos.append([
            Paragraph("<b>TOTAL</b>", styles['Normal']),
            "",
            "",
            "",
            "",
            f"${total_comisiones:,.2f}",
            f"${total_nomina:,.2f}"
        ])
        
        tabla = Table(tabla_datos, colWidths=[4*cm, 2.5*cm, 2*cm, 2*cm, 3*cm, 3*cm, 3*cm])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c3ce0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#999999')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.HexColor('#f9f9f9'), colors.white]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#2a2a3e')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ]))
        
        elementos.append(tabla)
        
        estilo_pie = ParagraphStyle(
            'Pie',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER,
            spaceBefore=20
        )
        
        elementos.append(Spacer(1, 1*cm))
        elementos.append(Paragraph(
            f"Reporte generado por AIsa - Sistema de Gestión Empresarial | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            estilo_pie
        ))
        
        doc.build(elementos)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        filename = f'nomina_{mes}_{ano}_{datetime.now().strftime("%Y%m%d")}.pdf'
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de nómina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# INICIO DE LA APLICACIÓN
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
