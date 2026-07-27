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
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================
# CREAR CARPETAS PARA ARCHIVOS ESTÁTICOS
# ============================================
os.makedirs('static/uploads/productos', exist_ok=True)
os.makedirs('static/uploads/facturas', exist_ok=True)
os.makedirs('static/img', exist_ok=True)
print("📁 Carpetas de almacenamiento creadas/verificadas")

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
        crear_venta, obtener_ventas, obtener_todas_ventas, obtener_estadisticas_ventas, eliminar_venta_con_reintegro,
        actualizar_estado_venta,
        crear_servicio, obtener_servicios, obtener_todos_servicios, toggle_servicio, eliminar_servicio,
        obtener_estadisticas_trabajador,
        crear_trabajador_negocio, toggle_trabajador_negocio, actualizar_trabajador_negocio,
        obtener_trabajadores_pendientes, aprobar_trabajador, rechazar_trabajador,
        actualizar_foto_producto, eliminar_foto_producto,
        crear_contrato, obtener_contratos, obtener_todos_contratos, 
        actualizar_contrato, actualizar_estado_contrato, eliminar_contrato,
        obtener_ultimo_numero_contrato
    )
    from web_admin.auth import crear_sesion, verificar_sesion, obtener_usuario_sesion
    from web_admin.storage import get_storage_manager
    from web_admin.reportes import GeneradorReportes
    print("✅ Módulos importados correctamente")
except Exception as e:
    print(f"❌ Error importando módulos: {e}")
    traceback.print_exc()

# ============================================
# CREAR APLICACIÓN FLASK
# ============================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
CORS(app)

# ============================================
# CONFIGURACIÓN DE CACHÉ (ANTI-CACHÉ)
# ============================================

@app.after_request
def add_header(response):
    """Agrega headers para evitar caché en el navegador"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ============================================
# INICIALIZAR BASE DE DATOS (DESACTIVADO)
# ============================================

print("⚠️ Inicialización automática desactivada")
print("👉 Visita /init-db para inicializar manualmente")

# ============================================
# ENDPOINT PARA INICIALIZAR BD MANUALMENTE
# ============================================

@app.route('/init-db', methods=['GET'])
def init_db_route():
    """Endpoint para inicializar la base de datos manualmente"""
    try:
        from web_admin.database import init_db
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
# ENDPOINT PARA REPARAR VENTAS
# ============================================

@app.route('/fix-ventas', methods=['GET'])
def fix_ventas():
    """Endpoint para agregar columnas faltantes a la tabla ventas"""
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
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ventas'
        """)
        columnas = cursor.fetchall()
        columnas_existentes = [col[0] for col in columnas]
        
        print("📋 Columnas existentes:", columnas_existentes)
        
        columnas_necesarias = [
            ('factura', 'TEXT'),
            ('transferencia_id', 'TEXT'),
            ('transferencia_cedula', 'TEXT'),
            ('transferencia_banco', 'TEXT'),
            ('transferencia_fecha', 'TEXT')
        ]
        
        columnas_agregadas = []
        mensajes = []
        
        for col, tipo in columnas_necesarias:
            if col not in columnas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE ventas ADD COLUMN {col} {tipo}")
                    columnas_agregadas.append(col)
                    mensajes.append(f"✅ Columna '{col}' agregada correctamente")
                    print(f"✅ Columna '{col}' agregada correctamente")
                except psycopg2.Error as e:
                    if "duplicate column" in str(e).lower():
                        mensajes.append(f"⚠️ Columna '{col}' ya existe")
                        print(f"⚠️ Columna '{col}' ya existe")
                    else:
                        mensajes.append(f"❌ Error al agregar '{col}': {e}")
                        print(f"❌ Error al agregar '{col}': {e}")
            else:
                mensajes.append(f"✅ Columna '{col}' ya existe")
                print(f"✅ Columna '{col}' ya existe")
        
        conn.commit()
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        
        return f"""
        <html>
            <head><title>Ventas Reparadas</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#6c3ce0;">✅ Ventas reparadas correctamente</h1>
                <div style="background:#1a1a2e;border-radius:8px;padding:20px;margin:20px auto;max-width:600px;text-align:left;border:1px solid #2a2a3e;">
                    {html_mensajes}
                </div>
                <p style="color:#888;">Columnas agregadas: factura, transferencia_id, transferencia_cedula, transferencia_banco, transferencia_fecha</p>
                <br>
                <a href="/negocio/ventas" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;display:inline-block;">Ir a Ventas</a>
                <a href="/dashboard" style="color:#888;text-decoration:none;border:1px solid #2a2a3e;padding:10px 20px;border-radius:8px;display:inline-block;margin-left:10px;">Volver al Dashboard</a>
            </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error al reparar ventas</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
            </body>
        </html>
        """, 500

# ============================================
# DECORADORES
# ============================================

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect(url_for('login'))
        usuario = obtener_usuario_sesion(token)
        if not usuario:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect(url_for('login'))
        usuario = obtener_usuario_sesion(token)
        if not usuario or usuario['rol'] != 'admin':
            return jsonify({'error': 'Acceso denegado'}), 403
        return f(*args, **kwargs)
    return decorated_function

def negocio_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect(url_for('login'))
        usuario = obtener_usuario_sesion(token)
        if not usuario or usuario['tipo'] != 'negocio':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# RUTAS PRINCIPALES
# ============================================

@app.route('/')
def index():
    token = request.cookies.get('token')
    if token:
        usuario = obtener_usuario_sesion(token)
        if usuario:
            return redirect(url_for('dashboard'))
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
        return jsonify({'error': f'Error interno del servidor'}), 500

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
    
    if usuario['rol'] == 'admin':
        return render_template('dashboard.html', usuario=usuario)
    elif usuario['rol'] == 'trabajador':
        return render_template('trabajador/dashboard.html', usuario=usuario)
    elif usuario['tipo'] == 'negocio':
        return render_template('negocio/dashboard.html', usuario=usuario)
    else:
        return render_template('cliente/dashboard.html', usuario=usuario)

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
# API - PERFIL
# ============================================

@app.route('/api/perfil')
@admin_required
def api_perfil():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return jsonify({
        'success': True,
        'usuario': {
            'id': usuario['id'],
            'username': usuario['username'],
            'email': usuario['email'],
            'nombre': usuario['nombre'],
            'rol': usuario['rol'],
            'fecha_registro': usuario['fecha_registro']
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
    
    if not verify_password(current_password, usuario['password_hash']):
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
    activos = len([u for u in usuarios if u['activo'] == 1])
    trabajadores = len([u for u in usuarios if u['rol'] == 'trabajador'])
    
    hoy = datetime.now().date()
    registros_hoy = len([l for l in logs if datetime.fromisoformat(l['fecha']).date() == hoy])
    
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
    """Endpoint para verificar si un usuario existe"""
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
    
    if usuario['id'] == user_id:
        return jsonify({'error': 'No puedes eliminar tu propio usuario'}), 400
    
    user = obtener_usuario_por_id(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    eliminar_usuario(user_id)
    registrar_log(usuario['id'], 'usuario_eliminado', f'Usuario {user_id} eliminado')
    
    return jsonify({'success': True, 'message': 'Usuario eliminado correctamente'})

# ============================================
# API - NEGOCIOS
# ============================================

@app.route('/api/negocios')
@admin_required
def api_negocios():
    negocios = obtener_negocios()
    return jsonify([dict(n) for n in negocios])

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
# API - MÓDULOS
# ============================================

@app.route('/api/modulos')
@login_required
def api_modulos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if usuario and usuario['rol'] == 'admin':
        modulos = obtener_modulos()
    else:
        tipo_usuario = usuario['tipo'] if usuario else 'cliente'
        modulos = obtener_modulos(tipo_usuario)
    
    return jsonify([dict(m) for m in modulos])

@app.route('/api/modulo/<int:modulo_id>/toggle', methods=['POST'])
@admin_required
def api_toggle_modulo_global(modulo_id):
    data = request.get_json()
    activo = data.get('activo', 1)
    toggle_modulo_global(modulo_id, activo)
    registrar_log(None, 'modulo_global', f'Módulo {modulo_id} activo={activo}')
    return jsonify({'success': True})

@app.route('/api/usuario/<int:user_id>/permisos')
@login_required
def api_permisos_usuario(user_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    if not usuario or (usuario['id'] != user_id and usuario['rol'] != 'admin'):
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
# API - NEGOCIO - TRABAJADORES
# ============================================

@app.route('/api/negocio/trabajadores')
@login_required
def api_obtener_trabajadores():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
                'fecha_registro': row[6]
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ Error en api_obtener_trabajadores: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/negocio/trabajador/crear', methods=['POST'])
@login_required
def api_crear_trabajador():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    
    # Datos personales
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
    
    # Validaciones
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
    
    # Verificar usuario único
    if obtener_usuario_por_username(username):
        return jsonify({'error': 'El nombre de usuario ya está en uso'}), 400
    
    # Preparar datos del negocio
    datos_negocio = {
        'nombre': nombre,
        'apellidos': apellidos,
        'ci': ci,
        'movil': movil,
        'direccion': direccion,
        'frecuencia': frecuencia,
        'salario': salario,
        'empresa_id': usuario['id']
    }
    
    # Crear usuario
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
    
    # Asignar a la empresa
    crear_trabajador_negocio(usuario['id'], user_id, 'Trabajador', salario)
    
    # Asignar módulos
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
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    
    # Datos personales
    nombre = data.get('nombre')
    apellidos = data.get('apellidos')
    ci = data.get('ci')
    movil = data.get('movil', '')
    direccion = data.get('direccion', '')
    frecuencia = data.get('frecuencia', 'diaria')
    salario = data.get('salario', 0)
    email = data.get('email', '')
    
    # Validaciones
    if not nombre:
        return jsonify({'error': 'El nombre es obligatorio'}), 400
    if not apellidos:
        return jsonify({'error': 'Los apellidos son obligatorios'}), 400
    if not ci:
        return jsonify({'error': 'El carnet de identidad es obligatorio'}), 400
    
    # Obtener trabajador actual
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT datos_negocio FROM usuarios WHERE id = %s', (trabajador_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return jsonify({'error': 'Trabajador no encontrado'}), 404
    
    datos_actuales = json.loads(result[0]) if result[0] else {}
    
    # Actualizar datos
    datos_actuales.update({
        'nombre': nombre,
        'apellidos': apellidos,
        'ci': ci,
        'movil': movil,
        'direccion': direccion,
        'frecuencia': frecuencia,
        'salario': salario
    })
    
    # Actualizar en la base de datos
    conn = get_db()
    cursor = conn.cursor()
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

@app.route('/api/negocio/trabajador/<int:trabajador_id>/toggle', methods=['POST'])
@login_required
def api_toggle_trabajador_negocio(trabajador_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    if request.method == 'GET':
        productos = obtener_productos(usuario['id'])
        return jsonify([dict(p) for p in productos])
    
    data = request.get_json()
    nombre = data.get('nombre')
    categoria = data.get('categoria')
    precio = data.get('precio')
    stock = data.get('stock', 0)
    stock_minimo = data.get('stock_minimo', 3)
    
    if not nombre or precio is None:
        return jsonify({'error': 'Nombre y precio son requeridos'}), 400
    
    producto_id = crear_producto(usuario['id'], nombre, categoria, precio, stock, stock_minimo)
    registrar_log(usuario['id'], 'producto_creado', f'Producto: {nombre}')
    
    return jsonify({'success': True, 'id': producto_id})

@app.route('/api/producto/<int:producto_id>', methods=['PUT', 'DELETE'])
@login_required
def api_producto(producto_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    # DELETE - ELIMINAR PRODUCTO
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
            
            if producto[0] != usuario['id']:
                print(f"❌ Producto {producto_id} no pertenece al usuario {usuario['id']}")
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
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    # PUT - ACTUALIZAR PRODUCTO
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Datos inválidos'}), 400
            
        nombre = data.get('nombre')
        categoria = data.get('categoria')
        precio = data.get('precio')
        stock = data.get('stock', 0)
        stock_minimo = data.get('stock_minimo', 3)
        
        if not nombre or precio is None:
            return jsonify({'error': 'Nombre y precio son requeridos'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT negocio_id FROM productos WHERE id = %s', (producto_id,))
        producto = cursor.fetchone()
        conn.close()
        
        if not producto or producto[0] != usuario['id']:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        actualizar_producto(producto_id, nombre, categoria, precio, stock, stock_minimo)
        registrar_log(usuario['id'], 'producto_actualizado', f'ID: {producto_id}')
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Error actualizando producto: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/stock')
@login_required
def api_productos_stock():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    productos = obtener_productos_con_stock(usuario['id'])
    return jsonify([dict(p) for p in productos])

# ============================================
# API - FOTOS DE PRODUCTOS
# ============================================

@app.route('/api/producto/<int:producto_id>/foto', methods=['POST'])
@login_required
def api_subir_foto_producto(producto_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/agregar', methods=['POST'])
@login_required
def api_tienda_agregar_producto():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tienda/producto/<int:tienda_id>/destacar', methods=['POST'])
@login_required
def api_tienda_destacar_producto(tienda_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
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
# API - TIENDA PÚBLICA
# ============================================

@app.route('/api/tienda/public', methods=['GET'])
def api_tienda_public():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT p.id, p.nombre, p.categoria, p.precio, p.stock, p.foto_url,
               u.id as negocio_id, u.nombre as negocio_nombre, u.username as negocio_username
        FROM productos_tienda pt
        JOIN productos p ON pt.producto_id = p.id
        JOIN usuarios u ON pt.negocio_id = u.id
        WHERE p.stock > 0 AND u.activo = 1
        ORDER BY pt.destacado DESC, pt.created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        resultado = []
        for row in rows:
            resultado.append({
                'id': row[0],
                'nombre': row[1],
                'categoria': row[2] or '',
                'precio': float(row[3]),
                'stock': row[4],
                'foto_url': row[5],
                'negocio_id': row[6],
                'negocio_nombre': row[7],
                'negocio_username': row[8]
            })
        
        return jsonify(resultado)
    except Exception as e:
        print(f"❌ Error en tienda pública: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# API - VENTAS
# ============================================

@app.route('/api/ventas', methods=['GET', 'POST'])
@login_required
def api_ventas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    if request.method == 'GET':
        trabajador_id = request.args.get('trabajador_id')
        ventas = obtener_ventas(usuario['id'], trabajador_id)
        return jsonify([dict(v) for v in ventas])
    
    data = request.get_json()
    print("📥 Datos recibidos en POST:", data)
    
    cliente = data.get('cliente')
    producto = data.get('producto')
    producto_id = data.get('producto_id')
    cantidad = data.get('cantidad', 1)
    precio = data.get('precio')
    total = data.get('total', precio * cantidad if precio else 0)
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
        cursor.execute('SELECT stock FROM productos WHERE id = %s AND negocio_id = %s', (producto_id, usuario['id']))
        stock_actual = cursor.fetchone()
        conn.close()
        
        if not stock_actual:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        if stock_actual[0] < cantidad:
            return jsonify({'error': f'Stock insuficiente. Disponible: {stock_actual[0]} unidades'}), 400
    
    venta_id = crear_venta(
        usuario['id'], trabajador_id, cliente, producto, 
        producto_id, cantidad, precio, total, estado, 
        empresa, tipo, factura_url, factura,
        transferencia_id, transferencia_cedula,
        transferencia_banco, transferencia_fecha
    )
    
    if tipo == 'producto' and producto_id:
        actualizar_stock_producto(producto_id, cantidad)
    
    registrar_log(usuario['id'], 'venta_creada', 
                  f'Venta: {producto} - Cliente: {cliente} - Cantidad: {cantidad} - Estado: {estado}')
    
    return jsonify({'success': True, 'id': venta_id, 'stock_actualizado': True})

@app.route('/api/ventas/estadisticas')
@login_required
def api_ventas_estadisticas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    estado = data.get('estado')
    
    if estado not in ['pagado', 'pendiente', 'cancelado', 'transferencia']:
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
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    exito, resultado = eliminar_venta_con_reintegro(venta_id, usuario['id'])
    
    if not exito:
        return jsonify({'error': resultado}), 404
    
    registrar_log(usuario['id'], 'venta_eliminada', 
                  f'Venta #{venta_id} eliminada. Producto: {resultado["producto"]} - Cantidad: {resultado["cantidad"]}')
    
    return jsonify({
        'success': True,
        'message': 'Venta eliminada y stock reintegrado correctamente',
        'producto': resultado['producto'],
        'cantidad': resultado['cantidad'],
        'cliente': resultado['cliente'],
        'total': resultado['total']
    })

# ============================================
# API - SERVICIOS
# ============================================

@app.route('/api/servicios', methods=['GET', 'POST'])
@login_required
def api_servicios():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    if request.method == 'GET':
        trabajador_id = request.args.get('trabajador_id')
        servicios = obtener_servicios(usuario['id'], trabajador_id)
        return jsonify([dict(s) for s in servicios])
    
    data = request.get_json()
    nombre = data.get('nombre')
    categoria = data.get('categoria')
    precio = data.get('precio')
    duracion = data.get('duracion', 60)
    descripcion = data.get('descripcion', '')
    trabajador_id = data.get('trabajador_id')
    
    if not nombre or precio is None:
        return jsonify({'error': 'Nombre y precio son requeridos'}), 400
    
    servicio_id = crear_servicio(usuario['id'], trabajador_id, nombre, categoria, precio, duracion, 1, descripcion)
    registrar_log(usuario['id'], 'servicio_creado', f'Servicio: {nombre}')
    
    return jsonify({'success': True, 'id': servicio_id})

@app.route('/api/servicio/<int:servicio_id>/toggle', methods=['POST'])
@login_required
def api_toggle_servicio(servicio_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    eliminar_servicio(servicio_id)
    registrar_log(usuario['id'], 'servicio_eliminado', f'ID: {servicio_id}')
    
    return jsonify({'success': True})

# ============================================
# API - CONTRATOS
# ============================================

@app.route('/api/contratos/ultimo_numero', methods=['GET'])
@login_required
def api_ultimo_numero_contrato():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    ultimo = obtener_ultimo_numero_contrato(usuario['id'])
    return jsonify({'ultimo_numero': ultimo})

@app.route('/api/contratos', methods=['GET', 'POST'])
@login_required
def api_contratos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    if request.method == 'GET':
        trabajador_id = request.args.get('trabajador_id')
        contratos = obtener_contratos(usuario['id'], trabajador_id)
        return jsonify([dict(c) for c in contratos])
    
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
        usuario['id'], None, empresa, numero_contrato,
        fecha_inicio, fecha_fin, tipo, monto, estado, descripcion
    )
    registrar_log(usuario['id'], 'contrato_creado', f'Contrato: {numero_contrato} - {empresa}')
    
    return jsonify({'success': True, 'id': contrato_id})

@app.route('/api/contrato/<int:contrato_id>', methods=['PUT'])
@login_required
def api_actualizar_contrato(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    eliminar_contrato(contrato_id)
    registrar_log(usuario['id'], 'contrato_eliminado', f'Contrato {contrato_id} eliminado')
    
    return jsonify({'success': True})

# ============================================
# API - REPORTES
# ============================================

@app.route('/api/reportes/contratos', methods=['GET'])
@login_required
def api_reporte_contratos():
    """Genera un reporte PDF de contratos"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    tipo = request.args.get('tipo', 'todos')
    
    try:
        # Obtener contratos del negocio
        contratos = obtener_contratos(usuario['id'])
        
        # Obtener datos del negocio
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT nombre, datos_negocio FROM usuarios WHERE id = %s', (usuario['id'],))
        negocio = cursor.fetchone()
        conn.close()
        
        negocio_nombre = negocio[0] or 'Mi Negocio'
        datos_negocio = json.loads(negocio[1]) if negocio[1] else {}
        negocio_telefono = datos_negocio.get('telefono', '')
        
        # Procesar contratos para el reporte
        hoy = datetime.now().date()
        contratos_procesados = []
        
        for c in contratos:
            # Determinar estado real
            fecha_fin = datetime.fromisoformat(c['fecha_fin']).date() if c['fecha_fin'] else None
            estado = c['estado']
            
            # Si está activo pero la fecha ya pasó, marcarlo como vencido
            if estado == 'activo' and fecha_fin and fecha_fin < hoy:
                estado = 'vencido'
            
            # Filtrar por tipo
            if tipo == 'activos' and estado != 'activo':
                continue
            if tipo == 'vencidos' and estado != 'vencido':
                continue
            
            contratos_procesados.append({
                'id': c['id'],
                'numero_contrato': c['numero_contrato'],
                'empresa': c['empresa'],
                'fecha_inicio': c['fecha_inicio'],
                'fecha_fin': c['fecha_fin'],
                'monto': c['monto'] or 0,
                'estado': estado,
                'tipo': c['tipo']
            })
        
        # Generar PDF
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono
        )
        
        pdf_bytes = generador.generar_reporte_contratos(
            contratos_procesados,
            tipo_reporte=tipo
        )
        
        # Crear respuesta con el PDF
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=reporte_contratos_{tipo}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        registrar_log(usuario['id'], 'reporte_generado', f'Reporte de contratos ({tipo})')
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/contratos/resumen', methods=['GET'])
@login_required
def api_resumen_contratos():
    """Obtiene un resumen de contratos para el panel lateral"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        contratos = obtener_contratos(usuario['id'])
        
        hoy = datetime.now().date()
        total = len(contratos)
        activos = 0
        vencidos = 0
        total_gastos = 0
        
        for c in contratos:
            fecha_fin = datetime.fromisoformat(c['fecha_fin']).date() if c['fecha_fin'] else None
            estado = c['estado']
            
            if estado == 'activo' and fecha_fin and fecha_fin < hoy:
                estado = 'vencido'
            
            if estado == 'activo':
                activos += 1
            elif estado == 'vencido':
                vencidos += 1
            
            total_gastos += c['monto'] or 0
        
        return jsonify({
            'total': total,
            'activos': activos,
            'vencidos': vencidos,
            'total_gastos': total_gastos,
            'tiene_contratos': total > 0
        })
        
    except Exception as e:
        print(f"❌ Error en resumen de contratos: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# API - ESTADÍSTICAS TRABAJADOR
# ============================================

@app.route('/api/trabajador/estadisticas')
@login_required
def api_trabajador_estadisticas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    stats = obtener_estadisticas_trabajador(usuario['id'])
    return jsonify(stats)

# ============================================
# API - SOLICITUDES DE MÓDULOS
# ============================================

@app.route('/api/usuario/<int:user_id>/solicitar/<int:modulo_id>', methods=['POST'])
@login_required
def api_solicitar_modulo(user_id, modulo_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    if not usuario or (usuario['id'] != user_id and usuario['rol'] != 'admin'):
        return jsonify({'error': 'No autorizado'}), 403
    
    solicitar_modulo(user_id, modulo_id)
    registrar_log(user_id, 'solicitud_modulo', f'Solicitó módulo {modulo_id}')
    return jsonify({'success': True})

@app.route('/api/solicitudes')
@admin_required
def api_solicitudes():
    solicitudes = obtener_solicitudes_pendientes()
    return jsonify([dict(s) for s in solicitudes])

@app.route('/api/solicitud/<int:solicitud_id>/aprobar', methods=['POST'])
@admin_required
def api_aprobar_solicitud(solicitud_id):
    aprobar_solicitud(solicitud_id)
    registrar_log(None, 'solicitud_aprobada', f'Solicitud {solicitud_id} aprobada')
    return jsonify({'success': True})

@app.route('/api/solicitud/<int:solicitud_id>/rechazar', methods=['POST'])
@admin_required
def api_rechazar_solicitud(solicitud_id):
    rechazar_solicitud(solicitud_id)
    registrar_log(None, 'solicitud_rechazada', f'Solicitud {solicitud_id} rechazada')
    return jsonify({'success': True})

# ============================================
# API - LOGS
# ============================================

@app.route('/api/logs')
@admin_required
def api_logs():
    logs = obtener_logs(50)
    return jsonify([dict(l) for l in logs])

# ============================================
# API - TRABAJADORES PENDIENTES
# ============================================

@app.route('/api/trabajadores/pendientes')
@admin_required
def api_trabajadores_pendientes():
    trabajadores = obtener_trabajadores_pendientes()
    return jsonify([dict(t) for t in trabajadores])

@app.route('/api/trabajador/<int:user_id>/aprobar', methods=['POST'])
@admin_required
def api_aprobar_trabajador(user_id):
    aprobar_trabajador(user_id)
    registrar_log(None, 'trabajador_aprobado', f'Trabajador {user_id} aprobado')
    return jsonify({'success': True})

@app.route('/api/trabajador/<int:user_id>/rechazar', methods=['POST'])
@admin_required
def api_rechazar_trabajador(user_id):
    rechazar_trabajador(user_id)
    registrar_log(None, 'trabajador_rechazado', f'Trabajador {user_id} rechazado')
    return jsonify({'success': True})

# ============================================
# EJECUCIÓN (VERSIÓN PARA RENDER)
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 AIsa Admin - Panel de Control")
    print("🌐 Puerto:", port)
    print("👤 admin / admin123")
    print("=" * 60)
    
    app.run(debug=False, host='0.0.0.0', port=port)
