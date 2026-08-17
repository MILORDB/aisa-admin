# web_admin/app.py

import os
import sys
import json
import logging
import traceback
import time
import uuid
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response, send_from_directory
from flask_cors import CORS

# ============================================
# IMPORTAR RealDictCursor PARA POSTGRESQL
# ============================================
from psycopg2.extras import RealDictCursor

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
    os.makedirs(os.path.join(BASE_DIR, 'static/temp'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static/img'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static/css'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static/js'), exist_ok=True)
    print("📁 Carpetas de almacenamiento creadas/verificadas")
except Exception as e:
    print(f"⚠️ Error creando carpetas: {e}")

# ============================================
# IMPORTAR FUNCIONES DE LA BASE DE DATOS
# ============================================
try:
    from web_admin.database import (
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
        actualizar_ubicacion_usuario, obtener_ubicacion_usuario, obtener_negocios_con_ubicacion,
        generar_numero_factura, obtener_ultimo_numero_factura, actualizar_ultimo_numero_factura,
        registrar_asistencia,
        generar_codigo_verificacion, guardar_codigo_verificacion,
        verificar_codigo, marcar_usuario_verificado, obtener_codigos_pendientes,
        obtener_productos_tienda_negocio,
        obtener_empresas_con_contratos_activos,
        obtener_resumen_contratos,
        obtener_resumen_ingresos,
        obtener_resumen_productos,
        obtener_ventas_por_periodo,
        obtener_productos_tienda_publica,
        obtener_venta_por_id,
        obtener_contrato_por_id,
        actualizar_trabajador,
        eliminar_trabajador_definitivo,
        obtener_trabajador_completo,
        obtener_asistencia_mes,
        obtener_detalle_nomina,
        obtener_contratos_activos_para_empresa,
        obtener_ventas_con_filtros,
        obtener_trabajadores_activos,
        obtener_productos_tienda_por_negocio,
        obtener_productos_con_stock_negocio,
        obtener_trabajador_negocio,
        # Funciones de notificaciones
        suscribir_usuario, desuscribir_usuario, esta_suscrito,
        obtener_suscriptores, obtener_suscripciones_usuario,
        registrar_notificacion, registrar_notificacion_negocio,
        obtener_notificaciones_usuario, contar_notificaciones_no_leidas,
        marcar_notificacion_leida, marcar_todas_notificaciones_leidas,
        generar_notificaciones_stock, generar_notificacion_producto_nuevo,
        generar_notificacion_stock_actualizado,
        obtener_producto_por_id, obtener_preferencias_notificaciones,
        actualizar_preferencias_notificaciones,
        actualizar_servicio,
        obtener_categorias, obtener_subcategorias,
        obtener_categoria_por_id, obtener_subcategoria_por_id
    )
    print("✅ Database importada correctamente")
except ImportError as e:
    print(f"❌ Error importando database: {e}")
    traceback.print_exc()
    try:
        from database import *
        print("✅ Database importada desde local")
    except ImportError as e2:
        print(f"❌ Error en fallback: {e2}")
        traceback.print_exc()

try:
    from web_admin.auth import crear_sesion, verificar_sesion, obtener_usuario_sesion
    print("✅ Auth importada correctamente")
except ImportError as e:
    print(f"❌ Error importando auth: {e}")
    traceback.print_exc()
    try:
        from auth import crear_sesion, verificar_sesion, obtener_usuario_sesion
        print("✅ Auth importada desde local")
    except ImportError as e2:
        print(f"❌ Error en fallback: {e2}")
        traceback.print_exc()

try:
    from web_admin.storage import get_storage_manager
    print("✅ Storage importada correctamente")
except ImportError as e:
    print(f"❌ Error importando storage: {e}")
    traceback.print_exc()
    try:
        from storage import get_storage_manager
        print("✅ Storage importada desde local")
    except ImportError as e2:
        print(f"❌ Error en fallback: {e2}")
        traceback.print_exc()

try:
    from web_admin.reportes import GeneradorReportes
    print("✅ Reportes importada correctamente")
except ImportError as e:
    print(f"❌ Error importando reportes: {e}")
    traceback.print_exc()
    try:
        from reportes import GeneradorReportes
        print("✅ Reportes importada desde local")
    except ImportError as e2:
        print(f"❌ Error en fallback: {e2}")
        traceback.print_exc()

# ============================================
# CREAR APLICACIÓN FLASK
# ============================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
CORS(app)

# ============================================
# RUTAS PARA FAVICON
# ============================================

@app.route('/favicon.ico')
def favicon():
    """Ruta directa para el favicon.ico"""
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/favicon.svg')
def favicon_svg():
    """Ruta directa para el favicon.svg"""
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'favicon.svg',
        mimetype='image/svg+xml'
    )

@app.route('/favicon-16x16.png')
def favicon_16():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'favicon-16x16.png',
        mimetype='image/png'
    )

@app.route('/favicon-32x32.png')
def favicon_32():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'favicon-32x32.png',
        mimetype='image/png'
    )

@app.route('/favicon-48x48.png')
def favicon_48():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'favicon-48x48.png',
        mimetype='image/png'
    )

@app.route('/favicon-64x64.png')
def favicon_64():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'favicon-64x64.png',
        mimetype='image/png'
    )

# ============================================
# RUTA PARA REPARAR TABLAS
# ============================================

@app.route('/fix-db')
def fix_db():
    """Repara las tablas faltantes de la base de datos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # TABLA SUSCRIPCIONES
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS suscripciones (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            negocio_id INTEGER NOT NULL,
            fecha_suscripcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(usuario_id, negocio_id)
        )
        ''')
        
        # TABLA PREFERENCIAS_NOTIFICACIONES
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferencias_notificaciones (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            notificaciones_email INTEGER DEFAULT 1,
            notificaciones_push INTEGER DEFAULT 1,
            notificaciones_in_app INTEGER DEFAULT 1,
            alerta_stock_bajo INTEGER DEFAULT 1,
            alerta_producto_nuevo INTEGER DEFAULT 1,
            alerta_stock_actualizado INTEGER DEFAULT 0,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(usuario_id)
        )
        ''')
        
        # TABLA NOTIFICACIONES
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notificaciones (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            negocio_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            leido INTEGER DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            url TEXT,
            producto_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
        )
        ''')
        
        # TABLA SUSCRIPCIONES_PUSH
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS suscripciones_push (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(usuario_id, endpoint)
        )
        ''')
        
        # ÍNDICES
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_suscripciones_usuario ON suscripciones(usuario_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_suscripciones_negocio ON suscripciones(negocio_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notificaciones_usuario ON notificaciones(usuario_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notificaciones_leido ON notificaciones(leido)')
        
        conn.commit()
        conn.close()
        
        return '''
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Reparación DB - AIsa</title>
        <style>
            body { font-family: Arial; background: #0f0f1a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .container { background: #1a1a2e; padding: 40px; border-radius: 16px; max-width: 600px; border: 1px solid #2a2a3e; text-align: center; }
            .icon { font-size: 64px; }
            h1 { color: #6c3ce0; }
            .ok { color: #6bff6b; }
            .log { background: #0f0f1a; padding: 16px; border-radius: 8px; text-align: left; font-family: monospace; font-size: 12px; margin-top: 20px; }
            .btn { display: inline-block; padding: 12px 30px; background: #6c3ce0; color: #fff; text-decoration: none; border-radius: 8px; margin-top: 20px; }
            .btn:hover { background: #5a2ec0; }
        </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">✅</div>
                <h1>Base de Datos Reparada</h1>
                <p>Todas las tablas faltantes han sido creadas correctamente.</p>
                <div class="log">
                    <div class="ok">✅ Tabla suscripciones creada</div>
                    <div class="ok">✅ Tabla preferencias_notificaciones creada</div>
                    <div class="ok">✅ Tabla notificaciones creada</div>
                    <div class="ok">✅ Tabla suscripciones_push creada</div>
                    <div class="ok">✅ Índices creados</div>
                </div>
                <br>
                <a href="/dashboard" class="btn">← Volver al Dashboard</a>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Error - AIsa</title>
        <style>
            body {{ font-family: Arial; background: #0f0f1a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; }}
            .container {{ background: #1a1a2e; padding: 40px; border-radius: 16px; max-width: 600px; border: 1px solid #2a2a3e; text-align: center; }}
            .icon {{ font-size: 64px; }}
            h1 {{ color: #ff6b6b; }}
            .error {{ color: #ff6b6b; }}
            .log {{ background: #0f0f1a; padding: 16px; border-radius: 8px; text-align: left; font-family: monospace; font-size: 12px; margin-top: 20px; }}
            .btn {{ display: inline-block; padding: 12px 30px; background: #6c3ce0; color: #fff; text-decoration: none; border-radius: 8px; margin-top: 20px; }}
        </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">❌</div>
                <h1>Error al reparar</h1>
                <p class="error">{str(e)}</p>
                <div class="log">
                    <div class="error">❌ Error: {str(e)}</div>
                </div>
                <br>
                <a href="/dashboard" class="btn">← Volver al Dashboard</a>
            </div>
        </body>
        </html>
        '''

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
            print("❌ No hay token en admin_required")
            return jsonify({'error': 'No autorizado'}), 401
        try:
            usuario = obtener_usuario_sesion(token)
            if not usuario:
                print(f"❌ Usuario no encontrado para token")
                return jsonify({'error': 'No autorizado'}), 401
            
            print(f"🔍 admin_required - Usuario: {usuario.get('username')}, Rol: {usuario.get('rol')}")
            
            if usuario.get('rol') != 'admin':
                print(f"❌ Usuario {usuario.get('username')} no es admin (rol: {usuario.get('rol')})")
                return jsonify({'error': 'Acceso denegado'}), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ Error en admin_required: {e}")
            traceback.print_exc()
            return jsonify({'error': 'Error de autenticación'}), 401
    return decorated_function

# ============================================
# API - AGREGAR COLUMNA DESCRIPCION A PRODUCTOS
# ============================================

@app.route('/api/agregar-columna-descripcion', methods=['GET'])
@admin_required
def agregar_columna_descripcion():
    """Endpoint para agregar la columna descripcion a la tabla productos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verificar si la columna existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'descripcion'
        """)
        existe = cursor.fetchone()
        
        if existe:
            conn.close()
            return jsonify({
                'success': True,
                'message': 'La columna descripcion ya existe en la tabla productos'
            })
        
        # Agregar la columna
        cursor.execute("ALTER TABLE productos ADD COLUMN descripcion TEXT")
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '✅ Columna descripcion agregada correctamente a la tabla productos'
        })
        
    except Exception as e:
        print(f"❌ Error agregando columna: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================
# API - AGREGAR COLUMNA DESCRIPCION A SERVICIOS
# ============================================

@app.route('/api/agregar-columna-descripcion-servicios', methods=['GET'])
@admin_required
def agregar_columna_descripcion_servicios():
    """Endpoint para agregar la columna descripcion a la tabla servicios"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verificar si la columna existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'servicios' AND column_name = 'descripcion'
        """)
        existe = cursor.fetchone()
        
        if existe:
            conn.close()
            return jsonify({
                'success': True,
                'message': 'La columna descripcion ya existe en la tabla servicios'
            })
        
        # Agregar la columna
        cursor.execute("ALTER TABLE servicios ADD COLUMN descripcion TEXT")
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '✅ Columna descripcion agregada correctamente a la tabla servicios'
        })
        
    except Exception as e:
        print(f"❌ Error agregando columna: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - ADMIN SQL
# ============================================

@app.route('/api/admin/sql', methods=['POST'])
@admin_required
def api_admin_sql():
    """Ejecuta comandos SQL directamente (solo admin)"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'La consulta SQL está vacía'}), 400
        
        # Verificar que solo sean comandos DDL o DML permitidos
        query_lower = query.lower()
        comandos_permitidos = ['create table', 'alter table', 'drop table', 'insert into', 'update', 'delete from', 'select']
        permitido = any(query_lower.startswith(cmd) for cmd in comandos_permitidos)
        
        if not permitido:
            return jsonify({'error': 'Comando SQL no permitido'}), 403
        
        # Lista de comandos peligrosos
        comandos_peligrosos = ['drop database', 'truncate', 'drop table usuarios', 'drop table sesiones']
        for peligroso in comandos_peligrosos:
            if peligroso in query_lower:
                return jsonify({'error': f'Comando peligroso no permitido: {peligroso}'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Ejecutar la consulta
        cursor.execute(query)
        
        # Si es SELECT, devolver resultados
        if query_lower.startswith('select'):
            column_names = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            
            # Convertir a diccionarios
            result = []
            for row in rows:
                if column_names:
                    result.append(dict(zip(column_names, row)))
                else:
                    result.append(row)
            
            conn.commit()
            conn.close()
            return jsonify({
                'success': True,
                'type': 'select',
                'columns': column_names,
                'rows': result,
                'count': len(result)
            })
        else:
            # Para INSERT, UPDATE, DELETE, ALTER, CREATE, DROP
            rowcount = cursor.rowcount
            conn.commit()
            conn.close()
            return jsonify({
                'success': True,
                'type': 'command',
                'message': f'Comando ejecutado correctamente',
                'affected_rows': rowcount
            })
        
    except Exception as e:
        print(f"❌ Error ejecutando SQL: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================
# API - DIAGNÓSTICO DE BASE DE DATOS
# ============================================

@app.route('/api/admin/db-status', methods=['GET'])
@admin_required
def api_admin_db_status():
    """Obtiene el estado de la base de datos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Obtener todas las tablas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tablas = [row[0] for row in cursor.fetchall()]
        
        # Obtener conteo de registros por tabla
        info_tablas = {}
        for tabla in tablas:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
                count = cursor.fetchone()[0]
                info_tablas[tabla] = count
            except:
                info_tablas[tabla] = 'Error'
        
        # Verificar si existe la columna descripcion en productos
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'descripcion'
        """)
        tiene_descripcion_productos = cursor.fetchone() is not None
        
        # Verificar si existe la columna descripcion en servicios
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'servicios' AND column_name = 'descripcion'
        """)
        tiene_descripcion_servicios = cursor.fetchone() is not None
        
        conn.close()
        
        return jsonify({
            'success': True,
            'tablas': tablas,
            'info_tablas': info_tablas,
            'tiene_descripcion_productos': tiene_descripcion_productos,
            'tiene_descripcion_servicios': tiene_descripcion_servicios
        })
        
    except Exception as e:
        print(f"❌ Error en db-status: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# API - CATEGORÍAS Y SUBCATEGORÍAS
# ============================================

@app.route('/api/categorias', methods=['GET'])
@login_required
def api_obtener_categorias():
    """Obtiene todas las categorías principales"""
    try:
        categorias = obtener_categorias()
        return jsonify([dict(c) for c in categorias])
    except Exception as e:
        print(f"❌ Error en api_obtener_categorias: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/subcategorias', methods=['GET'])
@login_required
def api_obtener_subcategorias():
    """Obtiene subcategorías (filtradas por categoría si se especifica)"""
    try:
        categoria_id = request.args.get('categoria_id')
        if categoria_id:
            subcategorias = obtener_subcategorias(int(categoria_id))
        else:
            subcategorias = obtener_subcategorias()
        return jsonify([dict(s) for s in subcategorias])
    except Exception as e:
        print(f"❌ Error en api_obtener_subcategorias: {e}")
        return jsonify({'error': str(e)}), 500

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
        rol = data.get('rol', 'usuario')
        
        if not username or not email or not password:
            return jsonify({'error': 'Todos los campos son requeridos'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
        
        if obtener_usuario_por_username(username):
            return jsonify({'error': 'El nombre de usuario ya está en uso'}), 400
        
        user_id = crear_usuario(username, email, password, nombre, rol, tipo, datos_negocio)
        
        if not user_id:
            return jsonify({'error': 'Error al crear el usuario'}), 500
        
        marcar_usuario_verificado(user_id)
        
        registrar_log(user_id, 'registro', f'Usuario registrado: {username} (tipo: {tipo})')
        
        return jsonify({
            'success': True,
            'message': 'Usuario registrado correctamente',
            'user_id': user_id,
            'verificado': True
        })
        
    except Exception as e:
        print(f"❌ Error en register: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/verificar')
def verificar():
    return redirect(url_for('login'))

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
            return render_template('admin/dashboard.html', usuario=usuario)
        elif usuario.get('rol') == 'trabajador':
            return render_template('trabajador/dashboard.html', usuario=usuario)
        elif usuario.get('tipo') == 'negocio':
            return render_template('negocio/dashboard.html', usuario=usuario)
        else:
            return render_template('cliente/dashboard.html', usuario=usuario)
    except Exception as e:
        print(f"❌ Error en dashboard: {e}")
        return render_template('login.html')

@app.route('/admin/sql')
@admin_required
def admin_sql():
    """Panel de administración SQL"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('admin/sql_manager.html', usuario=usuario)

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

@app.route('/api/usuario/cambiar-password', methods=['POST'])
@login_required
def api_cambiar_password_usuario():
    """Endpoint para que cualquier usuario cambie su propia contraseña"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'error': 'La contraseña actual y la nueva son requeridas'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'La nueva contraseña debe tener al menos 6 caracteres'}), 400
    
    # Verificar contraseña actual
    if not verify_password(current_password, usuario.get('password_hash')):
        return jsonify({'error': 'Contraseña actual incorrecta'}), 401
    
    # Hashear nueva contraseña
    new_hash = hash_password(new_password)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET password_hash = %s WHERE id = %s', (new_hash, usuario['id']))
    conn.commit()
    conn.close()
    
    registrar_log(usuario['id'], 'cambio_password', 'Contraseña actualizada')
    
    return jsonify({'success': True, 'message': 'Contraseña actualizada correctamente'})

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
@login_required
def api_perfil_password():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
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
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    negocio_id = None
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
    
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
    try:
        token = request.cookies.get('token')
        usuario = obtener_usuario_sesion(token)
        
        if not usuario:
            return jsonify({'error': 'No autorizado'}), 401
        
        data = request.get_json()
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
                'rol': usuario.get('rol'),
                'verificado': usuario.get('verificado')
            }
        })
    return jsonify({'exists': False, 'message': 'Usuario no encontrado'})

# ============================================
# API - PRODUCTOS
# ============================================

@app.route('/api/productos', methods=['GET'])
@login_required
def api_obtener_productos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        productos = obtener_productos(negocio_id)
        return jsonify([dict(p) for p in productos])
    except Exception as e:
        print(f"❌ Error en api_obtener_productos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos', methods=['POST'])
@login_required
def api_crear_producto():
    """Crear un nuevo producto"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'admin':
        return jsonify({'success': False, 'error': 'Solo los negocios pueden crear productos'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Datos inválidos'}), 400
    
    nombre = data.get('nombre')
    categoria_id = data.get('categoria_id')
    subcategoria_id = data.get('subcategoria_id')
    precio = data.get('precio')
    costo = data.get('costo', 0)
    comision = data.get('comision', 0)
    stock = data.get('stock', 0)
    stock_minimo = data.get('stock_minimo', 3)
    descripcion = data.get('descripcion', '')
    
    print(f"📝 Creando producto: {nombre}, categoria_id={categoria_id}, subcategoria_id={subcategoria_id}, precio={precio}")
    
    if not nombre or not categoria_id or precio is None:
        return jsonify({'success': False, 'error': 'Nombre, categoría y precio son obligatorios'}), 400
    
    try:
        negocio_id = usuario.get('id')
        producto_id = crear_producto(
            negocio_id, 
            nombre, 
            categoria_id,
            subcategoria_id,
            float(precio), 
            float(costo), 
            float(comision), 
            int(stock), 
            int(stock_minimo),
            descripcion
        )
        
        if producto_id:
            registrar_log(usuario['id'], 'producto_creado', f'Producto: {nombre}')
            generar_notificacion_producto_nuevo(negocio_id, producto_id)
            generar_notificaciones_stock(negocio_id)
            
            return jsonify({'success': True, 'id': producto_id, 'message': 'Producto creado correctamente'})
        else:
            return jsonify({'success': False, 'error': 'Error al crear el producto en la base de datos'}), 500
    except Exception as e:
        print(f"❌ Error en api_crear_producto: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/producto/<int:producto_id>', methods=['PUT'])
@login_required
def api_actualizar_producto(producto_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    nombre = data.get('nombre')
    categoria_id = data.get('categoria_id')
    subcategoria_id = data.get('subcategoria_id')
    precio = data.get('precio')
    costo = data.get('costo', 0)
    comision = data.get('comision', 0)
    stock = data.get('stock', 0)
    stock_minimo = data.get('stock_minimo', 3)
    descripcion = data.get('descripcion', '')
    
    if not nombre or not categoria_id or precio is None:
        return jsonify({'error': 'Nombre, categoría y precio son obligatorios'}), 400
    
    try:
        producto_anterior = obtener_producto_por_id(producto_id)
        stock_anterior = producto_anterior.get('stock', 0) if producto_anterior else 0
        
        exito = actualizar_producto(
            producto_id, 
            nombre, 
            categoria_id,
            subcategoria_id,
            float(precio), 
            float(costo), 
            float(comision), 
            int(stock), 
            int(stock_minimo),
            descripcion
        )
        
        if exito:
            registrar_log(usuario['id'], 'producto_actualizado', f'Producto ID: {producto_id}')
            
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            
            if negocio_id and stock_anterior != stock:
                generar_notificacion_stock_actualizado(negocio_id, producto_id, stock_anterior, stock)
            
            if negocio_id:
                generar_notificaciones_stock(negocio_id)
            
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al actualizar el producto'}), 500
    except Exception as e:
        print(f"❌ Error en api_actualizar_producto: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/producto/<int:producto_id>', methods=['DELETE'])
@login_required
def api_eliminar_producto(producto_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        exito = eliminar_producto(producto_id)
        
        if exito:
            registrar_log(usuario['id'], 'producto_eliminado', f'Producto ID: {producto_id}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al eliminar el producto'}), 500
    except Exception as e:
        print(f"❌ Error en api_eliminar_producto: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/producto/<int:producto_id>/foto', methods=['POST'])
@login_required
def api_subir_foto_producto(producto_id):
    """Sube una foto para un producto a Google Drive"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if 'foto' not in request.files:
        return jsonify({'error': 'No se envió ninguna foto'}), 400
    
    foto = request.files['foto']
    if foto.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
    
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    extension = foto.filename.rsplit('.', 1)[1].lower() if '.' in foto.filename else ''
    if extension not in allowed_extensions:
        return jsonify({'error': f'Formato no permitido. Use: {", ".join(allowed_extensions)}'}), 400
    
    try:
        storage = get_storage_manager()
        nombre_foto = f"{uuid.uuid4().hex}.{extension}"
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        exito = storage.subir_foto_producto(negocio_id, producto_id, foto, nombre_foto)
        
        if exito:
            if not storage.use_local:
                file_id = storage.obtener_file_id(negocio_id, producto_id, nombre_foto)
                foto_url = storage.obtener_url_foto(negocio_id, producto_id, nombre_foto, file_id)
                actualizar_foto_producto(producto_id, foto_url, file_id)
            else:
                foto_url = storage.obtener_url_foto(negocio_id, producto_id, nombre_foto)
                actualizar_foto_producto(producto_id, foto_url)
            
            return jsonify({'success': True, 'url': foto_url})
        else:
            return jsonify({'error': 'Error al subir la foto'}), 500
            
    except Exception as e:
        print(f"❌ Error en api_subir_foto_producto: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/stock', methods=['GET'])
@login_required
def api_productos_con_stock():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        productos = obtener_productos_con_stock(negocio_id)
        return jsonify([dict(p) for p in productos])
    except Exception as e:
        print(f"❌ Error en api_productos_con_stock: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/todos/productos', methods=['GET'])
@admin_required
def api_todos_productos():
    try:
        productos = obtener_todos_productos()
        return jsonify([dict(p) for p in productos])
    except Exception as e:
        print(f"❌ Error en api_todos_productos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - TIENDA
# ============================================

@app.route('/api/tienda/productos', methods=['GET'])
@login_required
def api_obtener_productos_tienda():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        productos = obtener_productos_tienda_negocio(negocio_id)
        return jsonify([dict(p) for p in productos])
    except Exception as e:
        print(f"❌ Error en api_obtener_productos_tienda: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/agregar', methods=['POST'])
@login_required
def api_agregar_producto_tienda():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    producto_id = data.get('producto_id')
    destacado = data.get('destacado', 0)
    
    if not producto_id:
        return jsonify({'error': 'Producto ID es requerido'}), 400
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        agregar_producto_tienda(negocio_id, producto_id, destacado)
        registrar_log(usuario['id'], 'producto_tienda_agregado', f'Producto ID: {producto_id}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_agregar_producto_tienda: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/<int:tienda_id>/destacar', methods=['POST'])
@login_required
def api_toggle_destacado_tienda(tienda_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    destacado = data.get('destacado', 0)
    
    try:
        toggle_destacado_tienda(tienda_id, destacado)
        registrar_log(usuario['id'], 'producto_tienda_destacado', f'Tienda ID: {tienda_id}, Destacado: {destacado}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_toggle_destacado_tienda: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/<int:tienda_id>', methods=['DELETE'])
@login_required
def api_eliminar_producto_tienda(tienda_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        eliminar_producto_tienda(tienda_id)
        registrar_log(usuario['id'], 'producto_tienda_eliminado', f'Tienda ID: {tienda_id}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_eliminar_producto_tienda: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - TIENDA PÚBLICA (PARA CLIENTE)
# ============================================

@app.route('/api/tienda/public', methods=['GET'])
@login_required
def api_tienda_publica():
    """Versión simple - obtiene productos de tienda sin JOIN complejos"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        print("=" * 50)
        print("🚀 /api/tienda/public - Iniciando (versión simple)")
        
        conn = get_db()
        cursor = conn.cursor()
        
        # PASO 1: Obtener todos los productos en tienda
        print("📊 PASO 1: Obteniendo productos_tienda...")
        cursor.execute("SELECT producto_id, destacado FROM productos_tienda")
        tienda_rows = cursor.fetchall()
        print(f"   → Encontrados: {len(tienda_rows)}")
        
        if not tienda_rows:
            print("⚠️ No hay productos en la tienda")
            conn.close()
            return jsonify([])
        
        # PASO 2: Obtener los productos
        producto_ids = [str(row[0]) for row in tienda_rows]
        ids_str = ','.join(producto_ids)
        
        print(f"📊 PASO 2: Obteniendo productos con IDs: {ids_str}")
        query = f"""
            SELECT id, nombre, categoria_id, subcategoria_id, precio, stock, foto_url, stock_minimo, negocio_id
            FROM productos
            WHERE id IN ({ids_str}) AND stock > 0
        """
        cursor.execute(query)
        productos_rows = cursor.fetchall()
        print(f"   → Productos encontrados: {len(productos_rows)}")
        
        if not productos_rows:
            print("⚠️ No hay productos con stock > 0")
            conn.close()
            return jsonify([])
        
        # Crear diccionario de destacados
        destacados = {row[0]: row[1] for row in tienda_rows}
        
        # PASO 3: Obtener datos de negocios uno por uno
        print("📊 PASO 3: Obteniendo datos de negocios...")
        negocio_ids = list(set([row[8] for row in productos_rows]))
        negocios = {}
        
        for neg_id in negocio_ids:
            cursor.execute("""
                SELECT id, username, nombre, datos_negocio, latitud, longitud
                FROM usuarios WHERE id = %s
            """, (neg_id,))
            row = cursor.fetchone()
            if row:
                datos = {}
                if row[3]:
                    try:
                        datos = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                    except:
                        pass
                negocios[neg_id] = {
                    'username': row[1],
                    'nombre': row[2] or datos.get('nombre_negocio', row[1]),
                    'telefono': datos.get('telefono', ''),
                    'direccion': datos.get('direccion', ''),
                    'provincia': datos.get('provincia', ''),
                    'municipio': datos.get('municipio', ''),
                    'latitud': row[4],
                    'longitud': row[5]
                }
        
        print(f"   → Negocios cargados: {len(negocios)}")
        
        # PASO 4: Obtener categorías y subcategorías
        print("📊 PASO 4: Obteniendo categorías...")
        categorias = {}
        cursor.execute("SELECT id, nombre, icono FROM categorias")
        for row in cursor.fetchall():
            categorias[row[0]] = {'nombre': row[1], 'icono': row[2]}
        
        subcategorias = {}
        cursor.execute("SELECT id, categoria_id, nombre FROM subcategorias")
        for row in cursor.fetchall():
            subcategorias[row[0]] = {'categoria_id': row[1], 'nombre': row[2]}
        
        # PASO 5: Construir resultado
        print("📊 PASO 5: Construyendo resultado...")
        resultado = []
        
        for p in productos_rows:
            negocio = negocios.get(p[8], {})
            
            # Obtener ubicación del usuario para filtrar
            datos_usuario = obtener_datos_negocio(usuario['id'])
            provincia = datos_usuario.get('provincia', '')
            municipio = datos_usuario.get('municipio', '')
            
            # Filtrar por ubicación
            if provincia and municipio:
                prov_negocio = negocio.get('provincia', '')
                mun_negocio = negocio.get('municipio', '')
                if prov_negocio != provincia or mun_negocio != municipio:
                    continue
            
            # Obtener nombres de categorías
            cat_id = p[2]
            subcat_id = p[3]
            categoria_nombre = categorias.get(cat_id, {}).get('nombre', '') if cat_id else ''
            categoria_icono = categorias.get(cat_id, {}).get('icono', '') if cat_id else ''
            subcategoria_nombre = subcategorias.get(subcat_id, {}).get('nombre', '') if subcat_id else ''
            
            resultado.append({
                'id': p[0],
                'nombre': p[1],
                'categoria_id': cat_id,
                'categoria_nombre': categoria_nombre,
                'categoria_icono': categoria_icono,
                'subcategoria_id': subcat_id,
                'subcategoria_nombre': subcategoria_nombre,
                'precio': float(p[4]),
                'stock': p[5],
                'stock_minimo': p[7] or 3,
                'foto_url': p[6],
                'descripcion': '',
                'negocio_id': p[8],
                'negocio_username': negocio.get('username', ''),
                'negocio_nombre': negocio.get('nombre', ''),
                'telefono': negocio.get('telefono', ''),
                'direccion': negocio.get('direccion', ''),
                'provincia': negocio.get('provincia', ''),
                'municipio': negocio.get('municipio', ''),
                'latitud': negocio.get('latitud'),
                'longitud': negocio.get('longitud'),
                'destacado': destacados.get(p[0], 0),
                'tipo': 'producto'
            })
        
        print(f"✅ Productos filtrados: {len(resultado)}")
        print("=" * 50)
        
        conn.close()
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ ERROR en api_tienda_publica: {e}")
        traceback.print_exc()
        try:
            conn.close()
        except:
            pass
        return jsonify({'error': str(e)}), 500

# ============================================
# API - SERVICIOS PÚBLICOS (PARA CLIENTE)
# ============================================

@app.route('/api/servicios/publicos', methods=['GET'])
@login_required
def api_servicios_publicos():
    """Obtiene servicios de negocios cercanos para el catálogo del cliente"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        print("=" * 50)
        print("🚀 /api/servicios/publicos - Iniciando")
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Obtener ubicación del usuario
        datos_usuario = obtener_datos_negocio(usuario['id'])
        provincia = datos_usuario.get('provincia', '')
        municipio = datos_usuario.get('municipio', '')
        print(f"📍 Ubicación usuario: {provincia}, {municipio}")
        
        # Obtener servicios activos con datos del negocio
        print("📊 Obteniendo servicios...")
        cursor.execute("""
            SELECT s.id, s.nombre, s.categoria, s.precio, s.duracion, 
                   s.negocio_id,
                   u.username, u.nombre, u.datos_negocio, u.latitud, u.longitud
            FROM servicios s
            JOIN usuarios u ON s.negocio_id = u.id
            WHERE s.activo = 1 AND u.activo = 1 AND u.tipo = 'negocio'
            ORDER BY s.id DESC
            LIMIT 30
        """)
        
        rows = cursor.fetchall()
        print(f"📋 Servicios encontrados: {len(rows)}")
        
        resultado = []
        for row in rows:
            datos = {}
            if row[8]:
                try:
                    datos = json.loads(row[8]) if isinstance(row[8], str) else row[8]
                except:
                    pass
            
            # Filtrar por ubicación
            if provincia and municipio:
                prov_servicio = datos.get('provincia', '')
                mun_servicio = datos.get('municipio', '')
                if prov_servicio != provincia or mun_servicio != municipio:
                    continue
            
            resultado.append({
                'id': row[0],
                'nombre': row[1],
                'categoria': row[2],
                'precio': float(row[3]),
                'duracion': row[4] or 60,
                'descripcion': '',
                'negocio_id': row[5],
                'negocio_username': row[6],
                'negocio_nombre': row[7] or datos.get('nombre_negocio', row[6]),
                'telefono': datos.get('telefono', ''),
                'direccion': datos.get('direccion', ''),
                'provincia': datos.get('provincia', ''),
                'municipio': datos.get('municipio', ''),
                'latitud': row[9],
                'longitud': row[10],
                'tipo': 'servicio'
            })
        
        print(f"✅ Servicios filtrados por ubicación: {len(resultado)}")
        print("=" * 50)
        
        conn.close()
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ ERROR en api_servicios_publicos: {e}")
        traceback.print_exc()
        try:
            conn.close()
        except:
            pass
        return jsonify({'error': str(e)}), 500

# ============================================
# API - SERVICIOS
# ============================================

@app.route('/api/servicios', methods=['GET'])
@login_required
def api_obtener_servicios():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            servicios = obtener_servicios(negocio_id, usuario['id'])
        else:
            servicios = obtener_servicios(negocio_id)
        
        return jsonify([dict(s) for s in servicios])
    except Exception as e:
        print(f"❌ Error en api_obtener_servicios: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/servicios', methods=['POST'])
@login_required
def api_crear_servicio():
    """Crear un nuevo servicio"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'admin':
        return jsonify({'success': False, 'error': 'Solo los negocios pueden crear servicios'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Datos inválidos'}), 400
    
    nombre = data.get('nombre')
    categoria = data.get('categoria')
    precio = data.get('precio')
    duracion = data.get('duracion', 60)
    activo = data.get('activo', True)
    descripcion = data.get('descripcion', '')
    
    print(f"📝 Creando servicio: {nombre}, {categoria}, {precio}")
    
    if not nombre or not categoria or precio is None:
        return jsonify({'success': False, 'error': 'Nombre, categoría y precio son obligatorios'}), 400
    
    try:
        negocio_id = usuario.get('id')
        trabajador_id = None
        
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'success': False, 'error': 'No estás asignado a ningún negocio'}), 403
            trabajador_id = usuario['id']
        
        servicio_id = crear_servicio(
            negocio_id, 
            trabajador_id, 
            nombre, 
            categoria, 
            float(precio), 
            int(duracion), 
            1 if activo else 0, 
            descripcion
        )
        
        if servicio_id:
            registrar_log(usuario['id'], 'servicio_creado', f'Servicio: {nombre}')
            return jsonify({'success': True, 'id': servicio_id, 'message': 'Servicio creado correctamente'})
        else:
            return jsonify({'success': False, 'error': 'Error al crear el servicio en la base de datos'}), 500
    except Exception as e:
        print(f"❌ Error en api_crear_servicio: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/servicio/<int:servicio_id>/toggle', methods=['POST'])
@login_required
def api_toggle_servicio(servicio_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    activo = data.get('activo', 1)
    
    try:
        toggle_servicio(servicio_id, activo)
        registrar_log(usuario['id'], 'servicio_toggle', f'Servicio ID: {servicio_id}, Activo: {activo}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_toggle_servicio: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/servicio/<int:servicio_id>', methods=['DELETE'])
@login_required
def api_eliminar_servicio(servicio_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        eliminar_servicio(servicio_id)
        registrar_log(usuario['id'], 'servicio_eliminado', f'Servicio ID: {servicio_id}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_eliminar_servicio: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/todos/servicios', methods=['GET'])
@admin_required
def api_todos_servicios():
    try:
        servicios = obtener_todos_servicios()
        return jsonify([dict(s) for s in servicios])
    except Exception as e:
        print(f"❌ Error en api_todos_servicios: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - TRABAJADORES
# ============================================

@app.route('/api/negocio/trabajadores', methods=['GET'])
@login_required
def api_obtener_trabajadores_negocio():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        if usuario.get('rol') == 'admin':
            trabajadores = obtener_todos_usuarios()
            trabajadores = [t for t in trabajadores if t.get('rol') == 'trabajador']
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            trabajadores = obtener_trabajadores_por_empresa(negocio_id)
        
        return jsonify([dict(t) for t in trabajadores])
    except Exception as e:
        print(f"❌ Error en api_obtener_trabajadores_negocio: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/negocio/trabajador/crear', methods=['POST'])
@login_required
def api_crear_trabajador_negocio():
    """Crear un nuevo trabajador para el negocio"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'admin':
        return jsonify({'error': 'Solo los negocios pueden crear trabajadores'}), 403
    
    data = request.get_json()
    print(f"📝 Datos recibidos para trabajador: {data}")
    
    nombre = data.get('nombre')
    apellidos = data.get('apellidos', '')
    ci = data.get('ci')
    movil = data.get('movil', '')
    direccion = data.get('direccion', '')
    frecuencia = data.get('frecuencia', 'diaria')
    salario = data.get('salario')
    email = data.get('email', '')
    usuario_username = data.get('usuario')
    password = data.get('password')
    modulos = data.get('modulos', [])
    
    # Validaciones
    if not nombre:
        return jsonify({'error': 'El nombre es obligatorio'}), 400
    if not ci:
        return jsonify({'error': 'El CI es obligatorio'}), 400
    if salario is None:
        return jsonify({'error': 'El salario es obligatorio'}), 400
    if not usuario_username:
        return jsonify({'error': 'El nombre de usuario es obligatorio'}), 400
    if not password:
        return jsonify({'error': 'La contraseña es obligatoria'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
    
    try:
        if obtener_usuario_por_username(usuario_username):
            return jsonify({'error': 'El nombre de usuario ya está en uso'}), 400
        
        datos_negocio = {
            'nombre': nombre,
            'apellidos': apellidos or '',
            'ci': ci,
            'movil': movil or '',
            'direccion': direccion or '',
            'frecuencia': frecuencia,
            'salario': float(salario),
            'negocio_id': usuario['id']
        }
        
        user_id = crear_usuario(
            usuario_username, 
            email or f'{usuario_username}@trabajador.com', 
            password, 
            nombre, 
            'trabajador', 
            'negocio', 
            datos_negocio
        )
        
        if not user_id:
            return jsonify({'error': 'Error al crear el trabajador'}), 500
        
        for modulo_nombre in modulos:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM modulos WHERE nombre = %s', (modulo_nombre,))
            mod = cursor.fetchone()
            conn.close()
            if mod:
                asignar_permiso_usuario(user_id, mod[0], 1)
        
        crear_trabajador_negocio(usuario['id'], user_id, nombre, float(salario))
        
        registrar_log(usuario['id'], 'trabajador_creado', f'Trabajador: {nombre} (ID: {user_id})')
        
        return jsonify({
            'success': True,
            'message': f'Trabajador {nombre} creado correctamente',
            'id': user_id
        })
    except Exception as e:
        print(f"❌ Error en api_crear_trabajador_negocio: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/negocio/trabajador/<int:trabajador_id>', methods=['PUT'])
@login_required
def api_actualizar_trabajador_negocio(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    nombre = data.get('nombre')
    apellidos = data.get('apellidos')
    ci = data.get('ci')
    movil = data.get('movil')
    direccion = data.get('direccion')
    frecuencia = data.get('frecuencia')
    salario = data.get('salario')
    email = data.get('email')
    modulos = data.get('modulos')
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        if salario is not None:
            actualizar_trabajador_negocio(negocio_id, trabajador_id, nombre or '', float(salario))
        
        if nombre or ci or movil or direccion:
            trabajador = obtener_trabajador_por_id(trabajador_id)
            if trabajador:
                datos_negocio = {}
                if trabajador.get('datos_negocio'):
                    try:
                        datos_negocio = json.loads(trabajador['datos_negocio']) if isinstance(trabajador['datos_negocio'], str) else trabajador['datos_negocio']
                    except:
                        pass
                
                datos_negocio.update({
                    'nombre': nombre or datos_negocio.get('nombre', ''),
                    'apellidos': apellidos or datos_negocio.get('apellidos', ''),
                    'ci': ci or datos_negocio.get('ci', ''),
                    'movil': movil or datos_negocio.get('movil', ''),
                    'direccion': direccion or datos_negocio.get('direccion', ''),
                    'frecuencia': frecuencia or datos_negocio.get('frecuencia', 'diaria')
                })
                
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('UPDATE usuarios SET datos_negocio = %s, nombre = %s, email = %s WHERE id = %s',
                             (json.dumps(datos_negocio, ensure_ascii=False), nombre, email or trabajador.get('email'), trabajador_id))
                conn.commit()
                conn.close()
        
        if modulos is not None:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM permisos_usuario WHERE usuario_id = %s', (trabajador_id,))
            
            for modulo_nombre in modulos:
                cursor.execute('SELECT id FROM modulos WHERE nombre = %s', (modulo_nombre,))
                mod = cursor.fetchone()
                if mod:
                    cursor.execute('INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud) VALUES (%s, %s, 1, %s)',
                                 (trabajador_id, mod[0], 'aprobado'))
            conn.commit()
            conn.close()
        
        registrar_log(usuario['id'], 'trabajador_actualizado', f'Trabajador ID: {trabajador_id}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_actualizar_trabajador_negocio: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/negocio/trabajador/<int:trabajador_id>/toggle', methods=['POST'])
@login_required
def api_toggle_trabajador_negocio(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    activo = data.get('activo', 1)
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        exito = toggle_trabajador_negocio(negocio_id, trabajador_id, activo)
        
        if exito:
            registrar_log(usuario['id'], 'trabajador_toggle', f'Trabajador ID: {trabajador_id}, Activo: {activo}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al actualizar el trabajador'}), 500
    except Exception as e:
        print(f"❌ Error en api_toggle_trabajador_negocio: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/negocio/trabajador/<int:trabajador_id>/eliminar', methods=['DELETE'])
@login_required
def api_eliminar_trabajador(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        exito = eliminar_trabajador_definitivo(trabajador_id)
        
        if exito:
            registrar_log(usuario['id'], 'trabajador_eliminado', f'Trabajador ID: {trabajador_id}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al eliminar el trabajador'}), 500
    except Exception as e:
        print(f"❌ Error en api_eliminar_trabajador: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - CONTRATOS
# ============================================

@app.route('/api/contratos', methods=['GET'])
@login_required
def api_obtener_contratos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        if usuario.get('rol') == 'admin':
            contratos = obtener_todos_contratos()
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            contratos = obtener_contratos(negocio_id)
        
        return jsonify([dict(c) for c in contratos])
    except Exception as e:
        print(f"❌ Error en api_obtener_contratos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contratos', methods=['POST'])
@login_required
def api_crear_contrato():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'admin':
        return jsonify({'error': 'Solo los negocios pueden crear contratos'}), 403
    
    data = request.get_json()
    print(f"📝 Datos para crear contrato: {data}")
    
    empresa = data.get('empresa')
    numero_contrato = data.get('numero_contrato')
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    tipo = data.get('tipo', 'ventas')
    monto = data.get('monto', 0)
    descripcion = data.get('descripcion', '')
    estado = data.get('estado', 'activo')
    
    # Validar campos obligatorios
    if not empresa:
        return jsonify({'error': 'La empresa es obligatoria'}), 400
    if not numero_contrato:
        return jsonify({'error': 'El número de contrato es obligatorio'}), 400
    if not fecha_inicio:
        return jsonify({'error': 'La fecha de inicio es obligatoria'}), 400
    if not fecha_fin:
        return jsonify({'error': 'La fecha de fin es obligatoria'}), 400
    if not tipo:
        return jsonify({'error': 'El tipo de contrato es obligatorio'}), 400
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        contrato_id = crear_contrato(
            negocio_id=negocio_id,
            trabajador_id=None,
            empresa=empresa,
            numero_contrato=numero_contrato,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo=tipo,
            monto=monto,
            estado=estado,
            descripcion=descripcion
        )
        
        if contrato_id:
            registrar_log(usuario['id'], 'contrato_creado', f'Contrato ID: {contrato_id}')
            return jsonify({'success': True, 'id': contrato_id})
        else:
            return jsonify({'error': 'Error al crear el contrato'}), 500
    except Exception as e:
        print(f"❌ Error en api_crear_contrato: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contrato/<int:contrato_id>', methods=['PUT'])
@login_required
def api_actualizar_contrato(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    
    empresa = data.get('empresa')
    numero_contrato = data.get('numero_contrato')
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    tipo = data.get('tipo')
    monto = data.get('monto')
    descripcion = data.get('descripcion')
    estado = data.get('estado')
    
    try:
        # Verificar que el contrato existe y pertenece al negocio
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT negocio_id FROM contratos WHERE id = %s', (contrato_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Contrato no encontrado'}), 404
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        
        if result[0] != negocio_id and usuario.get('rol') != 'admin':
            return jsonify({'error': 'No tienes permiso para modificar este contrato'}), 403
        
        # Actualizar el contrato
        exito = actualizar_contrato(
            contrato_id=contrato_id,
            tipo=tipo,
            salario=None,
            salario_promedio=None,
            frecuencia_pago=None,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            descripcion=descripcion
        )
        
        if exito:
            registrar_log(usuario['id'], 'contrato_actualizado', f'Contrato ID: {contrato_id}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al actualizar el contrato'}), 500
    except Exception as e:
        print(f"❌ Error en api_actualizar_contrato: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contrato/<int:contrato_id>/estado', methods=['POST'])
@login_required
def api_cambiar_estado_contrato(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    estado = data.get('estado')
    
    if estado not in ['activo', 'finalizado', 'cancelado', 'pendiente']:
        return jsonify({'error': 'Estado inválido'}), 400
    
    try:
        # Verificar que el contrato existe
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT negocio_id FROM contratos WHERE id = %s', (contrato_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Contrato no encontrado'}), 404
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        
        if result[0] != negocio_id and usuario.get('rol') != 'admin':
            return jsonify({'error': 'No tienes permiso para modificar este contrato'}), 403
        
        exito = actualizar_estado_contrato(contrato_id, estado)
        
        if exito:
            registrar_log(usuario['id'], 'contrato_estado', f'Contrato ID: {contrato_id}, Estado: {estado}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al actualizar el estado'}), 500
    except Exception as e:
        print(f"❌ Error en api_cambiar_estado_contrato: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contrato/<int:contrato_id>', methods=['DELETE'])
@login_required
def api_eliminar_contrato(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        # Verificar que el contrato existe
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT negocio_id FROM contratos WHERE id = %s', (contrato_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Contrato no encontrado'}), 404
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        
        if result[0] != negocio_id and usuario.get('rol') != 'admin':
            return jsonify({'error': 'No tienes permiso para eliminar este contrato'}), 403
        
        exito = eliminar_contrato(contrato_id)
        
        if exito:
            registrar_log(usuario['id'], 'contrato_eliminado', f'Contrato ID: {contrato_id}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al eliminar el contrato'}), 500
    except Exception as e:
        print(f"❌ Error en api_eliminar_contrato: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contratos/empresas', methods=['GET'])
@login_required
def api_contratos_empresas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        empresas = obtener_empresas_con_contratos_activos(negocio_id)
        return jsonify(empresas)
    except Exception as e:
        print(f"❌ Error en api_contratos_empresas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - NÓMINA
# ============================================

@app.route('/api/nomina', methods=['GET'])
@login_required
def api_obtener_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        
        if not mes or not anio:
            fecha = datetime.now()
            mes = fecha.month
            anio = fecha.year
        else:
            mes = int(mes)
            anio = int(anio)
        
        if usuario.get('rol') == 'admin':
            nomina = obtener_nomina_mes(mes, anio)
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            nomina = obtener_nomina_mes(mes, anio, negocio_id)
        
        return jsonify([dict(n) for n in nomina])
    except Exception as e:
        print(f"❌ Error en api_obtener_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/calcular', methods=['POST'])
@login_required
def api_calcular_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    trabajador_id = data.get('trabajador_id')
    mes = data.get('mes', datetime.now().month)
    anio = data.get('anio', datetime.now().year)
    
    if not trabajador_id:
        return jsonify({'error': 'Trabajador ID es requerido'}), 400
    
    try:
        resultado = calcular_nomina(trabajador_id, mes, anio)
        
        if resultado:
            return jsonify(resultado)
        else:
            return jsonify({'error': 'No se pudo calcular la nómina'}), 500
    except Exception as e:
        print(f"❌ Error en api_calcular_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/trabajador/<int:trabajador_id>', methods=['GET'])
@login_required
def api_obtener_nomina_trabajador(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        mes = request.args.get('mes', datetime.now().month, type=int)
        anio = request.args.get('anio', datetime.now().year, type=int)
        
        nomina = obtener_nomina_trabajador(trabajador_id, mes, anio)
        
        if nomina:
            return jsonify(dict(nomina))
        else:
            return jsonify({'error': 'No se encontró nómina para este trabajador'}), 404
    except Exception as e:
        print(f"❌ Error en api_obtener_nomina_trabajador: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/resumen', methods=['GET'])
@login_required
def api_resumen_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        if usuario.get('rol') == 'admin':
            resumen = obtener_resumen_nomina()
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            resumen = obtener_resumen_nomina(negocio_id)
        
        return jsonify(resumen)
    except Exception as e:
        print(f"❌ Error en api_resumen_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/asistencia', methods=['GET'])
@login_required
def api_obtener_asistencia():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        mes = request.args.get('mes', datetime.now().month, type=int)
        anio = request.args.get('anio', datetime.now().year, type=int)
        
        if usuario.get('rol') == 'trabajador':
            trabajador_id = usuario['id']
        else:
            trabajador_id = request.args.get('trabajador_id', type=int)
            if not trabajador_id:
                return jsonify({'error': 'Trabajador ID es requerido'}), 400
        
        asistencia = obtener_asistencia_mes(trabajador_id, mes, anio)
        return jsonify(asistencia)
    except Exception as e:
        print(f"❌ Error en api_obtener_asistencia: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/asistencia/registrar', methods=['POST'])
@login_required
def api_registrar_asistencia():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    trabajador_id = data.get('trabajador_id')
    fecha = data.get('fecha', datetime.now().date().isoformat())
    hora_entrada = data.get('hora_entrada')
    hora_salida = data.get('hora_salida')
    tipo = data.get('tipo', 'presencial')
    estado = data.get('estado', 'presente')
    observaciones = data.get('observaciones', '')
    
    if not trabajador_id and usuario.get('rol') != 'admin':
        trabajador_id = usuario['id']
    
    if not trabajador_id:
        return jsonify({'error': 'Trabajador ID es requerido'}), 400
    
    try:
        asistencia_id = registrar_asistencia(
            trabajador_id,
            fecha,
            hora_entrada,
            hora_salida,
            tipo,
            estado,
            observaciones
        )
        
        if asistencia_id:
            registrar_log(usuario['id'], 'asistencia_registrada', f'Trabajador: {trabajador_id}, Fecha: {fecha}')
            return jsonify({'success': True, 'id': asistencia_id})
        else:
            return jsonify({'error': 'Error al registrar la asistencia'}), 500
    except Exception as e:
        print(f"❌ Error en api_registrar_asistencia: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - COMISIONES
# ============================================

@app.route('/api/comisiones', methods=['GET'])
@login_required
def api_obtener_comisiones():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        mes = request.args.get('mes', datetime.now().month, type=int)
        anio = request.args.get('anio', datetime.now().year, type=int)
        
        if usuario.get('rol') == 'admin':
            comisiones = obtener_comisiones_negocio_mes(mes, anio)
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
                comisiones = obtener_comisiones_trabajador_mes(usuario['id'], mes, anio)
            else:
                comisiones = obtener_comisiones_negocio_mes(mes, anio, negocio_id)
        
        return jsonify([dict(c) for c in comisiones])
    except Exception as e:
        print(f"❌ Error en api_obtener_comisiones: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/comisiones/registrar', methods=['POST'])
@login_required
def api_registrar_comision():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'admin':
        return jsonify({'error': 'Solo los negocios pueden registrar comisiones'}), 403
    
    data = request.get_json()
    trabajador_id = data.get('trabajador_id')
    monto = data.get('monto')
    concepto = data.get('concepto', 'Comisión')
    mes = data.get('mes', datetime.now().month)
    anio = data.get('anio', datetime.now().year)
    
    if not trabajador_id or monto is None:
        return jsonify({'error': 'Trabajador y monto son obligatorios'}), 400
    
    try:
        comision_id = registrar_comision(
            trabajador_id,
            float(monto),
            concepto,
            mes,
            anio
        )
        
        if comision_id:
            registrar_log(usuario['id'], 'comision_registrada', f'Trabajador: {trabajador_id}, Monto: {monto}')
            return jsonify({'success': True, 'id': comision_id})
        else:
            return jsonify({'error': 'Error al registrar la comisión'}), 500
    except Exception as e:
        print(f"❌ Error en api_registrar_comision: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - VENTAS
# ============================================

@app.route('/api/ventas', methods=['GET'])
@login_required
def api_obtener_ventas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        if usuario.get('rol') == 'admin':
            ventas = obtener_todas_ventas()
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
                ventas = obtener_ventas(negocio_id, usuario['id'])
            else:
                ventas = obtener_ventas(negocio_id)
        
        return jsonify([dict(v) for v in ventas])
    except Exception as e:
        print(f"❌ Error en api_obtener_ventas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ventas', methods=['POST'])
@login_required
def api_crear_venta():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'admin' and usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'No tienes permiso para crear ventas'}), 403
    
    data = request.get_json()
    print(f"📝 Datos para crear venta: {data}")
    
    # Obtener datos del frontend
    productos = data.get('productos', [])
    cliente = data.get('cliente', '')
    estado = data.get('estado', 'completada')
    empresa = data.get('empresa')
    factura = data.get('factura')
    es_oferta = data.get('es_oferta', False) or estado == 'oferta'
    
    if not productos:
        return jsonify({'error': 'Debe incluir al menos un producto'}), 400
    
    try:
        negocio_id = usuario.get('id')
        trabajador_id = None
        
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            trabajador_id = usuario['id']
        
        total = sum(p.get('precio', 0) * p.get('cantidad', 0) for p in productos)
        cantidad_total = sum(p.get('cantidad', 1) for p in productos)
        
        # Obtener el primer producto para los campos simples
        primer_producto = productos[0] if productos else None
        producto_id = primer_producto.get('id') if primer_producto else None
        producto_nombre = primer_producto.get('nombre', '') if primer_producto else ''
        tipo_producto = 'servicio' if primer_producto and primer_producto.get('tipo') == 'servicio' else 'producto'
        
        # Generar número de factura SOLO si NO es oferta y hay empresa
        numero_factura = None
        if not es_oferta and empresa:
            if factura:
                numero_factura = factura
            else:
                numero_factura = generar_numero_factura(negocio_id, empresa)
        
        # Si es oferta, usar estado 'oferta'
        if es_oferta:
            estado = 'oferta'
        
        # Crear la venta (esto descuenta el stock automáticamente)
        venta_id = crear_venta(
            negocio_id=negocio_id,
            trabajador_id=trabajador_id,
            cliente=cliente,
            producto=producto_nombre,
            producto_id=producto_id,
            cantidad=cantidad_total,
            precio=total,
            total=total,
            estado=estado,
            empresa=empresa,
            tipo=tipo_producto,
            factura=numero_factura,
            factura_url=None,
            transferencia_id=data.get('transferencia_id'),
            transferencia_cedula=data.get('transferencia_cedula'),
            transferencia_banco=data.get('transferencia_banco'),
            transferencia_fecha=data.get('transferencia_fecha')
        )
        
        if venta_id:
            registrar_log(usuario['id'], 'venta_creada', f'Venta ID: {venta_id}, Total: {total}')
            return jsonify({
                'success': True, 
                'id': venta_id, 
                'numero_factura': numero_factura,
                'es_oferta': es_oferta,
                'message': 'Venta creada correctamente'
            })
        else:
            return jsonify({'error': 'Error al crear la venta'}), 500
    except Exception as e:
        print(f"❌ Error en api_crear_venta: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/venta/<int:venta_id>', methods=['GET'])
@login_required
def api_obtener_venta(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        venta = obtener_venta_por_id(venta_id)
        
        if not venta:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        # Verificar que el usuario tenga acceso a esta venta
        if usuario.get('rol') != 'admin':
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            
            if venta.get('negocio_id') != negocio_id and venta.get('trabajador_id') != usuario.get('id'):
                return jsonify({'error': 'No tienes permiso para ver esta venta'}), 403
        
        return jsonify(dict(venta))
    except Exception as e:
        print(f"❌ Error en api_obtener_venta: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/venta/<int:venta_id>/estado', methods=['POST'])
@login_required
def api_actualizar_estado_venta(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    estado = data.get('estado')
    
    if estado not in ['completada', 'cancelada', 'pendiente', 'reembolsada']:
        return jsonify({'error': 'Estado inválido'}), 400
    
    try:
        exito = actualizar_estado_venta(venta_id, estado)
        
        if exito:
            registrar_log(usuario['id'], 'venta_estado', f'Venta ID: {venta_id}, Estado: {estado}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al actualizar el estado'}), 500
    except Exception as e:
        print(f"❌ Error en api_actualizar_estado_venta: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - ELIMINAR VENTA
# ============================================

@app.route('/api/venta/<int:venta_id>', methods=['DELETE'])
@login_required
def api_eliminar_venta(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        # Obtener el negocio_id de la venta
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT negocio_id, estado, total FROM ventas WHERE id = %s', (venta_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        negocio_id = result[0]
        estado = result[1]
        total = result[2]
        
        # Verificar permisos
        if usuario.get('rol') != 'admin':
            if usuario.get('id') != negocio_id and usuario.get('rol') != 'negocio':
                negocio_trabajador = obtener_negocio_de_trabajador(usuario['id'])
                if negocio_trabajador != negocio_id:
                    return jsonify({'error': 'No tienes permiso para eliminar esta venta'}), 403
        
        # Ejecutar eliminación con reintegro
        exito, mensaje = eliminar_venta_con_reintegro(venta_id, negocio_id)
        
        if exito:
            registrar_log(usuario['id'], 'venta_eliminada', f'Venta ID: {venta_id}, Total: {total}')
            return jsonify({
                'success': True,
                'message': mensaje or 'Venta eliminada correctamente'
            })
        else:
            return jsonify({
                'error': mensaje or 'Error al eliminar la venta'
            }), 500
            
    except Exception as e:
        print(f"❌ Error en api_eliminar_venta: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/estadisticas/ventas', methods=['GET'])
@login_required
def api_estadisticas_ventas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        if usuario.get('rol') == 'admin':
            estadisticas = obtener_estadisticas_ventas()
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            estadisticas = obtener_estadisticas_ventas(negocio_id)
        
        return jsonify(estadisticas)
    except Exception as e:
        print(f"❌ Error en api_estadisticas_ventas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ventas/periodo', methods=['GET'])
@login_required
def api_ventas_por_periodo():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fecha inicio y fin son requeridas'}), 400
        
        if usuario.get('rol') == 'admin':
            ventas = obtener_ventas_por_periodo(fecha_inicio, fecha_fin)
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            ventas = obtener_ventas_por_periodo(fecha_inicio, fecha_fin, negocio_id)
        
        return jsonify([dict(v) for v in ventas])
    except Exception as e:
        print(f"❌ Error en api_ventas_por_periodo: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - REPORTES
# ============================================

@app.route('/api/reporte/ventas', methods=['GET'])
@login_required
def api_generar_reporte_ventas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        formato = request.args.get('formato', 'json')
        
        if not fecha_inicio or not fecha_fin:
            return jsonify({'error': 'Fecha inicio y fin son requeridas'}), 400
        
        generador = GeneradorReportes()
        
        if usuario.get('rol') == 'admin':
            reporte = generador.generar_reporte_ventas(fecha_inicio, fecha_fin)
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            reporte = generador.generar_reporte_ventas(fecha_inicio, fecha_fin, negocio_id)
        
        if formato == 'pdf':
            pdf = generador.generar_pdf(reporte)
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=reporte_ventas_{fecha_inicio}_{fecha_fin}.pdf'
            return response
        
        return jsonify(reporte)
    except Exception as e:
        print(f"❌ Error en api_generar_reporte_ventas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reporte/productos', methods=['GET'])
@login_required
def api_generar_reporte_productos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        categoria = request.args.get('categoria')
        formato = request.args.get('formato', 'json')
        
        generador = GeneradorReportes()
        
        if usuario.get('rol') == 'admin':
            reporte = generador.generar_reporte_productos(categoria)
        else:
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
                if not negocio_id:
                    return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            reporte = generador.generar_reporte_productos(categoria, negocio_id)
        
        if formato == 'pdf':
            pdf = generador.generar_pdf(reporte)
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=reporte_productos.pdf'
            return response
        
        return jsonify(reporte)
    except Exception as e:
        print(f"❌ Error en api_generar_reporte_productos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - NOTIFICACIONES
# ============================================

@app.route('/api/notificaciones/preferencias', methods=['GET'])
@login_required
def api_obtener_preferencias_notificaciones():
    """Obtener las preferencias de notificaciones del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        preferencias = obtener_preferencias_notificaciones(usuario['id'])
        return jsonify({
            'success': True,
            'preferencias': preferencias
        })
    except Exception as e:
        print(f"❌ Error en api_obtener_preferencias_notificaciones: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/preferencias', methods=['POST'])
@login_required
def api_actualizar_preferencias_notificaciones():
    """Actualizar las preferencias de notificaciones del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    try:
        preferencias = data.get('preferencias')
        if not preferencias:
            return jsonify({'error': 'Preferencias requeridas'}), 400
        
        exito = actualizar_preferencias_notificaciones(usuario['id'], preferencias)
        
        if exito:
            return jsonify({
                'success': True,
                'message': 'Preferencias actualizadas correctamente'
            })
        else:
            return jsonify({'error': 'Error al actualizar preferencias'}), 500
    except Exception as e:
        print(f"❌ Error en api_actualizar_preferencias_notificaciones: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/suscribir', methods=['POST'])
@login_required
def api_suscribir_usuario():
    """Suscriptor para recibir notificaciones push"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    endpoint = data.get('endpoint')
    p256dh = data.get('p256dh')
    auth = data.get('auth')
    
    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'Endpoint, p256dh y auth son requeridos'}), 400
    
    try:
        exito = suscribir_usuario(usuario['id'], endpoint, p256dh, auth)
        
        if exito:
            return jsonify({
                'success': True,
                'message': 'Usuario suscrito correctamente'
            })
        else:
            return jsonify({'error': 'Error al suscribir usuario'}), 500
    except Exception as e:
        print(f"❌ Error en api_suscribir_usuario: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/desuscribir', methods=['POST'])
@login_required
def api_desuscribir_usuario():
    """Desuscribir usuario de notificaciones"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    endpoint = data.get('endpoint')
    
    if not endpoint:
        return jsonify({'error': 'Endpoint es requerido'}), 400
    
    try:
        exito = desuscribir_usuario(usuario['id'], endpoint)
        
        if exito:
            return jsonify({
                'success': True,
                'message': 'Usuario desuscrito correctamente'
            })
        else:
            return jsonify({'error': 'Error al desuscribir usuario'}), 500
    except Exception as e:
        print(f"❌ Error en api_desuscribir_usuario: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/check', methods=['GET'])
@login_required
def api_check_suscripcion():
    """Verificar si el usuario está suscrito a notificaciones"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    endpoint = request.args.get('endpoint')
    
    if not endpoint:
        return jsonify({'error': 'Endpoint es requerido'}), 400
    
    try:
        suscrito = esta_suscrito(usuario['id'], endpoint)
        return jsonify({
            'success': True,
            'suscrito': suscrito
        })
    except Exception as e:
        print(f"❌ Error en api_check_suscripcion: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones', methods=['GET'])
@login_required
def api_obtener_notificaciones():
    """Obtener todas las notificaciones del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        notificaciones = obtener_notificaciones_usuario(usuario['id'], limit, offset)
        no_leidas = contar_notificaciones_no_leidas(usuario['id'])
        
        return jsonify({
            'success': True,
            'notificaciones': notificaciones,
            'no_leidas': no_leidas,
            'total': len(notificaciones)
        })
    except Exception as e:
        print(f"❌ Error en api_obtener_notificaciones: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/no-leidas', methods=['GET'])
@login_required
def api_contar_no_leidas():
    """Contar notificaciones no leídas del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        no_leidas = contar_notificaciones_no_leidas(usuario['id'])
        return jsonify({
            'success': True,
            'no_leidas': no_leidas
        })
    except Exception as e:
        print(f"❌ Error en api_contar_no_leidas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/<int:notificacion_id>/leer', methods=['POST'])
@login_required
def api_marcar_notificacion_leida(notificacion_id):
    """Marcar una notificación como leída"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        exito = marcar_notificacion_leida(notificacion_id)
        
        if exito:
            return jsonify({
                'success': True,
                'message': 'Notificación marcada como leída'
            })
        else:
            return jsonify({'error': 'Error al marcar notificación como leída'}), 500
    except Exception as e:
        print(f"❌ Error en api_marcar_notificacion_leida: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/leer-todas', methods=['POST'])
@login_required
def api_marcar_todas_leidas():
    """Marcar todas las notificaciones como leídas"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        exito = marcar_todas_notificaciones_leidas(usuario['id'])
        
        if exito:
            return jsonify({
                'success': True,
                'message': 'Todas las notificaciones marcadas como leídas'
            })
        else:
            return jsonify({'error': 'Error al marcar todas como leídas'}), 500
    except Exception as e:
        print(f"❌ Error en api_marcar_todas_leidas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/stock', methods=['POST'])
@login_required
def api_generar_notificaciones_stock():
    """Generar notificaciones de stock bajo para el negocio"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        if usuario.get('tipo') != 'negocio' and usuario.get('rol') != 'admin':
            return jsonify({'error': 'Solo los negocios pueden generar notificaciones de stock'}), 403
        
        contador = generar_notificaciones_stock(negocio_id)
        
        return jsonify({
            'success': True,
            'message': f'Se generaron {contador} notificaciones de stock bajo',
            'cantidad': contador
        })
    except Exception as e:
        print(f"❌ Error en api_generar_notificaciones_stock: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/enviar-test', methods=['POST'])
@login_required
def api_enviar_notificacion_test():
    """Endpoint para enviar una notificación de prueba (solo para desarrollo)"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        titulo = data.get('titulo', '🔔 Notificación de prueba')
        mensaje = data.get('mensaje', 'Esta es una notificación de prueba del sistema.')
        icono = data.get('icono', '🔔')
        
        # Registrar la notificación en la base de datos
        notificacion_id = registrar_notificacion(
            usuario['id'],
            titulo,
            mensaje,
            'test',
            icono
        )
        
        if notificacion_id:
            return jsonify({
                'success': True,
                'message': 'Notificación de prueba enviada',
                'notificacion_id': notificacion_id
            })
        else:
            return jsonify({'error': 'Error al enviar notificación de prueba'}), 500
    except Exception as e:
        print(f"❌ Error en api_enviar_notificacion_test: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# ENDPOINT PÚBLICO PARA SERVICE WORKER
# ============================================
@app.route('/sw.js')
def service_worker():
    """Endpoint público para el Service Worker"""
    response = make_response(render_template('sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/manifest.json')
def manifest():
    """Endpoint público para el manifest.json"""
    response = make_response(render_template('manifest.json'))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/offline')
def offline():
    """Página offline para cuando no hay conexión"""
    return render_template('offline.html')

# ============================================
# INICIAR APLICACIÓN
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
