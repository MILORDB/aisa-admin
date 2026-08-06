# test_terabox.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web_admin.storage import get_storage_manager

def test_terabox():
    print("=" * 60)
    print("🔍 VERIFICANDO CONEXIÓN A TERABOX")
    print("=" * 60)
    
    storage = get_storage_manager()
    estado = storage.obtener_estado()
    
    print(f"\n📁 Estado del almacenamiento:")
    print(f"   • Tipo: {estado['tipo']}")
    print(f"   • Cookie configurada: {estado['cookie_configurada']}")
    print(f"   • Usando local: {estado['use_local']}")
    print(f"   • Cookie: {estado['cookie_preview']}")
    
    if not estado['use_local']:
        print("\n✅ TeraBox configurado correctamente!")
        print("📤 Las fotos se subirán a TeraBox")
    else:
        print("\n⚠️ TeraBox NO configurado")
        print("📁 Usando almacenamiento LOCAL")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_terabox()
