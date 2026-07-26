import os
import requests
import json
import time
import uuid
from datetime import datetime

class StorageManager:
    """Gestor de almacenamiento en la nube para cada negocio"""
    
    def __init__(self):
        self.cookie = os.environ.get('TERABOX_COOKIE', '')
        self.use_local = not self.cookie
        self.base_url = "https://www.terabox.com/api/"
        
        if self.use_local:
            # Crear carpeta local para desarrollo
            os.makedirs('static/uploads', exist_ok=True)
            print("📁 Usando almacenamiento LOCAL (sin TeraBox)")
        else:
            print("📁 Usando almacenamiento en TeraBox")
    
    def get_negocio_path(self, negocio_id):
        """Obtiene la ruta base para un negocio"""
        return f"Negocios/negocio_{negocio_id}"
    
    def get_productos_path(self, negocio_id):
        """Obtiene la ruta de productos para un negocio"""
        return f"{self.get_negocio_path(negocio_id)}/productos"
    
    def get_producto_path(self, negocio_id, producto_id):
        """Obtiene la ruta de un producto específico"""
        return f"{self.get_productos_path(negocio_id)}/producto_{producto_id}"
    
    def subir_foto_producto(self, negocio_id, producto_id, archivo_foto, nombre_foto):
        """Sube una foto para un producto"""
        # Si no hay cookie, guardar localmente
        if self.use_local:
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
        
        # Subir a TeraBox
        return self._subir_terabox(negocio_id, producto_id, archivo_foto, nombre_foto)
    
    def obtener_url_foto(self, negocio_id, producto_id, nombre_foto):
        """Obtiene la URL pública de una foto de producto"""
        # Si es local, devolver URL local
        if self.use_local:
            return self._url_local(negocio_id, producto_id, nombre_foto)
        
        # Obtener URL de TeraBox
        return self._url_terabox(negocio_id, producto_id, nombre_foto)
    
    # ============================================
    # MÉTODOS PARA ALMACENAMIENTO LOCAL (Desarrollo)
    # ============================================
    
    def _guardar_local(self, negocio_id, producto_id, archivo, nombre_foto):
        """Guarda la foto en el sistema de archivos local"""
        try:
            # Crear la ruta de la carpeta
            folder_path = os.path.join('static/uploads', f"negocio_{negocio_id}", f"producto_{producto_id}")
            os.makedirs(folder_path, exist_ok=True)
            
            # Guardar el archivo
            file_path = os.path.join(folder_path, nombre_foto)
            archivo.save(file_path)
            
            print(f"✅ Foto guardada localmente: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error guardando foto local: {e}")
            return False
    
    def _url_local(self, negocio_id, producto_id, nombre_foto):
        """Devuelve la URL local de la foto"""
        return f"/static/uploads/negocio_{negocio_id}/producto_{producto_id}/{nombre_foto}"
    
    # ============================================
    # MÉTODOS PARA TERABOX (Producción)
    # ============================================
    
    def _subir_terabox(self, negocio_id, producto_id, archivo, nombre_foto):
        """Sube la foto a TeraBox usando la API"""
        try:
            # 1. Obtener URL de subida
            upload_url = self._obtener_url_subida(negocio_id, producto_id, nombre_foto)
            if not upload_url:
                print("❌ No se pudo obtener URL de subida")
                return False
            
            # 2. Subir el archivo
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Leer el archivo
            archivo.seek(0)
            files = {'file': (nombre_foto, archivo.read(), 'image/jpeg')}
            
            response = requests.post(upload_url, headers=headers, files=files)
            
            if response.status_code == 200:
                print(f"✅ Foto subida a TeraBox: {nombre_foto}")
                return True
            else:
                print(f"❌ Error subiendo a TeraBox: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error subiendo a TeraBox: {e}")
            # Fallback a local
            print("🔄 Fallback a almacenamiento local...")
            return self._guardar_local(negocio_id, producto_id, archivo, nombre_foto)
    
    def _obtener_url_subida(self, negocio_id, producto_id, nombre_foto):
        """Obtiene la URL de subida de TeraBox"""
        try:
            # Construir la ruta en TeraBox
            path = f"/{self.get_producto_path(negocio_id, producto_id)}"
            
            # Obtener token de subida
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Esta es una API simplificada - en producción usarías la API oficial de TeraBox
            # Como alternativa, usamos un servicio de intercambio de archivos
            # o guardamos localmente
            
            # Por ahora, devolvemos None para usar el fallback local
            # En una implementación real, aquí iría la lógica de TeraBox
            return None
            
        except Exception as e:
            print(f"❌ Error obteniendo URL de subida: {e}")
            return None
    
    def _url_terabox(self, negocio_id, producto_id, nombre_foto):
        """Obtiene la URL pública de TeraBox"""
        try:
            # Construir la ruta en TeraBox
            path = f"/{self.get_producto_path(negocio_id, producto_id)}/{nombre_foto}"
            
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # URL pública de TeraBox (simplificada)
            # En producción, usarías la API real de TeraBox para obtener el enlace
            return f"https://www.terabox.com/sharing/link?surl=...&path={path}"
            
        except Exception as e:
            print(f"❌ Error obteniendo URL de TeraBox: {e}")
            return self._url_local(negocio_id, producto_id, nombre_foto)
    
    # ============================================
    # MÉTODOS PARA GUARDAR FACTURAS
    # ============================================
    
    def get_facturas_path(self, negocio_id):
        """Obtiene la ruta de facturas para un negocio"""
        return f"{self.get_negocio_path(negocio_id)}/facturas"
    
    def guardar_factura(self, negocio_id, factura_id, archivo_pdf):
        """Guarda una factura en la carpeta del negocio"""
        nombre = f"factura_{factura_id}.pdf"
        
        if self.use_local:
            # Guardar localmente
            try:
                folder_path = os.path.join('static/uploads', f"negocio_{negocio_id}", "facturas")
                os.makedirs(folder_path, exist_ok=True)
                file_path = os.path.join(folder_path, nombre)
                archivo_pdf.save(file_path)
                return True
            except Exception as e:
                print(f"❌ Error guardando factura: {e}")
                return False
        
        # Subir a TeraBox
        return self._subir_terabox(negocio_id, f"factura_{factura_id}", archivo_pdf, nombre)
