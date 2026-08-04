import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import bcrypt
import json
import urllib.parse
import random
import string
from calendar import monthrange

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_db():
    """Obtiene una conexión a PostgreSQL"""
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

def init_db():
    """Inicializa la base de datos con PostgreSQL"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return
    
    # ============================================
    # TABLA USUARIOS (con verificado)
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        nombre TEXT,
        rol TEXT DEFAULT 'usuario',
        tipo TEXT DEFAULT 'cliente',
        activo INTEGER DEFAULT 1,
        aprobado INTEGER DEFAULT 1,
        verificado INTEGER DEFAULT 0,
        fecha_registro TEXT NOT NULL,
        ultimo_acceso TEXT,
        datos_negocio TEXT,
        latitud REAL,
        longitud REAL,
        ubicacion_actualizada TEXT
    )
    ''')
    
    # ============================================
    # TABLA SESIONES
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sesiones (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        fecha_creacion TEXT NOT NULL,
        fecha_expiracion TEXT NOT NULL,
        activo INTEGER DEFAULT 1,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )
    ''')
    
    # ============================================
    # TABLA MODULOS
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS modulos (
        id SERIAL PRIMARY KEY,
        nombre TEXT UNIQUE NOT NULL,
        descripcion TEXT,
        activo_global INTEGER DEFAULT 1,
        tipo_requerido TEXT DEFAULT 'ambos'
    )
    ''')
    
    # ============================================
    # TABLA PERMISOS_USUARIO
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS permisos_usuario (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER NOT NULL,
        modulo_id INTEGER NOT NULL,
        activo INTEGER DEFAULT 1,
        fecha_solicitud TEXT,
        estado_solicitud TEXT DEFAULT 'aprobado',
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (modulo_id) REFERENCES modulos(id) ON DELETE CASCADE,
        UNIQUE(usuario_id, modulo_id)
    )
    ''')
    
    # ============================================
    # TABLA LOGS
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY,
        usuario_id INTEGER,
        accion TEXT,
        detalle TEXT,
        fecha TEXT NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
    )
    ''')
    
    # ============================================
    # TABLA PRODUCTOS
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS productos (
        id SERIAL PRIMARY KEY,
        negocio_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        categoria TEXT,
        precio REAL NOT NULL,
        costo REAL DEFAULT 0,
        comision REAL DEFAULT 0,
        stock INTEGER DEFAULT 0,
        stock_minimo INTEGER DEFAULT 3,
        foto_url TEXT,
        foto_public_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )
    ''')
    
    # ============================================
    # TABLA PRODUCTOS_TIENDA
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS productos_tienda (
        id SERIAL PRIMARY KEY,
        negocio_id INTEGER NOT NULL,
        producto_id INTEGER NOT NULL,
        destacado INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )
    ''')
    
    # ============================================
    # TABLA VENTAS
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ventas (
        id SERIAL PRIMARY KEY,
        negocio_id INTEGER NOT NULL,
        trabajador_id INTEGER,
        cliente TEXT NOT NULL,
        producto TEXT NOT NULL,
        producto_id INTEGER,
        cantidad INTEGER DEFAULT 1,
        precio REAL NOT NULL,
        total REAL NOT NULL,
        estado TEXT DEFAULT 'pagado',
        empresa TEXT,
        tipo TEXT DEFAULT 'producto',
        factura_url TEXT,
        factura TEXT,
        transferencia_id TEXT,
        transferencia_cedula TEXT,
        transferencia_banco TEXT,
        transferencia_fecha TEXT,
        fecha TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE SET NULL,
        FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
    )
    ''')
    
    # ============================================
    # TABLA SERVICIOS
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS servicios (
        id SERIAL PRIMARY KEY,
        negocio_id INTEGER NOT NULL,
        trabajador_id INTEGER,
        nombre TEXT NOT NULL,
        categoria TEXT,
        precio REAL NOT NULL,
        duracion INTEGER DEFAULT 60,
        activo INTEGER DEFAULT 1,
        descripcion TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE SET NULL
    )
    ''')
    
    # ============================================
    # TABLA TRABAJADORES_NEGOCIO
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trabajadores_negocio (
        id SERIAL PRIMARY KEY,
        negocio_id INTEGER NOT NULL,
        trabajador_id INTEGER NOT NULL,
        activo INTEGER DEFAULT 1,
        cargo TEXT,
        salario REAL DEFAULT 0,
        fecha_contratacion TEXT NOT NULL,
        FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        UNIQUE(negocio_id, trabajador_id)
    )
    ''')
    
    # ============================================
    # TABLA CONTRATOS
    # ============================================
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contratos (
        id SERIAL PRIMARY KEY,
        negocio_id INTEGER NOT NULL,
        trabajador_id INTEGER,
        empresa TEXT NOT NULL,
        numero_contrato TEXT UNIQUE NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'ventas',
        monto REAL DEFAULT 0,
        estado TEXT DEFAULT 'activo',
        descripcion TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE SET NULL
    )
    ''')
    
    # ============================================
    # TABLA FACTURAS_SECUENCIA
    # ============================================
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
    
    # ============================================
    # TABLA ASISTENCIA
    # ============================================
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
    
    # ============================================
    # TABLA COMISIONES_TRABAJADOR
    # ============================================
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
    
    # ============================================
    # TABLA NOMINA
    # ============================================
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
    
    # ============================================
    # TABLA CODIGOS_VERIFICACION
    # ============================================
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
    
    # ============================================
    # INSERTAR MÓDULOS
    # ============================================
    cursor.execute("SELECT COUNT(*) FROM modulos")
    if cursor.fetchone()[0] == 0:
        modulos = [
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
        cursor.executemany(
            'INSERT INTO modulos (nombre, descripcion, activo_global, tipo_requerido) VALUES (%s, %s, %s, %s)',
            modulos
        )
        print("✅ Módulos insertados")
    
    # ============================================
    # CREAR USUARIO ADMIN
    # ============================================
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'admin'")
    if cursor.fetchone()[0] == 0:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), salt).decode('utf-8')
        fecha = datetime.now().isoformat()
        cursor.execute('''
        INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado, verificado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1, 1)
        ''', ('admin', 'admin@aisa.com', password_hash, 'Administrador', 'admin', 'admin', fecha))
        
        admin_id = cursor.lastrowid
        cursor.execute("SELECT id FROM modulos")
        for mod in cursor.fetchall():
            cursor.execute('''
            INSERT INTO permisos_usuario (usuario_id, modulo_id, activo)
            VALUES (%s, %s, 1)
            ''', (admin_id, mod[0]))
        print("✅ Usuario admin creado (admin/admin123)")
    
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente")

# ============================================
# FUNCIONES DE USUARIOS
# ============================================

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def crear_usuario(username, email, password, nombre=None, rol='usuario', tipo='cliente', datos_negocio=None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        password_hash = hash_password(password)
        fecha = datetime.now().isoformat()
        
        if datos_negocio and isinstance(datos_negocio, dict):
            # Asegurar campos mínimos
            for key in ['provincia', 'municipio', 'nombre_negocio', 'ruc', 'telefono', 'direccion', 'descripcion', 'salario']:
                if key not in datos_negocio:
                    datos_negocio[key] = ''
            if 'salario' not in datos_negocio:
                datos_negocio['salario'] = 0
            datos_negocio = json.dumps(datos_negocio, ensure_ascii=False)
        elif datos_negocio and isinstance(datos_negocio, str):
            pass
        else:
            datos_negocio = None
        
        # Si es trabajador, se verifica automáticamente
        verificado = 1 if rol == 'trabajador' else 0
        aprobado = 1 if rol == 'trabajador' else 0
        
        cursor.execute('''
        INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado, verificado, datos_negocio)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
        RETURNING id
        ''', (username, email, password_hash, nombre, rol, tipo, fecha, aprobado, verificado, datos_negocio))
        
        user_id = cursor.fetchone()[0]
        
        # Si es admin, activar todo
        if rol == 'admin':
            cursor.execute('UPDATE usuarios SET verificado = 1, aprobado = 1 WHERE id = %s', (user_id,))
        
        # Asignar permisos según tipo
        if rol != 'trabajador':
            if tipo == 'negocio':
                cursor.execute('SELECT id FROM modulos WHERE tipo_requerido IN (%s, %s) AND activo_global = 1', ('ambos', 'negocio'))
            else:
                cursor.execute('SELECT id FROM modulos WHERE tipo_requerido IN (%s, %s) AND activo_global = 1', ('ambos', 'cliente'))
            
            for mod in cursor.fetchall():
                cursor.execute('''
                INSERT INTO permisos_usuario (usuario_id, modulo_id, activo)
                VALUES (%s, %s, 1)
                ''', (user_id, mod[0]))
        
        conn.commit()
        print(f"✅ Usuario creado: {username} (ID: {user_id}) - Tipo: {tipo} - Verificado: {verificado}")
        return user_id
        
    except Exception as e:
        print(f"❌ Error al crear usuario: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return None
    finally:
        conn.close()

def obtener_usuario_por_username(username):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM usuarios WHERE username = %s', (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def obtener_usuario_por_id(user_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM usuarios WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def obtener_todos_usuarios():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM usuarios ORDER BY id')
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def obtener_negocios():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT id, username, email, nombre, activo, fecha_registro, datos_negocio FROM usuarios WHERE tipo = %s', ('negocio',))
    negocios = cursor.fetchall()
    conn.close()
    return negocios

def eliminar_usuario(user_id):
    """Elimina un usuario y todos sus datos relacionados"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Verificar si el usuario existe
        cursor.execute("SELECT id, username, rol FROM usuarios WHERE id = %s", (user_id,))
        usuario = cursor.fetchone()
        if not usuario:
            print(f"⚠️ Usuario {user_id} no encontrado")
            conn.close()
            return False
        
        print(f"🗑️ Eliminando usuario: {usuario[1]} (ID: {user_id}) - Rol: {usuario[2]}")
        
        # ============================================
        # ELIMINAR EN ORDEN PARA RESPETAR FK
        # ============================================
        
        # 1. Eliminar códigos de verificación
        cursor.execute("DELETE FROM codigos_verificacion WHERE usuario_id = %s", (user_id,))
        print(f"   ✅ Códigos de verificación eliminados")
        
        # 2. Eliminar sesiones
        cursor.execute("DELETE FROM sesiones WHERE usuario_id = %s", (user_id,))
        print(f"   ✅ Sesiones eliminadas")
        
        # 3. Eliminar permisos
        cursor.execute("DELETE FROM permisos_usuario WHERE usuario_id = %s", (user_id,))
        print(f"   ✅ Permisos eliminados")
        
        # 4. Eliminar de trabajadores_negocio (si es trabajador o negocio)
        cursor.execute("DELETE FROM trabajadores_negocio WHERE trabajador_id = %s OR negocio_id = %s", (user_id, user_id))
        print(f"   ✅ Trabajadores_Negocio eliminados")
        
        # 5. Eliminar comisiones_trabajador
        cursor.execute("DELETE FROM comisiones_trabajador WHERE trabajador_id = %s OR negocio_id = %s", (user_id, user_id))
        print(f"   ✅ Comisiones eliminadas")
        
        # 6. Eliminar asistencia
        cursor.execute("DELETE FROM asistencia WHERE trabajador_id = %s OR negocio_id = %s", (user_id, user_id))
        print(f"   ✅ Asistencia eliminada")
        
        # 7. Eliminar nomina
        cursor.execute("DELETE FROM nomina WHERE trabajador_id = %s OR negocio_id = %s", (user_id, user_id))
        print(f"   ✅ Nómina eliminada")
        
        # 8. Eliminar contratos
        cursor.execute("DELETE FROM contratos WHERE negocio_id = %s OR trabajador_id = %s", (user_id, user_id))
        print(f"   ✅ Contratos eliminados")
        
        # 9. Eliminar productos_tienda
        cursor.execute("DELETE FROM productos_tienda WHERE negocio_id = %s", (user_id,))
        print(f"   ✅ Productos_Tienda eliminados")
        
        # 10. Eliminar productos
        cursor.execute("DELETE FROM productos WHERE negocio_id = %s", (user_id,))
        print(f"   ✅ Productos eliminados")
        
        # 11. Eliminar ventas
        cursor.execute("DELETE FROM ventas WHERE negocio_id = %s OR trabajador_id = %s", (user_id, user_id))
        print(f"   ✅ Ventas eliminadas")
        
        # 12. Eliminar servicios
        cursor.execute("DELETE FROM servicios WHERE negocio_id = %s OR trabajador_id = %s", (user_id, user_id))
        print(f"   ✅ Servicios eliminados")
        
        # 13. Eliminar logs
        cursor.execute("DELETE FROM logs WHERE usuario_id = %s", (user_id,))
        print(f"   ✅ Logs eliminados")
        
        # 14. Eliminar facturas_secuencia
        cursor.execute("DELETE FROM facturas_secuencia WHERE negocio_id = %s", (user_id,))
        print(f"   ✅ Facturas secuencia eliminadas")
        
        # 15. FINALMENTE eliminar el usuario
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
        print(f"   ✅ Usuario eliminado")
        
        conn.commit()
        conn.close()
        print(f"✅ Usuario {usuario[1]} (ID: {user_id}) eliminado correctamente")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Error SQL eliminando usuario {user_id}: {e}")
        conn.rollback()
        conn.close()
        return False
    except Exception as e:
        print(f"❌ Error eliminando usuario {user_id}: {e}")
        conn.rollback()
        conn.close()
        return False

def actualizar_ultimo_acceso(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET ultimo_acceso = %s WHERE id = %s',
                   (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def toggle_usuario(user_id, activo):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET activo = %s WHERE id = %s', (activo, user_id))
    conn.commit()
    conn.close()

def actualizar_rol_usuario(user_id, rol):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET rol = %s WHERE id = %s', (rol, user_id))
    conn.commit()
    conn.close()

def actualizar_tipo_usuario(user_id, tipo):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET tipo = %s WHERE id = %s', (tipo, user_id))
    conn.commit()
    conn.close()

def actualizar_datos_negocio(user_id, datos):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET datos_negocio = %s WHERE id = %s', (json.dumps(datos, ensure_ascii=False), user_id))
    conn.commit()
    conn.close()

def obtener_datos_negocio(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT datos_negocio FROM usuarios WHERE id = %s', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]:
        try:
            return json.loads(result[0])
        except:
            return {}
    return {}

def obtener_negocio_de_trabajador(trabajador_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT negocio_id FROM trabajadores_negocio 
            WHERE trabajador_id = %s AND activo = 1
        ''', (trabajador_id,))
        resultado = cursor.fetchone()
        conn.close()
        if resultado:
            return resultado[0]
        return None
    except Exception as e:
        print(f"❌ Error en obtener_negocio_de_trabajador: {e}")
        conn.close()
        return None

# ============================================
# FUNCIONES DE VERIFICACIÓN POR CORREO
# ============================================

def generar_codigo_verificacion():
    """Genera un código de 6 dígitos aleatorio"""
    return ''.join(random.choices(string.digits, k=6))

def guardar_codigo_verificacion(usuario_id, email, codigo):
    """Guarda un código de verificación en la base de datos"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        expira = (datetime.now() + timedelta(minutes=15)).isoformat()
        cursor.execute('''
            INSERT INTO codigos_verificacion (usuario_id, email, codigo, expira_en, usado)
            VALUES (%s, %s, %s, %s, 0)
        ''', (usuario_id, email, codigo, expira))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error guardando código de verificación: {e}")
        conn.rollback()
        conn.close()
        return False

def verificar_codigo(email, codigo):
    """Verifica si un código es válido y lo marca como usado"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT * FROM codigos_verificacion 
            WHERE email = %s AND codigo = %s AND usado = 0 AND expira_en > %s
            ORDER BY id DESC LIMIT 1
        ''', (email, codigo, datetime.now().isoformat()))
        registro = cursor.fetchone()
        
        if registro:
            # Marcar como usado
            cursor.execute('''
                UPDATE codigos_verificacion SET usado = 1 
                WHERE id = %s
            ''', (registro['id'],))
            conn.commit()
            conn.close()
            return registro
        conn.close()
        return None
    except Exception as e:
        print(f"❌ Error verificando código: {e}")
        conn.close()
        return None

def marcar_usuario_verificado(user_id):
    """Marca un usuario como verificado"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE usuarios SET verificado = 1, aprobado = 1
            WHERE id = %s
        ''', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error marcando usuario como verificado: {e}")
        conn.rollback()
        conn.close()
        return False

def obtener_codigos_pendientes(email):
    """Obtiene códigos pendientes para un email"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT * FROM codigos_verificacion 
            WHERE email = %s AND usado = 0 AND expira_en > %s
            ORDER BY id DESC
        ''', (email, datetime.now().isoformat()))
        registros = cursor.fetchall()
        conn.close()
        return registros
    except Exception as e:
        print(f"❌ Error obteniendo códigos pendientes: {e}")
        conn.close()
        return []

# ============================================
# FUNCIONES DE UBICACIÓN
# ============================================

def actualizar_ubicacion_usuario(user_id, latitud, longitud):
    """Actualiza la ubicación de un usuario en el mapa"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE usuarios 
            SET latitud = %s, longitud = %s, ubicacion_actualizada = %s
            WHERE id = %s
        ''', (latitud, longitud, datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error al actualizar ubicación: {e}")
        conn.rollback()
        conn.close()
        return False

def obtener_ubicacion_usuario(user_id):
    """Obtiene la ubicación de un usuario"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT latitud, longitud, ubicacion_actualizada, datos_negocio
        FROM usuarios 
        WHERE id = %s
    ''', (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado

def obtener_negocios_con_ubicacion(negocio_id=None):
    """Obtiene todos los negocios con ubicación registrada"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if negocio_id:
        cursor.execute('''
            SELECT id, username, nombre, latitud, longitud, datos_negocio, ubicacion_actualizada
            FROM usuarios 
            WHERE tipo = 'negocio' AND latitud IS NOT NULL AND longitud IS NOT NULL AND id = %s
        ''', (negocio_id,))
    else:
        cursor.execute('''
            SELECT id, username, nombre, latitud, longitud, datos_negocio, ubicacion_actualizada
            FROM usuarios 
            WHERE tipo = 'negocio' AND latitud IS NOT NULL AND longitud IS NOT NULL
            ORDER BY nombre ASC
        ''')
    
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
            'id': n['id'],
            'username': n['username'],
            'nombre': n['nombre'] or datos.get('nombre_negocio', n['username']),
            'latitud': float(n['latitud']) if n['latitud'] else None,
            'longitud': float(n['longitud']) if n['longitud'] else None,
            'direccion': datos.get('direccion', ''),
            'telefono': datos.get('telefono', ''),
            'descripcion': datos.get('descripcion', ''),
            'ubicacion_actualizada': n['ubicacion_actualizada']
        })
    
    return resultado

# ============================================
# FUNCIONES DE MÓDULOS
# ============================================

def obtener_modulos(tipo_usuario=None):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if tipo_usuario:
        cursor.execute('SELECT * FROM modulos WHERE tipo_requerido IN (%s, %s) ORDER BY nombre', ('ambos', tipo_usuario))
    else:
        cursor.execute('SELECT * FROM modulos ORDER BY nombre')
    modulos = cursor.fetchall()
    conn.close()
    return modulos

def obtener_permisos_usuario(user_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT m.id, m.nombre, m.descripcion, m.activo_global, m.tipo_requerido, 
           p.activo as permiso_activo, p.estado_solicitud
    FROM modulos m
    LEFT JOIN permisos_usuario p ON m.id = p.modulo_id AND p.usuario_id = %s
    ORDER BY m.nombre
    ''', (user_id,))
    permisos = cursor.fetchall()
    conn.close()
    return permisos

def asignar_permiso_usuario(user_id, modulo_id, activo):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
            VALUES (%s, %s, %s, 'aprobado')
            ON CONFLICT (usuario_id, modulo_id) DO UPDATE SET 
                activo = %s, 
                estado_solicitud = 'aprobado'
        ''', (user_id, modulo_id, activo, activo))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error en asignar_permiso_usuario: {e}")
        conn.rollback()
        conn.close()
        return False

def toggle_modulo_global(modulo_id, activo):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE modulos SET activo_global = %s WHERE id = %s', (activo, modulo_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error en toggle_modulo_global: {e}")
        conn.rollback()
        conn.close()
        return False

def solicitar_modulo(user_id, modulo_id):
    conn = get_db()
    cursor = conn.cursor()
    fecha = datetime.now().isoformat()
    cursor.execute('''
    INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud, fecha_solicitud)
    VALUES (%s, %s, 0, 'pendiente', %s)
    ON CONFLICT (usuario_id, modulo_id) DO UPDATE SET
        activo = 0, estado_solicitud = 'pendiente', fecha_solicitud = %s
    ''', (user_id, modulo_id, fecha, fecha))
    conn.commit()
    conn.close()

def obtener_solicitudes_pendientes():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT p.*, u.username, u.nombre, m.nombre as modulo_nombre
    FROM permisos_usuario p
    JOIN usuarios u ON p.usuario_id = u.id
    JOIN modulos m ON p.modulo_id = m.id
    WHERE p.estado_solicitud = 'pendiente'
    ORDER BY p.fecha_solicitud DESC
    ''')
    solicitudes = cursor.fetchall()
    conn.close()
    return solicitudes

def aprobar_solicitud(permiso_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE permisos_usuario SET activo = 1, estado_solicitud = %s WHERE id = %s',
                   ('aprobado', permiso_id))
    conn.commit()
    conn.close()

def rechazar_solicitud(permiso_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE permisos_usuario SET activo = 0, estado_solicitud = %s WHERE id = %s',
                   ('rechazado', permiso_id))
    conn.commit()
    conn.close()

# ============================================
# FUNCIONES DE LOGS
# ============================================

def registrar_log(usuario_id, accion, detalle=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO logs (usuario_id, accion, detalle, fecha) VALUES (%s, %s, %s, %s)',
                   (usuario_id, accion, detalle, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def obtener_logs(limit=50):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT l.*, u.username FROM logs l
    LEFT JOIN usuarios u ON l.usuario_id = u.id
    ORDER BY l.fecha DESC LIMIT %s
    ''', (limit,))
    logs = cursor.fetchall()
    conn.close()
    return logs

# ============================================
# FUNCIONES PARA PRODUCTOS
# ============================================

def crear_producto(negocio_id, nombre, categoria, precio, costo=0, comision=0, stock=0, stock_minimo=3):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO productos (negocio_id, nombre, categoria, precio, costo, comision, stock, stock_minimo, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (negocio_id, nombre, categoria, precio, costo, comision, stock, stock_minimo, datetime.now().isoformat()))
        conn.commit()
        producto_id = cursor.lastrowid
        conn.close()
        return producto_id
    except Exception as e:
        print(f"❌ Error al crear producto: {e}")
        conn.rollback()
        conn.close()
        return None

def obtener_productos(negocio_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM productos WHERE negocio_id = %s ORDER BY id DESC', (negocio_id,))
    productos = cursor.fetchall()
    conn.close()
    return productos

def obtener_todos_productos():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT p.*, u.username as negocio_username
    FROM productos p JOIN usuarios u ON p.negocio_id = u.id ORDER BY p.id DESC
    ''')
    productos = cursor.fetchall()
    conn.close()
    return productos

def obtener_productos_con_stock(negocio_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT id, nombre, precio, costo, comision, stock FROM productos WHERE negocio_id = %s AND stock > 0 ORDER BY nombre',
                   (negocio_id,))
    productos = cursor.fetchall()
    conn.close()
    return productos

def obtener_productos_tienda():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT p.id, p.nombre, p.categoria, p.precio, p.stock, p.foto_url
    FROM productos p JOIN usuarios u ON p.negocio_id = u.id
    WHERE u.tipo = 'negocio' AND u.activo = 1 AND p.stock > 0 ORDER BY p.id DESC
    ''')
    productos = cursor.fetchall()
    conn.close()
    return productos

def actualizar_producto(producto_id, nombre, categoria, precio, costo, comision, stock, stock_minimo):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        UPDATE productos 
        SET nombre = %s, categoria = %s, precio = %s, costo = %s, comision = %s,
        stock = %s, stock_minimo = %s, updated_at = %s 
        WHERE id = %s
        ''', (nombre, categoria, precio, costo, comision, stock, stock_minimo, datetime.now().isoformat(), producto_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error al actualizar producto: {e}")
        conn.rollback()
        conn.close()
        return False

def actualizar_foto_producto(producto_id, foto_url, foto_public_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE productos 
        SET foto_url = %s, foto_public_id = %s, updated_at = %s 
        WHERE id = %s
    ''', (foto_url, foto_public_id, datetime.now().isoformat(), producto_id))
    conn.commit()
    conn.close()

def eliminar_foto_producto(producto_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE productos 
        SET foto_url = NULL, foto_public_id = NULL, updated_at = %s 
        WHERE id = %s
    ''', (datetime.now().isoformat(), producto_id))
    conn.commit()
    conn.close()

def eliminar_producto(producto_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, nombre, negocio_id FROM productos WHERE id = %s', (producto_id,))
        producto = cursor.fetchone()
        if not producto:
            conn.close()
            return False
        
        cursor.execute('DELETE FROM productos_tienda WHERE producto_id = %s', (producto_id,))
        cursor.execute('DELETE FROM productos WHERE id = %s', (producto_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error eliminando producto {producto_id}: {e}")
        conn.rollback()
        conn.close()
        return False

def actualizar_stock_producto(producto_id, cantidad):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE productos SET stock = stock - %s, updated_at = %s WHERE id = %s AND stock >= %s
    ''', (cantidad, datetime.now().isoformat(), producto_id, cantidad))
    filas = cursor.rowcount
    conn.commit()
    conn.close()
    return filas > 0

def obtener_estadisticas_productos(negocio_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM productos WHERE negocio_id = %s', (negocio_id,))
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM productos WHERE negocio_id = %s AND stock > 0 AND stock <= stock_minimo', (negocio_id,))
    stock_bajo = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM productos WHERE negocio_id = %s AND stock = 0', (negocio_id,))
    agotados = cursor.fetchone()[0]
    
    cursor.execute('SELECT COALESCE(SUM(precio * stock), 0) FROM productos WHERE negocio_id = %s', (negocio_id,))
    valor_total = cursor.fetchone()[0]
    
    conn.close()
    return {'total': total, 'stock_bajo': stock_bajo, 'agotados': agotados, 'valor_total': valor_total}

# ============================================
# FUNCIONES PARA PRODUCTOS EN TIENDA
# ============================================

def agregar_producto_tienda(negocio_id, producto_id, destacado=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO productos_tienda (negocio_id, producto_id, destacado, created_at)
    VALUES (%s, %s, %s, %s)
    ''', (negocio_id, producto_id, destacado, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def obtener_productos_tienda_negocio(negocio_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT pt.id, p.nombre, p.precio, p.costo, p.comision, p.stock, p.foto_url, pt.destacado
    FROM productos_tienda pt
    JOIN productos p ON pt.producto_id = p.id
    WHERE pt.negocio_id = %s ORDER BY pt.id DESC
    ''', (negocio_id,))
    productos = cursor.fetchall()
    conn.close()
    return productos

def toggle_destacado_tienda(producto_tienda_id, destacado):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE productos_tienda SET destacado = %s WHERE id = %s', (destacado, producto_tienda_id))
    conn.commit()
    conn.close()

def eliminar_producto_tienda(producto_tienda_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM productos_tienda WHERE id = %s', (producto_tienda_id,))
    conn.commit()
    conn.close()

# ============================================
# FUNCIONES PARA TRABAJADORES
# ============================================

def obtener_trabajadores_por_empresa(empresa_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.nombre, u.activo, 
                   u.datos_negocio, u.fecha_registro,
                   tn.cargo, tn.salario, tn.fecha_contratacion
            FROM trabajadores_negocio tn
            JOIN usuarios u ON tn.trabajador_id = u.id
            WHERE tn.negocio_id = %s AND tn.activo = 1 AND u.activo = 1
            ORDER BY u.nombre ASC
        ''', (empresa_id,))
        trabajadores = cursor.fetchall()
        conn.close()
        return trabajadores
    except Exception as e:
        print(f"❌ Error en obtener_trabajadores_por_empresa: {e}")
        conn.close()
        return []

def obtener_trabajador_por_id(user_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT u.id, u.username, u.email, u.nombre, u.activo, 
           u.datos_negocio, u.fecha_registro,
           STRING_AGG(m.nombre, ',') as modulos
    FROM usuarios u
    LEFT JOIN permisos_usuario p ON u.id = p.usuario_id
    LEFT JOIN modulos m ON p.modulo_id = m.id AND p.activo = 1
    WHERE u.id = %s AND u.rol = 'trabajador'
    GROUP BY u.id
    ''', (user_id,))
    trabajador = cursor.fetchone()
    conn.close()
    return trabajador

def crear_trabajador_negocio(negocio_id, trabajador_id, cargo, salario):
    conn = get_db()
    cursor = conn.cursor()
    fecha = datetime.now().isoformat()
    cursor.execute('''
    INSERT INTO trabajadores_negocio (negocio_id, trabajador_id, cargo, salario, fecha_contratacion, activo)
    VALUES (%s, %s, %s, %s, %s, 1)
    ON CONFLICT (negocio_id, trabajador_id) DO UPDATE SET
        cargo = EXCLUDED.cargo, salario = EXCLUDED.salario,
        fecha_contratacion = EXCLUDED.fecha_contratacion, activo = 1
    ''', (negocio_id, trabajador_id, cargo, salario, fecha))
    conn.commit()
    conn.close()

def toggle_trabajador_negocio(negocio_id, trabajador_id, activo):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE trabajadores_negocio SET activo = %s WHERE negocio_id = %s AND trabajador_id = %s',
                   (activo, negocio_id, trabajador_id))
    conn.commit()
    conn.close()

def actualizar_trabajador_negocio(negocio_id, trabajador_id, cargo, salario):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE trabajadores_negocio SET cargo = %s, salario = %s WHERE negocio_id = %s AND trabajador_id = %s',
                   (cargo, salario, negocio_id, trabajador_id))
    conn.commit()
    conn.close()

def obtener_trabajadores_pendientes():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT id, username, email, nombre, fecha_registro
    FROM usuarios WHERE rol = 'trabajador' AND aprobado = 0 AND activo = 1
    ORDER BY fecha_registro DESC
    ''')
    trabajadores = cursor.fetchall()
    conn.close()
    return trabajadores

def aprobar_trabajador(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET aprobado = 1 WHERE id = %s', (user_id,))
    conn.commit()
    conn.close()

def rechazar_trabajador(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET activo = 0 WHERE id = %s', (user_id,))
    conn.commit()
    conn.close()

# ============================================
# FUNCIONES PARA VENTAS
# ============================================

def crear_venta(negocio_id, trabajador_id, cliente, producto, producto_id, cantidad, precio, total,
                estado='pagado', empresa=None, tipo='producto', factura_url=None,
                factura=None, transferencia_id=None, transferencia_cedula=None,
                transferencia_banco=None, transferencia_fecha=None):
    conn = get_db()
    cursor = conn.cursor()
    fecha = datetime.now().isoformat()
    cursor.execute('''
    INSERT INTO ventas (negocio_id, trabajador_id, cliente, producto, producto_id,
                        cantidad, precio, total, estado, empresa, tipo, factura_url,
                        factura, transferencia_id, transferencia_cedula,
                        transferencia_banco, transferencia_fecha, fecha, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (negocio_id, trabajador_id, cliente, producto, producto_id,
          cantidad, precio, total, estado, empresa, tipo, factura_url,
          factura, transferencia_id, transferencia_cedula,
          transferencia_banco, transferencia_fecha, fecha, fecha))
    conn.commit()
    venta_id = cursor.lastrowid
    conn.close()
    return venta_id

def obtener_ventas(negocio_id, trabajador_id=None):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if trabajador_id:
        cursor.execute('''
        SELECT id, cliente, producto, cantidad, total, fecha, estado, 
               trabajador_id, producto_id, empresa, tipo, factura_url,
               factura, transferencia_id, transferencia_cedula,
               transferencia_banco, transferencia_fecha
        FROM ventas 
        WHERE negocio_id = %s AND trabajador_id = %s 
        ORDER BY id DESC
        ''', (negocio_id, trabajador_id))
    else:
        cursor.execute('''
        SELECT id, cliente, producto, cantidad, total, fecha, estado, 
               trabajador_id, producto_id, empresa, tipo, factura_url,
               factura, transferencia_id, transferencia_cedula,
               transferencia_banco, transferencia_fecha
        FROM ventas 
        WHERE negocio_id = %s 
        ORDER BY id DESC
        ''', (negocio_id,))
    ventas = cursor.fetchall()
    conn.close()
    return ventas

def obtener_todas_ventas():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT v.*, u.username as negocio_username
    FROM ventas v JOIN usuarios u ON v.negocio_id = u.id ORDER BY v.id DESC
    ''')
    ventas = cursor.fetchall()
    conn.close()
    return ventas

def obtener_estadisticas_ventas(negocio_id, trabajador_id=None):
    conn = get_db()
    cursor = conn.cursor()
    hoy = datetime.now().date().isoformat()
    if trabajador_id:
        cursor.execute('''
        SELECT COUNT(*) as total, COALESCE(SUM(total), 0) as ingresos
        FROM ventas WHERE negocio_id = %s AND trabajador_id = %s AND fecha = %s
        ''', (negocio_id, trabajador_id, hoy))
    else:
        cursor.execute('''
        SELECT COUNT(*) as total, COALESCE(SUM(total), 0) as ingresos
        FROM ventas WHERE negocio_id = %s AND fecha = %s
        ''', (negocio_id, hoy))
    stats = cursor.fetchone()
    conn.close()
    return stats

def actualizar_estado_venta(venta_id, negocio_id, estado):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE ventas SET estado = %s
    WHERE id = %s AND negocio_id = %s
    ''', (estado, venta_id, negocio_id))
    filas = cursor.rowcount
    conn.commit()
    conn.close()
    return filas > 0

def eliminar_venta_con_reintegro(venta_id, negocio_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT producto_id, cantidad, total, cliente, producto, fecha, empresa, tipo, 
                   factura_url, factura, transferencia_id, transferencia_cedula, 
                   transferencia_banco, transferencia_fecha
            FROM ventas 
            WHERE id = %s AND negocio_id = %s
        ''', (venta_id, negocio_id))
        venta = cursor.fetchone()
        if not venta:
            conn.close()
            return False, "Venta no encontrada"
        
        producto_id = venta[0]
        cantidad = venta[1]
        
        if producto_id:
            cursor.execute('''
                UPDATE productos 
                SET stock = stock + %s, updated_at = %s 
                WHERE id = %s
            ''', (cantidad, datetime.now().isoformat(), producto_id))
            if cursor.rowcount == 0:
                conn.rollback()
                conn.close()
                return False, "Error al actualizar el stock"
        
        cursor.execute('DELETE FROM ventas WHERE id = %s AND negocio_id = %s', (venta_id, negocio_id))
        conn.commit()
        conn.close()
        return True, {'producto_id': producto_id, 'cantidad': cantidad}
    except Exception as e:
        print(f"❌ Error eliminando venta: {e}")
        conn.rollback()
        conn.close()
        return False, str(e)

# ============================================
# FUNCIONES PARA SERVICIOS
# ============================================

def crear_servicio(negocio_id, trabajador_id, nombre, categoria, precio, duracion, activo=1, descripcion=''):
    conn = get_db()
    cursor = conn.cursor()
    fecha = datetime.now().isoformat()
    cursor.execute('''
    INSERT INTO servicios (negocio_id, trabajador_id, nombre, categoria, precio, duracion, activo, descripcion, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (negocio_id, trabajador_id, nombre, categoria, precio, duracion, activo, descripcion, fecha))
    conn.commit()
    servicio_id = cursor.lastrowid
    conn.close()
    return servicio_id

def obtener_servicios(negocio_id, trabajador_id=None):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if trabajador_id:
            cursor.execute('''
                SELECT * FROM servicios 
                WHERE negocio_id = %s AND trabajador_id = %s AND activo = 1
                ORDER BY id DESC
            ''', (negocio_id, trabajador_id))
        else:
            cursor.execute('''
                SELECT * FROM servicios 
                WHERE negocio_id = %s AND activo = 1
                ORDER BY id DESC
            ''', (negocio_id,))
        servicios = cursor.fetchall()
        conn.close()
        return servicios
    except Exception as e:
        print(f"❌ Error en obtener_servicios: {e}")
        conn.close()
        return []

def obtener_todos_servicios():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT s.*, u.username as negocio_username
    FROM servicios s JOIN usuarios u ON s.negocio_id = u.id ORDER BY s.id DESC
    ''')
    servicios = cursor.fetchall()
    conn.close()
    return servicios

def toggle_servicio(servicio_id, activo):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE servicios SET activo = %s, updated_at = %s WHERE id = %s',
                   (activo, datetime.now().isoformat(), servicio_id))
    conn.commit()
    conn.close()

def eliminar_servicio(servicio_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM servicios WHERE id = %s', (servicio_id,))
    conn.commit()
    conn.close()

# ============================================
# FUNCIONES PARA ESTADÍSTICAS DE TRABAJADORES
# ============================================

def obtener_estadisticas_trabajador(trabajador_id):
    conn = get_db()
    cursor = conn.cursor()
    hoy = datetime.now().date().isoformat()
    cursor.execute('SELECT COUNT(*) as ventas, COALESCE(SUM(total), 0) as ingresos FROM ventas WHERE trabajador_id = %s AND fecha = %s',
                   (trabajador_id, hoy))
    ventas = cursor.fetchone()
    cursor.execute('SELECT COUNT(*) as servicios FROM servicios WHERE trabajador_id = %s AND activo = 1', (trabajador_id,))
    servicios = cursor.fetchone()
    cursor.execute('SELECT COUNT(DISTINCT cliente) as clientes FROM ventas WHERE trabajador_id = %s AND fecha = %s',
                   (trabajador_id, hoy))
    clientes = cursor.fetchone()
    conn.close()
    return {
        'ventas': ventas[0] if ventas else 0,
        'ingresos': ventas[1] if ventas else 0,
        'servicios': servicios[0] if servicios else 0,
        'clientes': clientes[0] if clientes else 0
    }

# ============================================
# FUNCIONES PARA CONTRATOS
# ============================================

def obtener_ultimo_numero_contrato(negocio_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT numero_contrato FROM contratos WHERE negocio_id = %s ORDER BY id DESC LIMIT 1', (negocio_id,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        partes = resultado[0].split('-')
        if len(partes) == 3:
            try:
                return int(partes[2])
            except ValueError:
                return 0
    return 0

def crear_contrato(negocio_id, trabajador_id, empresa, numero_contrato, fecha_inicio, fecha_fin,
                   tipo, monto=0, estado='activo', descripcion=''):
    conn = get_db()
    cursor = conn.cursor()
    fecha = datetime.now().isoformat()
    cursor.execute('''
    INSERT INTO contratos (negocio_id, trabajador_id, empresa, numero_contrato, fecha_inicio, fecha_fin,
                           tipo, monto, estado, descripcion, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (negocio_id, trabajador_id, empresa, numero_contrato, fecha_inicio, fecha_fin,
          tipo, monto, estado, descripcion, fecha))
    conn.commit()
    contrato_id = cursor.lastrowid
    conn.close()
    return contrato_id

def obtener_contratos(negocio_id, trabajador_id=None):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if trabajador_id:
        cursor.execute('''
        SELECT c.*, u.nombre as trabajador_nombre
        FROM contratos c LEFT JOIN usuarios u ON c.trabajador_id = u.id
        WHERE c.negocio_id = %s AND c.trabajador_id = %s ORDER BY c.id DESC
        ''', (negocio_id, trabajador_id))
    else:
        cursor.execute('''
        SELECT c.*, u.nombre as trabajador_nombre
        FROM contratos c LEFT JOIN usuarios u ON c.trabajador_id = u.id
        WHERE c.negocio_id = %s ORDER BY c.id DESC
        ''', (negocio_id,))
    contratos = cursor.fetchall()
    conn.close()
    return contratos

def obtener_todos_contratos():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
    SELECT c.*, u.nombre as trabajador_nombre, u2.username as negocio_username
    FROM contratos c
    JOIN usuarios u2 ON c.negocio_id = u2.id
    LEFT JOIN usuarios u ON c.trabajador_id = u.id
    ORDER BY c.id DESC
    ''')
    contratos = cursor.fetchall()
    conn.close()
    return contratos

def actualizar_contrato(contrato_id, empresa, fecha_inicio, fecha_fin, tipo, monto, estado, descripcion):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE contratos SET empresa = %s, fecha_inicio = %s, fecha_fin = %s, tipo = %s, monto = %s,
    estado = %s, descripcion = %s, updated_at = %s WHERE id = %s
    ''', (empresa, fecha_inicio, fecha_fin, tipo, monto, estado, descripcion, datetime.now().isoformat(), contrato_id))
    conn.commit()
    conn.close()

def actualizar_estado_contrato(contrato_id, estado):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE contratos SET estado = %s, updated_at = %s WHERE id = %s',
                   (estado, datetime.now().isoformat(), contrato_id))
    conn.commit()
    conn.close()

def eliminar_contrato(contrato_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM contratos WHERE id = %s', (contrato_id,))
    conn.commit()
    conn.close()

# ============================================
# FUNCIONES PARA NÓMINA Y ASISTENCIA
# ============================================

def registrar_asistencia(trabajador_id, negocio_id, fecha, presente=1, horas=8):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO asistencia (trabajador_id, negocio_id, fecha, presente, horas_trabajadas, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (trabajador_id, fecha) DO UPDATE SET
            presente = EXCLUDED.presente,
            horas_trabajadas = EXCLUDED.horas_trabajadas
        ''', (trabajador_id, negocio_id, fecha, presente, horas, datetime.now()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error al registrar asistencia: {e}")
        conn.rollback()
        conn.close()
        return False

def obtener_asistencia_mes(trabajador_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT * FROM asistencia 
            WHERE trabajador_id = %s 
            AND EXTRACT(MONTH FROM fecha) = %s
            AND EXTRACT(YEAR FROM fecha) = %s
            ORDER BY fecha ASC
        ''', (trabajador_id, mes, ano))
        asistencias = cursor.fetchall()
        conn.close()
        return asistencias
    except Exception as e:
        print(f"❌ Error en obtener_asistencia_mes: {e}")
        conn.close()
        return []

def obtener_dias_trabajados_mes(trabajador_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT COUNT(*) FROM asistencia 
            WHERE trabajador_id = %s 
            AND EXTRACT(MONTH FROM fecha) = %s
            AND EXTRACT(YEAR FROM fecha) = %s
            AND presente = 1
        ''', (trabajador_id, mes, ano))
        dias = cursor.fetchone()[0]
        conn.close()
        return dias
    except Exception as e:
        print(f"❌ Error en obtener_dias_trabajados_mes: {e}")
        conn.close()
        return 0

def obtener_dias_ausencia_mes(trabajador_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT COUNT(*) FROM asistencia 
            WHERE trabajador_id = %s 
            AND EXTRACT(MONTH FROM fecha) = %s
            AND EXTRACT(YEAR FROM fecha) = %s
            AND presente = 0
        ''', (trabajador_id, mes, ano))
        dias = cursor.fetchone()[0]
        conn.close()
        return dias
    except Exception as e:
        print(f"❌ Error en obtener_dias_ausencia_mes: {e}")
        conn.close()
        return 0

def obtener_dias_extras_mes(trabajador_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT COUNT(*) FROM asistencia 
            WHERE trabajador_id = %s 
            AND EXTRACT(MONTH FROM fecha) = %s
            AND EXTRACT(YEAR FROM fecha) = %s
            AND horas_trabajadas > 8
        ''', (trabajador_id, mes, ano))
        dias = cursor.fetchone()[0]
        conn.close()
        return dias
    except Exception as e:
        print(f"❌ Error en obtener_dias_extras_mes: {e}")
        conn.close()
        return 0

def registrar_comision(negocio_id, trabajador_id, venta_id, producto_id, monto):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO comisiones_trabajador (negocio_id, trabajador_id, venta_id, producto_id, monto, fecha, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (negocio_id, trabajador_id, venta_id, producto_id, monto, datetime.now().date(), datetime.now()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error al registrar comisión: {e}")
        conn.rollback()
        conn.close()
        return False

def obtener_comisiones_trabajador_mes(trabajador_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT c.*, p.nombre as producto_nombre, v.cliente, v.fecha as venta_fecha
            FROM comisiones_trabajador c
            LEFT JOIN productos p ON c.producto_id = p.id
            LEFT JOIN ventas v ON c.venta_id = v.id
            WHERE c.trabajador_id = %s 
            AND EXTRACT(MONTH FROM c.fecha) = %s
            AND EXTRACT(YEAR FROM c.fecha) = %s
            ORDER BY c.fecha DESC
        ''', (trabajador_id, mes, ano))
        comisiones = cursor.fetchall()
        conn.close()
        return comisiones
    except Exception as e:
        print(f"❌ Error en obtener_comisiones_trabajador_mes: {e}")
        conn.close()
        return []

def obtener_total_comisiones_mes(trabajador_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT COALESCE(SUM(monto), 0) FROM comisiones_trabajador 
            WHERE trabajador_id = %s 
            AND EXTRACT(MONTH FROM fecha) = %s
            AND EXTRACT(YEAR FROM fecha) = %s
        ''', (trabajador_id, mes, ano))
        total = cursor.fetchone()[0]
        conn.close()
        return float(total) if total else 0
    except Exception as e:
        print(f"❌ Error en obtener_total_comisiones_mes: {e}")
        conn.close()
        return 0

def obtener_comisiones_negocio_mes(negocio_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT c.*, u.nombre as trabajador_nombre, p.nombre as producto_nombre, v.cliente
        FROM comisiones_trabajador c
        JOIN usuarios u ON c.trabajador_id = u.id
        LEFT JOIN productos p ON c.producto_id = p.id
        LEFT JOIN ventas v ON c.venta_id = v.id
        WHERE c.negocio_id = %s 
        AND EXTRACT(MONTH FROM c.fecha) = %s
        AND EXTRACT(YEAR FROM c.fecha) = %s
        ORDER BY u.nombre ASC, c.fecha DESC
    ''', (negocio_id, mes, ano))
    comisiones = cursor.fetchall()
    conn.close()
    return comisiones

def calcular_nomina(negocio_id, trabajador_id, mes, ano):
    try:
        _, dias_mes = monthrange(ano, mes)
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT u.id, u.nombre, u.datos_negocio
            FROM usuarios u WHERE u.id = %s
        ''', (trabajador_id,))
        trabajador = cursor.fetchone()
        if not trabajador:
            conn.close()
            return None
        
        datos = {}
        if trabajador['datos_negocio']:
            try:
                datos = json.loads(trabajador['datos_negocio']) if isinstance(trabajador['datos_negocio'], str) else trabajador['datos_negocio']
            except:
                datos = {}
        salario_base = datos.get('salario', 0)
        if salario_base == 0:
            conn.close()
            return None
        
        dias_trabajados = obtener_dias_trabajados_mes(trabajador_id, mes, ano)
        dias_ausencia = obtener_dias_ausencia_mes(trabajador_id, mes, ano)
        dias_extras = obtener_dias_extras_mes(trabajador_id, mes, ano)
        
        if dias_trabajados == 0:
            # Estimar días laborables
            for d in range(1, dias_mes + 1):
                fecha = datetime(ano, mes, d)
                if fecha.weekday() < 5:
                    dias_trabajados += 1
        
        salario_diario = salario_base / dias_mes if dias_mes > 0 else 0
        salario_devengado = salario_diario * dias_trabajados
        comisiones = obtener_total_comisiones_mes(trabajador_id, mes, ano)
        total = salario_devengado + comisiones
        
        # Guardar en tabla nomina
        cursor.execute('''
            SELECT id FROM nomina 
            WHERE negocio_id = %s AND trabajador_id = %s AND mes = %s AND ano = %s
        ''', (negocio_id, trabajador_id, mes, ano))
        existe = cursor.fetchone()
        
        if existe:
            cursor.execute('''
                UPDATE nomina SET
                    salario_base = %s, dias_trabajados = %s, dias_ausencia = %s,
                    dias_extras = %s, salario_devengado = %s, comisiones = %s,
                    total = %s, actualizado_en = %s
                WHERE id = %s
            ''', (salario_base, dias_trabajados, dias_ausencia, dias_extras,
                  salario_devengado, comisiones, total, datetime.now(), existe['id']))
        else:
            cursor.execute('''
                INSERT INTO nomina (negocio_id, trabajador_id, mes, ano, salario_base,
                    dias_trabajados, dias_ausencia, dias_extras, salario_devengado,
                    comisiones, total, creado_en)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (negocio_id, trabajador_id, mes, ano, salario_base,
                  dias_trabajados, dias_ausencia, dias_extras, salario_devengado,
                  comisiones, total, datetime.now()))
        
        conn.commit()
        conn.close()
        return {
            'trabajador_id': trabajador_id,
            'nombre': trabajador['nombre'],
            'salario_base': salario_base,
            'dias_mes': dias_mes,
            'dias_trabajados': dias_trabajados,
            'dias_ausencia': dias_ausencia,
            'dias_extras': dias_extras,
            'salario_diario': salario_diario,
            'salario_devengado': salario_devengado,
            'comisiones': comisiones,
            'total': total
        }
    except Exception as e:
        print(f"❌ Error en calcular_nomina: {e}")
        return None

def obtener_nomina_mes(negocio_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT n.*, u.nombre, u.datos_negocio
            FROM nomina n
            JOIN usuarios u ON n.trabajador_id = u.id
            WHERE n.negocio_id = %s AND n.mes = %s AND n.ano = %s
            ORDER BY u.nombre ASC
        ''', (negocio_id, mes, ano))
        nomina = cursor.fetchall()
        conn.close()
        return nomina
    except Exception as e:
        print(f"❌ Error en obtener_nomina_mes: {e}")
        conn.close()
        return []

def obtener_nomina_trabajador(trabajador_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT n.*, u.nombre, u.datos_negocio
            FROM nomina n
            JOIN usuarios u ON n.trabajador_id = u.id
            WHERE n.trabajador_id = %s AND n.mes = %s AND n.ano = %s
        ''', (trabajador_id, mes, ano))
        nomina = cursor.fetchone()
        conn.close()
        return nomina
    except Exception as e:
        print(f"❌ Error en obtener_nomina_trabajador: {e}")
        conn.close()
        return None

def obtener_resumen_nomina(negocio_id, mes, ano):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trabajadores,
                COALESCE(SUM(dias_trabajados), 0) as total_dias_trabajados,
                COALESCE(SUM(dias_ausencia), 0) as total_ausencias,
                COALESCE(SUM(salario_devengado), 0) as total_salarios,
                COALESCE(SUM(comisiones), 0) as total_comisiones,
                COALESCE(SUM(total), 0) as total_nomina
            FROM nomina
            WHERE negocio_id = %s AND mes = %s AND ano = %s
        ''', (negocio_id, mes, ano))
        resultado = cursor.fetchone()
        conn.close()
        return {
            'total_trabajadores': resultado[0] or 0,
            'total_dias_trabajados': resultado[1] or 0,
            'total_ausencias': resultado[2] or 0,
            'total_salarios': resultado[3] or 0,
            'total_comisiones': resultado[4] or 0,
            'total_nomina': resultado[5] or 0
        }
    except Exception as e:
        print(f"❌ Error en obtener_resumen_nomina: {e}")
        conn.close()
        return {
            'total_trabajadores': 0,
            'total_dias_trabajados': 0,
            'total_ausencias': 0,
            'total_salarios': 0,
            'total_comisiones': 0,
            'total_nomina': 0
        }

# ============================================
# FUNCIONES PARA SECUENCIA DE FACTURAS
# ============================================

def obtener_ultimo_numero_factura(negocio_id, empresa):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT ultimo_numero FROM facturas_secuencia 
            WHERE negocio_id = %s AND empresa = %s
        ''', (negocio_id, empresa))
        resultado = cursor.fetchone()
        conn.close()
        if resultado:
            return resultado[0]
        return 0
    except Exception as e:
        print(f"❌ Error en obtener_ultimo_numero_factura: {e}")
        conn.close()
        return 0

def actualizar_ultimo_numero_factura(negocio_id, empresa, numero):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO facturas_secuencia (negocio_id, empresa, ultimo_numero, created_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (negocio_id, empresa) DO UPDATE SET 
                ultimo_numero = EXCLUDED.ultimo_numero,
                updated_at = %s
        ''', (negocio_id, empresa, numero, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error en actualizar_ultimo_numero_factura: {e}")
        conn.rollback()
        conn.close()
        return False

def generar_numero_factura(negocio_id, empresa, año=None):
    if not año:
        año = datetime.now().year
    ultimo = obtener_ultimo_numero_factura(negocio_id, empresa)
    nuevo = ultimo + 1
    actualizar_ultimo_numero_factura(negocio_id, empresa, nuevo)
    return f"FAC-{año}-{str(nuevo).zfill(4)}"

# ============================================
# FUNCIONES ADICIONALES PARA MÓDULOS
# ============================================

def obtener_modulos_negocio():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT * FROM modulos 
        WHERE tipo_requerido IN ('ambos', 'negocio') AND activo_global = 1
        ORDER BY nombre
    ''')
    modulos = cursor.fetchall()
    conn.close()
    return modulos

def obtener_modulos_trabajador():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT * FROM modulos 
        WHERE tipo_requerido IN ('ambos', 'negocio') AND activo_global = 1
        ORDER BY nombre
    ''')
    modulos = cursor.fetchall()
    conn.close()
    return modulos
