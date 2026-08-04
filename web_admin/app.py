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
import urllib.parse

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
# ENDPOINT PARA REPARAR ADMIN (URL DIRECTA)
# ============================================
@app.route('/fix-admin', methods=['GET'])
def fix_admin_endpoint():
    """Endpoint para reparar el admin - URL directa /fix-admin"""
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
                INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado, verificado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1, 1)
                RETURNING id
            ''', ('admin', 'admin@aisa.com', password_hash, 'Administrador', 'admin', 'admin', fecha))
            
            admin_id = cursor.fetchone()['id']
            conn.commit()
            mensajes.append(f"✅ Admin creado con ID: {admin_id}")
        
        # 2. FORZAR rol y tipo a 'admin'
        cursor.execute('''
            UPDATE usuarios 
            SET rol = 'admin', tipo = 'admin', activo = 1, aprobado = 1, verificado = 1
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
        cursor.execute("SELECT id, username, rol, tipo, activo, verificado FROM usuarios WHERE id = %s", (admin_id,))
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
                            <div class="row">
                                <span class="label">🔐 Verificado</span>
                                <span class="value ok">{'Sí' if admin_final['verificado'] == 1 else 'No'}</span>
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
# ENDPOINT PARA AGREGAR COLUMNA VERIFICADO
# ============================================
@app.route('/fix-verificado', methods=['GET'])
def fix_verificado():
    """Endpoint para agregar la columna verificado a la tabla usuarios"""
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
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL - Agregando columna verificado...")
        
        mensajes = []
        
        # Verificar si la columna verificado existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'usuarios' AND column_name = 'verificado'
        """)
        
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE usuarios ADD COLUMN verificado INTEGER DEFAULT 0")
            mensajes.append("✅ Columna 'verificado' agregada a la tabla usuarios")
        else:
            mensajes.append("✅ Columna 'verificado' ya existe")
        
        # Verificar si la tabla codigos_verificacion existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'codigos_verificacion'
            )
        """)
        
        if not cursor.fetchone()[0]:
            mensajes.append("⚠️ Tabla 'codigos_verificacion' no existe. Creándola...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS codigos_verificacion (
                id SERIAL PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                codigo TEXT NOT NULL,
                email TEXT NOT NULL,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expira_en TIMESTAMP NOT NULL,
                usado INTEGER DEFAULT 0,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
            ''')
            mensajes.append("✅ Tabla 'codigos_verificacion' creada")
        else:
            mensajes.append("✅ Tabla 'codigos_verificacion' ya existe")
        
        conn.commit()
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        
        return f"""
        <html>
            <head>
                <title>Columna Verificado Agregada</title>
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
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Verificación</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        {html_mensajes}
                    </div>
                    
                    <div>
                        <a href="/register" class="btn btn-primary">📝 Ir a Registro</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        import traceback
        error_detalle = traceback.format_exc()
        print(f"❌ Error: {e}")
        
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error al agregar columna</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;font-size:12px;overflow:auto;max-height:400px;">{error_detalle}</pre>
                <div style="margin-top:16px;">
                    <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
                </div>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINT PARA MARCAR TODOS LOS USUARIOS COMO VERIFICADOS
# ============================================
@app.route('/fix-verificar-todos', methods=['GET'])
@admin_required
def fix_verificar_todos():
    """Endpoint para marcar todos los usuarios existentes como verificados"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Actualizar todos los usuarios que no son admin ni trabajador (ya que esos ya están verificados)
        cursor.execute('''
            UPDATE usuarios 
            SET verificado = 1, aprobado = 1 
            WHERE verificado = 0
            RETURNING id, username, email
        ''')
        
        actualizados = cursor.fetchall()
        conn.commit()
        conn.close()
        
        if actualizados:
            mensajes = [f"✅ Usuario {u[1]} (ID: {u[0]}) - {u[2]} marcado como verificado" for u in actualizados]
            html_lista = "<br>".join(mensajes)
            total = len(actualizados)
        else:
            html_lista = "✅ No hay usuarios pendientes de verificación"
            total = 0
        
        return f"""
        <html>
            <head>
                <title>Usuarios Verificados</title>
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
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔐 Verificación Masiva de Usuarios</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        <div style="font-size:18px;font-weight:700;color:#6bff6b;text-align:center;padding:10px;">
                            {total} usuarios verificados
                        </div>
                        <div class="result-box">
                            {html_lista}
                        </div>
                    </div>
                    
                    <div>
                        <a href="/dashboard" class="btn btn-primary">← Volver al Dashboard</a>
                        <a href="/login" class="btn btn-secondary">🔑 Ir al Login</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        import traceback
        error_detalle = traceback.format_exc()
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;font-size:12px;overflow:auto;max-height:400px;">{error_detalle}</pre>
                <div style="margin-top:16px;">
                    <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
                </div>
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
# ENDPOINT PARA REPARAR TABLAS DE NÓMINA
# ============================================
@app.route('/fix-tablas-nomina', methods=['GET'])
def fix_tablas_nomina():
    """Endpoint para crear tablas de nómina desde el navegador"""
    try:
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        if not DATABASE_URL:
            return """
            <html>
                <head><title>Error</title></head>
                <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                    <h1 style="color:#ff6b6b;">❌ DATABASE_URL no está configurada</h1>
                    <p style="color:#888;">Asegúrate de que la variable de entorno DATABASE_URL esté configurada en Render</p>
                    <br>
                    <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
                </body>
            </html>
            """, 500
        
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
        print("✅ Conectado a PostgreSQL - Reparando tablas de nómina...")
        
        mensajes = []
        
        # 1. Crear tabla asistencia
        print("🔧 Creando tabla asistencia...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS asistencia (
            id SERIAL PRIMARY KEY,
            trabajador_id INTEGER NOT NULL,
            negocio_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            presente INTEGER DEFAULT 1,
            horas_trabajadas REAL DEFAULT 8,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(trabajador_id, fecha)
        )
        ''')
        mensajes.append("✅ Tabla 'asistencia' creada/verificada")
        
        # 2. Crear tabla comisiones_trabajador
        print("🔧 Creando tabla comisiones_trabajador...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS comisiones_trabajador (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL,
            trabajador_id INTEGER NOT NULL,
            venta_id INTEGER NOT NULL,
            producto_id INTEGER,
            monto REAL NOT NULL DEFAULT 0,
            fecha DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
        )
        ''')
        mensajes.append("✅ Tabla 'comisiones_trabajador' creada/verificada")
        
        # 3. Verificar tabla nomina
        print("🔧 Verificando tabla nomina...")
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
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(negocio_id, trabajador_id, mes, ano)
        )
        ''')
        mensajes.append("✅ Tabla 'nomina' creada/verificada")
        
        # 4. Verificar columna comision en productos
        print("🔧 Verificando columna comision en productos...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'comision'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE productos ADD COLUMN comision REAL DEFAULT 0")
            mensajes.append("✅ Columna 'comision' agregada a productos")
        else:
            mensajes.append("✅ Columna 'comision' ya existe")
        
        # 5. Verificar columna costo en productos
        print("🔧 Verificando columna costo en productos...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'costo'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE productos ADD COLUMN costo REAL DEFAULT 0")
            mensajes.append("✅ Columna 'costo' agregada a productos")
        else:
            mensajes.append("✅ Columna 'costo' ya existe")
        
        # 6. Verificar columna factura en ventas
        print("🔧 Verificando columna factura en ventas...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ventas' AND column_name = 'factura'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE ventas ADD COLUMN factura TEXT")
            mensajes.append("✅ Columna 'factura' agregada a ventas")
        else:
            mensajes.append("✅ Columna 'factura' ya existe")
        
        conn.commit()
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        
        return f"""
        <html>
            <head>
                <title>Tablas de Nómina Reparadas</title>
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
                    .btn-success {{ background: #4caf50; color: #fff; }}
                    .btn-success:hover {{ background: #3d8b40; }}
                    ul {{ list-style: none; padding: 0; }}
                    ul li {{ padding: 6px 0; border-bottom: 1px solid #1a1a2e; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Tablas de Nómina</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        <ul>
                            {''.join([f'<li>✅ {m}</li>' for m in mensajes])}
                        </ul>
                    </div>
                    
                    <div class="card">
                        <h3>📋 Tablas Creadas/Verificadas</h3>
                        <ul>
                            <li>✅ <strong>asistencia</strong> - Registro de asistencia de trabajadores</li>
                            <li>✅ <strong>comisiones_trabajador</strong> - Comisiones por ventas de trabajadores</li>
                            <li>✅ <strong>nomina</strong> - Cálculo de nómina mensual</li>
                            <li>✅ <strong>productos</strong> - Columnas 'costo' y 'comision' agregadas</li>
                            <li>✅ <strong>ventas</strong> - Columna 'factura' agregada</li>
                        </ul>
                    </div>
                    
                    <div>
                        <a href="/negocio/nomina" class="btn btn-primary">📊 Ir a Nómina</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 16px; background: #0f0f1a; border-radius: 8px; border: 1px solid #2a2a3e;">
                        <p style="color: #888;">ℹ️ Si el problema persiste, reinicia el servidor en Render</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        import traceback
        error_detalle = traceback.format_exc()
        print(f"❌ Error en fix_tablas_nomina: {e}")
        print(error_detalle)
        
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error al reparar tablas</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;font-size:12px;overflow:auto;max-height:400px;">{error_detalle}</pre>
                <div style="margin-top:16px;">
                    <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
                </div>
            </body>
        </html>
        """, 500

# ============================================
# ENDPOINT PARA REPARAR TODAS LAS TABLAS DE NÓMINA Y COMISIONES (COMPLETO)
# ============================================
@app.route('/fix-nomina-completo', methods=['GET'])
def fix_nomina_completo():
    """Endpoint para crear todas las tablas relacionadas con nómina y comisiones"""
    try:
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        
        if not DATABASE_URL:
            return """
            <html>
                <head><title>Error</title></head>
                <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                    <h1 style="color:#ff6b6b;">❌ DATABASE_URL no está configurada</h1>
                    <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
                </body>
            </html>
            """, 500
        
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
        print("✅ Conectado a PostgreSQL - Reparando tablas de nómina y comisiones...")
        
        mensajes = []
        errores = []
        
        # 1. TABLA ASISTENCIA
        print("🔧 Creando tabla asistencia...")
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS asistencia (
                id SERIAL PRIMARY KEY,
                trabajador_id INTEGER NOT NULL,
                negocio_id INTEGER NOT NULL,
                fecha DATE NOT NULL,
                presente INTEGER DEFAULT 1,
                horas_trabajadas REAL DEFAULT 8,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                UNIQUE(trabajador_id, fecha)
            )
            ''')
            mensajes.append("✅ Tabla 'asistencia' creada/verificada")
        except Exception as e:
            errores.append(f"❌ Error creando 'asistencia': {str(e)}")
            print(f"❌ Error: {e}")
        
        # 2. TABLA COMISIONES_TRABAJADOR
        print("🔧 Creando tabla comisiones_trabajador...")
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS comisiones_trabajador (
                id SERIAL PRIMARY KEY,
                negocio_id INTEGER NOT NULL,
                trabajador_id INTEGER NOT NULL,
                venta_id INTEGER NOT NULL,
                producto_id INTEGER,
                monto REAL NOT NULL DEFAULT 0,
                fecha DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
            )
            ''')
            mensajes.append("✅ Tabla 'comisiones_trabajador' creada/verificada")
        except Exception as e:
            errores.append(f"❌ Error creando 'comisiones_trabajador': {str(e)}")
            print(f"❌ Error: {e}")
        
        # 3. TABLA NOMINA
        print("🔧 Creando tabla nomina...")
        try:
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
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                actualizado_en TIMESTAMP,
                FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                UNIQUE(negocio_id, trabajador_id, mes, ano)
            )
            ''')
            mensajes.append("✅ Tabla 'nomina' creada/verificada")
        except Exception as e:
            errores.append(f"❌ Error creando 'nomina': {str(e)}")
            print(f"❌ Error: {e}")
        
        # 4. VERIFICAR COLUMNA COMISION EN PRODUCTOS
        print("🔧 Verificando columna comision en productos...")
        try:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'productos' AND column_name = 'comision'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE productos ADD COLUMN comision REAL DEFAULT 0")
                mensajes.append("✅ Columna 'comision' agregada a productos")
            else:
                mensajes.append("✅ Columna 'comision' ya existe en productos")
        except Exception as e:
            errores.append(f"❌ Error verificando columna 'comision': {str(e)}")
            print(f"❌ Error: {e}")
        
        # 5. VERIFICAR COLUMNA COSTO EN PRODUCTOS
        print("🔧 Verificando columna costo en productos...")
        try:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'productos' AND column_name = 'costo'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE productos ADD COLUMN costo REAL DEFAULT 0")
                mensajes.append("✅ Columna 'costo' agregada a productos")
            else:
                mensajes.append("✅ Columna 'costo' ya existe en productos")
        except Exception as e:
            errores.append(f"❌ Error verificando columna 'costo': {str(e)}")
            print(f"❌ Error: {e}")
        
        # 6. VERIFICAR COLUMNA FACTURA EN VENTAS
        print("🔧 Verificando columna factura en ventas...")
        try:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'ventas' AND column_name = 'factura'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE ventas ADD COLUMN factura TEXT")
                mensajes.append("✅ Columna 'factura' agregada a ventas")
            else:
                mensajes.append("✅ Columna 'factura' ya existe en ventas")
        except Exception as e:
            errores.append(f"❌ Error verificando columna 'factura': {str(e)}")
            print(f"❌ Error: {e}")
        
        # 7. CREAR ÍNDICES
        print("🔧 Creando índices...")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_asistencia_trabajador ON asistencia(trabajador_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_asistencia_fecha ON asistencia(fecha)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comisiones_trabajador ON comisiones_trabajador(trabajador_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comisiones_fecha ON comisiones_trabajador(fecha)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nomina_trabajador ON nomina(trabajador_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nomina_mes_ano ON nomina(mes, ano)")
            mensajes.append("✅ Índices creados/verificados")
        except Exception as e:
            errores.append(f"⚠️ Error creando índices: {str(e)}")
            print(f"⚠️ Error: {e}")
        
        conn.commit()
        
        # 8. VERIFICAR QUE LAS TABLAS EXISTAN
        print("🔧 Verificando tablas...")
        tablas_verificadas = []
        for tabla in ['asistencia', 'comisiones_trabajador', 'nomina']:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (tabla,))
            existe = cursor.fetchone()[0]
            tablas_verificadas.append(f"{tabla}: {'✅ Existe' if existe else '❌ NO EXISTE'}")
            if not existe:
                errores.append(f"❌ Tabla '{tabla}' NO existe después de la creación")
        
        conn.close()
        
        html_mensajes = "<br>".join(mensajes)
        html_errores = "<br>".join(errores) if errores else "✅ Sin errores"
        html_verificacion = "<br>".join(tablas_verificadas)
        
        return f"""
        <html>
            <head>
                <title>Tablas de Nómina y Comisiones Reparadas</title>
                <style>
                    body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                    .container {{ max-width: 900px; margin: 0 auto; }}
                    .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                    .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                    .success {{ color: #6bff6b; }}
                    .error {{ color: #ff6b6b; }}
                    .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                    .btn-primary {{ background: #6c3ce0; color: #fff; }}
                    .btn-primary:hover {{ background: #5a2ec0; }}
                    .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                    .btn-secondary:hover {{ background: #3a3a4e; }}
                    .btn-success {{ background: #4caf50; color: #fff; }}
                    .btn-success:hover {{ background: #3d8b40; }}
                    ul {{ list-style: none; padding: 0; }}
                    ul li {{ padding: 6px 0; border-bottom: 1px solid #1a1a2e; }}
                    .result-box {{ background: #0f0f1a; border-radius: 8px; padding: 12px; border: 1px solid #2a2a3e; margin-top: 12px; }}
                    .tabla-status {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
                    .tabla-status td {{ padding: 6px 12px; border-bottom: 1px solid #1a1a2e; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Tablas de Nómina y Comisiones</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        <ul>
                            {''.join([f'<li>✅ {m}</li>' for m in mensajes])}
                        </ul>
                        {f'<div style="margin-top:10px;color:#ff6b6b;"><strong>❌ Errores:</strong><br>{html_errores}</div>' if errores else ''}
                    </div>
                    
                    <div class="card">
                        <h3>📋 Verificación de Tablas</h3>
                        <table class="tabla-status">
                            {''.join([f'<tr><td>📌 {t}</td></tr>' for t in tablas_verificadas])}
                        </table>
                    </div>
                    
                    <div class="card">
                        <h3>📋 Tablas Creadas/Verificadas</h3>
                        <ul>
                            <li>✅ <strong>asistencia</strong> - Registro de asistencia de trabajadores</li>
                            <li>✅ <strong>comisiones_trabajador</strong> - Comisiones por ventas de trabajadores</li>
                            <li>✅ <strong>nomina</strong> - Cálculo de nómina mensual</li>
                            <li>✅ <strong>productos</strong> - Columnas 'costo' y 'comision' agregadas</li>
                            <li>✅ <strong>ventas</strong> - Columna 'factura' agregada</li>
                        </ul>
                    </div>
                    
                    <div>
                        <a href="/negocio/nomina" class="btn btn-primary">📊 Ir a Nómina</a>
                        <a href="/negocio/ventas" class="btn btn-success">💰 Ir a Ventas</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 16px; background: #0f0f1a; border-radius: 8px; border: 1px solid #2a2a3e;">
                        <p style="color: #888;">ℹ️ Si el problema persiste, reinicia el servidor en Render</p>
                        <p style="color: #888;">🔧 También puedes ejecutar: <code style="color:#6c3ce0;">/fix-tablas-nomina</code></p>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        import traceback
        error_detalle = traceback.format_exc()
        print(f"❌ Error en fix_nomina_completo: {e}")
        print(error_detalle)
        
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error al reparar tablas</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;font-size:12px;overflow:auto;max-height:400px;">{error_detalle}</pre>
                <div style="margin-top:16px;">
                    <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
                </div>
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
        else:
            mapa_id = mapa['id']
            mensajes.append("✅ Módulo 'mapa' ya existe")
        
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
# ENDPOINT PARA REPARAR SECUENCIAS DE FACTURAS
# ============================================
@app.route('/fix-facturas-secuencia', methods=['GET'])
@admin_required
def fix_facturas_secuencia():
    """Endpoint para reparar/migrar secuencias de facturas"""
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
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL - Reparando secuencias de facturas...")
        
        mensajes = []
        
        # 1. Crear tabla si no existe
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas_secuencia (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL,
            empresa TEXT NOT NULL,
            ultimo_numero INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            UNIQUE(negocio_id, empresa)
        )
        ''')
        mensajes.append("✅ Tabla facturas_secuencia creada/verificada")
        
        # 2. Migrar secuencias existentes
        cursor.execute('''
            SELECT DISTINCT negocio_id, empresa FROM ventas 
            WHERE empresa IS NOT NULL AND empresa != '' AND estado != 'oferta'
        ''')
        empresas = cursor.fetchall()
        
        contador = 0
        for negocio_id, empresa in empresas:
            if empresa and empresa != '' and empresa != '📄 OFERTA':
                cursor.execute('''
                    SELECT MAX(CAST(SUBSTRING(factura FROM 'FAC-[0-9]+-([0-9]+)') AS INTEGER)) 
                    FROM ventas 
                    WHERE negocio_id = %s AND empresa = %s AND factura IS NOT NULL
                ''', (negocio_id, empresa))
                ultimo = cursor.fetchone()[0]
                if ultimo:
                    cursor.execute('''
                        INSERT INTO facturas_secuencia (negocio_id, empresa, ultimo_numero, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (negocio_id, empresa) DO UPDATE SET 
                            ultimo_numero = EXCLUDED.ultimo_numero,
                            updated_at = EXCLUDED.updated_at
                    ''', (negocio_id, empresa, ultimo, datetime.now().isoformat(), datetime.now().isoformat()))
                    contador += 1
        
        conn.commit()
        mensajes.append(f"✅ {contador} secuencias migradas")
        
        # 3. Verificar secuencias actuales
        cursor.execute('''
            SELECT fs.*, u.username 
            FROM facturas_secuencia fs
            JOIN usuarios u ON fs.negocio_id = u.id
            ORDER BY u.username, fs.empresa
        ''')
        secuencias = cursor.fetchall()
        conn.close()
        
        html_secuencias = ""
        for s in secuencias:
            html_secuencias += f"""
                <tr>
                    <td>{s[5]}</td>
                    <td>{s[2]}</td>
                    <td><strong style="color:#6c3ce0;">{s[3]}</strong></td>
                    <td>{s[4] or s[3]}</td>
                </tr>
            """
        
        return f"""
        <html>
            <head>
                <title>Secuencias de Facturas</title>
                <style>
                    body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                    .container {{ max-width: 900px; margin: 0 auto; }}
                    .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                    .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                    .success {{ color: #6bff6b; }}
                    .btn {{ display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                    .btn-primary {{ background: #6c3ce0; color: #fff; }}
                    .btn-primary:hover {{ background: #5a2ec0; }}
                    .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                    .btn-secondary:hover {{ background: #3a3a4e; }}
                    .tabla { width: 100%; border-collapse: collapse; font-size: 13px; }
                    .tabla th { text-align: left; padding: 8px 12px; color: #888; border-bottom: 1px solid #2a2a3e; }
                    .tabla td { padding: 8px 12px; border-bottom: 1px solid #1a1a2e; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Secuencias de Facturas</h1>
                    
                    <div class="card">
                        <h3>📊 Resultado</h3>
                        <ul>
                            {''.join([f'<li>✅ {m}</li>' for m in mensajes])}
                        </ul>
                    </div>
                    
                    <div class="card">
                        <h3>📋 Secuencias por Empresa</h3>
                        <table class="tabla">
                            <thead>
                                <tr>
                                    <th>Negocio</th>
                                    <th>Empresa</th>
                                    <th>Último Número</th>
                                    <th>Actualizado</th>
                                </tr>
                            </thead>
                            <tbody>
                                {html_secuencias}
                            </tbody>
                        </table>
                    </div>
                    
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
# ENDPOINT PARA DEBUG DE SECUENCIAS DE FACTURAS
# ============================================
@app.route('/debug/facturas-secuencia', methods=['GET'])
@admin_required
def debug_facturas_secuencia():
    """Endpoint para ver las secuencias de facturas"""
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT fs.*, u.username 
            FROM facturas_secuencia fs
            JOIN usuarios u ON fs.negocio_id = u.id
            ORDER BY u.username, fs.empresa
        ''')
        secuencias = cursor.fetchall()
        conn.close()
        
        html = """
        <html>
            <head>
                <title>Secuencias de Facturas</title>
                <style>
                    body { background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }
                    .container { max-width: 900px; margin: 0 auto; }
                    .card { background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }
                    .card h3 { color: #aaa; margin-bottom: 10px; }
                    .tabla { width: 100%; border-collapse: collapse; font-size: 13px; }
                    .tabla th { text-align: left; padding: 8px 12px; color: #888; border-bottom: 1px solid #2a2a3e; }
                    .tabla td { padding: 8px 12px; border-bottom: 1px solid #1a1a2e; }
                    .btn { display: inline-block; padding: 10px 20px; margin: 10px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; transition: all 0.3s; }}
                    .btn-primary { background: #6c3ce0; color: #fff; }
                    .btn-primary:hover { background: #5a2ec0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">📊 Secuencias de Facturas</h1>
                    <div class="card">
                        <h3>📋 Secuencias por Empresa</h3>
                        <table class="tabla">
                            <thead>
                                <tr>
                                    <th>Negocio</th>
                                    <th>Empresa</th>
                                    <th>Último Número</th>
                                    <th>Actualizado</th>
                                </tr>
                            </thead>
                            <tbody>
        """
        
        for s in secuencias:
            html += f"""
                                <tr>
                                    <td>{s['username']}</td>
                                    <td>{s['empresa']}</td>
                                    <td><strong style="color:#6c3ce0;">{s['ultimo_numero']}</strong></td>
                                    <td>{s['updated_at'] or s['created_at']}</td>
                                </tr>
            """
        
        html += """
                            </tbody>
                        </table>
                    </div>
                    <div>
                        <a href="/admin/db" class="btn btn-primary">← Volver al Gestor DB</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
        return html
        
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
# ENDPOINT PARA REPARAR TABLA NOMINA
# ============================================
@app.route('/fix-nomina-tabla', methods=['GET'])
def fix_nomina_tabla_endpoint():
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
        
        registro = verificar_codigo(email, codigo)
        
        if not registro:
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
        
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT id, username FROM usuarios WHERE email = %s AND verificado = 0', (email,))
        usuario = cursor.fetchone()
        conn.close()
        
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado o ya verificado'}), 404
        
        codigo = generar_codigo_verificacion()
        guardar_codigo_verificacion(usuario['id'], email, codigo)
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
# API - MÓDULOS
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
# INICIO DE LA APLICACIÓN
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
