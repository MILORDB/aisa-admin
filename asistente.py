import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.memoria import MemoriaAsistente
from core.deepseek import preguntar
from core.contexto import ContextoConversacion
from core.intencion import ClasificadorIntencion
from modules import get_android_conexion

class Asistente:
    def __init__(self):
        self.memoria = MemoriaAsistente()
        self.contexto = ContextoConversacion()
        self.clasificador = ClasificadorIntencion()
        self.nombre = self.memoria.obtener_nombre()
        self.usuario = self.memoria.obtener_usuario()
        
        # Iniciar módulo Android
        try:
            self.android = get_android_conexion()
            self.android.iniciar()
            print(f"📱 Servidor Android en: ws://localhost:8765")
        except Exception as e:
            print(f"⚠️ Error al iniciar módulo Android: {e}")
            self.android = None
        
        print("=" * 60)
        print(f"🤖 {self.nombre} - Asistente Inteligente")
        print("=" * 60)
    
    def responder(self, texto):
        intencion = self.clasificador.clasificar(texto)
        print(f"🎯 Intención: {intencion}")
        
        contexto = self.contexto.obtener_contexto()
        respuesta = preguntar(texto, self.memoria, contexto)
        self.contexto.agregar(texto, respuesta)
        self.memoria.guardar_conversacion(texto, respuesta)
        
        # Enviar a Android si está disponible
        if self.android and self.android.clients:
            self.android.enviar_a_android({
                "tipo": "respuesta",
                "texto": respuesta,
                "timestamp": time.time()
            })
        
        return respuesta
    
    def modo_texto(self):
        print("\n📝 Escribe 'salir' para terminar")
        print("-" * 40)
        
        while True:
            try:
                texto = input("Tú: ").strip()
                if texto.lower() in ["salir", "exit"]:
                    print(f"👋 ¡Hasta luego!")
                    break
                if not texto:
                    continue
                
                print("🧠 Pensando...")
                respuesta = self.responder(texto)
                print(f"🤖 {self.nombre}: {respuesta}")
                
            except KeyboardInterrupt:
                print("\n👋 ¡Hasta luego!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def modo_android(self):
        print("\n📱 Servidor Android ejecutándose...")
        print("   Esperando conexiones en: ws://localhost:8765")
        print("   Presiona Ctrl+C para detener")
        
        try:
            while True:
                time.sleep(3)
                if self.android and self.android.clients:
                    print(f"📱 Clientes conectados: {len(self.android.clients)}")
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo servidor...")
            if self.android:
                self.android.detener()

def main():
    import sys
    asistente = Asistente()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--android":
        asistente.modo_android()
    else:
        asistente.modo_texto()

if __name__ == "__main__":
    main()