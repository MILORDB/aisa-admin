# web_admin/storage.py

import os
import pickle
import json
from datetime import datetime
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ============================================
# CONFIGURACIÓN DE GOOGLE DRIVE
# ============================================
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# IMPORTANTE: La ruta correcta en Render
# En desarrollo local: credentials.json
# En Render: /etc/secrets/credentials.json
CREDENTIALS_FILE = os.environ.get('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

# Si estamos en Render, usar la ruta de secret files
if os.path.exists('/etc/secrets/credentials.json'):
    CREDENTIALS_FILE = '/etc/secrets/credentials.json'

TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'token.pickle')

class StorageManager:
    """Gestor de almacenamiento en Google Drive"""
    
    def __init__(self):
        self.drive_service = None
        self.use_local = True
        self.folder_id = None
        self.base_folder_id = None
        
        print(f"📁 Buscando credenciales en: {CREDENTIALS_FILE}")
        
        # Verificar si existe el archivo de credenciales
        if os.path.exists(CREDENTIALS_FILE):
            print("✅ Archivo credentials.json encontrado")
            self._authenticate()
        else:
            print("❌ No se encontró credentials.json")
            print("📁 Usando almacenamiento LOCAL")
            self.use_local = True
        
        # Crear carpeta base si existe conexión
        if self.drive_service:
            self._create_base_folder()
    
    def _authenticate(self):
        """Autentica con Google Drive usando OAuth 2.0"""
        creds = None
        
        # Cargar token guardado si existe
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'rb') as token:
                    creds = pickle.load(token)
                print("✅ Token de Google Drive cargado")
            except Exception as e:
                print(f"⚠️ Error cargando token: {e}")
                creds = None
        
        # Si no hay credenciales válidas, autenticar
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("🔄 Token refrescado")
                except Exception as e:
                    print(f"⚠️ Error refrescando token: {e}")
                    creds = None
            
            # Si sigue sin credenciales, pedir autenticación
            if not creds:
                try:
                    if not os.path.exists(CREDENTIALS_FILE):
                        print(f"❌ No se encontró {CREDENTIALS_FILE}")
                        print("📁 Por favor, coloca el archivo credentials.json")
                        return
                    
                    print("🔐 Iniciando autenticación OAuth...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_FILE, SCOPES
                    )
                    creds = flow.run_local_server(port=8080, open_browser=True)
                    print("✅ Autenticación completada")
                except Exception as e:
                    print(f"❌ Error en autenticación: {e}")
                    return
            
            # Guardar token para futuros usos
            try:
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(creds, token)
                print("✅ Token guardado")
            except Exception as e:
                print(f"⚠️ Error guardando token: {e}")
        
        if creds and creds.valid:
            try:
                self.drive_service = build('drive', 'v3', credentials=creds)
                self.use_local = False
                print("✅ Google Drive conectado correctamente")
                
                # Verificar espacio disponible
                about = self.drive_service.about().get(fields="storageQuota").execute()
                quota = about.get('storageQuota', {})
                used = int(quota.get('usage', 0))
                limit = int(quota.get('limit', 0))
                if limit > 0:
                    free_gb = (limit - used) / (1024**3)
                    print(f"📊 Espacio disponible: {free_gb:.2f} GB")
                    if free_gb < 0.5:
                        print("⚠️ Espacio bajo en Google Drive")
            except Exception as e:
                print(f"❌ Error conectando a Google Drive: {e}")
                self.drive_service = None
                self.use_local = True
    
    def _create_base_folder(self):
        """Crea la carpeta base 'AIsa' en Google Drive si no existe"""
        if not self.drive_service:
            return
        
        try:
            results = self.drive_service.files().list(
                q="name='AIsa' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if not folders:
                file_metadata = {
                    'name': 'AIsa',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.drive_service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                self.base_folder_id = folder.get('id')
                print(f"📁 Carpeta 'AIsa' creada en Google Drive (ID: {self.base_folder_id})")
            else:
                self.base_folder_id = folders[0]['id']
                print(f"📁 Carpeta 'AIsa' encontrada (ID: {self.base_folder_id})")
            
        except Exception as e:
            print(f"⚠️ Error creando carpeta base: {e}")
    
    def _get_or_create_folder(self, path, parent_id=None):
        """Obtiene o crea una carpeta por su ruta"""
        if not self.drive_service:
            return None
        
        if not parent_id:
            parent_id = self.base_folder_id
        
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
            folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
            folder_id = self._get_or_create_folder(folder_path)
            
            if not folder_id:
                print("⚠️ No se pudo crear carpeta en Google Drive, usando local")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
            
            temp_path = os.path.join('static/temp', nombre_foto)
            os.makedirs('static/temp', exist_ok=True)
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
            folder_path = f"negocio_{negocio_id}/facturas"
            folder_id = self._get_or_create_folder(folder_path)
            
            if not folder_id:
                return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)
            
            temp_path = os.path.join('static/temp', nombre)
            os.makedirs('static/temp', exist_ok=True)
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
            'mensaje': '✅ Conectado a Google Drive' if not self.use_local else '📁 Usando almacenamiento local'
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
            except:
                pass
        
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


if __name__ == "__main__":
    print("=" * 60)
    print("🔍 PRUEBA DE ALMACENAMIENTO - GOOGLE DRIVE")
    print("=" * 60)
    
    storage = get_storage_manager()
    estado = storage.obtener_estado()
    
    print(f"\n📁 Estado del almacenamiento:")
    print(f"   • Tipo: {estado['tipo']}")
    print(f"   • Autenticado: {estado['autenticado']}")
    print(f"   • Usando local: {estado['use_local']}")
    print(f"   • Mensaje: {estado['mensaje']}")
    if 'used_gb' in estado:
        print(f"   • Espacio usado: {estado['used_gb']} GB")
        print(f"   • Espacio total: {estado['total_gb']} GB")
        print(f"   • Espacio libre: {estado['free_gb']} GB")
    
    if not estado['use_local']:
        print("\n✅ Google Drive configurado correctamente!")
        print("📤 Las fotos y facturas se subirán a Google Drive")
    else:
        print("\n⚠️ Google Drive NO configurado")
        print("📁 Usando almacenamiento LOCAL")
    
    print("\n" + "=" * 60)
