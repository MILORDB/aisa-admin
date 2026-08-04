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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
        actualizar_ubicacion_usuario, obtener_ubicacion_usuario, obtener_negocios_con_ubicacion,
        generar_numero_factura, obtener_ultimo_numero_factura, actualizar_ultimo_numero_factura,
        registrar_asistencia,
        # Nuevas funciones de verificación
        generar_codigo_verificacion, guardar_codigo_verificacion, 
        verificar_codigo, marcar_usuario_verificado, obtener_codigos_pendientes
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
# FUNCIÓN PARA ENVIAR CORREOS DE VERIFICACIÓN
# ============================================

def enviar_correo_verificacion(email, username, codigo):
    """Envía un correo con el código de verificación"""
    try:
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_password = os.environ.get('SMTP_PASSWORD', '')
        
        if not smtp_user or not smtp_password:
            print("⚠️ SMTP_USER o SMTP_PASSWORD no configurados")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email
        msg['Subject'] = "🔐 Código de verificación - AIsa"
        
        body = f"""
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f0f1a; color: #fff; padding: 40px; text-align: center;">
            <div style="max-width: 500px; margin: 0 auto; background: #1a1a2e; border-radius: 12px; padding: 30px; border: 1px solid #2a2a3e;">
                <h1 style="color: #6c3ce0; font-size: 24px;">🤖 AIsa</h1>
                <p style="color: #aaa; font-size: 14px;">Hola <strong style="color: #6c3ce0;">{username}</strong>,</p>
                <p style="color: #aaa; font-size: 14px;">Gracias por registrarte en AIsa. Para activar tu cuenta, ingresa el siguiente código:</p>
                
                <div style="background: #0f0f1a; border-radius: 8px; padding: 20px; margin: 20px 0; border: 2px solid #6c3ce0;">
                    <span style="font-size: 36px; font-weight: 700; color: #6c3ce0; letter-spacing: 8px;">{codigo}</span>
                </div>
                
                <p style="color: #666; font-size: 12px;">Este código expirará en 15 minutos.</p>
                <p style="color: #666; font-size: 12px;">Si no solicitaste este registro, ignora este mensaje.</p>
                
                <hr style="border-color: #2a2a3e; margin: 20px 0;">
                <p style="color: #444; font-size: 11px;">© 2024 AIsa - Sistema de Gestión Empresarial</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, email, msg.as_string())
        server.quit()
        
        print(f"✅ Correo de verificación enviado a {email}")
        return True
        
    except Exception as e:
        print(f"❌ Error enviando correo: {e}")
        return False

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
# ENDPOINTS DE REPARACIÓN (MANTENIDOS)
# ============================================
# (Todos los endpoints /fix-* y /debug-* se mantienen igual que en la versión anterior)
# Por brevedad, aquí se incluyen solo los nuevos endpoints de verificación.
# Se asume que los endpoints de reparación ya están presentes en tu código.

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
        
        # Verificar si la cuenta está verificada (excepto admin y trabajador)
        if usuario.get('verificado') != 1 and usuario.get('rol') != 'admin' and usuario.get('rol') != 'trabajador':
            return jsonify({
                'error': 'Cuenta no verificada. Revisa tu correo para activar la cuenta.',
                'requires_verification': True,
                'email': usuario.get('email'),
                'user_id': usuario.get('id')
            }), 401
        
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
        
        # Crear usuario
        user_id = crear_usuario(username, email, password, nombre, rol, tipo, datos_negocio)
        
        if not user_id:
            return jsonify({'error': 'Error al crear el usuario'}), 500
        
        # Para trabajadores y admin, activar automáticamente
        if rol == 'trabajador':
            marcar_usuario_verificado(user_id)
            registrar_log(user_id, 'registro_trabajador', f'Trabajador registrado: {username}')
            return jsonify({
                'success': True,
                'message': 'Trabajador registrado correctamente',
                'user_id': user_id,
                'verificado': True
            })
        
        if rol == 'admin':
            marcar_usuario_verificado(user_id)
            registrar_log(user_id, 'registro_admin', f'Admin registrado: {username}')
            return jsonify({
                'success': True,
                'message': 'Administrador registrado correctamente',
                'user_id': user_id,
                'verificado': True
            })
        
        # Para clientes y negocios, generar código de verificación
        codigo = generar_codigo_verificacion()
        guardar_codigo_verificacion(user_id, email, codigo)
        
        # Enviar correo
        enviar_correo_verificacion(email, username, codigo)
        
        registrar_log(user_id, 'registro_pendiente', f'Usuario registrado pendiente de verificación: {username}')
        
        return jsonify({
            'success': True,
            'message': 'Usuario registrado correctamente. Revisa tu correo para activar la cuenta.',
            'user_id': user_id,
            'verificado': False,
            'email': email,
            'requires_verification': True,
            'redirect_url': f'/verificar?email={email}&user_id={user_id}'
        })
        
    except Exception as e:
        print(f"❌ Error en register: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/verificar')
def verificar():
    """Página de verificación de código"""
    email = request.args.get('email')
    user_id = request.args.get('user_id')
    
    if not email or not user_id:
        return redirect(url_for('login'))
    
    return render_template('verificar.html', email=email, user_id=user_id)

# ============================================
# API - VERIFICACIÓN DE CÓDIGO
# ============================================

@app.route('/api/verificar-codigo', methods=['POST'])
def api_verificar_codigo():
    """Verifica el código de activación de una cuenta"""
    try:
        data = request.get_json()
        email = data.get('email')
        codigo = data.get('codigo')
        
        if not email or not codigo:
            return jsonify({'error': 'Email y código son requeridos'}), 400
        
        # Verificar código
        registro = verificar_codigo(email, codigo)
        
        if not registro:
            # Verificar si hay códigos pendientes
            pendientes = obtener_codigos_pendientes(email)
            if pendientes:
                return jsonify({
                    'error': 'Código inválido o expirado. Solicita un nuevo código.',
                    'codigos_pendientes': len(pendientes)
                }), 400
            else:
                return jsonify({
                    'error': 'Código inválido o expirado. Solicita un nuevo código.'
                }), 400
        
        # Marcar usuario como verificado
        user_id = registro['usuario_id']
        exito = marcar_usuario_verificado(user_id)
        
        if not exito:
            return jsonify({'error': 'Error al activar la cuenta'}), 500
        
        registrar_log(user_id, 'cuenta_verificada', f'Cuenta verificada con código: {codigo}')
        
        return jsonify({
            'success': True,
            'message': 'Cuenta activada correctamente. Ya puedes iniciar sesión.',
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"❌ Error en api_verificar_codigo: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reenviar-codigo', methods=['POST'])
def api_reenviar_codigo():
    """Reenvía el código de verificación a un email"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email es requerido'}), 400
        
        # Buscar usuario por email
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT id, username FROM usuarios WHERE email = %s AND verificado = 0', (email,))
        usuario = cursor.fetchone()
        conn.close()
        
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado o ya verificado'}), 404
        
        # Generar nuevo código
        codigo = generar_codigo_verificacion()
        guardar_codigo_verificacion(usuario['id'], email, codigo)
        
        # Enviar correo
        enviar_correo_verificacion(email, usuario['username'], codigo)
        
        registrar_log(usuario['id'], 'codigo_reenviado', f'Código reenviado a {email}')
        
        return jsonify({
            'success': True,
            'message': 'Código reenviado correctamente. Revisa tu correo.'
        })
        
    except Exception as e:
        print(f"❌ Error en api_reenviar_codigo: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# DASHBOARD Y DEMÁS RUTAS (MANTENIDAS)
# ============================================
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
# RUTAS DE MÓDULOS DE NEGOCIO (MANTENIDAS)
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
# API - PERFIL DE USUARIO (MANTENIDO)
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
# API - SQL QUERY (MANTENIDO)
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
# API - ESTADÍSTICAS (MANTENIDO)
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
# API - USUARIOS (MANTENIDO)
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
# API - MÓDULOS (MANTENIDO)
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
# API - NEGOCIOS (MANTENIDO)
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
# API - VENTAS (MANTENIDO)
# ============================================
# (Se mantiene igual que en la versión anterior, solo se incluye un resumen)
# Asegúrate de que todos los endpoints de ventas, contratos, servicios, nómina, reportes,
# productos, tienda, trabajadores, etc. estén presentes en tu código final.
# Aquí se omite el resto por brevedad, pero deben estar incluidos.

# ============================================
# INICIO DE LA APLICACIÓN
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
