import os
import time
import json
from google import genai
from google.genai import types

# 1. IMPORTAMOS EL NUEVO GESTOR DE CONFIGURACIÓN
from src.config_manager import cargar_config

config = cargar_config()
API_KEY = config.get("GEMINI_API_KEY")
PERFIL_ACTIVO = config.get("PERFIL_ACTIVO", "GENERAL")

if not API_KEY:
    raise ValueError("❌ No se encontró la API Key en config.json. Ejecuta config_manager.py primero.")

# Inicializamos el cliente con la nueva Key
client = genai.Client(api_key=API_KEY)

# 2. DICCIONARIO DE CONTEXTOS POR ÁREA (MODULAR)
CONTEXTOS = {
    "AMS": "Actúa como un Consultor Senior de BI y Analista Funcional experto en AMS. Tu objetivo es analizar la reunión, enfocado en la lógica de negocio, requerimientos funcionales, KPIs, tablas y filtros. NO transcribas código fuente, explica su función.",
    "GENERAL": "Actúa como un Business Analyst experto. Tu objetivo es analizar esta reunión general, extraer los requerimientos, acuerdos principales y próximos pasos. Mantén un tono profesional y corporativo."
}

def procesar_video_gemini(ruta_video):
    """Sube el video a Gemini y espera a que el estado sea ACTIVE."""
    print(f"   Subiendo a la nube: {os.path.basename(ruta_video)}...")
    
    video_file = client.files.upload(file=ruta_video)
    
    print("   Procesando internamente", end="")
    while video_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(5)
        video_file = client.files.get(name=video_file.name)
        
    if video_file.state.name == "FAILED":
        raise ValueError("❌ El procesamiento del video en la nube falló.")
        
    print("\n   ✅ Listo.")
    return video_file

def generar_minuta_ia(video_file, ticket_context=None, contexto_previo=""):
    """Genera la minuta usando OCR visual y una sección de FAQ/Terminología profesional."""
    
    contexto_base = CONTEXTOS.get(PERFIL_ACTIVO, CONTEXTOS["GENERAL"])
    info_ticket = f"\nTicket: {ticket_context.get('ID Ticket', '')} - {ticket_context.get('Título', '')}" if ticket_context else ""
    
    prompt = f"""
    ### ROLE & OBJECTIVE
    {contexto_base}
    {info_ticket}
    {contexto_previo}
    
    ### TAREA Y REGLAS
    1. Genera la minuta enfocada en el análisis funcional.
    2. INSTRUCCIÓN MULTIMODAL CRÍTICA (PARTICIPANTES): Analiza visualmente los frames del video. Haz OCR sobre las etiquetas de texto en los recuadros de las cámaras. Excluye al consultor.
    
    3. INSTRUCCIÓN "FAQ Y TERMINOLOGÍA" (QUIRÚRGICA Y MINIMALISTA):
       A. TERMINOLOGÍA DE NEGOCIO: Extrae SOLO conceptos exclusivos del negocio agropecuario o métricas afectadas por el Issue (ej. "Período Comercial", "Cosecha", "Compras Acumuladas").
          - PROHIBIDO definir términos IT estándar (como API, Excel, QVD, ETL, etc.).
          - Para cada término incluir: Nombre, Definición operativa breve, y Regla de cálculo (solo si se discute).
       B. FAQ ENFOCADA EN EL ISSUE: Genera máximo 3 preguntas/respuestas que aborden DIRECTAMENTE el problema discutido (ej. datos duplicados, inconsistencias).
          - No inventes dudas genéricas de BI.
          - Las respuestas deben ir directo a la solución o regla acordada.

    4. Devuelve ESTRICTAMENTE un formato JSON válido.

    ### JSON STRUCTURE
    {{
      "OBJETIVO": "...",
      "PARTICIPANTES": "...",
      "MINUTA_DETALLE": "...",
      "COMENT_V": "...",
      "FAQ": "AQUÍ SOLO EL TEXTO FORMATEADO de la terminología de negocio (sin términos IT) y las 3 FAQ críticas del Issue."
    }}
    """
    
    modelos_a_probar = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-flash-latest']

    for modelo in modelos_a_probar:
        try:
            print(f"   🤖 Intentando con: {modelo}...")
            response = client.models.generate_content(
                model=modelo,
                contents=[prompt, video_file],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg: continue
            if "429" in error_msg or "503" in error_msg:
                print(f"   ⏳ Google saturado. Reintentando en 10s...")
                time.sleep(10)
                continue
            else:
                raise e

    raise Exception("❌ Ninguno de tus modelos habilitados pudo procesar el video.")

def consolidar_faqs(lista_faqs):
    """Consolida múltiples secciones de FAQ en un único bloque unificado y con formato estricto."""
    if not lista_faqs:
        return ""
    if len(lista_faqs) == 1:
        return lista_faqs[0]

    print("   🔗 Consolidando inteligentemente las secciones de FAQ...")
    
    texto_combinado = "\n\n--- PARTE --- \n\n".join([f for f in lista_faqs if f.strip()])
    
    prompt = f"""
    Eres un Business Analyst experto. A continuación tienes varias secciones de "FAQ y Terminología" extraídas de diferentes partes de una misma reunión:
    
    {texto_combinado}
    
    TAREA:
    Unifica todo este contenido en un ÚNICO bloque cohesivo.
    
    FORMATO Y ESTRUCTURA ESTRICTA:
    Debes devolver el texto EXACTAMENTE con esta estructura (usa los mismos títulos una sola vez):

    ### TERMINOLOGÍA DE NEGOCIO
    * **[Término 1]:** [Definición unificada].
    * **[Término 2]:** [Definición unificada].
    
    ### FAQ ENFOCADA EN EL ISSUE
    1. **[Pregunta 1]**
       * **Respuesta:** [Respuesta unificada].
    2. **[Pregunta 2]**
       * **Respuesta:** [Respuesta unificada].
    
    REGLAS ESTRICTAS:
    1. Fusiona los conceptos repetidos.
    2. Mantén máximo 3-4 términos y 3 preguntas clave.
    3. PROHIBIDO agregar términos IT estándar (API, QVD, etc.), solo mantén el negocio.
    4. Devuelve ÚNICAMENTE el texto final formateado, sin bloques de código ``` ni JSON.
    """
    
    modelos_a_probar = ['gemini-2.5-flash', 'gemini-2.0-flash']
    for modelo in modelos_a_probar:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=[prompt]
            )
            # Limpiamos posibles formatos extra residuales
            clean_text = response.text.replace("```markdown", "").replace("```", "").strip()
            return clean_text
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "503" in error_msg:
                time.sleep(5)
                continue
    
    return "\n\n".join(lista_faqs)