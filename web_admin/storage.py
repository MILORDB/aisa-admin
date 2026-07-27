import os
import uuid
from datetime import datetime

class StorageManager:
    """Gestor de almacenamiento LOCAL para fotos de productos y facturas"""
    
    def __init__(self):
        # Crear carpetas necesarias
        os.makedirs('static/uploads/productos', exist_ok=True)
        os.makedirs('static/uploads/facturas', exist_ok=True)
        os.makedirs('static/img', exist_ok=True)
        print("📁 Usando almacenamiento LOCAL")
    
    def subir_foto_producto(self, negocio_id, producto_id, archivo_foto, nombre_foto):
        """Guarda la foto en el sistema de archivos local"""
        try:
            # Crear la ruta de la carpeta
            folder_path = os.path.join('static/uploads/productos', f"negocio_{negocio_id}", f"producto_{producto_id}")
            os.makedirs(folder_path, exist_ok=True)
            
            # Guardar el archivo
            file_path = os.path.join(folder_path, nombre_foto)
            archivo_foto.save(file_path)
            
            print(f"✅ Foto guardada localmente: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error guardando foto local: {e}")
            return False
    
    def obtener_url_foto(self, negocio_id, producto_id, nombre_foto):
        """Devuelve la URL local de la foto"""
        return f"/static/uploads/productos/negocio_{negocio_id}/producto_{producto_id}/{nombre_foto}"
    
    def eliminar_foto_producto(self, negocio_id, producto_id, nombre_foto):
        """Elimina una foto de producto del sistema local"""
        try:
            file_path = os.path.join('static/uploads/productos', f"negocio_{negocio_id}", f"producto_{producto_id}", nombre_foto)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✅ Foto local eliminada: {file_path}")
                return True
            return False
        except Exception as e:
            print(f"❌ Error eliminando foto local: {e}")
            return False
    
    def guardar_factura(self, negocio_id, factura_id, archivo_pdf):
        """Guarda una factura localmente"""
        try:
            folder_path = os.path.join('static/uploads/facturas', f"negocio_{negocio_id}")
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, f"factura_{factura_id}.pdf")
            archivo_pdf.save(file_path)
            print(f"✅ Factura guardada localmente: {file_path}")
            return True
        except Exception as e:
            print(f"❌ Error guardando factura local: {e}")
            return False
    
    def obtener_estado(self):
        """Devuelve el estado del almacenamiento"""
        return {
            'tipo': 'Local',
            'use_local': True,
            'carpetas': {
                'productos': 'static/uploads/productos',
                'facturas': 'static/uploads/facturas'
            }
        }

# ============================================
# INSTANCIA GLOBAL
# ============================================

_storage_instance = None

def get_storage_manager():
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance
