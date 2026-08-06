# web_admin/storage.py

import os
import requests
import json
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse

class StorageManager:
    """Gestor de almacenamiento en TeraBox para fotos de productos y facturas"""
    
    def __init__(self):
        # ============================================
        # CONFIGURACIÓN DE TERABOX CON TUS COOKIES
        # ============================================
        self.cookie = os.environ.get('TERABOX_COOKIE', '')
        
        # Si no hay cookie en entorno, usar tus cookies directamente
        if not self.cookie:
            self.cookie = 'ndus=Y2duleyteHuiFgvBvNIsZwtFwvUcuQlAxWwtr6gp; Lang=es; csrfToken=fKAwNR25tDWjz3IoI7p5YT0J; browserid=Kmgc1pw1acojRXVyJFXz1vyMK2TpOubHjxhgwYQoHooiRQjqcruL1zNFkFQ='
        
        self.base_url = "https://www.terabox.com"
        self.api_url = "https://www.terabox.com/api/v1"
        self.use_local = not self.cookie
        
        # ============================================
        # HEADERS CON TUS COOKIES
        # ============================================
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.terabox.com',
            'Referer': 'https://www.terabox.com/',
            'Cookie': self.cookie,
            'X-CSRF-TOKEN': 'fKAwNR25tDWjz3IoI7p5YT0J'
        }
        
        if self.cookie:
            print("📁 Usando almacenamiento en TeraBox con cookie configurada")
            # Verificar sesión
            self._verificar_sesion()
        else:
            self.use_local = True
            os.makedirs('static/uploads', exist_ok=True)
            print("📁 Usando almacenamiento LOCAL (sin TeraBox)")
    
    def _verificar_sesion(self):
        """Verifica que la sesión de TeraBox sea válida con tus cookies"""
        try:
            # Usar el endpoint de getinfo
            response = requests.get(
                f"{self.base_url}/api/v1/getinfo",
                headers=self.headers
            )
            
            print(f"📡 Verificando sesión TeraBox... Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('errno') == 0:
                    user_data = data.get('data', {})
                    print(f"✅ Sesión TeraBox válida!")
                    print(f"👤 Usuario: {user_data.get('username', 'Desconocido')}")
                    print(f"📊 Espacio usado: {user_data.get('used', 0) / (1024**3):.2f} GB")
                    print(f"📊 Espacio total: {user_data.get('total', 0) / (1024**3):.2f} GB")
                    self.use_local = False
                    return True
                else:
                    print(f"⚠️ Error en sesión: {data.get('errmsg', 'Error desconocido')}")
                    self.use_local = True
                    return False
            else:
                print(f"⚠️ Error HTTP: {response.status_code}")
                print(f"📝 Respuesta: {response.text[:200]}")
                self.use_local = True
                return False
        except Exception as e:
            print(f"⚠️ Error verificando sesión: {e}")
            self.use_local = True
            return False
    
    def get_negocio_path(self, negocio_id):
        return f"/apps/AIsa/Negocios/negocio_{negocio_id}"
    
    def get_productos_path(self, negocio_id):
        return f"{self.get_negocio_path(negocio_id)}/productos"
    
    def get_producto_path(self, negocio_id, producto_id):
        return f"{self.get_productos_path(negocio_id)}/producto_{producto_id}"
    
    def get_facturas_path(self, negocio_id):
        return f"{self.get_negocio_path(negocio_id)}/facturas"
    
    def _crear_carpeta(self, path):
        """Crea una carpeta en TeraBox si no existe"""
        try:
            if self.use_local:
                return True
            
            clean_path = path.replace('//', '/')
            if not clean_path.startswith('/'):
                clean_path = '/' + clean_path
            
            print(f"📁 Creando carpeta: {clean_path}")
            
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
                    print(f"✅ Carpeta creada: {path}")
                    return True
                else:
                    errmsg = result.get('errmsg', '')
                    if 'exists' in errmsg.lower() or 'exist' in errmsg.lower():
                        print(f"ℹ️ La carpeta ya existe: {path}")
                        return True
                    print(f"⚠️ Error creando carpeta: {errmsg}")
                    return False
            return False
        except Exception as e:
            print(f"⚠️ Error creando carpeta: {e}")
            return False
    
    def _obtener_url_subida(self, folder_path, filename):
        """Obtiene la URL de subida de TeraBox"""
        try:
            if self.use_local:
                return None
            
            clean_path = folder_path.replace('//', '/')
            if not clean_path.startswith('/'):
                clean_path = '/' + clean_path
            
            full_path = f"{clean_path}/{filename}"
            full_path = full_path.replace('//', '/')
            
            print(f"🔗 Solicitando URL para: {full_path}")
            
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
    
    def subir_foto_producto(self, negocio_id, producto_id, archivo_foto, nombre_foto):
        """Sube una foto para un producto a TeraBox"""
        try:
            if self.cookie and self.use_local:
                self._verificar_sesion()
            
            if self.use_local:
                print("📁 Usando almacenamiento LOCAL (fallback)")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
            
            print(f"📤 Subiendo {nombre_foto} a TeraBox...")
            
            folder_path = self.get_producto_path(negocio_id, producto_id)
            self._crear_carpeta(folder_path)
            
            upload_url = self._obtener_url_subida(folder_path, nombre_foto)
            if not upload_url:
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
            
            archivo_foto.seek(0)
            files = {'file': (nombre_foto, archivo_foto.read(), 'image/jpeg')}
            
            upload_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Cookie': self.cookie,
                'Accept': '*/*',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Origin': 'https://www.terabox.com',
                'Referer': 'https://www.terabox.com/'
            }
            
            response = requests.post(upload_url, files=files, headers=upload_headers)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get('errno') == 0:
                        print(f"✅ Foto subida a TeraBox: {nombre_foto}")
                        return True
                    else:
                        print(f"❌ Error: {result.get('errmsg')}")
                        return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
                except:
                    print(f"✅ Foto subida a TeraBox: {nombre_foto}")
                    return True
            else:
                print(f"❌ Error HTTP: {response.status_code}")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
    
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
            return self._url_local(negocio_id, producto_id, nombre_foto)
                
        except Exception as e:
            print(f"❌ Error obteniendo URL: {e}")
            return self._url_local(negocio_id, producto_id, nombre_foto)
    
    def _guardar_local(self, negocio_id, producto_id, archivo, nombre_foto):
        """Guarda la foto en el sistema de archivos local"""
        try:
            folder_path = os.path.join('static/uploads/productos', f"negocio_{negocio_id}", f"producto_{producto_id}")
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, nombre_foto)
            archivo.save(file_path)
            print(f"✅ Foto guardada localmente: {file_path}")
            return True
        except Exception as e:
            print(f"❌ Error guardando foto local: {e}")
            return False
    
    def _url_local(self, negocio_id, producto_id, nombre_foto):
        return f"/static/uploads/productos/negocio_{negocio_id}/producto_{producto_id}/{nombre_foto}"
    
    def guardar_factura(self, negocio_id, factura_id, archivo_pdf):
        """Guarda una factura en TeraBox"""
        nombre = f"factura_{factura_id}.pdf"
        
        try:
            if self.cookie and self.use_local:
                self._verificar_sesion()
            
            if self.use_local:
                return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
            
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
            print(f"❌ Error: {e}")
            return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
    
    def _guardar_local_factura(self, negocio_id, factura_id, archivo_pdf):
        try:
            folder_path = os.path.join('static/uploads/facturas', f"negocio_{negocio_id}")
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, f"factura_{factura_id}.pdf")
            archivo_pdf.save(file_path)
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def eliminar_foto_producto(self, negocio_id, producto_id, nombre_foto):
        """Elimina una foto de producto de TeraBox o local"""
        try:
            file_path = os.path.join('static/uploads/productos', f"negocio_{negocio_id}", f"producto_{producto_id}", nombre_foto)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✅ Foto local eliminada: {file_path}")
            
            if self.use_local:
                return True
            
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
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return True
    
    def obtener_estado(self):
        return {
            'tipo': 'TeraBox' if not self.use_local else 'Local',
            'cookie_configurada': bool(self.cookie),
            'use_local': self.use_local,
            'cookie_preview': self.cookie[:30] + '...' if self.cookie and len(self.cookie) > 30 else self.cookie
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
