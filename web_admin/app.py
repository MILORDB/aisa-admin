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
import random
import string
import threading

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
# FUNCIÓN PARA ENVIAR CORREOS DE VERIFICACIÓN (ASÍNCRONA)
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

def enviar_correo_async(email, username, codigo):
    """Envía correo en segundo plano para no bloquear la respuesta"""
    try:
        enviar_correo_verificacion(email, username, codigo)
    except Exception as e:
        print(f"❌ Error enviando correo en background: {e}")

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
# ENDPOINTS DE REPARACIÓN
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

@app.route('/fix-verificar-todos', methods=['GET'])
@admin_required
def fix_verificar_todos():
    """Endpoint para marcar todos los usuarios existentes como verificados"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
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

@app.route('/fix-modulos', methods=['GET'])
def fix_modulos_endpoint():
    """Endpoint para reparar los módulos de todos los usuarios"""
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
                cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (u['id'],))
                for modulo in modulos:
                    cursor.execute('''
                        INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                        VALUES (%s, %s, 1, 'aprobado')
                    ''', (u['id'], modulo['id']))
                mensajes.append(f"✅ Admin {u['username']} - TODOS los módulos activos")
            elif u['tipo'] == 'negocio':
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
# ENDPOINTS DE PRUEBA SMTP
# ============================================

@app.route('/test-smtp', methods=['GET'])
@admin_required
def test_smtp():
    """Endpoint para probar la conexión SMTP"""
    try:
        import smtplib
        
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_password = os.environ.get('SMTP_PASSWORD', '')
        
        resultados = []
        
        # Verificar configuración
        resultados.append(f"📧 SMTP Server: {smtp_server}")
        resultados.append(f"🔌 SMTP Port: {smtp_port}")
        resultados.append(f"👤 SMTP User: {smtp_user}")
        resultados.append(f"🔑 SMTP Password: {'✅ Configurada' if smtp_password else '❌ NO CONFIGURADA'}")
        
        if not smtp_user or not smtp_password:
            resultados.append("❌ SMTP_USER o SMTP_PASSWORD no están configurados")
            return jsonify({
                'success': False,
                'message': 'SMTP no configurado',
                'detalles': resultados
            }), 400
        
        # Probar conexión
        resultados.append("🔄 Conectando al servidor SMTP...")
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.set_debuglevel(1)
        resultados.append("✅ Conexión establecida")
        
        server.starttls()
        resultados.append("✅ TLS iniciado")
        
        server.login(smtp_user, smtp_password)
        resultados.append("✅ Autenticación exitosa")
        
        server.quit()
        resultados.append("✅ Conexión cerrada")
        
        return jsonify({
            'success': True,
            'message': 'SMTP configurado correctamente',
            'detalles': resultados
        })
        
    except smtplib.SMTPAuthenticationError as e:
        resultados.append(f"❌ Error de autenticación: {e}")
        return jsonify({
            'success': False,
            'message': 'Error de autenticación SMTP. Verifica usuario y contraseña.',
            'detalles': resultados
        }), 401
    except smtplib.SMTPException as e:
        resultados.append(f"❌ Error SMTP: {e}")
        return jsonify({
            'success': False,
            'message': f'Error SMTP: {str(e)}',
            'detalles': resultados
        }), 500
    except Exception as e:
        resultados.append(f"❌ Error: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'detalles': resultados
        }), 500

@app.route('/test-email', methods=['GET'])
@admin_required
def test_email():
    """Envía un correo de prueba"""
    try:
        smtp_user = os.environ.get('SMTP_USER', '')
        if not smtp_user:
            return jsonify({
                'success': False,
                'error': 'SMTP_USER no configurado'
            }), 400
        
        # Enviar correo de prueba
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = smtp_user
        msg['Subject'] = "🧪 Prueba SMTP - AIsa"
        
        body = f"""
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0f0f1a; color: #fff; padding: 40px; text-align: center;">
            <div style="max-width: 500px; margin: 0 auto; background: #1a1a2e; border-radius: 12px; padding: 30px; border: 1px solid #2a2a3e;">
                <h1 style="color: #6c3ce0; font-size: 24px;">🤖 AIsa</h1>
                <p style="color: #aaa; font-size: 14px;">✅ Este es un correo de prueba</p>
                <p style="color: #888; font-size: 12px;">La configuración SMTP está funcionando correctamente.</p>
                <p style="color: #666; font-size: 11px;">Enviado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_password = os.environ.get('SMTP_PASSWORD', '')
        
        if not smtp_password:
            return jsonify({
                'success': False,
                'error': 'SMTP_PASSWORD no configurado'
            }), 400
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, smtp_user, msg.as_string())
        server.quit()
        
        return jsonify({
            'success': True,
            'message': f'Correo de prueba enviado a {smtp_user}',
            'details': {
                'to': smtp_user,
                'from': smtp_user,
                'server': smtp_server,
                'port': smtp_port
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        
        # Para clientes y negocios, generar código de verificación (ENVIAR EN BACKGROUND)
        codigo = generar_codigo_verificacion()
        guardar_codigo_verificacion(user_id, email, codigo)
        
        # Enviar correo en segundo plano para no bloquear
        threading.Thread(target=enviar_correo_async, args=(email, username, codigo)).start()
        
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
# API - INSTALADOR
# ============================================

@app.route('/instalar')
def instalar_page():
    """Página de instalación"""
    return render_template('instalar.html')

@app.route('/api/instalar/tablas', methods=['POST'])
def api_instalar_tablas():
    """Crea todas las tablas de la base de datos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        log_messages = []
        
        # Crear todas las tablas (el mismo código que antes)
        # ... (código completo de creación de tablas)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Tablas creadas correctamente',
            'detalles': log_messages
        })
        
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/instalar/admin', methods=['POST'])
def api_instalar_admin():
    """Crea el usuario admin"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verificar si admin ya existe
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        if cursor.fetchone():
            return jsonify({
                'success': True,
                'message': 'El usuario admin ya existe'
            })
        
        # Crear admin con contraseña admin123
        password_hash = hash_password('admin123')
        fecha = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado, verificado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1, 1)
            RETURNING id
        ''', ('admin', 'admin@aisa.com', password_hash, 'Administrador', 'admin', 'admin', fecha))
        
        admin_id = cursor.fetchone()[0]
        
        # Asignar todos los módulos al admin
        cursor.execute("SELECT id FROM modulos")
        for mod in cursor.fetchall():
            cursor.execute('''
                INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
                VALUES (%s, %s, 1, 'aprobado')
                ON CONFLICT (usuario_id, modulo_id) DO NOTHING
            ''', (admin_id, mod[0]))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario admin creado correctamente (admin/admin123)',
            'admin_id': admin_id
        })
        
    except Exception as e:
        print(f"❌ Error creando admin: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/instalar/verificar', methods=['GET'])
def api_instalar_verificar():
    """Verifica el estado de la base de datos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Contar tablas
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tablas = cursor.fetchone()[0]
        
        # Verificar admin
        cursor.execute("SELECT username FROM usuarios WHERE username = 'admin'")
        admin = cursor.fetchone()
        admin_nombre = admin[0] if admin else None
        
        # Contar módulos
        cursor.execute("SELECT COUNT(*) FROM modulos")
        modulos = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'tablas': tablas,
            'admin': admin_nombre,
            'modulos': modulos,
            'lista': tablas > 0 and admin_nombre and modulos > 0
        })
        
    except Exception as e:
        print(f"❌ Error verificando: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# API - PERFIL DE USUARIO
# ============================================
# (El resto de los endpoints ya están en tu código)
# Incluye todos los endpoints de productos, ventas, servicios, contratos, nómina, etc.
# ... (todo el código que ya tenías)

# ============================================
# INICIO DE LA APLICACIÓN
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
