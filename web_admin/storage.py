import os
import requests
import json
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class StorageManager:
    """Gestor de almacenamiento en TeraBox para fotos de productos y facturas"""
    
    def __init__(self):
        # Configuración de TeraBox - Desde .env
        self.cookie = os.environ.get('TERABOX_COOKIE', '')
        self.base_url = "https://www.terabox.com"
        self.api_url = "https://www.terabox.com/api/v1"
        self.use_local = not self.cookie
        
        # Headers para las peticiones a TeraBox
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.terabox.com',
            'Referer': 'https://www.terabox.com/'
        }
        
        if self.cookie:
            self.headers['Cookie'] = self.cookie
            print("📁 Usando almacenamiento en TeraBox con cookie configurada")
            self._verificar_sesion()
        else:
            self.use_local = True
            # Crear carpeta local para desarrollo
            os.makedirs('static/uploads', exist_ok=True)
            print("📁 Usando almacenamiento LOCAL (sin TeraBox)")
            print("⚠️ Para usar TeraBox, configura TERABOX_COOKIE en .env")
    
    def _verificar_sesion(self):
        """Verifica que la sesión de TeraBox sea válida"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/getinfo", headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                if data.get('errno') == 0:
                    print(f"✅ Sesión TeraBox válida - Usuario: {data.get('data', {}).get('username', 'Desconocido')}")
                    self.use_local = False
                    return True
                else:
                    print(f"⚠️ Error en sesión TeraBox: {data.get('errmsg', 'Error desconocido')}")
                    self.use_local = True
                    return False
            else:
                print(f"⚠️ Error verificando sesión TeraBox: {response.status_code}")
                self.use_local = True
                return False
        except Exception as e:
            print(f"⚠️ Error verificando sesión TeraBox: {e}")
            self.use_local = True
            return False
    
    def get_negocio_path(self, negocio_id):
        """Obtiene la ruta base para un negocio"""
        return f"/apps/AIsa/Negocios/negocio_{negocio_id}"
    
    def get_productos_path(self, negocio_id):
        """Obtiene la ruta de productos para un negocio"""
        return f"{self.get_negocio_path(negocio_id)}/productos"
    
    def get_producto_path(self, negocio_id, producto_id):
        """Obtiene la ruta de un producto específico"""
        return f"{self.get_productos_path(negocio_id)}/producto_{producto_id}"
    
    def get_facturas_path(self, negocio_id):
        """Obtiene la ruta de facturas para un negocio"""
        return f"{self.get_negocio_path(negocio_id)}/facturas"
    
    # ============================================
    # MÉTODOS PARA SUBIR FOTOS A TERABOX
    # ============================================
    
    def subir_foto_producto(self, negocio_id, producto_id, archivo_foto, nombre_foto):
        """Sube una foto para un producto a TeraBox"""
        if self.use_local:
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
        
        try:
            # 1. Crear carpeta si no existe
            folder_path = self.get_producto_path(negocio_id, producto_id)
            self._crear_carpeta(folder_path)
            
            # 2. Obtener URL de subida
            upload_url = self._obtener_url_subida(folder_path, nombre_foto)
            if not upload_url:
                print("❌ No se pudo obtener URL de subida, usando fallback local")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
            
            # 3. Subir el archivo
            archivo_foto.seek(0)
            files = {'file': (nombre_foto, archivo_foto.read(), 'image/jpeg')}
            
            response = requests.post(upload_url, files=files, headers=self.headers)
            
            if response.status_code == 200:
                print(f"✅ Foto subida a TeraBox: {nombre_foto}")
                return True
            else:
                print(f"❌ Error subiendo a TeraBox: {response.status_code} - {response.text}")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
                
        except Exception as e:
            print(f"❌ Error subiendo a TeraBox: {e}")
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
    
    def _crear_carpeta(self, path):
        """Crea una carpeta en TeraBox si no existe"""
        try:
            clean_path = path.replace('//', '/')
            if not clean_path.startswith('/'):
                clean_path = '/' + clean_path
            
            data = {
                'path': clean_path,
                'is_folder': '1'
            }
            
            response = requests.post(
                f"{self.api_url}/create",
                data=data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errno') == 0:
                    print(f"✅ Carpeta creada/verificada: {path}")
                    return True
                else:
                    if result.get('errmsg') and 'exists' in result.get('errmsg', '').lower():
                        return True
                    print(f"⚠️ Error creando carpeta: {result.get('errmsg')}")
                    return False
            return False
        except Exception as e:
            print(f"⚠️ Error creando carpeta: {e}")
            return False
    
    def _obtener_url_subida(self, folder_path, filename):
        """Obtiene la URL de subida de TeraBox"""
        try:
            clean_path = folder_path.replace('//', '/')
            if not clean_path.startswith('/'):
                clean_path = '/' + clean_path
            
            full_path = f"{clean_path}/{filename}"
            full_path = full_path.replace('//', '/')
            
            data = {
                'path': full_path,
                'size': '0',
                'upload_id': '0',
                'is_renew': '0',
                'auto_rename': '1'
            }
            
            response = requests.post(
                f"{self.api_url}/precreate",
                data=data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errno') == 0:
                    upload_data = result.get('data', {})
                    upload_url = upload_data.get('upload_url')
                    if upload_url:
                        return upload_url
                    else:
                        print("⚠️ No se recibió URL de subida")
                        return None
                else:
                    print(f"⚠️ Error en precreate: {result.get('errmsg')}")
                    return None
            else:
                print(f"⚠️ Error HTTP en precreate: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error obteniendo URL de subida: {e}")
            return None
    
    def obtener_url_foto(self, negocio_id, producto_id, nombre_foto):
        """Obtiene la URL pública de una foto de producto"""
        if self.use_local:
            return self._url_local(negocio_id, producto_id, nombre_foto)
        
        try:
            path = f"{self.get_producto_path(negocio_id, producto_id)}/{nombre_foto}"
            path = path.replace('//', '/')
            if not path.startswith('/'):
                path = '/' + path
            
            data = {
                'path': path,
                'period': 86400
            }
            
            response = requests.post(
                f"{self.api_url}/share/create",
                data=data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errno') == 0:
                    share_data = result.get('data', {})
                    url = share_data.get('url')
                    if url:
                        return url
                    else:
                        return f"{self.base_url}{path}"
                else:
                    print(f"⚠️ Error creando enlace: {result.get('errmsg')}")
                    return self._url_local(negocio_id, producto_id, nombre_foto)
            else:
                return self._url_local(negocio_id, producto_id, nombre_foto)
                
        except Exception as e:
            print(f"❌ Error obteniendo URL de TeraBox: {e}")
            return self._url_local(negocio_id, producto_id, nombre_foto)
    
    # ============================================
    # MÉTODOS PARA ALMACENAMIENTO LOCAL (FALLBACK)
    # ============================================
    
    def _guardar_local(self, negocio_id, producto_id, archivo, nombre_foto):
        """Guarda la foto en el sistema de archivos local"""
        try:
            folder_path = os.path.join('static/uploads', f"negocio_{negocio_id}", f"producto_{producto_id}")
            os.makedirs(folder_path, exist_ok=True)
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
    # MÉTODOS PARA FACTURAS
    # ============================================
    
    def guardar_factura(self, negocio_id, factura_id, archivo_pdf):
        """Guarda una factura en TeraBox"""
        nombre = f"factura_{factura_id}.pdf"
        
        if self.use_local:
            try:
                folder_path = os.path.join('static/uploads', f"negocio_{negocio_id}", "facturas")
                os.makedirs(folder_path, exist_ok=True)
                file_path = os.path.join(folder_path, nombre)
                archivo_pdf.save(file_path)
                return True
            except Exception as e:
                print(f"❌ Error guardando factura: {e}")
                return False
        
        try:
            folder_path = self.get_facturas_path(negocio_id)
            self._crear_carpeta(folder_path)
            upload_url = self._obtener_url_subida(folder_path, nombre)
            if not upload_url:
                return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
            
            archivo_pdf.seek(0)
            files = {'file': (nombre, archivo_pdf.read(), 'application/pdf')}
            response = requests.post(upload_url, files=files, headers=self.headers)
            
            if response.status_code == 200:
                print(f"✅ Factura subida a TeraBox: {nombre}")
                return True
            else:
                return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
                
        except Exception as e:
            print(f"❌ Error subiendo factura: {e}")
            return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
    
    def _guardar_local_factura(self, negocio_id, factura_id, archivo_pdf):
        """Guarda una factura localmente (fallback)"""
        try:
            folder_path = os.path.join('static/uploads', f"negocio_{negocio_id}", "facturas")
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, f"factura_{factura_id}.pdf")
            archivo_pdf.save(file_path)
            return True
        except Exception as e:
            print(f"❌ Error guardando factura local: {e}")
            return False
    
    # ============================================
    # MÉTODOS PARA ELIMINAR ARCHIVOS
    # ============================================
    
    def eliminar_foto_producto(self, negocio_id, producto_id, nombre_foto):
        """Elimina una foto de producto de TeraBox"""
        if self.use_local:
            try:
                file_path = os.path.join('static/uploads', f"negocio_{negocio_id}", f"producto_{producto_id}", nombre_foto)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"✅ Foto local eliminada: {file_path}")
                return True
            except Exception as e:
                print(f"❌ Error eliminando foto local: {e}")
                return False
        
        try:
            path = f"{self.get_producto_path(negocio_id, producto_id)}/{nombre_foto}"
            path = path.replace('//', '/')
            if not path.startswith('/'):
                path = '/' + path
            
            data = {
                'path_list': json.dumps([path])
            }
            
            response = requests.post(
                f"{self.api_url}/delete",
                data=data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errno') == 0:
                    print(f"✅ Foto eliminada de TeraBox: {nombre_foto}")
                    return True
                else:
                    print(f"⚠️ Error eliminando de TeraBox: {result.get('errmsg')}")
                    return False
            return False
        except Exception as e:
            print(f"❌ Error eliminando de TeraBox: {e}")
            return False
    
    def obtener_estado(self):
        """Devuelve el estado del almacenamiento"""
        return {
            'tipo': 'TeraBox' if not self.use_local else 'Local',
            'cookie_configurada': bool(self.cookie),
            'use_local': self.use_local,
            'cookie_preview': self.cookie[:20] + '...' if self.cookie and len(self.cookie) > 20 else self.cookie
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
