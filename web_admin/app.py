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

from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from flask_cors import CORS

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
        # Nuevas funciones de notificaciones
        suscribir_usuario, desuscribir_usuario, esta_suscrito,
        obtener_suscriptores, obtener_suscripciones_usuario,
        registrar_notificacion, registrar_notificacion_negocio,
        obtener_notificaciones_usuario, contar_notificaciones_no_leidas,
        marcar_notificacion_leida, marcar_todas_notificaciones_leidas,
        generar_notificaciones_stock, generar_notificacion_producto_nuevo,
        generar_notificacion_stock_actualizado,
        obtener_producto_por_id, obtener_preferencias_notificaciones,
        actualizar_preferencias_notificaciones
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
    categoria = data.get('categoria')
    precio = data.get('precio')
    costo = data.get('costo', 0)
    comision = data.get('comision', 0)
    stock = data.get('stock', 0)
    stock_minimo = data.get('stock_minimo', 3)
    
    print(f"📝 Creando producto: {nombre}, {categoria}, {precio}")
    
    if not nombre or not categoria or precio is None:
        return jsonify({'success': False, 'error': 'Nombre, categoría y precio son obligatorios'}), 400
    
    try:
        negocio_id = usuario.get('id')
        producto_id = crear_producto(negocio_id, nombre, categoria, float(precio), float(costo), float(comision), int(stock), int(stock_minimo))
        
        if producto_id:
            registrar_log(usuario['id'], 'producto_creado', f'Producto: {nombre}')
            
            # 🔔 GENERAR NOTIFICACIÓN DE PRODUCTO NUEVO
            generar_notificacion_producto_nuevo(negocio_id, producto_id)
            
            # 🔔 VERIFICAR STOCK BAJO
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
    categoria = data.get('categoria')
    precio = data.get('precio')
    costo = data.get('costo', 0)
    comision = data.get('comision', 0)
    stock = data.get('stock', 0)
    stock_minimo = data.get('stock_minimo', 3)
    
    if not nombre or not categoria or precio is None:
        return jsonify({'error': 'Nombre, categoría y precio son obligatorios'}), 400
    
    try:
        # Obtener stock anterior para generar notificación
        producto_anterior = obtener_producto_por_id(producto_id)
        stock_anterior = producto_anterior.get('stock', 0) if producto_anterior else 0
        
        exito = actualizar_producto(producto_id, nombre, categoria, float(precio), float(costo), float(comision), int(stock), int(stock_minimo))
        
        if exito:
            registrar_log(usuario['id'], 'producto_actualizado', f'Producto ID: {producto_id}')
            
            # 🔔 GENERAR NOTIFICACIÓN DE STOCK ACTUALIZADO
            negocio_id = usuario.get('id')
            if usuario.get('rol') == 'trabajador':
                negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            
            if negocio_id and stock_anterior != stock:
                generar_notificacion_stock_actualizado(negocio_id, producto_id, stock_anterior, stock)
            
            # 🔔 VERIFICAR STOCK BAJO
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

@app.route('/api/tienda/public', methods=['GET'])
@login_required
def api_tienda_publica():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        datos_usuario = obtener_datos_negocio(usuario['id'])
        provincia = datos_usuario.get('provincia')
        municipio = datos_usuario.get('municipio')
        
        productos = obtener_productos_tienda_publica(provincia, municipio)
        return jsonify([dict(p) for p in productos])
    except Exception as e:
        print(f"❌ Error en api_tienda_publica: {e}")
        traceback.print_exc()
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

@app.route('/api/negocio/trabajador/<int:trabajador_id>', methods=['DELETE'])
@login_required
def api_eliminar_trabajador_negocio(trabajador_id):
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
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM trabajadores_negocio WHERE negocio_id = %s AND trabajador_id = %s', (negocio_id, trabajador_id))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'El trabajador no pertenece a tu negocio'}), 403
        conn.close()
        
        exito = eliminar_usuario(trabajador_id)
        
        if exito:
            registrar_log(usuario['id'], 'trabajador_eliminado', f'Trabajador ID: {trabajador_id}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al eliminar el trabajador'}), 500
    except Exception as e:
        print(f"❌ Error en api_eliminar_trabajador_negocio: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/trabajador/estadisticas', methods=['GET'])
@login_required
def api_trabajador_estadisticas():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if usuario.get('rol') != 'trabajador':
        return jsonify({'error': 'Solo para trabajadores'}), 403
    
    try:
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
        trabajador_id = request.args.get('trabajador_id')
        if trabajador_id:
            trabajador_id = int(trabajador_id)
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
            if not trabajador_id:
                trabajador_id = usuario['id']
        
        ventas = obtener_ventas(negocio_id, trabajador_id)
        return jsonify([dict(v) for v in ventas])
    except Exception as e:
        print(f"❌ Error en api_obtener_ventas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/ventas', methods=['POST'])
@login_required
def api_crear_venta():
    """Crear una nueva venta"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Datos inválidos'}), 400
        
        print(f"📝 Datos de venta recibidos: {data}")
        
        cliente = data.get('cliente')
        producto = data.get('producto')
        producto_id = data.get('producto_id')
        cantidad = data.get('cantidad', 1)
        precio = data.get('precio')
        total = data.get('total')
        estado = data.get('estado', 'pagado')
        empresa = data.get('empresa')
        tipo = data.get('tipo', 'producto')
        factura_url = data.get('factura_url')
        factura = data.get('factura')
        trabajador_id = data.get('trabajador_id')
        transferencia_id = data.get('transferencia_id')
        transferencia_cedula = data.get('transferencia_cedula')
        transferencia_banco = data.get('transferencia_banco')
        transferencia_fecha = data.get('transferencia_fecha')
        
        if not cliente or not producto or precio is None or total is None:
            return jsonify({'success': False, 'error': 'Cliente, producto, precio y total son obligatorios'}), 400
        
        # Determinar negocio_id
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'success': False, 'error': 'No estás asignado a ningún negocio'}), 403
            if not trabajador_id:
                trabajador_id = usuario['id']
        
        # Si es oferta, no afecta inventario
        if estado == 'oferta':
            producto_id = None
            factura = None
        
        # Crear la venta
        venta_id = crear_venta(
            negocio_id, trabajador_id, cliente, producto, producto_id,
            cantidad, float(precio), float(total), estado, empresa, tipo, factura_url,
            factura, transferencia_id, transferencia_cedula,
            transferencia_banco, transferencia_fecha
        )
        
        if not venta_id:
            return jsonify({'success': False, 'error': 'Error al crear la venta en la base de datos'}), 500
        
        # Si no es oferta y tiene producto_id, descontar stock
        if estado != 'oferta' and producto_id:
            try:
                actualizar_stock_producto(producto_id, cantidad)
                
                # 🔔 VERIFICAR STOCK BAJO DESPUÉS DE VENTA
                generar_notificaciones_stock(negocio_id)
            except Exception as e:
                print(f"⚠️ Error al actualizar stock: {e}")
        
        # Registrar comisión si corresponde
        if estado != 'oferta' and trabajador_id and producto_id:
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('SELECT comision FROM productos WHERE id = %s', (producto_id,))
                producto_comision = cursor.fetchone()
                conn.close()
                
                if producto_comision and producto_comision[0] > 0:
                    monto_comision = float(producto_comision[0]) * cantidad
                    registrar_comision(negocio_id, trabajador_id, venta_id, producto_id, monto_comision)
            except Exception as e:
                print(f"⚠️ Error al registrar comisión: {e}")
        
        registrar_log(usuario['id'], 'venta_creada', f'Venta ID: {venta_id}, Cliente: {cliente}')
        
        # Generar número de factura si no es oferta
        factura_numero = None
        if estado != 'oferta' and empresa:
            try:
                factura_numero = generar_numero_factura(negocio_id, empresa)
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('UPDATE ventas SET factura = %s WHERE id = %s', (factura_numero, venta_id))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"⚠️ Error al generar factura: {e}")
        
        return jsonify({
            'success': True,
            'id': venta_id,
            'factura': factura_numero,
            'message': 'Venta creada correctamente'
        })
        
    except Exception as e:
        print(f"❌ Error en api_crear_venta: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/venta/<int:venta_id>/estado', methods=['PUT'])
@login_required
def api_actualizar_estado_venta(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    estado = data.get('estado')
    
    if not estado:
        return jsonify({'error': 'Estado es requerido'}), 400
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        exito = actualizar_estado_venta(venta_id, negocio_id, estado)
        
        if exito:
            registrar_log(usuario['id'], 'venta_estado_actualizado', f'Venta ID: {venta_id}, Estado: {estado}')
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al actualizar el estado'}), 500
    except Exception as e:
        print(f"❌ Error en api_actualizar_estado_venta: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/venta/<int:venta_id>', methods=['DELETE'])
@login_required
def api_eliminar_venta(venta_id):
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
        
        exito, mensaje = eliminar_venta_con_reintegro(venta_id, negocio_id)
        
        if exito:
            registrar_log(usuario['id'], 'venta_eliminada', f'Venta ID: {venta_id}')
            return jsonify({'success': True, 'message': mensaje})
        else:
            return jsonify({'error': mensaje}), 500
    except Exception as e:
        print(f"❌ Error en api_eliminar_venta: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/venta/<int:venta_id>/factura', methods=['GET'])
@login_required
def api_generar_factura(venta_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        es_oferta = request.args.get('oferta', 'false').lower() == 'true'
        
        venta = obtener_venta_por_id(venta_id)
        if not venta:
            return jsonify({'error': 'Venta no encontrada'}), 404
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        if venta.get('negocio_id') != negocio_id:
            return jsonify({'error': 'No tienes permiso para acceder a esta venta'}), 403
        
        datos_negocio = obtener_datos_negocio(negocio_id)
        negocio_nombre = datos_negocio.get('nombre_negocio', 'Mi Negocio')
        negocio_telefono = datos_negocio.get('telefono', '')
        negocio_direccion = datos_negocio.get('direccion', '')
        
        generador = GeneradorReportes(negocio_id, negocio_nombre, negocio_telefono, negocio_direccion)
        
        items = []
        if venta.get('producto') and venta.get('cantidad', 0) > 0:
            producto_nombre = venta.get('producto')
            cantidad = venta.get('cantidad', 1)
            precio_unitario = venta.get('precio', 0) / cantidad if cantidad > 0 else venta.get('precio', 0)
            subtotal = venta.get('total', 0)
            
            items.append({
                'nombre': producto_nombre,
                'cantidad': cantidad,
                'precio': precio_unitario,
                'subtotal': subtotal
            })
        else:
            items.append({
                'nombre': venta.get('producto', 'Producto'),
                'cantidad': 1,
                'precio': venta.get('precio', 0),
                'subtotal': venta.get('total', 0)
            })
        
        pdf_bytes = generador.generar_factura_venta(venta, items, es_oferta)
        
        response = make_response(pdf_bytes)
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', f'attachment; filename={"oferta" if es_oferta else "factura"}_{venta_id}.pdf')
        return response
        
    except Exception as e:
        print(f"❌ Error en api_generar_factura: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/todos/ventas', methods=['GET'])
@admin_required
def api_todos_ventas():
    try:
        ventas = obtener_todas_ventas()
        return jsonify([dict(v) for v in ventas])
    except Exception as e:
        print(f"❌ Error en api_todos_ventas: {e}")
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
    
    data = request.get_json()
    empresa = data.get('empresa')
    numero_contrato = data.get('numero_contrato')
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    tipo = data.get('tipo', 'ventas')
    monto = data.get('monto', 0)
    estado = data.get('estado', 'activo')
    descripcion = data.get('descripcion', '')
    trabajador_id = data.get('trabajador_id')
    
    if not empresa or not numero_contrato or not fecha_inicio or not fecha_fin:
        return jsonify({'error': 'Empresa, número de contrato, fecha inicio y fecha fin son obligatorios'}), 400
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        contrato_id = crear_contrato(negocio_id, trabajador_id, empresa, numero_contrato, fecha_inicio, fecha_fin, tipo, float(monto), estado, descripcion)
        
        if contrato_id:
            registrar_log(usuario['id'], 'contrato_creado', f'Contrato: {empresa} (ID: {contrato_id})')
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
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    tipo = data.get('tipo')
    monto = data.get('monto')
    estado = data.get('estado')
    descripcion = data.get('descripcion')
    
    if not empresa or not fecha_inicio or not fecha_fin:
        return jsonify({'error': 'Empresa, fecha inicio y fecha fin son obligatorios'}), 400
    
    try:
        actualizar_contrato(contrato_id, empresa, fecha_inicio, fecha_fin, tipo, float(monto) if monto else 0, estado, descripcion)
        registrar_log(usuario['id'], 'contrato_actualizado', f'Contrato ID: {contrato_id}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_actualizar_contrato: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contrato/<int:contrato_id>/estado', methods=['PUT'])
@login_required
def api_actualizar_estado_contrato(contrato_id):
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    estado = data.get('estado')
    
    if not estado:
        return jsonify({'error': 'Estado es requerido'}), 400
    
    try:
        actualizar_estado_contrato(contrato_id, estado)
        registrar_log(usuario['id'], 'contrato_estado_actualizado', f'Contrato ID: {contrato_id}, Estado: {estado}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_actualizar_estado_contrato: {e}")
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
        eliminar_contrato(contrato_id)
        registrar_log(usuario['id'], 'contrato_eliminado', f'Contrato ID: {contrato_id}')
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error en api_eliminar_contrato: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contratos/ultimo_numero', methods=['GET'])
@login_required
def api_obtener_ultimo_numero_contrato():
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
        
        ultimo = obtener_ultimo_numero_contrato(negocio_id)
        return jsonify({'ultimo_numero': ultimo})
    except Exception as e:
        print(f"❌ Error en api_obtener_ultimo_numero_contrato: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contratos/empresas', methods=['GET'])
@login_required
def api_obtener_empresas_contratos():
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
        print(f"❌ Error en api_obtener_empresas_contratos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/todos/contratos', methods=['GET'])
@admin_required
def api_todos_contratos():
    try:
        contratos = obtener_todos_contratos()
        return jsonify([dict(c) for c in contratos])
    except Exception as e:
        print(f"❌ Error en api_todos_contratos: {e}")
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
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        resumen = obtener_resumen_contratos(negocio_id)
        return jsonify(resumen)
    except Exception as e:
        print(f"❌ Error en api_reportes_contratos_resumen: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/ingresos/resumen', methods=['GET'])
@login_required
def api_reportes_ingresos_resumen():
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
        
        resumen = obtener_resumen_ingresos(negocio_id)
        return jsonify(resumen)
    except Exception as e:
        print(f"❌ Error en api_reportes_ingresos_resumen: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/productos/resumen', methods=['GET'])
@login_required
def api_reportes_productos_resumen():
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
        
        resumen = obtener_resumen_productos(negocio_id)
        return jsonify(resumen)
    except Exception as e:
        print(f"❌ Error en api_reportes_productos_resumen: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/contratos', methods=['GET'])
@login_required
def api_reporte_contratos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        tipo = request.args.get('tipo', 'todos')
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        contratos = obtener_contratos(negocio_id)
        
        if tipo == 'activos':
            contratos = [c for c in contratos if c.get('estado') == 'activo']
        elif tipo == 'vencidos':
            contratos = [c for c in contratos if c.get('estado') == 'vencido']
        
        datos_negocio = obtener_datos_negocio(negocio_id)
        negocio_nombre = datos_negocio.get('nombre_negocio', 'Mi Negocio')
        negocio_telefono = datos_negocio.get('telefono', '')
        
        generador = GeneradorReportes(negocio_id, negocio_nombre, negocio_telefono)
        pdf_bytes = generador.generar_reporte_contratos(contratos, tipo)
        
        response = make_response(pdf_bytes)
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', f'attachment; filename=reporte_contratos_{tipo}.pdf')
        return response
        
    except Exception as e:
        print(f"❌ Error en api_reporte_contratos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/ingresos', methods=['GET'])
@login_required
def api_reporte_ingresos():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        tipo = request.args.get('tipo', 'hoy')
        
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        ventas, total_ingresos, total_ventas = obtener_ventas_por_periodo(negocio_id, tipo)
        
        datos_negocio = obtener_datos_negocio(negocio_id)
        negocio_nombre = datos_negocio.get('nombre_negocio', 'Mi Negocio')
        negocio_telefono = datos_negocio.get('telefono', '')
        
        generador = GeneradorReportes(negocio_id, negocio_nombre, negocio_telefono)
        periodo = {'hoy': 'Hoy', 'semana': 'Esta Semana', 'mes': 'Este Mes', 'todos': 'Todos los períodos'}.get(tipo, '')
        pdf_bytes = generador.generar_reporte_ingresos(ventas, total_ingresos, total_ventas, periodo)
        
        response = make_response(pdf_bytes)
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', f'attachment; filename=reporte_ingresos_{tipo}.pdf')
        return response
        
    except Exception as e:
        print(f"❌ Error en api_reporte_ingresos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reportes/productos', methods=['GET'])
@login_required
def api_reporte_productos():
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
        
        datos_negocio = obtener_datos_negocio(negocio_id)
        negocio_nombre = datos_negocio.get('nombre_negocio', 'Mi Negocio')
        negocio_telefono = datos_negocio.get('telefono', '')
        
        generador = GeneradorReportes(negocio_id, negocio_nombre, negocio_telefono)
        pdf_bytes = generador.generar_reporte_productos(productos)
        
        response = make_response(pdf_bytes)
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', 'attachment; filename=reporte_inventario.pdf')
        return response
        
    except Exception as e:
        print(f"❌ Error en api_reporte_productos: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - NÓMINA
# ============================================

@app.route('/api/nomina/asistencia', methods=['POST'])
@login_required
def api_registrar_asistencia():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    trabajador_id = data.get('trabajador_id')
    fecha = data.get('fecha')
    presente = data.get('presente', 1)
    horas = data.get('horas', 8)
    
    if not trabajador_id or not fecha:
        return jsonify({'error': 'Trabajador ID y fecha son requeridos'}), 400
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        exito = registrar_asistencia(trabajador_id, negocio_id, fecha, presente, horas)
        
        if exito:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al registrar asistencia'}), 500
    except Exception as e:
        print(f"❌ Error en api_registrar_asistencia: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/comisiones', methods=['GET'])
@login_required
def api_obtener_comisiones():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    trabajador_id = request.args.get('trabajador_id')
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    
    if not trabajador_id or not mes or not ano:
        return jsonify({'error': 'trabajador_id, mes y ano son requeridos'}), 400
    
    try:
        comisiones = obtener_comisiones_trabajador_mes(int(trabajador_id), int(mes), int(ano))
        return jsonify({'comisiones': [dict(c) for c in comisiones]})
    except Exception as e:
        print(f"❌ Error en api_obtener_comisiones: {e}")
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
    mes = data.get('mes')
    ano = data.get('ano')
    dias_trabajados = data.get('dias_trabajados')
    
    if not trabajador_id or not mes or not ano:
        return jsonify({'error': 'trabajador_id, mes y ano son requeridos'}), 400
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        resultado = calcular_nomina(negocio_id, int(trabajador_id), int(mes), int(ano))
        
        if resultado:
            return jsonify({'success': True, 'nomina': resultado})
        else:
            return jsonify({'error': 'Error al calcular la nómina'}), 500
    except Exception as e:
        print(f"❌ Error en api_calcular_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/detalle', methods=['GET'])
@login_required
def api_obtener_detalle_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    trabajador_id = request.args.get('trabajador_id')
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    
    if not trabajador_id or not mes or not ano:
        return jsonify({'error': 'trabajador_id, mes y ano son requeridos'}), 400
    
    try:
        detalle = obtener_detalle_nomina(int(trabajador_id), int(mes), int(ano))
        return jsonify({'success': True, 'detalle': detalle})
    except Exception as e:
        print(f"❌ Error en api_obtener_detalle_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/nomina/reporte', methods=['GET'])
@login_required
def api_generar_reporte_nomina():
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    trabajador_id = request.args.get('trabajador_id')
    mes = request.args.get('mes')
    ano = request.args.get('ano')
    
    if not trabajador_id or not mes or not ano:
        return jsonify({'error': 'trabajador_id, mes y ano son requeridos'}), 400
    
    try:
        negocio_id = usuario.get('id')
        if usuario.get('rol') == 'trabajador':
            negocio_id = obtener_negocio_de_trabajador(usuario['id'])
            if not negocio_id:
                return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
        
        detalle = obtener_detalle_nomina(int(trabajador_id), int(mes), int(ano))
        
        if not detalle:
            return jsonify({'error': 'No se encontró nómina para este trabajador'}), 404
        
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        import io
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        elementos = []
        
        estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#6c3ce0'), alignment=1)
        elementos.append(Paragraph('Reporte de Nómina', estilo_titulo))
        elementos.append(Spacer(1, 0.5*cm))
        
        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        elementos.append(Paragraph(f'Trabajador: {detalle.get("nombre", "")}', styles['Normal']))
        elementos.append(Paragraph(f'Período: {meses[int(mes)-1]} {ano}', styles['Normal']))
        elementos.append(Spacer(1, 0.5*cm))
        
        datos = [
            ['Concepto', 'Valor'],
            ['Salario Base', f'${detalle.get("salario_base", 0):.2f}'],
            ['Días del Mes', str(detalle.get("dias_mes", 0))],
            ['Días Trabajados', str(detalle.get("dias_trabajados", 0))],
            ['Ausencias', str(detalle.get("dias_ausencia", 0))],
            ['Días Extras', str(detalle.get("dias_extras", 0))],
            ['Salario Diario', f'${detalle.get("salario_diario", 0):.2f}'],
            ['Salario Devengado', f'${detalle.get("salario_devengado", 0):.2f}'],
            ['Comisiones', f'${detalle.get("comisiones", 0):.2f}'],
            ['TOTAL', f'${detalle.get("total", 0):.2f}']
        ]
        
        tabla = Table(datos, colWidths=[8*cm, 6*cm])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c3ce0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#999999')),
            ('BACKGROUND', (0, 8), (-1, 9), colors.HexColor('#e8e8f0')),
        ]))
        
        elementos.append(tabla)
        doc.build(elementos)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        response = make_response(pdf_bytes)
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Content-Disposition', f'attachment; filename=nomina_{trabajador_id}_{mes}_{ano}.pdf')
        return response
        
    except Exception as e:
        print(f"❌ Error en api_generar_reporte_nomina: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - LOGS
# ============================================

@app.route('/api/logs', methods=['GET'])
@admin_required
def api_logs():
    try:
        limit = request.args.get('limit', 50, type=int)
        logs = obtener_logs(limit)
        return jsonify([dict(l) for l in logs])
    except Exception as e:
        print(f"❌ Error en api_logs: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - STORAGE (GOOGLE DRIVE)
# ============================================

@app.route('/api/storage/estado', methods=['GET'])
@admin_required
def api_storage_estado():
    """Obtiene el estado del almacenamiento"""
    try:
        storage = get_storage_manager()
        estado = storage.obtener_estado()
        return jsonify(estado)
    except Exception as e:
        print(f"❌ Error en api_storage_estado: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/storage/auth', methods=['GET'])
@admin_required
def api_storage_auth():
    """Re-autenticar con Google Drive"""
    try:
        token_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'token.pickle')
        if os.path.exists(token_file):
            os.remove(token_file)
            print(f"🗑️ Token eliminado: {token_file}")
        
        storage = get_storage_manager()
        estado = storage.obtener_estado()
        return jsonify({'success': True, 'estado': estado})
    except Exception as e:
        print(f"❌ Error en api_storage_auth: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# ENDPOINTS DE REPARACIÓN
# ============================================

@app.route('/fix-admin', methods=['GET'])
def fix_admin_endpoint():
    """Endpoint para reparar el admin"""
    try:
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
        import bcrypt
        
        cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
        admin = cursor.fetchone()
        
        if not admin:
            password = "admin123"
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            fecha = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado, verificado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1, 1)
            ''', ('admin', 'admin@aisa.com', password_hash, 'Administrador', 'admin', 'admin', fecha))
            conn.commit()
        
        cursor.execute('''
            UPDATE usuarios 
            SET rol = 'admin', tipo = 'admin', activo = 1, aprobado = 1, verificado = 1
            WHERE username = 'admin'
        ''')
        conn.commit()
        conn.close()
        
        return """
        <html>
            <head><title>Admin Reparado</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#6c3ce0;">✅ Admin reparado correctamente</h1>
                <p style="color:#888;">Usuario: <strong style="color:#6c3ce0;">admin</strong></p>
                <p style="color:#888;">Contraseña: <strong style="color:#6c3ce0;">admin123</strong></p>
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
                <h1 style="color:#ff6b6b;">❌ Error</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/login" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Login</a>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINTS DE INSTALACIÓN - NOTIFICACIONES
# ============================================

@app.route('/fix-notificaciones')
@admin_required
def fix_notificaciones():
    """Página de instalación de notificaciones"""
    return render_template('fix-notificaciones.html')

@app.route('/api/instalar/tablas-notificaciones', methods=['POST'])
@admin_required
def api_instalar_tablas_notificaciones():
    """Crea las tablas de notificaciones y suscripciones"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        tablas_creadas = []
        
        # 1. Tabla suscripciones
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
        tablas_creadas.append({'nombre': 'suscripciones', 'existe': True})
        print("✅ Tabla suscripciones creada/verificada")
        
        # 2. Tabla notificaciones
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
        tablas_creadas.append({'nombre': 'notificaciones', 'existe': True})
        print("✅ Tabla notificaciones creada/verificada")
        
        # 3. Tabla preferencias_notificaciones
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
        tablas_creadas.append({'nombre': 'preferencias_notificaciones', 'existe': True})
        print("✅ Tabla preferencias_notificaciones creada/verificada")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Tablas de notificaciones creadas correctamente',
            'tablas': tablas_creadas
        })
        
    except Exception as e:
        print(f"❌ Error en api_instalar_tablas_notificaciones: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/instalar/verificar-notificaciones', methods=['GET'])
@admin_required
def api_instalar_verificar_notificaciones():
    """Verifica si las tablas de notificaciones existen"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        tablas = {}
        
        # Verificar suscripciones
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'suscripciones'
            )
        """)
        tablas['suscripciones'] = cursor.fetchone()[0]
        
        # Verificar notificaciones
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'notificaciones'
            )
        """)
        tablas['notificaciones'] = cursor.fetchone()[0]
        
        # Verificar preferencias_notificaciones
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'preferencias_notificaciones'
            )
        """)
        tablas['preferencias'] = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'tablas': tablas
        })
        
    except Exception as e:
        print(f"❌ Error en api_instalar_verificar_notificaciones: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/instalar/preferencias-usuarios', methods=['POST'])
@admin_required
def api_instalar_preferencias_usuarios():
    """Crea preferencias de notificaciones para todos los usuarios que no tengan"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Obtener usuarios sin preferencias
        cursor.execute('''
            SELECT u.id FROM usuarios u
            LEFT JOIN preferencias_notificaciones p ON u.id = p.usuario_id
            WHERE p.id IS NULL
        ''')
        usuarios = cursor.fetchall()
        
        procesados = 0
        for u in usuarios:
            cursor.execute('''
                INSERT INTO preferencias_notificaciones (usuario_id)
                VALUES (%s)
            ''', (u[0],))
            procesados += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Preferencias creadas para {procesados} usuarios',
            'usuarios_procesados': procesados
        })
        
    except Exception as e:
        print(f"❌ Error en api_instalar_preferencias_usuarios: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================
# API - SUSCRIPCIONES
# ============================================

@app.route('/api/suscribir/<int:negocio_id>', methods=['POST'])
@login_required
def api_suscribir(negocio_id):
    """Suscribe al usuario autenticado a un negocio"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if usuario.get('id') == negocio_id:
        return jsonify({'error': 'No puedes suscribirte a tu propio negocio'}), 400
    
    # Verificar que el negocio existe
    negocio = obtener_usuario_por_id(negocio_id)
    if not negocio or negocio.get('tipo') != 'negocio':
        return jsonify({'error': 'El negocio no existe'}), 404
    
    # Verificar si ya está suscrito
    if esta_suscrito(usuario['id'], negocio_id):
        return jsonify({
            'success': True,
            'message': 'Ya estás suscrito a este negocio',
            'suscrito': True
        })
    
    exito = suscribir_usuario(usuario['id'], negocio_id)
    
    if exito:
        registrar_log(usuario['id'], 'suscripcion', f'Usuario suscrito al negocio {negocio_id}')
        return jsonify({
            'success': True,
            'message': '✅ Te has suscrito correctamente',
            'suscrito': True
        })
    else:
        return jsonify({'error': 'Error al suscribirse'}), 500

@app.route('/api/desuscribir/<int:negocio_id>', methods=['POST'])
@login_required
def api_desuscribir(negocio_id):
    """Desuscribe al usuario autenticado de un negocio"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    if not esta_suscrito(usuario['id'], negocio_id):
        return jsonify({
            'success': True,
            'message': 'No estás suscrito a este negocio',
            'suscrito': False
        })
    
    exito = desuscribir_usuario(usuario['id'], negocio_id)
    
    if exito:
        registrar_log(usuario['id'], 'desuscripcion', f'Usuario desuscrito del negocio {negocio_id}')
        return jsonify({
            'success': True,
            'message': '✅ Te has desuscrito correctamente',
            'suscrito': False
        })
    else:
        return jsonify({'error': 'Error al desuscribirse'}), 500

@app.route('/api/esta-suscrito/<int:negocio_id>', methods=['GET'])
@login_required
def api_esta_suscrito(negocio_id):
    """Verifica si el usuario está suscrito a un negocio"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    suscrito = esta_suscrito(usuario['id'], negocio_id)
    
    return jsonify({
        'success': True,
        'suscrito': suscrito
    })

@app.route('/api/mis-suscripciones', methods=['GET'])
@login_required
def api_mis_suscripciones():
    """Obtiene todos los negocios a los que el usuario está suscrito"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    suscripciones = obtener_suscripciones_usuario(usuario['id'])
    
    return jsonify({
        'success': True,
        'suscripciones': [dict(s) for s in suscripciones]
    })

@app.route('/api/negocio/suscriptores', methods=['GET'])
@login_required
def api_negocio_suscriptores():
    """Obtiene los suscriptores del negocio del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    negocio_id = usuario.get('id')
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
    
    suscriptores = obtener_suscriptores(negocio_id)
    
    return jsonify({
        'success': True,
        'suscriptores': [dict(s) for s in suscriptores],
        'total': len(suscriptores)
    })

# ============================================
# API - NOTIFICACIONES
# ============================================

@app.route('/api/notificaciones', methods=['GET'])
@login_required
def api_notificaciones():
    """Obtiene las notificaciones del usuario autenticado"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    limite = request.args.get('limite', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    notificaciones = obtener_notificaciones_usuario(usuario['id'], limite, offset)
    no_leidas = contar_notificaciones_no_leidas(usuario['id'])
    
    return jsonify({
        'success': True,
        'notificaciones': [dict(n) for n in notificaciones],
        'no_leidas': no_leidas,
        'total': len(notificaciones)
    })

@app.route('/api/notificaciones/no-leidas', methods=['GET'])
@login_required
def api_notificaciones_no_leidas():
    """Obtiene el número de notificaciones no leídas"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    no_leidas = contar_notificaciones_no_leidas(usuario['id'])
    
    return jsonify({
        'success': True,
        'no_leidas': no_leidas
    })

@app.route('/api/notificacion/<int:notificacion_id>/leer', methods=['POST'])
@login_required
def api_marcar_notificacion_leida(notificacion_id):
    """Marca una notificación como leída"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    marcar_notificacion_leida(notificacion_id, usuario['id'])
    
    return jsonify({
        'success': True,
        'message': 'Notificación marcada como leída'
    })

@app.route('/api/notificaciones/leer-todas', methods=['POST'])
@login_required
def api_marcar_todas_notificaciones_leidas():
    """Marca todas las notificaciones como leídas"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    marcar_todas_notificaciones_leidas(usuario['id'])
    
    return jsonify({
        'success': True,
        'message': 'Todas las notificaciones marcadas como leídas'
    })

@app.route('/api/notificaciones/generar-stock', methods=['POST'])
@login_required
def api_generar_notificaciones_stock():
    """Genera notificaciones de stock bajo para el negocio del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    negocio_id = usuario.get('id')
    if usuario.get('rol') == 'trabajador':
        negocio_id = obtener_negocio_de_trabajador(usuario['id'])
        if not negocio_id:
            return jsonify({'error': 'No estás asignado a ningún negocio'}), 403
    
    generar_notificaciones_stock(negocio_id)
    
    return jsonify({
        'success': True,
        'message': 'Notificaciones de stock generadas'
    })

# ============================================
# API - PREFERENCIAS DE NOTIFICACIONES
# ============================================

@app.route('/api/preferencias-notificaciones', methods=['GET'])
@login_required
def api_obtener_preferencias_notificaciones():
    """Obtiene las preferencias de notificaciones del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    preferencias = obtener_preferencias_notificaciones(usuario['id'])
    
    return jsonify({
        'success': True,
        'preferencias': preferencias
    })

@app.route('/api/preferencias-notificaciones', methods=['PUT'])
@login_required
def api_actualizar_preferencias_notificaciones():
    """Actualiza las preferencias de notificaciones del usuario"""
    token = request.cookies.get('token')
    usuario = obtener_usuario_sesion(token)
    
    if not usuario:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json()
    
    preferencias = {
        'notificaciones_email': data.get('notificaciones_email', 1),
        'notificaciones_push': data.get('notificaciones_push', 1),
        'notificaciones_in_app': data.get('notificaciones_in_app', 1),
        'alerta_stock_bajo': data.get('alerta_stock_bajo', 1),
        'alerta_producto_nuevo': data.get('alerta_producto_nuevo', 1),
        'alerta_stock_actualizado': data.get('alerta_stock_actualizado', 0)
    }
    
    actualizar_preferencias_notificaciones(usuario['id'], preferencias)
    
    registrar_log(usuario['id'], 'preferencias_notificaciones', 'Preferencias actualizadas')
    
    return jsonify({
        'success': True,
        'message': '✅ Preferencias actualizadas correctamente'
    })

# ============================================
# INICIO DE LA APLICACIÓN
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
