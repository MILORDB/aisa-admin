import os
import sys
import psycopg2
from datetime import datetime
import bcrypt
import urllib.parse

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no está configurada")
    sys.exit(1)

print("🔧 Conectando a PostgreSQL...")

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
    cursor = conn.cursor()
    print("✅ Conectado a PostgreSQL")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print("🔧 Creando tablas...")

# Crear todas las tablas con SERIAL (PostgreSQL)
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
print("✅ Tabla usuarios creada")

cursor.execute('''
CREATE TABLE IF NOT EXISTS sesiones (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    fecha_creacion TEXT NOT NULL,
    fecha_expiracion TEXT NOT NULL,
    activo INTEGER DEFAULT 1,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
)
''')
print("✅ Tabla sesiones creada")

cursor.execute('''
CREATE TABLE IF NOT EXISTS modulos (
    id SERIAL PRIMARY KEY,
    nombre TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    activo_global INTEGER DEFAULT 1,
    tipo_requerido TEXT DEFAULT 'ambos'
)
''')
print("✅ Tabla modulos creada")

cursor.execute('''
CREATE TABLE IF NOT EXISTS permisos_usuario (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    modulo_id INTEGER NOT NULL,
    activo INTEGER DEFAULT 1,
    fecha_solicitud TEXT,
    estado_solicitud TEXT DEFAULT 'aprobado',
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
    FOREIGN KEY (modulo_id) REFERENCES modulos (id),
    UNIQUE(usuario_id, modulo_id)
)
''')
print("✅ Tabla permisos_usuario creada")

cursor.execute('''
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER,
    accion TEXT,
    detalle TEXT,
    fecha TEXT NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
)
''')
print("✅ Tabla logs creada")

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
    FOREIGN KEY (negocio_id) REFERENCES usuarios(id)
)
''')
print("✅ Tabla productos creada")

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
    fecha TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (negocio_id) REFERENCES usuarios(id),
    FOREIGN KEY (trabajador_id) REFERENCES usuarios(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
)
''')
print("✅ Tabla ventas creada")

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
    FOREIGN KEY (negocio_id) REFERENCES usuarios(id),
    FOREIGN KEY (trabajador_id) REFERENCES usuarios(id)
)
''')
print("✅ Tabla servicios creada")

cursor.execute('''
CREATE TABLE IF NOT EXISTS trabajadores_negocio (
    id SERIAL PRIMARY KEY,
    negocio_id INTEGER NOT NULL,
    trabajador_id INTEGER NOT NULL,
    activo INTEGER DEFAULT 1,
    cargo TEXT,
    salario REAL DEFAULT 0,
    fecha_contratacion TEXT NOT NULL,
    FOREIGN KEY (negocio_id) REFERENCES usuarios(id),
    FOREIGN KEY (trabajador_id) REFERENCES usuarios(id),
    UNIQUE(negocio_id, trabajador_id)
)
''')
print("✅ Tabla trabajadores_negocio creada")

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
    FOREIGN KEY (negocio_id) REFERENCES usuarios(id),
    FOREIGN KEY (trabajador_id) REFERENCES usuarios(id)
)
''')
print("✅ Tabla contratos creada")

cursor.execute('''
CREATE TABLE IF NOT EXISTS productos_tienda (
    id SERIAL PRIMARY KEY,
    negocio_id INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    destacado INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (negocio_id) REFERENCES usuarios(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
)
''')
print("✅ Tabla productos_tienda creada")

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

# Crear admin
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

print("\n" + "=" * 50)
print("✅ BASE DE DATOS INICIALIZADA CORRECTAMENTE")
print("👤 Usuario: admin")
print("🔑 Contraseña: admin123")
print("=" * 50)
