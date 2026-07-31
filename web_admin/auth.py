import secrets
from datetime import datetime, timedelta
from web_admin.database import get_db, obtener_usuario_por_id
from psycopg2.extras import RealDictCursor

def generar_token():
    return secrets.token_urlsafe(64)

def crear_sesion(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Crear tabla sesiones si no existe (PostgreSQL - SERIAL)
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
    
    token = generar_token()
    fecha_creacion = datetime.now().isoformat()
    fecha_expiracion = (datetime.now() + timedelta(days=7)).isoformat()
    
    # Desactivar sesiones anteriores
    cursor.execute('UPDATE sesiones SET activo = 0 WHERE usuario_id = %s', (user_id,))
    cursor.execute('''
    INSERT INTO sesiones (usuario_id, token, fecha_creacion, fecha_expiracion, activo)
    VALUES (%s, %s, %s, %s, 1)
    ''', (user_id, token, fecha_creacion, fecha_expiracion))
    conn.commit()
    conn.close()
    return token

def verificar_sesion(token):
    if not token:
        return None
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM sesiones WHERE token = %s AND activo = 1', (token,))
    sesion = cursor.fetchone()
    
    if not sesion:
        conn.close()
        return None
    
    fecha_expiracion = datetime.fromisoformat(sesion['fecha_expiracion'])
    if datetime.now() > fecha_expiracion:
        cursor.execute('UPDATE sesiones SET activo = 0 WHERE id = %s', (sesion['id'],))
        conn.commit()
        conn.close()
        return None
    
    conn.close()
    return sesion

def obtener_usuario_sesion(token):
    sesion = verificar_sesion(token)
    if not sesion:
        return None
    usuario = obtener_usuario_por_id(sesion['usuario_id'])
    if usuario:
        print(f"🔍 obtener_usuario_sesion: {usuario.get('username')} - Rol: {usuario.get('rol')}")
    return usuario
