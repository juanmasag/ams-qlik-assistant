import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Buscando modelos disponibles para procesar contenido en tu cuenta...\n")
try:
    for model in client.models.list():
        # Filtramos para mostrar solo los que nos sirven (gemini)
        if "gemini" in model.name:
            print(f"✅ Habilitado: {model.name}")
except Exception as e:
    print(f"Error al listar: {e}")