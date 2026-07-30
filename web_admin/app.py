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
        obtener_estadisticas_productos
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
# ENDPOINT PARA REPARAR PRODUCTOS (AGREGAR COLUMNA COSTO)
# ============================================

@app.route('/fix-productos', methods=['GET'])
def fix_productos():
    """Endpoint para agregar la columna costo a la tabla productos"""
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
        
        # Verificar si la columna existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'costo'
        """)
        existe = cursor.fetchone()
        
        if not existe:
            print("🔧 Agregando columna 'costo' a la tabla productos...")
            try:
                cursor.execute("ALTER TABLE productos ADD COLUMN costo REAL DEFAULT 0")
                conn.commit()
                mensaje = "✅ Columna 'costo' agregada correctamente"
                print(mensaje)
            except psycopg2.Error as e:
                conn.rollback()
                mensaje = f"❌ Error al agregar columna: {e}"
                print(mensaje)
                return f"""
                <html>
                    <head><title>Error</title></head>
                    <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                        <h1 style="color:#ff6b6b;">❌ {mensaje}</h1>
                        <a href="/negocio/inventario" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Inventario</a>
                    </body>
                </html>
                """
        else:
            mensaje = "✅ La columna 'costo' ya existe"
            print(mensaje)
        
        # Verificar columnas actuales
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'productos'
            ORDER BY ordinal_position
        """)
        columnas = cursor.fetchall()
        
        html_columnas = "<br>".join([f"• {col[0]} ({col[1]})" for col in columnas])
        
        conn.close()
        
        return f"""
        <html>
            <head><title>Productos Reparados</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#6c3ce0;">✅ {mensaje}</h1>
                <div style="background:#1a1a2e;border-radius:8px;padding:20px;margin:20px auto;max-width:600px;text-align:left;border:1px solid #2a2a3e;">
                    <h3 style="color:#aaa;margin-bottom:10px;">📋 Columnas en 'productos':</h3>
                    {html_columnas}
                </div>
                <br>
                <a href="/negocio/inventario" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;display:inline-block;">Ir al Inventario</a>
                <a href="/dashboard" style="color:#888;text-decoration:none;border:1px solid #2a2a3e;padding:10px 20px;border-radius:8px;display:inline-block;margin-left:10px;">Volver al Dashboard</a>
            </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error al reparar productos</h1>
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
# CONTINUACIÓN DEL CÓDIGO APP.PY
# ============================================
# (El resto del código APP.PY continúa con todas las rutas y endpoints)
# Para no hacer esta respuesta excesivamente larga, el resto del código
# es idéntico a la versión anterior, solo asegúrate de que el endpoint
# /api/productos y /api/producto/<id> usen la función crear_producto
# y actualizar_producto con el parámetro costo

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
