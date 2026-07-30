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
        print("✅ Conectado a PostgreSQL")
        
        # 1. Verificar si la columna 'costo' existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'productos' AND column_name = 'costo'
        """)
        existe = cursor.fetchone()
        
        mensaje = ""
        
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
                        <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                        <a href="/negocio/inventario" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Inventario</a>
                    </body>
                </html>
                """
        else:
            mensaje = "✅ La columna 'costo' ya existe"
            print(mensaje)
        
        # 2. Verificar todas las columnas de la tabla productos
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'productos'
            ORDER BY ordinal_position
        """)
        columnas = cursor.fetchall()
        
        # 3. Contar productos
        cursor.execute("SELECT COUNT(*) FROM productos")
        total_productos = cursor.fetchone()[0]
        
        # 4. Verificar si hay productos sin costo (NULL)
        cursor.execute("SELECT COUNT(*) FROM productos WHERE costo IS NULL")
        null_costos = cursor.fetchone()[0]
        
        # 5. Actualizar productos con costo NULL a 0
        if null_costos > 0:
            cursor.execute("UPDATE productos SET costo = 0 WHERE costo IS NULL")
            conn.commit()
            print(f"✅ {null_costos} productos actualizados con costo = 0")
        
        conn.close()
        
        # Generar HTML con los resultados
        html_columnas = ""
        for col, tipo, nullable in columnas:
            html_columnas += f"• <strong>{col}</strong> ({tipo}) - {'Puede ser NULL' if nullable == 'YES' else 'NOT NULL'}<br>"
        
        return f"""
        <html>
            <head>
                <title>Productos Reparados</title>
                <style>
                    body {{ background: #0f0f1a; color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; text-align: center; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    .card {{ background: #1a1a2e; border-radius: 12px; padding: 24px; border: 1px solid #2a2a3e; margin-bottom: 20px; text-align: left; }}
                    .card h3 {{ color: #aaa; margin-bottom: 10px; }}
                    .success {{ color: #6bff6b; }}
                    .error {{ color: #ff6b6b; }}
                    .info {{ color: #ffbb33; }}
                    .btn {{
                        display: inline-block;
                        padding: 10px 20px;
                        margin: 10px;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                        text-decoration: none;
                        transition: all 0.3s;
                    }}
                    .btn-primary {{ background: #6c3ce0; color: #fff; }}
                    .btn-primary:hover {{ background: #5a2ec0; }}
                    .btn-secondary {{ background: #2a2a3e; color: #fff; }}
                    .btn-secondary:hover {{ background: #3a3a4e; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="color:#6c3ce0;">🔧 Reparación de Productos</h1>
                    
                    <div class="card">
                        <h3>📊 Resumen</h3>
                        <p><strong>Total de productos:</strong> {total_productos}</p>
                        <p><strong>Productos sin costo (NULL):</strong> {null_costos}</p>
                        <p><strong>Estado:</strong> <span class="success">{mensaje}</span></p>
                    </div>
                    
                    <div class="card">
                        <h3>📋 Columnas en 'productos'</h3>
                        {html_columnas}
                    </div>
                    
                    <div>
                        <a href="/negocio/inventario" class="btn btn-primary">📦 Ir al Inventario</a>
                        <a href="/dashboard" class="btn btn-secondary">← Volver al Dashboard</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except psycopg2.Error as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error en la base de datos</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
            </body>
        </html>
        """, 500
    except Exception as e:
        return f"""
        <html>
            <head><title>Error</title></head>
            <body style="background:#0f0f1a;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ff6b6b;">❌ Error general</h1>
                <pre style="color:#aaa;text-align:left;background:#1a1a2e;padding:20px;border-radius:8px;max-width:800px;margin:20px auto;">{e}</pre>
                <a href="/dashboard" style="color:#6c3ce0;text-decoration:none;border:1px solid #6c3ce0;padding:10px 20px;border-radius:8px;">Volver al Dashboard</a>
            </body>
        </html>
        """, 500
