import json
import os
import threading
from datetime import datetime

# Buscamos la raíz del proyecto para ubicar la carpeta de datos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
COLA_PATH = os.path.join(DATA_DIR, "pendientes.json")

# 🛡️ FIX DEADLOCK: Usamos RLock (Reentrant Lock) para que el mismo hilo pueda entrar varias veces
_lock = threading.RLock()

def _asegurar_directorio():
    """Se asegura de que la carpeta 'data' exista."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def obtener_cola_inicial():
    """Estructura base para el archivo de cola."""
    return []

def cargar_cola():
    """Carga el JSON de la cola o crea uno inicial si no existe."""
    _asegurar_directorio()
    with _lock:
        if not os.path.exists(COLA_PATH):
            cola = obtener_cola_inicial()
            _guardar_cola_interno(cola)
            return cola
        
        try:
            with open(COLA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Si el archivo se corrompe, lo iniciamos de nuevo
            return obtener_cola_inicial()

def _guardar_cola_interno(cola):
    """Guarda la cola en el archivo JSON (Solo debe llamarse cuando ya se tiene el lock)."""
    with open(COLA_PATH, "w", encoding="utf-8") as f:
        json.dump(cola, f, indent=4, ensure_ascii=False)

def agregar_a_cola(ruta_video, ticket_data, custom_folder_id, perfil, estado_inicial="pendiente", url_drive=""):
    """Agrega un nuevo video a la lista de pendientes con soporte para checkpoints."""
    with _lock:
        cola = cargar_cola()
        
        nuevo_item = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "fecha_agregado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ruta_video": ruta_video,
            "ticket_data": ticket_data,
            "custom_folder_id": custom_folder_id,
            "perfil": perfil,
            "estado": estado_inicial,  # Ej: pendiente, drive_ok_esperando_gemini, error
            "url_drive": url_drive,    # Guardamos el link si se pausó tras subir a Drive
            "mensaje_error": ""
        }
        
        cola.append(nuevo_item)
        _guardar_cola_interno(cola)
        return nuevo_item["id"]

def obtener_pendientes():
    """Retorna la lista de todos los videos que no han sido procesados con éxito."""
    cola = cargar_cola()
    # Ahora buscamos pendientes puros y los que se pausaron a mitad de camino (checkpoints)
    return [item for item in cola if item.get("estado") in ["pendiente", "drive_ok_esperando_gemini", "error"]]

def actualizar_estado_item(item_id, nuevo_estado, mensaje_error="", url_drive=None):
    """Actualiza el estado de un video en la cola y opcionalmente su link de Drive."""
    with _lock:
        cola = cargar_cola()
        for item in cola:
            if item.get("id") == item_id:
                item["estado"] = nuevo_estado
                if mensaje_error:
                    item["mensaje_error"] = str(mensaje_error)
                if url_drive is not None:
                    item["url_drive"] = url_drive
                break
        _guardar_cola_interno(cola)

def eliminar_item_cola(item_id):
    """Elimina un video de la cola (usualmente después de un procesamiento exitoso)."""
    with _lock:
        cola = cargar_cola()
        # Filtramos la cola para mantener todos menos el que queremos eliminar
        cola = [item for item in cola if item.get("id") != item_id]
        _guardar_cola_interno(cola)