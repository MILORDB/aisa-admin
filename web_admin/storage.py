# web_admin/storage.py

import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

class StorageManager:
    def __init__(self):
        self.drive_service = None
        self.use_local = True
        self.base_folder_id = None
        self.credentials_file = None
        
        # ============================================
        # BUSCAR CREDENCIALES
        # ============================================
        # 1. En Render: /etc/secrets/credentials.json
        if os.path.exists('/etc/secrets/credentials.json'):
            self.credentials_file = '/etc/secrets/credentials.json'
            print("📁 Credenciales en Render: /etc/secrets/credentials.json")
        # 2. En local: credentials.json
        elif os.path.exists('credentials.json'):
            self.credentials_file = 'credentials.json'
            print("📁 Credenciales locales: credentials.json")
        # 3. En variable de entorno
        elif os.environ.get('GOOGLE_CREDENTIALS_JSON'):
            try:
                creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
                if creds_json.startswith('{'):
                    self.credentials_file = '/tmp/credentials.json'
                    os.makedirs('/tmp', exist_ok=True)
                    with open(self.credentials_file, 'w') as f:
                        f.write(creds_json)
                    print("📁 Credenciales desde variable de entorno")
            except Exception as e:
                print(f"⚠️ Error cargando credenciales desde variable: {e}")
        
        if not self.credentials_file or not os.path.exists(self.credentials_file):
            print("❌ No se encontró credentials.json")
            print("📁 Usando almacenamiento LOCAL")
            self.use_local = True
            return
        
        # Intentar autenticar con Cuenta de Servicio
        self._authenticate()
        
        if self.drive_service:
            self._create_base_folder()
            # IMPORTANTE: Si la autenticación fue exitosa, usar Google Drive
            if not self.use_local:
                print("✅ Google Drive configurado correctamente")
        else:
            self.use_local = True
    
    def _authenticate(self):
        """Autentica con Google Drive usando Cuenta de Servicio"""
        try:
            print(f"🔐 Autenticando con: {self.credentials_file}")
            
            # Verificar que el archivo existe
            if not os.path.exists(self.credentials_file):
                print(f"❌ Archivo no encontrado: {self.credentials_file}")
                self.use_local = True
                return
            
            # Cargar credenciales de Cuenta de Servicio
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=SCOPES
            )
            
            # Construir el servicio
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            # ✅ IMPORTANTE: Establecer use_local = False SOLO si la autenticación fue exitosa
            self.use_local = False
            
            print("✅ Autenticación exitosa con Cuenta de Servicio")
            
            # Verificar acceso
            try:
                about = self.drive_service.about().get(fields="storageQuota").execute()
                quota = about.get('storageQuota', {})
                used = int(quota.get('usage', 0))
                limit = int(quota.get('limit', 0))
                if limit > 0:
                    free_gb = (limit - used) / (1024**3)
                    print(f"📊 Espacio disponible: {free_gb:.2f} GB")
            except Exception as e:
                print(f"⚠️ Error obteniendo cuota: {e}")
            
        except Exception as e:
            print(f"❌ Error en autenticación: {e}")
            self.use_local = True
            self.drive_service = None
    
    def _create_base_folder(self):
        """Crea la carpeta base 'AIsa' en Google Drive si no existe"""
        if not self.drive_service:
            print("⚠️ No hay servicio de Google Drive")
            return
        
        try:
            print("📁 Buscando carpeta 'AIsa' en Google Drive...")
            
            results = self.drive_service.files().list(
                q="name='AIsa' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if not folders:
                print("📁 No se encontró 'AIsa', creando carpeta...")
                file_metadata = {
                    'name': 'AIsa',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.drive_service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                self.base_folder_id = folder.get('id')
                print(f"✅ Carpeta 'AIsa' creada (ID: {self.base_folder_id})")
            else:
                self.base_folder_id = folders[0]['id']
                print(f"✅ Carpeta 'AIsa' encontrada (ID: {self.base_folder_id})")
            
        except Exception as e:
            print(f"⚠️ Error creando carpeta base: {e}")
            # Si hay error, seguir con local
            self.use_local = True
    
    def _get_or_create_folder(self, path, parent_id=None):
        """Obtiene o crea una carpeta por su ruta"""
        if not self.drive_service:
            return None
        
        if not parent_id:
            parent_id = self.base_folder_id
        
        if not parent_id:
            print("⚠️ No hay carpeta base para crear subcarpetas")
            return None
        
        try:
            parts = path.strip('/').split('/')
            current_parent = parent_id
            
            for part in parts:
                if not part:
                    continue
                
                query = f"name='{part}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = self.drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name)'
                ).execute()
                
                folders = results.get('files', [])
                
                if not folders:
                    file_metadata = {
                        'name': part,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_parent]
                    }
                    folder = self.drive_service.files().create(
                        body=file_metadata,
                        fields='id'
                    ).execute()
                    current_parent = folder.get('id')
                    print(f"📁 Carpeta creada: {part}")
                else:
                    current_parent = folders[0]['id']
            
            return current_parent
            
        except Exception as e:
            print(f"⚠️ Error creando carpeta {path}: {e}")
            return None
    
    def subir_foto_producto(self, negocio_id, producto_id, archivo_foto, nombre_foto):
        """Sube una foto de producto a Google Drive"""
        if self.use_local or not self.drive_service:
            print("📁 Usando almacenamiento LOCAL")
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
        
        try:
            print(f"📤 Subiendo {nombre_foto} a Google Drive...")
            
            folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
            folder_id = self._get_or_create_folder(folder_path)
            
            if not folder_id:
                print("⚠️ No se pudo crear carpeta en Google Drive, usando local")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
            
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, nombre_foto)
            archivo_foto.save(temp_path)
            
            file_metadata = {
                'name': nombre_foto,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(temp_path, mimetype='image/jpeg', resumable=True)
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            ).execute()
            
            file_id = file.get('id')
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            if file_id:
                print(f"✅ Foto subida a Google Drive: {nombre_foto} (ID: {file_id})")
                return True
            else:
                print("❌ Error subiendo a Google Drive")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
                
        except Exception as e:
            print(f"❌ Error subiendo a Google Drive: {e}")
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
    
    def obtener_url_foto(self, negocio_id, producto_id, nombre_foto, file_id=None):
        """Obtiene la URL pública de una foto de producto"""
        if self.use_local or not self.drive_service:
            return self._url_local(negocio_id, producto_id, nombre_foto)
        
        try:
            if file_id:
                file = self.drive_service.files().get(
                    fileId=file_id,
                    fields='webViewLink, webContentLink'
                ).execute()
                return file.get('webViewLink') or file.get('webContentLink')
            else:
                folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
                folder_id = self._get_or_create_folder(folder_path)
                
                if not folder_id:
                    return self._url_local(negocio_id, producto_id, nombre_foto)
                
                results = self.drive_service.files().list(
                    q=f"name='{nombre_foto}' and '{folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='files(id, webViewLink, webContentLink)'
                ).execute()
                
                files = results.get('files', [])
                
                if files:
                    return files[0].get('webViewLink') or files[0].get('webContentLink')
            
            return self._url_local(negocio_id, producto_id, nombre_foto)
                
        except Exception as e:
            print(f"❌ Error obteniendo URL: {e}")
            return self._url_local(negocio_id, producto_id, nombre_foto)
    
    def obtener_file_id(self, negocio_id, producto_id, nombre_foto):
        """Obtiene el ID de un archivo en Google Drive"""
        if self.use_local or not self.drive_service:
            return None
        
        try:
            folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
            folder_id = self._get_or_create_folder(folder_path)
            
            if not folder_id:
                return None
            
            results = self.drive_service.files().list(
                q=f"name='{nombre_foto}' and '{folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id)'
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                return files[0]['id']
            return None
                
        except Exception as e:
            print(f"❌ Error obteniendo file ID: {e}")
            return None
    
    def _guardar_local(self, negocio_id, producto_id, archivo, nombre_foto):
        """Guarda la foto en el sistema de archivos local"""
        try:
            folder_path = os.path.join(
                'static/uploads/productos',
                f"negocio_{negocio_id}",
                f"producto_{producto_id}"
            )
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
        """Guarda una factura en Google Drive"""
        nombre = f"factura_{factura_id}.pdf"
        
        if self.use_local or not self.drive_service:
            return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
        
        try:
            print(f"📤 Subiendo factura {nombre} a Google Drive...")
            
            folder_path = f"negocio_{negocio_id}/facturas"
            folder_id = self._get_or_create_folder(folder_path)
            
            if not folder_id:
                return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
            
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, nombre)
            archivo_pdf.save(temp_path)
            
            file_metadata = {
                'name': nombre,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(temp_path, mimetype='application/pdf', resumable=True)
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            print(f"✅ Factura subida a Google Drive: {nombre}")
            return True
            
        except Exception as e:
            print(f"❌ Error subiendo factura: {e}")
            return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
    
    def _guardar_local_factura(self, negocio_id, factura_id, archivo_pdf):
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
    
    def eliminar_foto_producto(self, negocio_id, producto_id, nombre_foto, file_id=None):
        """Elimina una foto de producto de Google Drive y local"""
        try:
            file_path = os.path.join(
                'static/uploads/productos',
                f"negocio_{negocio_id}",
                f"producto_{producto_id}",
                nombre_foto
            )
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✅ Foto local eliminada: {file_path}")
            
            if self.use_local or not self.drive_service:
                return True
            
            if file_id:
                self.drive_service.files().delete(fileId=file_id).execute()
                print(f"✅ Foto eliminada de Google Drive: {nombre_foto}")
                return True
            else:
                folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
                folder_id = self._get_or_create_folder(folder_path)
                
                if folder_id:
                    results = self.drive_service.files().list(
                        q=f"name='{nombre_foto}' and '{folder_id}' in parents and trashed=false",
                        spaces='drive',
                        fields='files(id)'
                    ).execute()
                    
                    files = results.get('files', [])
                    
                    if files:
                        self.drive_service.files().delete(fileId=files[0]['id']).execute()
                        print(f"✅ Foto eliminada de Google Drive: {nombre_foto}")
                        return True
            
            return True
            
        except Exception as e:
            print(f"❌ Error eliminando foto: {e}")
            return True
    
    def obtener_estado(self):
        """Obtiene el estado del almacenamiento"""
        estado = {
            'tipo': 'Google Drive' if not self.use_local else 'Local',
            'autenticado': self.drive_service is not None,
            'use_local': self.use_local,
            'base_folder_id': self.base_folder_id,
            'mensaje': '📁 Usando almacenamiento local'
        }
        
        if self.drive_service and not self.use_local:
            try:
                about = self.drive_service.about().get(fields="storageQuota").execute()
                quota = about.get('storageQuota', {})
                used = int(quota.get('usage', 0))
                limit = int(quota.get('limit', 0))
                if limit > 0:
                    estado['used_gb'] = round(used / (1024**3), 2)
                    estado['total_gb'] = round(limit / (1024**3), 2)
                    estado['free_gb'] = round((limit - used) / (1024**3), 2)
                    estado['mensaje'] = f"✅ Conectado a Google Drive ({estado['free_gb']} GB libres)"
                else:
                    estado['mensaje'] = "✅ Conectado a Google Drive"
            except Exception as e:
                print(f"⚠️ Error obteniendo cuota: {e}")
                estado['mensaje'] = "✅ Conectado a Google Drive"
        
        return estado


# ============================================
# INSTANCIA GLOBAL
# ============================================

_storage_instance = None

def get_storage_manager():
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance
