import os
import json
import requests
from datetime import datetime
import base64

class StorageManager:
    """Gestor de almacenamiento en la nube para cada negocio"""
    
    def __init__(self, provider='terabox'):
        self.provider = provider
        self.base_url = "https://terabox.com/api/"
        self.cookie = os.environ.get('TERABOX_COOKIE', '')
        
    def get_negocio_path(self, negocio_id):
        """Obtiene la ruta base para un negocio"""
        return f"Negocios/negocio_{negocio_id}"
    
    def get_facturas_path(self, negocio_id):
        """Obtiene la ruta de facturas para un negocio"""
        return f"{self.get_negocio_path(negocio_id)}/facturas"
    
    def get_productos_path(self, negocio_id):
        """Obtiene la ruta de productos para un negocio"""
        return f"{self.get_negocio_path(negocio_id)}/productos"
    
    def get_producto_path(self, negocio_id, producto_id):
        """Obtiene la ruta de un producto específico"""
        return f"{self.get_productos_path(negocio_id)}/producto_{producto_id}"
    
    def crear_carpeta_negocio(self, negocio_id):
        """Crea la estructura de carpetas para un nuevo negocio"""
        paths = [
            self.get_negocio_path(negocio_id),
            self.get_facturas_path(negocio_id),
            self.get_productos_path(negocio_id),
        ]
        resultados = []
        for path in paths:
            resultado = self._crear_carpeta(path)
            resultados.append(resultado)
        return all(resultados)
    
    def guardar_factura(self, negocio_id, factura_id, archivo_pdf):
        """Guarda una factura en la carpeta del negocio"""
        path = f"{self.get_facturas_path(negocio_id)}/factura_{factura_id}.pdf"
        return self._subir_archivo(archivo_pdf, path)
    
    def subir_foto_producto(self, negocio_id, producto_id, archivo_foto, nombre_foto="foto_principal.jpg"):
        """Sube una foto para un producto"""
        path = f"{self.get_producto_path(negocio_id, producto_id)}/{nombre_foto}"
        return self._subir_archivo(archivo_foto, path)
    
    def obtener_url_foto(self, negocio_id, producto_id, nombre_foto="foto_principal.jpg"):
        """Obtiene la URL pública de una foto de producto"""
        path = f"{self.get_producto_path(negocio_id, producto_id)}/{nombre_foto}"
        return self._obtener_url(path)
    
    def obtener_facturas(self, negocio_id):
        """Lista todas las facturas de un negocio"""
        path = self.get_facturas_path(negocio_id)
        return self._listar_archivos(path)
    
    def _crear_carpeta(self, path):
        """Crea una carpeta en el almacenamiento"""
        if self.provider == 'terabox':
            return self._terabox_crear_carpeta(path)
        elif self.provider == 'googledrive':
            return self._gdrive_crear_carpeta(path)
        return False
    
    def _subir_archivo(self, archivo, path):
        """Sube un archivo al almacenamiento"""
        if self.provider == 'terabox':
            return self._terabox_subir_archivo(archivo, path)
        elif self.provider == 'googledrive':
            return self._gdrive_subir_archivo(archivo, path)
        return False
    
    def _obtener_url(self, path):
        """Obtiene la URL pública de un archivo"""
        if self.provider == 'terabox':
            return self._terabox_obtener_url(path)
        elif self.provider == 'googledrive':
            return self._gdrive_obtener_url(path)
        return None
    
    def _listar_archivos(self, path):
        """Lista archivos en una carpeta"""
        if self.provider == 'terabox':
            return self._terabox_listar(path)
        elif self.provider == 'googledrive':
            return self._gdrive_listar(path)
        return []
    
    # ============================================
    # MÉTODOS PARA TERABOX
    # ============================================
    
    def _terabox_crear_carpeta(self, path):
        """Crea carpeta en TeraBox usando la API"""
        try:
            # Usar terabox-gateway o API directa
            url = f"{self.base_url}create_folder"
            headers = {'Cookie': self.cookie}
            data = {'path': path}
            response = requests.post(url, headers=headers, json=data)
            return response.status_code == 200
        except Exception as e:
            print(f"Error creando carpeta: {e}")
            return False
    
    def _terabox_subir_archivo(self, archivo, path):
        """Sube archivo a TeraBox"""
        try:
            url = f"{self.base_url}upload"
            headers = {'Cookie': self.cookie}
            files = {'file': archivo}
            data = {'path': path}
            response = requests.post(url, headers=headers, data=data, files=files)
            return response.status_code == 200
        except Exception as e:
            print(f"Error subiendo archivo: {e}")
            return False
    
    def _terabox_obtener_url(self, path):
        """Obtiene URL de un archivo en TeraBox"""
        try:
            url = f"{self.base_url}get_file_url"
            headers = {'Cookie': self.cookie}
            data = {'path': path}
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json().get('url')
            return None
        except Exception as e:
            print(f"Error obteniendo URL: {e}")
            return None
    
    def _terabox_listar(self, path):
        """Lista archivos en TeraBox"""
        try:
            url = f"{self.base_url}list_files"
            headers = {'Cookie': self.cookie}
            data = {'path': path}
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json().get('files', [])
            return []
        except Exception as e:
            print(f"Error listando archivos: {e}")
            return []
    
    # ============================================
    # MÉTODOS PARA GOOGLE DRIVE
    # ============================================
    
    def _gdrive_crear_carpeta(self, path):
        """Crea carpeta en Google Drive (requiere PyDrive2)"""
        # Implementar con PyDrive2
        pass
    
    def _gdrive_subir_archivo(self, archivo, path):
        """Sube archivo a Google Drive"""
        # Implementar con PyDrive2
        pass
    
    def _gdrive_obtener_url(self, path):
        """Obtiene URL de Google Drive"""
        # Implementar con PyDrive2
        pass
    
    def _gdrive_listar(self, path):
        """Lista archivos en Google Drive"""
        # Implementar con PyDrive2
        pass