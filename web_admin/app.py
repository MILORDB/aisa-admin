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
        obtener_ultimo_numero_contrato, obtener_datos_negocio,
        obtener_estadisticas_productos,
        obtener_nomina_mes, calcular_nomina, obtener_nomina_trabajador,
        obtener_comisiones_trabajador_mes, obtener_comisiones_negocio_mes,
        registrar_comision, obtener_resumen_nomina,
        obtener_negocio_de_trabajador
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

@app.route('/perfil')
@login_required
def perfil_usuario():
    """Página de perfil del usuario"""
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
# API - PERFIL DE USUARIO
# ============================================

@app.route('/api/usuario/perfil', methods=['GET'])
@login_required
def api_obtener_perfil_usuario():
    """Obtiene el perfil completo del usuario actual"""
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
            'id': usuario['id'],
            'username': usuario['username'],
            'email': usuario['email'],
            'nombre': usuario['nombre'],
            'rol': usuario['rol'],
            'tipo': usuario['tipo'],
            'fecha_registro': usuario['fecha_registro'],
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
    """Actualiza el perfil del usuario actual"""
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
    
    if usuario['tipo'] == 'negocio':
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
    """Obtiene la ubicación del usuario actual"""
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

@app.route('/negocio/nomina')
@login_required
def negocio_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    return render_template('negocio/nomina.html', usuario=usuario, version=int(time.time()))

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
    
    exito = eliminar_usuario(user_id)
    
    if not exito:
        return jsonify({'error': 'Error al eliminar el usuario'}), 500
    
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

@app.route('/api/negocios/cercanos', methods=['GET'])
@login_required
def api_negocios_cercanos():
    """Obtiene negocios cercanos basados en la ubicación del usuario"""
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
            if n['datos_negocio']:
                try:
                    datos = json.loads(n['datos_negocio']) if isinstance(n['datos_negocio'], str) else n['datos_negocio']
                except:
                    pass
            
            resultado.append({
                'id': n['id'],
                'username': n['username'],
                'nombre': n['nombre'] or datos.get('nombre_negocio', n['username']),
                'telefono': datos.get('telefono', ''),
                'direccion': datos.get('direccion', ''),
                'descripcion': datos.get('descripcion', ''),
                'activo': n['activo']
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
                'fecha_registro': row[6],
                'modulos': datos.get('modulos', [])
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
    
    if not usuario or usuario['tipo'] != 'negocio':
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
    """Elimina un trabajador de un negocio"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
# API - PRODUCTOS (CON COSTO Y COMISION - PARA NEGOCIOS Y TRABAJADORES)
# ============================================

@app.route('/api/productos', methods=['GET', 'POST'])
@login_required
def api_productos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    # Permitir tanto a negocios como a trabajadores
    if usuario['tipo'] != 'negocio' and usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener el negocio_id del trabajador o usar su propio id
    negocio_id = usuario['id']
    if usuario['rol'] == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    if request.method == 'GET':
        productos = obtener_productos(negocio_id)
        return jsonify([dict(p) for p in productos])
    
    # Los trabajadores NO pueden crear/editar productos
    if usuario['rol'] == 'trabajador':
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
    
    if usuario['tipo'] != 'negocio' and usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener el negocio_id
    negocio_id = usuario['id']
    if usuario['rol'] == 'trabajador':
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
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    # Los trabajadores NO pueden editar productos
    if usuario['rol'] == 'trabajador':
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/stock')
@login_required
def api_productos_stock():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario['tipo'] != 'negocio' and usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener el negocio_id
    negocio_id = usuario['id']
    if usuario['rol'] == 'trabajador':
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
# API - TIENDA PÚBLICA FILTRADA POR UBICACIÓN
# ============================================

@app.route('/api/tienda/public', methods=['GET'])
def api_tienda_public():
    """Obtiene productos de la tienda pública con filtro de ubicación"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        token = request.cookies.get('token')
        usuario = None
        provincia_filtro = None
        municipio_filtro = None
        
        if token:
            usuario = obtener_usuario_sesion(token)
            if usuario:
                datos_negocio = obtener_datos_negocio(usuario['id'])
                provincia_filtro = datos_negocio.get('provincia')
                municipio_filtro = datos_negocio.get('municipio')
        
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
        # ============================================
# API - SERVICIOS (PARA NEGOCIOS Y TRABAJADORES) - CORREGIDO
# ============================================

@app.route('/api/servicios', methods=['GET', 'POST'])
@login_required
def api_servicios():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    # Permitir tanto a negocios como a trabajadores
    if usuario['tipo'] != 'negocio' and usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener el negocio_id
    negocio_id = usuario['id']
    trabajador_id = None
    
    if usuario['rol'] == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
        trabajador_id = usuario['id']
    
    if request.method == 'GET':
        # Si es trabajador, ver sus servicios (y los del negocio)
        if usuario['rol'] == 'trabajador':
            # Obtener servicios del negocio (todos, no solo los del trabajador)
            servicios = obtener_servicios(negocio_id, None)
        else:
            trabajador_id_param = request.args.get('trabajador_id')
            servicios = obtener_servicios(negocio_id, trabajador_id_param)
        
        print(f"📋 Servicios encontrados: {len(servicios)} para negocio {negocio_id}")
        return jsonify([dict(s) for s in servicios])
    
    # Los trabajadores NO pueden crear servicios
    if usuario['rol'] == 'trabajador':
        return jsonify({'error': 'No tienes permisos para crear servicios'}), 403
    
    data = request.get_json()
    nombre = data.get('nombre')
    categoria = data.get('categoria')
    precio = data.get('precio')
    duracion = data.get('duracion', 60)
    descripcion = data.get('descripcion', '')
    trabajador_id_crear = data.get('trabajador_id')
    
    if not nombre or precio is None:
        return jsonify({'error': 'Nombre y precio son requeridos'}), 400
    
    servicio_id = crear_servicio(negocio_id, trabajador_id_crear, nombre, categoria, precio, duracion, 1, descripcion)
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
# API - VENTAS (PARA NEGOCIOS Y TRABAJADORES)
# ============================================

@app.route('/api/ventas', methods=['GET', 'POST'])
@login_required
def api_ventas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario['tipo'] != 'negocio' and usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener el negocio_id del trabajador o usar su propio id
    negocio_id = usuario['id']
    trabajador_id = None
    if usuario['rol'] == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
        trabajador_id = usuario['id']
    
    if request.method == 'GET':
        # Si es trabajador, solo ver sus propias ventas
        if usuario['rol'] == 'trabajador':
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
    # Si es trabajador, forzar su ID
    if usuario['rol'] == 'trabajador':
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
    
    # Registrar comisión si corresponde
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
    """Elimina una venta y reintegra el stock"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
            'producto': resultado['producto'],
            'cantidad': resultado['cantidad'],
            'cliente': resultado['cliente'],
            'total': resultado['total']
        })
        
    except psycopg2.Error as e:
        print(f"❌ Error SQL eliminando venta: {e}")
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500
    except Exception as e:
        print(f"❌ Error eliminando venta: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - FACTURAS Y OFERTAS
# ============================================

@app.route('/api/venta/<int:venta_id>/factura', methods=['GET'])
@login_required
def api_generar_factura(venta_id):
    """Genera una factura PDF de una venta con todos los items uno debajo del otro"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
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
        producto_str = venta['producto']
        
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
        
        atendido_por = venta.get('atendido_por_nombre') or usuario['nombre'] or usuario['username'] or 'Admin'
        
        venta_data = {
            'id': venta['id'],
            'factura': venta.get('factura', f"FAC-{venta['id']}"),
            'fecha': venta['fecha'],
            'cliente': venta['cliente'],
            'empresa': venta.get('empresa', ''),
            'estado': venta['estado'],
            'total': venta['total'],
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - CONTRATOS (PARA NEGOCIOS Y TRABAJADORES)
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
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario['tipo'] != 'negocio' and usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener el negocio_id del trabajador o usar su propio id
    negocio_id = usuario['id']
    if usuario['rol'] == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asociado a ningún negocio'}), 403
    
    if request.method == 'GET':
        trabajador_id = request.args.get('travajador_id')
        contratos = obtener_contratos(negocio_id, trabajador_id)
        return jsonify([dict(c) for c in contratos])
    
    # Los trabajadores NO pueden crear contratos
    if usuario['rol'] == 'trabajador':
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
# API - OBTENER EMPRESAS CON CONTRATOS ACTIVOS (PARA TRABAJADORES)
# ============================================

@app.route('/api/contratos/empresas', methods=['GET'])
@login_required
def api_obtener_empresas_con_contratos():
    """Obtiene la lista de empresas con contratos activos"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 403
    
    if usuario['tipo'] != 'negocio' and usuario['rol'] != 'trabajador':
        return jsonify({'error': 'No autorizado'}), 403
    
    # Obtener el negocio_id del trabajador o usar su propio id
    negocio_id = usuario['id']
    if usuario['rol'] == 'trabajador':
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
        contratos = obtener_contratos(usuario['id'])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT nombre, datos_negocio FROM usuarios WHERE id = %s', (usuario['id'],))
        negocio = cursor.fetchone()
        conn.close()
        
        negocio_nombre = negocio[0] or 'Mi Negocio'
        datos_negocio = json.loads(negocio[1]) if negocio[1] else {}
        negocio_telefono = datos_negocio.get('telefono', '')
        
        hoy = datetime.now().date()
        contratos_procesados = []
        
        for c in contratos:
            fecha_fin = datetime.fromisoformat(c['fecha_fin']).date() if c['fecha_fin'] else None
            estado = c['estado']
            
            if estado == 'activo' and fecha_fin and fecha_fin < hoy:
                estado = 'vencido'
            
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
        
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono
        )
        
        pdf_bytes = generador.generar_reporte_contratos(
            contratos_procesados,
            tipo_reporte=tipo
        )
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=reporte_contratos_{tipo}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        registrar_log(usuario['id'], 'reporte_generado', f'Reporte de contratos ({tipo})')
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de contratos: {e}")
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


@app.route('/api/reportes/ingresos', methods=['GET'])
@login_required
def api_reporte_ingresos():
    """Genera un reporte PDF de ingresos"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    periodo = request.args.get('periodo', 'todos')
    
    try:
        ventas = obtener_ventas(usuario['id'])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT nombre, datos_negocio FROM usuarios WHERE id = %s', (usuario['id'],))
        negocio = cursor.fetchone()
        conn.close()
        
        negocio_nombre = negocio[0] or 'Mi Negocio'
        datos_negocio = json.loads(negocio[1]) if negocio[1] else {}
        negocio_telefono = datos_negocio.get('telefono', '')
        
        ventas_filtradas = []
        hoy = datetime.now().date()
        
        for v in ventas:
            fecha_venta = datetime.fromisoformat(v['fecha']).date() if v['fecha'] else None
            if not fecha_venta:
                continue
            
            if periodo == 'hoy':
                if fecha_venta == hoy:
                    ventas_filtradas.append(v)
            elif periodo == 'semana':
                inicio_semana = hoy - timedelta(days=hoy.weekday())
                if fecha_venta >= inicio_semana:
                    ventas_filtradas.append(v)
            elif periodo == 'mes':
                if fecha_venta.month == hoy.month and fecha_venta.year == hoy.year:
                    ventas_filtradas.append(v)
            else:
                ventas_filtradas.append(v)
        
        total_ingresos = sum(v.get('total', 0) for v in ventas_filtradas)
        total_ventas = len(ventas_filtradas)
        
        periodos = {
            'hoy': 'Hoy',
            'semana': 'Esta semana',
            'mes': 'Este mes',
            'todos': 'Todos los períodos'
        }
        nombre_periodo = periodos.get(periodo, 'Todos los períodos')
        
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono
        )
        
        pdf_bytes = generador.generar_reporte_ingresos(
            ventas_filtradas,
            total_ingresos,
            total_ventas,
            periodo=nombre_periodo
        )
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=reporte_ingresos_{periodo}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        registrar_log(usuario['id'], 'reporte_generado', f'Reporte de ingresos ({periodo})')
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de ingresos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reportes/ingresos/resumen', methods=['GET'])
@login_required
def api_resumen_ingresos():
    """Obtiene un resumen de ingresos para el panel lateral"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        ventas = obtener_ventas(usuario['id'])
        
        hoy = datetime.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        
        total_ventas = len(ventas)
        total_ingresos = sum(v.get('total', 0) for v in ventas)
        
        ventas_hoy = [v for v in ventas if v['fecha'] and datetime.fromisoformat(v['fecha']).date() == hoy]
        ingresos_hoy = sum(v.get('total', 0) for v in ventas_hoy)
        
        ventas_semana = [v for v in ventas if v['fecha'] and datetime.fromisoformat(v['fecha']).date() >= inicio_semana]
        ingresos_semana = sum(v.get('total', 0) for v in ventas_semana)
        
        ventas_mes = [v for v in ventas if v['fecha'] and datetime.fromisoformat(v['fecha']).month == hoy.month]
        ingresos_mes = sum(v.get('total', 0) for v in ventas_mes)
        
        return jsonify({
            'total_ventas': total_ventas,
            'total_ingresos': total_ingresos,
            'ingresos_hoy': ingresos_hoy,
            'ingresos_semana': ingresos_semana,
            'ingresos_mes': ingresos_mes,
            'tiene_ventas': total_ventas > 0
        })
        
    except Exception as e:
        print(f"❌ Error en resumen de ingresos: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reportes/productos', methods=['GET'])
@login_required
def api_reporte_productos():
    """Genera un reporte PDF de productos en almacén"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        productos = obtener_productos(usuario['id'])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT nombre, datos_negocio FROM usuarios WHERE id = %s', (usuario['id'],))
        negocio = cursor.fetchone()
        conn.close()
        
        negocio_nombre = negocio[0] or 'Mi Negocio'
        datos_negocio = json.loads(negocio[1]) if negocio[1] else {}
        negocio_telefono = datos_negocio.get('telefono', '')
        
        generador = GeneradorReportes(
            negocio_id=usuario['id'],
            negocio_nombre=negocio_nombre,
            negocio_telefono=negocio_telefono
        )
        
        pdf_bytes = generador.generar_reporte_productos(productos)
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=reporte_productos_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        registrar_log(usuario['id'], 'reporte_generado', 'Reporte de productos en almacén')
        
        return response
        
    except Exception as e:
        print(f"❌ Error generando reporte de productos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/reportes/productos/resumen', methods=['GET'])
@login_required
def api_resumen_productos():
    """Obtiene un resumen de productos para el panel lateral"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        productos = obtener_productos(usuario['id'])
        
        total = len(productos)
        stock_bajo = len([p for p in productos if p.get('stock', 0) <= (p.get('stock_minimo', 3)) and p.get('stock', 0) > 0])
        stock_agotado = len([p for p in productos if p.get('stock', 0) == 0])
        valor_total = sum(p.get('precio', 0) * p.get('stock', 0) for p in productos)
        
        return jsonify({
            'total': total,
            'stock_bajo': stock_bajo,
            'stock_agotado': stock_agotado,
            'valor_total': valor_total,
            'tiene_productos': total > 0
        })
        
    except Exception as e:
        print(f"❌ Error en resumen de productos: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# API - NÓMINA (CORREGIDO)
# ============================================

@app.route('/api/nomina', methods=['GET'])
@login_required
def api_obtener_nomina():
    """Obtiene la nómina de un mes específico"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    
    if not mes or not ano:
        return jsonify({'error': 'Mes y año son requeridos'}), 400
    
    nominas = obtener_nomina_mes(usuario['id'], mes, ano)
    
    return jsonify({
        'success': True,
        'nominas': nominas
    })

@app.route('/api/nomina/calcular', methods=['POST'])
@login_required
def api_calcular_nomina():
    """Calcula la nómina para todos los trabajadores en un mes"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    data = request.get_json()
    mes = data.get('mes')
    ano = data.get('ano')
    
    if not mes or not ano:
        return jsonify({'error': 'Mes y año son requeridos'}), 400
    
    try:
        # Obtener trabajadores del negocio
        trabajadores = obtener_trabajadores_por_empresa(usuario['id'])
        
        if not trabajadores:
            return jsonify({
                'success': True,
                'trabajadores': 0,
                'message': 'No hay trabajadores registrados'
            })
        
        contador = 0
        errores = []
        
        for t in trabajadores:
            try:
                resultado = calcular_nomina(usuario['id'], t['id'], mes, ano)
                if resultado:
                    contador += 1
            except Exception as e:
                errores.append(f"Error con trabajador {t.get('nombre', t.get('id'))}: {str(e)}")
                print(f"❌ Error calculando nómina para trabajador {t.get('id')}: {e}")
        
        mensaje = f'Nómina calculada para {contador} trabajadores'
        if errores:
            mensaje += f' ({len(errores)} errores)'
            print(f"⚠️ Errores: {errores}")
        
        return jsonify({
            'success': True,
            'trabajadores': contador,
            'message': mensaje,
            'errores': errores if errores else None
        })
        
    except Exception as e:
        print(f"❌ Error en api_calcular_nomina: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Error al calcular nómina: {str(e)}'
        }), 500

@app.route('/api/nomina/detalle', methods=['GET'])
@login_required
def api_nomina_detalle():
    """Obtiene el detalle de nómina de un trabajador"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    trabajador_id = request.args.get('trabajador_id', type=int)
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    
    if not trabajador_id or not mes or not ano:
        return jsonify({'error': 'Trabajador, mes y año son requeridos'}), 400
    
    nomina = obtener_nomina_trabajador(trabajador_id, mes, ano)
    
    if not nomina:
        return jsonify({'error': 'No se encontró nómina para este trabajador'}), 404
    
    comisiones = obtener_comisiones_trabajador_mes(trabajador_id, mes, ano)
    
    from calendar import monthrange
    _, dias_mes = monthrange(ano, mes)
    
    trabajador = obtener_usuario_por_id(trabajador_id)
    datos = json.loads(trabajador['datos_negocio']) if trabajador['datos_negocio'] else {}
    salario_base = datos.get('salario', 0)
    
    salario_diario = salario_base / dias_mes if dias_mes > 0 else 0
    
    return jsonify({
        'success': True,
        'detalle': {
            'id': nomina['id'],
            'trabajador_id': trabajador_id,
            'nombre': trabajador['nombre'],
            'mes': mes,
            'ano': ano,
            'dias_mes': dias_mes,
            'salario_base': salario_base,
            'salario_diario': salario_diario,
            'dias_trabajados': nomina['dias_trabajados'],
            'dias_ausencia': nomina['dias_ausencia'] or 0,
            'salario_devengado': nomina['salario_devengado'],
            'comisiones': nomina['comisiones'] or 0,
            'total': nomina['total'],
            'comisiones_list': comisiones
        }
    })

@app.route('/api/nomina/reporte', methods=['GET'])
@login_required
def api_nomina_reporte():
    """Genera un reporte PDF de nómina"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    
    if not mes or not ano:
        return jsonify({'error': 'Mes y año son requeridos'}), 400
    
    nominas = obtener_nomina_mes(usuario['id'], mes, ano)
    
    if not nominas:
        return jsonify({'error': 'No hay datos de nómina para este mes'}), 404
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT nombre, datos_negocio FROM usuarios WHERE id = %s', (usuario['id'],))
    negocio = cursor.fetchone()
    conn.close()
    
    negocio_nombre = negocio[0] or 'Mi Negocio'
    datos_negocio = json.loads(negocio[1]) if negocio[1] else {}
    negocio_telefono = datos_negocio.get('telefono', '')
    negocio_direccion = datos_negocio.get('direccion', '')
    
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    elementos = []
    
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#6c3ce0'), alignment=TA_CENTER)
    elementos.append(Paragraph(f"📊 REPORTE DE NÓMINA", estilo_titulo))
    elementos.append(Paragraph(f"{negocio_nombre}", styles['Heading2']))
    
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    nombre_mes = meses[mes - 1] if 1 <= mes <= 12 else str(mes)
    elementos.append(Paragraph(f"{nombre_mes} de {ano}", styles['Normal']))
    elementos.append(Spacer(1, 10))
    
    tabla_datos = []
    headers = ['Trabajador', 'Salario Base', 'Días Trabajados', 'Ausencias', 'Salario Devengado', 'Comisiones', 'Total']
    tabla_datos.append(headers)
    
    total_general = 0
    total_comisiones = 0
    
    for n in nominas:
        total_general += n['total']
        total_comisiones += n['comisiones'] or 0
        tabla_datos.append([
            n['nombre'],
            f"${n['salario_base']:.2f}",
            str(n['dias_trabajados']),
            str(n['dias_ausencia'] or 0),
            f"${n['salario_devengado']:.2f}",
            f"${(n['comisiones'] or 0):.2f}",
            f"${n['total']:.2f}"
        ])
    
    tabla_datos.append([
        'TOTAL',
        '',
        '',
        '',
        '',
        f"${total_comisiones:.2f}",
        f"${total_general:.2f}"
    ])
    
    tabla = Table(tabla_datos, colWidths=[120, 90, 80, 80, 100, 100, 100])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c3ce0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#999999')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (4, 1), (6, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8e8e8')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    
    elementos.append(tabla)
    elementos.append(Spacer(1, 10))
    
    estilo_resumen = ParagraphStyle('Resumen', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)
    elementos.append(Paragraph(f"Total de trabajadores: {len(nominas)}", estilo_resumen))
    elementos.append(Paragraph(f"Total de comisiones: ${total_comisiones:.2f}", estilo_resumen))
    elementos.append(Paragraph(f"Total de nómina: ${total_general:.2f}", estilo_resumen))
    
    estilo_pie = ParagraphStyle('Pie', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)
    elementos.append(Spacer(1, 20))
    elementos.append(Paragraph(f"Reporte generado por AIsa - {datetime.now().strftime('%d/%m/%Y %H:%M')}", estilo_pie))
    
    doc.build(elementos)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=nomina_{mes}_{ano}.pdf'
    
    return response

# ============================================
# API - NOMINA DEBUG (PARA DEPURAR ERRORES)
# ============================================

@app.route('/api/nomina/debug', methods=['GET'])
@login_required
def api_nomina_debug():
    """Endpoint de depuración para nómina"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario or usuario['tipo'] != 'negocio':
        return jsonify({'error': 'No autorizado'}), 403
    
    try:
        # Verificar trabajadores
        trabajadores = obtener_trabajadores_por_empresa(usuario['id'])
        
        # Verificar funciones
        resultado = {
            'negocio_id': usuario['id'],
            'trabajadores': len(trabajadores),
            'trabajadores_lista': [{'id': t['id'], 'nombre': t['nombre']} for t in trabajadores],
            'db_conexion': 'OK'
        }
        
        # Probar una consulta simple
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        conn.close()
        resultado['db_test'] = 'OK'
        
        return jsonify(resultado)
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

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
    
