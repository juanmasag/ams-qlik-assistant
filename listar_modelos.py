from src.config_manager import cargar_config
from google import genai

print("Cargando configuración...")
config = cargar_config()
api_key = config.get("GEMINI_API_KEY")

if not api_key:
    print("❌ No se encontró la API KEY.")
else:
    print("Conectando con Google Gemini...")
    client = genai.Client(api_key=api_key)
    
    print("\n--- MODELOS DISPONIBLES EN TU CUENTA ---")
    try:
        for m in client.models.list():
            # Filtramos para que solo muestre los modelos que generan texto/contenido
            if "generateContent" in m.supported_actions:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error al buscar modelos: {e}")
    print("----------------------------------------\n")