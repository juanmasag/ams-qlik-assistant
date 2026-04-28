import json
import os

# Buscamos la raíz del proyecto para ubicar el config.json
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def obtener_config_inicial():
    """Estructura base para el archivo de configuración."""
    return {
        "GEMINI_API_KEY": "",
        "PERFIL_ACTIVO": "AMS",
        "PERFILES": {
            "AMS": {
                "MODO": "AMS",
                "GOOGLE_SHEET": "AMS_BI_Assistant_Log",
                "TEMPLATE": "PLANTILLA_REQ.docx",
                "OUTPUT_PATH": ""
            },
            "GENERAL": {
                "MODO": "GENERAL",
                "GOOGLE_SHEET": None,
                "TEMPLATE": "PLANTILLA_REQ.docx",
                "OUTPUT_PATH": ""
            }
        },
        "RUTAS_LOCALES": {
            "RECORDINGS": "",
            "TEMPLATES": ""
        }
    }

def cargar_config():
    """Carga el JSON o crea uno inicial si no existe."""
    if not os.path.exists(CONFIG_PATH):
        config = obtener_config_inicial()
        guardar_config(config)
        return config
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_config(config):
    """Guarda los cambios en el archivo config.json."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def setup_interactivo():
    """Valida la configuración al inicio y guía al usuario paso a paso."""
    config = cargar_config()
    if not config.get("GEMINI_API_KEY"):
        print("\n" + "="*60)
        print(" 🔧 CONFIGURACIÓN INICIAL DETECTADA")
        print("="*60)
        print("\nPara que el asistente funcione, necesitas tu propia API KEY de Gemini.")
        print("Es gratuita y se genera en estos simples pasos:\n")
        print("  1. Entrá a: https://aistudio.google.com/app/apikey")
        print("  2. Ingresá con tu cuenta de Google corporativa.")
        print("  3. Hacé clic en el botón 'Crear clave de API'.")
        print("  4. En la ventana que se abre, podés dejar el nombre por defecto en 'Asigna un nombre a la clave'.")
        print("  5. En 'Elige un proyecto importado', dejalo como 'Default Gemini Project'.")
        print("  6. Hacé clic en el botón 'Crear clave'.")
        print("  7. En la última ventana, hacé clic en el botón 'Copiar' (el código empieza con 'AIza...').\n")
        
        key = input("🔑 Pegá tu API KEY aquí y dale Enter: ").strip()
        if key:
            config["GEMINI_API_KEY"] = key
            guardar_config(config)
            print("\n✅ ¡Excelente! Configuración guardada en config.json.")
        else:
            print("\n⚠️ No ingresaste ninguna clave. El sistema no podrá analizar los videos.")
    return config

# --- TEST DE FUNCIONAMIENTO ---
if __name__ == "__main__":
    setup_interactivo()