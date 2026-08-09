# web_admin/storage.py

import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive.file']

class StorageManager:
    def __init__(self):
        self.drive_service = None
        self.use_local = True
        self.base_folder_id = None

        # ============================================
        # BUSCAR CREDENCIALES
        # ============================================
        self.credentials_file = None

        # 1. En Render: /etc/secrets/credentials.json
        if os.path.exists('/etc/secrets/credentials.json'):
            self.credentials_file = '/etc/secrets/credentials.json'
            print("📁 Credenciales en Render: /etc/secrets/credentials.json")
        # 2. En local: credentials.json
        elif os.path.exists('credentials.json'):
            self.credentials_file = 'credentials.json'
            print("📁 Credenciales locales: credentials.json")

        if not self.credentials_file or not os.path.exists(self.credentials_file):
            print("❌ No se encontró credentials.json")
            print("📁 Usando almacenamiento LOCAL")
            self.use_local = True
            return

        # ============================================
        # AUTENTICAR CON CUENTA DE SERVICIO
        # ============================================
        try:
            print(f"🔐 Autenticando con: {self.credentials_file}")

            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=SCOPES
            )

            self.drive_service = build('drive', 'v3', credentials=creds)
            self.use_local = False

            print("✅ Autenticación exitosa con Cuenta de Servicio")

            # ============================================
            # ⭐ SHARED DRIVE - ID DE TU UNIDAD COMPARTIDA
            # ============================================
            self.base_folder_id = '1vEJM_yYBWv0nB2inUsLqcvnm99gDufrm'
            print(f"📁 Usando Shared Drive con ID: {self.base_folder_id}")

            # Verificar acceso
            try:
                about = self.drive_service.about().get(fields="storageQuota").execute()
                print("✅ Acceso a Google Drive verificado")
            except Exception as e:
                print(f"⚠️ Error verificando acceso: {e}")

        except Exception as e:
            print(f"❌ Error en autenticación: {e}")
            self.drive_service = None
            self.use_local = True

    def _get_or_create_folder(self, path, parent_id=None):
        """
        Obtiene o crea una carpeta por su ruta (con soporte para Shared Drive)

        Args:
            path (str): Ruta de la carpeta (ej: "negocio_1/productos/producto_1")
            parent_id (str): ID de la carpeta padre (opcional)

        Returns:
            str: ID de la carpeta, o None si hay error
        """
        if not self.drive_service or self.use_local:
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

                print(f"📁 Buscando/creando carpeta: {part} (padre: {current_parent})")

                # Buscar carpeta con este nombre
                query = f"name='{part}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = self.drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name)',
                    supportsAllDrives=True,  # ⭐ SOPORTE PARA SHARED DRIVE
                    includeItemsFromAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                ).execute()

                folders = results.get('files', [])

                if not folders:
                    # Crear carpeta
                    file_metadata = {
                        'name': part,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_parent]
                    }
                    folder = self.drive_service.files().create(
                        body=file_metadata,
                        fields='id',
                        supportsAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                    ).execute()
                    current_parent = folder.get('id')
                    print(f"✅ Carpeta creada: {part} (ID: {current_parent})")
                else:
                    current_parent = folders[0]['id']
                    print(f"✅ Carpeta encontrada: {part} (ID: {current_parent})")

            return current_parent

        except Exception as e:
            print(f"❌ Error creando carpeta {path}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def subir_foto_producto(self, negocio_id, producto_id, archivo_foto, nombre_foto):
        """
        Sube una foto de producto a Google Drive (Shared Drive)

        Args:
            negocio_id (int): ID del negocio
            producto_id (int): ID del producto
            archivo_foto: Archivo de imagen (objeto FileStorage)
            nombre_foto (str): Nombre del archivo

        Returns:
            bool: True si se subió correctamente
        """
        print("=" * 60)
        print("📤 INICIANDO SUBIDA DE FOTO A SHARED DRIVE")
        print(f"   Negocio ID: {negocio_id}")
        print(f"   Producto ID: {producto_id}")
        print(f"   Nombre: {nombre_foto}")
        print(f"   Base Folder ID: {self.base_folder_id}")
        print("=" * 60)

        if self.use_local or not self.drive_service:
            print("📁 Usando almacenamiento LOCAL (fallback)")
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)

        try:
            # ============================================
            # PASO 1: Crear estructura de carpetas
            # ============================================
            folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
            print(f"📁 Creando estructura de carpetas: {folder_path}")

            folder_id = self._get_or_create_folder(folder_path)

            if not folder_id:
                print("❌ No se pudo crear carpeta en Google Drive, usando local")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)

            print(f"✅ Carpeta destino ID: {folder_id}")

            # ============================================
            # PASO 2: Guardar archivo temporalmente
            # ============================================
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, nombre_foto)

            print(f"📁 Guardando archivo temporal en: {temp_path}")
            archivo_foto.save(temp_path)

            if not os.path.exists(temp_path):
                print(f"❌ Error: No se pudo guardar el archivo temporal")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)

            file_size = os.path.getsize(temp_path)
            print(f"📊 Tamaño del archivo: {file_size} bytes")

            # ============================================
            # PASO 3: Subir a Google Drive (Shared Drive)
            # ============================================
            mime_type = 'image/jpeg'
            if nombre_foto.lower().endswith('.png'):
                mime_type = 'image/png'
            elif nombre_foto.lower().endswith('.gif'):
                mime_type = 'image/gif'
            elif nombre_foto.lower().endswith('.webp'):
                mime_type = 'image/webp'

            print(f"📤 Subiendo archivo a Google Drive...")
            print(f"   MIME Type: {mime_type}")

            file_metadata = {
                'name': nombre_foto,
                'parents': [folder_id]
            }

            media = MediaFileUpload(temp_path, mimetype=mime_type, resumable=True)

            try:
                file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink, webContentLink',
                    supportsAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                ).execute()

                file_id = file.get('id')
                print(f"✅ Archivo subido a Google Drive (ID: {file_id})")

            except HttpError as e:
                print(f"❌ Error HTTP en Google Drive: {e}")
                print(f"   Respuesta: {e.content}")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)
            except Exception as e:
                print(f"❌ Error en subida a Google Drive: {e}")
                import traceback
                traceback.print_exc()
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)

            # ============================================
            # PASO 4: Eliminar archivo temporal
            # ============================================
            if os.path.exists(temp_path):
                os.remove(temp_path)
                print(f"🗑️ Archivo temporal eliminado: {temp_path}")

            if file_id:
                print(f"✅ Foto subida exitosamente a Google Drive: {nombre_foto} (ID: {file_id})")
                return True
            else:
                print("❌ Error subiendo a Google Drive - No se recibió ID")
                return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)

        except Exception as e:
            print(f"❌ Error subiendo a Google Drive: {e}")
            import traceback
            traceback.print_exc()
            return self._guardar_local(negocio_id, producto_id, archivo_foto, nombre_foto)

    def obtener_url_foto(self, negocio_id, producto_id, nombre_foto, file_id=None):
        """
        Obtiene la URL pública de una foto de producto

        Args:
            negocio_id (int): ID del negocio
            producto_id (int): ID del producto
            nombre_foto (str): Nombre del archivo
            file_id (str): ID del archivo en Google Drive (opcional)

        Returns:
            str: URL de la foto
        """
        if self.use_local or not self.drive_service:
            return self._url_local(negocio_id, producto_id, nombre_foto)

        try:
            if file_id:
                file = self.drive_service.files().get(
                    fileId=file_id,
                    fields='webViewLink, webContentLink',
                    supportsAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                ).execute()
                return file.get('webViewLink') or file.get('webContentLink')
            else:
                # Buscar el archivo por nombre
                folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
                folder_id = self._get_or_create_folder(folder_path)

                if not folder_id:
                    return self._url_local(negocio_id, producto_id, nombre_foto)

                results = self.drive_service.files().list(
                    q=f"name='{nombre_foto}' and '{folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='files(id, webViewLink, webContentLink)',
                    supportsAllDrives=True,  # ⭐ SOPORTE PARA SHARED DRIVE
                    includeItemsFromAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                ).execute()

                files = results.get('files', [])

                if files:
                    return files[0].get('webViewLink') or files[0].get('webContentLink')

            return self._url_local(negocio_id, producto_id, nombre_foto)

        except Exception as e:
            print(f"❌ Error obteniendo URL: {e}")
            return self._url_local(negocio_id, producto_id, nombre_foto)

    def obtener_file_id(self, negocio_id, producto_id, nombre_foto):
        """
        Obtiene el ID de un archivo en Google Drive

        Args:
            negocio_id (int): ID del negocio
            producto_id (int): ID del producto
            nombre_foto (str): Nombre del archivo

        Returns:
            str: ID del archivo, o None si no se encuentra
        """
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
                fields='files(id)',
                supportsAllDrives=True,  # ⭐ SOPORTE PARA SHARED DRIVE
                includeItemsFromAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
            ).execute()

            files = results.get('files', [])

            if files:
                return files[0]['id']
            return None

        except Exception as e:
            print(f"❌ Error obteniendo file ID: {e}")
            return None

    def _guardar_local(self, negocio_id, producto_id, archivo, nombre_foto):
        """Guarda la foto en el sistema de archivos local (fallback)"""
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
        """Genera la URL local de una foto"""
        return f"/static/uploads/productos/negocio_{negocio_id}/producto_{producto_id}/{nombre_foto}"

    def guardar_factura(self, negocio_id, factura_id, archivo_pdf):
        """
        Guarda una factura en Google Drive

        Args:
            negocio_id (int): ID del negocio
            factura_id (int): ID de la factura
            archivo_pdf: Archivo PDF (objeto FileStorage)

        Returns:
            bool: True si se guardó correctamente
        """
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
                fields='id',
                supportsAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
            ).execute()

            if os.path.exists(temp_path):
                os.remove(temp_path)

            print(f"✅ Factura subida a Google Drive: {nombre}")
            return True

        except Exception as e:
            print(f"❌ Error subiendo factura: {e}")
            return self._guardar_local_factura(negocio_id, factura_id, archivo_pdf)

    def _guardar_local_factura(self, negocio_id, factura_id, archivo_pdf):
        """Guarda una factura en el sistema de archivos local (fallback)"""
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
        """
        Elimina una foto de producto de Google Drive y local

        Args:
            negocio_id (int): ID del negocio
            producto_id (int): ID del producto
            nombre_foto (str): Nombre del archivo
            file_id (str): ID del archivo en Google Drive (opcional)

        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            # Eliminar de local
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

            # Eliminar de Google Drive
            if file_id:
                self.drive_service.files().delete(
                    fileId=file_id,
                    supportsAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                ).execute()
                print(f"✅ Foto eliminada de Google Drive: {nombre_foto}")
                return True
            else:
                # Buscar el archivo por nombre
                folder_path = f"negocio_{negocio_id}/productos/producto_{producto_id}"
                folder_id = self._get_or_create_folder(folder_path)

                if folder_id:
                    results = self.drive_service.files().list(
                        q=f"name='{nombre_foto}' and '{folder_id}' in parents and trashed=false",
                        spaces='drive',
                        fields='files(id)',
                        supportsAllDrives=True,  # ⭐ SOPORTE PARA SHARED DRIVE
                        includeItemsFromAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                    ).execute()

                    files = results.get('files', [])

                    if files:
                        self.drive_service.files().delete(
                            fileId=files[0]['id'],
                            supportsAllDrives=True  # ⭐ SOPORTE PARA SHARED DRIVE
                        ).execute()
                        print(f"✅ Foto eliminada de Google Drive: {nombre_foto}")
                        return True

            return True

        except Exception as e:
            print(f"❌ Error eliminando foto: {e}")
            return True

    def obtener_estado(self):
        """
        Obtiene el estado del almacenamiento

        Returns:
            dict: Estado del almacenamiento
        """
        estado = {
            'tipo': 'Google Drive' if not self.use_local else 'Local',
            'autenticado': self.drive_service is not None,
            'use_local': self.use_local,
            'base_folder_id': self.base_folder_id,
            'mensaje': '📁 Usando almacenamiento local'
        }

        if self.drive_service and not self.use_local:
            if self.base_folder_id:
                estado['mensaje'] = "✅ Conectado a Google Drive (Shared Drive)"
            else:
                estado['mensaje'] = "✅ Conectado a Google Drive (carpeta base pendiente)"

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
                    estado['mensaje'] = "✅ Conectado a Google Drive (Shared Drive)"
            except Exception as e:
                print(f"⚠️ Error obteniendo cuota: {e}")
                estado['mensaje'] = "✅ Conectado a Google Drive (Shared Drive)"

        return estado


# ============================================
# INSTANCIA GLOBAL
# ============================================

_storage_instance = None

def get_storage_manager():
    """Obtiene la instancia global del StorageManager (Singleton)"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance


# ============================================
# PRUEBA DIRECTA
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🔍 PRUEBA DE ALMACENAMIENTO - GOOGLE DRIVE SHARED DRIVE")
    print("=" * 60)

    storage = get_storage_manager()
    estado = storage.obtener_estado()

    print(f"\n📁 Estado del almacenamiento:")
    for key, value in estado.items():
        print(f"   • {key}: {value}")

    if not estado['use_local']:
        print("\n✅ Google Drive configurado correctamente!")
        print("📤 Las fotos y facturas se subirán al Shared Drive")
    else:
        print("\n⚠️ Google Drive NO configurado")
        print("📁 Usando almacenamiento LOCAL")

    print("\n" + "=" * 60)
