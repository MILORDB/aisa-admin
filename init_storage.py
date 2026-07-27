# init_storage.py
import os

def crear_carpetas():
    """Crea las carpetas necesarias para el almacenamiento"""
    carpetas = [
        'static/uploads',
        'static/uploads/productos',
        'static/uploads/facturas',
        'static/img'
    ]
    
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
        print(f"✅ Carpeta creada: {carpeta}")
        
        # Crear .gitkeep
        gitkeep = os.path.join(carpeta, '.gitkeep')
        if not os.path.exists(gitkeep):
            with open(gitkeep, 'w') as f:
                f.write('# Esta carpeta se usa para almacenamiento de archivos\n')
            print(f"✅ .gitkeep creado en: {carpeta}")

if __name__ == "__main__":
    crear_carpetas()
    print("\n📁 Todas las carpetas están listas!")
    print("📌 Las imágenes se guardarán en static/uploads/productos/")
