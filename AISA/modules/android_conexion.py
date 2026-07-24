import asyncio
import json
import logging
import threading
import time
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

class AndroidConexion:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.is_running = False
        self.loop = None
        self.thread = None
        self.server = None
        
    def iniciar(self):
        """Inicia el servidor WebSocket en un hilo separado"""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._ejecutar_servidor, daemon=True)
        self.thread.start()
        print(f"📱 Servidor Android iniciado en ws://{self.host}:{self.port}")
        
    def _ejecutar_servidor(self):
        """Ejecuta el servidor en un hilo separado con su propio event loop"""
        try:
            # Crear nuevo event loop para este hilo
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Iniciar servidor
            self.server = self.loop.run_until_complete(
                websockets.serve(self._manejar_cliente, self.host, self.port)
            )
            
            print(f"✅ Servidor WebSocket escuchando en ws://{self.host}:{self.port}")
            
            # Mantener el loop en ejecución
            self.loop.run_forever()
            
        except Exception as e:
            print(f"❌ Error en servidor WebSocket: {e}")
            self.is_running = False
        finally:
            if self.loop and not self.loop.is_closed():
                self.loop.close()
            
    async def _manejar_cliente(self, websocket, path):
        """Maneja la conexión de un cliente"""
        client_id = f"android_{int(time.time())}"
        print(f"📱 Nuevo cliente conectado: {client_id}")
        self.clients.add(websocket)
        
        # Enviar mensaje de bienvenida
        try:
            await websocket.send(json.dumps({
                "tipo": "bienvenida",
                "mensaje": "Conectado al asistente AIsa",
                "timestamp": datetime.now().isoformat()
            }))
        except:
            pass
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    print(f"📨 Mensaje de {client_id}: {data}")
                    
                    respuesta = await self._procesar_mensaje(data)
                    if respuesta:
                        await websocket.send(json.dumps(respuesta))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "tipo": "error",
                        "mensaje": "Formato JSON inválido"
                    }))
                except Exception as e:
                    print(f"❌ Error procesando mensaje: {e}")
                    
        except ConnectionClosed:
            print(f"📱 Cliente {client_id} desconectado")
        except Exception as e:
            print(f"❌ Error con cliente {client_id}: {e}")
        finally:
            self.clients.discard(websocket)
            
    async def _procesar_mensaje(self, data):
        """Procesa los mensajes recibidos"""
        tipo = data.get("tipo", "desconocido")
        
        if tipo == "ping":
            return {"tipo": "pong", "timestamp": datetime.now().isoformat()}
            
        elif tipo == "mensaje":
            texto = data.get("texto", "")
            return {
                "tipo": "respuesta_mensaje",
                "texto": f"Recibido: {texto}",
                "timestamp": datetime.now().isoformat()
            }
            
        elif tipo == "comando":
            comando = data.get("comando", "")
            return {
                "tipo": "respuesta_comando",
                "comando": comando,
                "estado": "recibido",
                "timestamp": datetime.now().isoformat()
            }
            
        else:
            return {
                "tipo": "respuesta",
                "mensaje": f"Tipo no reconocido: {tipo}"
            }
            
    def enviar_a_android(self, mensaje):
        """Envía un mensaje a todos los clientes Android"""
        if not self.is_running or not self.clients:
            return False
            
        try:
            for websocket in list(self.clients):
                try:
                    asyncio.run_coroutine_threadsafe(
                        websocket.send(json.dumps(mensaje)),
                        self.loop
                    )
                except Exception as e:
                    print(f"❌ Error enviando a cliente: {e}")
            return True
        except Exception as e:
            print(f"❌ Error al enviar mensaje: {e}")
            return False
            
    def detener(self):
        """Detiene el servidor"""
        self.is_running = False
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        print("🛑 Servidor Android detenido")
    
    def clientes_conectados(self):
        """Devuelve el número de clientes conectados"""
        return len(self.clients)
    
    def obtener_estado(self):
        """Devuelve el estado del servidor"""
        return {
            "activo": self.is_running,
            "puerto": self.port,
            "clientes": len(self.clients),
            "clients": list(self.clients) if self.clients else []
        }

# ============================================
# INSTANCIA GLOBAL
# ============================================

_instancia = None

def get_android_conexion():
    global _instancia
    if _instancia is None:
        _instancia = AndroidConexion()
    return _instancia