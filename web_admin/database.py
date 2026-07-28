import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import bcrypt
import json
import urllib.parse

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
    """Inicializa la base de datos con PostgreSQL (SERIAL)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return
    
    # TABLAS CON SERIAL (PostgreSQL) - CON ON DELETE CASCADE
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
        fecha_registro TEXT NOT NULL,
        ultimo_acceso TEXT,
        datos_negocio TEXT
    )
    ''')
    
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
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS modulos (
        id SERIAL PRIMARY KEY,
        nombre TEXT UNIQUE NOT NULL,
        descripcion TEXT,
        activo_global INTEGER DEFAULT 1,
        tipo_requerido TEXT DEFAULT 'ambos'
    )
    ''')
    
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
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS productos (
        id SERIAL PRIMARY KEY,
        negocio_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        categoria TEXT,
        precio REAL NOT NULL,
        stock INTEGER DEFAULT 0,
        stock_minimo INTEGER DEFAULT 3,
        foto_url TEXT,
        foto_public_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (negocio_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )
    ''')
    
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
    
    # Insertar módulos
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
        ]
        cursor.executemany(
            'INSERT INTO modulos (nombre, descripcion, activo_global, tipo_requerido) VALUES (%s, %s, %s, %s)',
            modulos
        )
        print("✅ Módulos insertados")
    
    # Crear usuario admin
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'admin'")
    if cursor.fetchone()[0] == 0:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), salt).decode('utf-8')
        fecha = datetime.now().isoformat()
        cursor.execute('''
        INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1)
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
            datos_negocio = json.dumps(datos_negocio)
        elif datos_negocio and isinstance(datos_negocio, str):
            pass
        else:
            datos_negocio = None
        
        cursor.execute('''
        INSERT INTO usuarios (username, email, password_hash, nombre, rol, tipo, fecha_registro, activo, aprobado, datos_negocio)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1, %s)
        RETURNING id
        ''', (username, email, password_hash, nombre, rol, tipo, fecha, datos_negocio))
        
        user_id = cursor.fetchone()[0]
        
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
        print(f"✅ Usuario creado: {username} (ID: {user_id})")
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
    cursor.execute('SELECT id, username, email, nombre, activo, fecha_registro FROM usuarios WHERE tipo = %s', ('negocio',))
    negocios = cursor.fetchall()
    conn.close()
    return negocios

def eliminar_usuario(user_id):
    """Elimina un usuario y todos sus datos relacionados (ON DELETE CASCADE lo hará automáticamente)"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM usuarios WHERE id = %s', (user_id,))
        conn.commit()
        conn.close()
        return True
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
    cursor.execute('UPDATE usuarios SET datos_negocio = %s WHERE id = %s', (json.dumps(datos), user_id))
    conn.commit()
    conn.close()

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
    cursor.execute('''
    INSERT INTO permisos_usuario (usuario_id, modulo_id, activo, estado_solicitud)
    VALUES (%s, %s, %s, 'aprobado')
    ON CONFLICT (usuario_id, modulo_id) DO UPDATE SET activo = %s, estado_solicitud = 'aprobado'
    ''', (user_id, modulo_id, activo, activo))
    conn.commit()
    conn.close()

def toggle_modulo_global(modulo_id, activo):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE modulos SET activo_global = %s WHERE id = %s', (activo, modulo_id))
    conn.commit()
    conn.close()

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

def crear_producto(negocio_id, nombre, categoria, precio, stock, stock_minimo=3):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO productos (negocio_id, nombre, categoria, precio, stock, stock_minimo, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (negocio_id, nombre, categoria, precio, stock, stock_minimo, datetime.now().isoformat()))
    conn.commit()
    producto_id = cursor.lastrowid
    conn.close()
    return producto_id

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
    cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE negocio_id = %s AND stock > 0 ORDER BY nombre',
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

def actualizar_producto(producto_id, nombre, categoria, precio, stock, stock_minimo):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE productos SET nombre = %s, categoria = %s, precio = %s, stock = %s,
    stock_minimo = %s, updated_at = %s WHERE id = %s
    ''', (nombre, categoria, precio, stock, stock_minimo, datetime.now().isoformat(), producto_id))
    conn.commit()
    conn.close()

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

def obtener_foto_producto(producto_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT foto_url, foto_public_id FROM productos WHERE id = %s', (producto_id,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return {'url': resultado[0], 'public_id': resultado[1]}
    return {'url': None, 'public_id': None}

def eliminar_producto(producto_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id, nombre, negocio_id FROM productos WHERE id = %s', (producto_id,))
        producto = cursor.fetchone()
        
        if not producto:
            conn.close()
            print(f"⚠️ Producto {producto_id} no encontrado")
            return False
        
        print(f"🗑️ Eliminando producto: {producto[1]} (ID: {producto_id})")
        
        cursor.execute('SELECT id FROM productos_tienda WHERE producto_id = %s', (producto_id,))
        tienda = cursor.fetchone()
        if tienda:
            print(f"⚠️ Eliminando referencia en productos_tienda para producto {producto_id}")
            cursor.execute('DELETE FROM productos_tienda WHERE producto_id = %s', (producto_id,))
        
        cursor.execute('SELECT id FROM ventas WHERE producto_id = %s LIMIT 1', (producto_id,))
        venta = cursor.fetchone()
        if venta:
            print(f"⚠️ El producto {producto_id} tiene ventas asociadas. No se puede eliminar.")
            conn.close()
            return False
        
        cursor.execute('DELETE FROM productos WHERE id = %s', (producto_id,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✅ Producto {producto_id} eliminado correctamente")
            conn.close()
            return True
        else:
            conn.rollback()
            conn.close()
            print(f"❌ No se eliminó ningún producto (rowcount=0)")
            return False
            
    except psycopg2.Error as e:
        print(f"❌ Error SQL en eliminar_producto: {e}")
        conn.rollback()
        conn.close()
        return False
    except Exception as e:
        print(f"❌ Error inesperado en eliminar_producto: {e}")
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
    SELECT pt.id, p.nombre, p.precio, p.stock, p.foto_url, pt.destacado
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
    cursor.execute('''
    SELECT u.id, u.username, u.email, u.nombre, u.activo, 
           u.datos_negocio, u.fecha_registro,
           tn.cargo, tn.salario, tn.fecha_contratacion,
           STRING_AGG(m.nombre, ',') as modulos
    FROM trabajadores_negocio tn
    JOIN usuarios u ON tn.trabajador_id = u.id
    LEFT JOIN permisos_usuario p ON u.id = p.usuario_id
    LEFT JOIN modulos m ON p.modulo_id = m.id AND p.activo = 1
    WHERE tn.negocio_id = %s AND tn.activo = 1
    GROUP BY u.id, tn.cargo, tn.salario, tn.fecha_contratacion
    ORDER BY u.id DESC
    ''', (empresa_id,))
    trabajadores = cursor.fetchall()
    conn.close()
    return trabajadores

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
    """Elimina una venta y reintegra el stock del producto"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Obtener datos de la venta
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
        
        # 2. Si tiene producto, reintegrar stock
        if producto_id:
            cursor.execute('''
                UPDATE productos 
                SET stock = stock + %s, updated_at = %s 
                WHERE id = %s
            ''', (cantidad, datetime.now().isoformat(), producto_id))
            
            # Verificar que se actualizó el stock
            if cursor.rowcount == 0:
                conn.rollback()
                conn.close()
                return False, "Error al actualizar el stock del producto"
        
        # 3. Eliminar la venta
        cursor.execute('DELETE FROM ventas WHERE id = %s AND negocio_id = %s', (venta_id, negocio_id))
        
        # Verificar que se eliminó
        if cursor.rowcount == 0:
            conn.rollback()
            conn.close()
            return False, "Error al eliminar la venta"
        
        conn.commit()
        conn.close()
        
        return True, {
            'producto_id': producto_id, 
            'cantidad': cantidad, 
            'cliente': venta[3],
            'producto': venta[4], 
            'total': venta[2], 
            'fecha': venta[5]
        }
        
    except psycopg2.Error as e:
        print(f"❌ Error SQL eliminando venta: {e}")
        conn.rollback()
        conn.close()
        return False, f"Error de base de datos: {str(e)}"
    except Exception as e:
        print(f"❌ Error eliminando venta: {e}")
        conn.rollback()
        conn.close()
        return False, f"Error: {str(e)}"

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
    if trabajador_id:
        cursor.execute('SELECT * FROM servicios WHERE negocio_id = %s AND trabajador_id = %s ORDER BY id DESC',
                       (negocio_id, trabajador_id))
    else:
        cursor.execute('SELECT * FROM servicios WHERE negocio_id = %s ORDER BY id DESC', (negocio_id,))
    servicios = cursor.fetchall()
    conn.close()
    return servicios

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
