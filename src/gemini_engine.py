import os
import time
import json
from google import genai
from google.genai import types

from src.config_manager import cargar_config
from src.video_splitter import dividir_video

# ==========================================
# 1. CONSTANTES GLOBALES Y CONFIGURACIÓN
# ==========================================

CONTEXTOS = {
    "AMS": "Actúa como un Consultor Senior de BI y Analista Funcional experto en AMS. Tu objetivo es analizar la reunión, enfocado en la lógica de negocio, requerimientos funcionales, KPIs, tablas y filtros. NO transcribas código fuente, explica su función.",
    "GENERAL": "Actúa como un Business Analyst experto. Tu objetivo es analizar esta reunión general, extraer los requerimientos, acuerdos principales y próximos pasos. Mantén un tono profesional y corporativo."
}

MODELOS_A_PROBAR = [
    'gemini-2.5-pro',
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-2.5-flash-lite',
    'gemini-flash-lite-latest'
]

# ==========================================
# 2. CARGA PEREZOSA (LAZY LOADING)
# ==========================================

def obtener_cliente_gemini():
    config = cargar_config()
    api_key = config.get("GEMINI_API_KEY", "").strip()
    
    if not api_key or api_key == "CLAVE_FALSA_PARA_PASAR":
        raise ValueError("API_KEY_FALTANTE: Configura una API Key válida en el Onboarding.")
        
    return genai.Client(api_key=api_key)

# ==========================================
# 3. INTERACCIÓN CON LA API (CON REINTENTOS)
# ==========================================

def procesar_video_gemini(ruta_video, callback_ui=None):
    client = obtener_cliente_gemini()
    
    if callback_ui: callback_ui("log", f"☁️ Subiendo a la nube: {os.path.basename(ruta_video)}...")
    video_file = client.files.upload(file=ruta_video)
    
    if callback_ui: callback_ui("log", "⚙️ Procesando internamente en servidores de Google...")
    while video_file.state.name == "PROCESSING":
        time.sleep(5)
        video_file = client.files.get(name=video_file.name)
        
    if video_file.state.name == "FAILED":
        raise ValueError(f"❌ El procesamiento del video en la nube falló: {ruta_video}")
        
    return video_file

def generar_minuta_ia(video_file, ticket_context=None, contexto_previo="", callback_ui=None):
    client = obtener_cliente_gemini()
    config = cargar_config()
    perfil_activo = config.get("PERFIL_ACTIVO", "GENERAL")
    contexto_base = CONTEXTOS.get(perfil_activo, CONTEXTOS["GENERAL"])
    info_ticket = f"\nTicket: {ticket_context.get('ID Ticket', '')} - {ticket_context.get('Título', '')}" if ticket_context else ""
    
    prompt = f"""
    ### ROLE & OBJECTIVE
    {contexto_base}
    {info_ticket}
    {contexto_previo}
    
    ### 🚨 REGLA CRÍTICA DE CERO ALUCINACIÓN (ANTI-FAKE)
    Si en el video NO se habla de temas de negocio, no hay diálogo relevante, o parece ser solo una prueba de grabación/técnica, ESTÁ ESTRICTAMENTE PROHIBIDO inventar, deducir o simular información basándote únicamente en el título del ticket.
    Si el video carece de contenido real de reunión, debes llenar TODOS los campos de texto con la frase exacta: "Sin contenido de negocio detectado en la grabación." y dejar la FAQ vacía. No pidas disculpas ni des explicaciones, solo pon esa frase.
    
    ### TAREA Y REGLAS
    1. Genera la minuta enfocada en el análisis funcional (si aplica).
    2. INSTRUCCIÓN MULTIMODAL CRÍTICA (PARTICIPANTES): Analiza visualmente los frames del video. Haz OCR sobre las etiquetas de texto en las cámaras. Excluye al consultor.
    3. INSTRUCCIÓN "COMENTARIO DE CABECERA" (COMENT_V): Define el tema central a tratar usando un MÁXIMO DE 5 PALABRAS.
    4. INSTRUCCIÓN "MINUTA" (REUNION_INFO): Redacta el resumen detallado de la reunión.
    5. INSTRUCCIÓN "FAQ Y TERMINOLOGÍA" (QUIRÚRGICA Y MINIMALISTA):
       A. TERMINOLOGÍA DE NEGOCIO: Extrae SOLO conceptos exclusivos del negocio agropecuario o métricas.
       B. FAQ ENFOCADA EN EL ISSUE: Genera máximo 3 preguntas/respuestas.
    6. Devuelve ESTRICTAMENTE un formato JSON válido.

    ### JSON STRUCTURE
    {{
      "OBJETIVO": "...",
      "PARTICIPANTES": "...",
      "REUNION_INFO": "...",
      "COMENT_V": "...",
      "FAQ": "AQUÍ SOLO EL TEXTO FORMATEADO de la terminología de negocio y las 3 FAQ críticas del Issue."
    }}
    """
    
    for modelo in MODELOS_A_PROBAR:
        if callback_ui: callback_ui("log", f"🤖 Intentando análisis con: {modelo}...")
        for intento in range(3):
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=[prompt, video_file],
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                if callback_ui: callback_ui("log", f"✅ Análisis exitoso con {modelo}.")
                return response.text
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg: 
                    break 
                if "429" in error_msg or "503" in error_msg:
                    if intento < 2:
                        if callback_ui: callback_ui("log", f"⏳ {modelo} saturado (Intento {intento+1}/3). Esperando 20s...")
                        time.sleep(20)
                        continue
                    else:
                        break 
                else:
                    raise e 

    raise Exception("❌ Ninguno de los modelos habilitados pudo procesar el fragmento tras múltiples reintentos.")

def consolidar_faqs(lista_faqs, callback_ui=None):
    if not lista_faqs: return ""
    
    # 🛡️ NUEVO ESCUDO ANTI-ALUCINACIÓN DE FORMATO: 
    # Sanitizar lista_faqs para asegurar que todo sea texto antes de usar .strip()
    faqs_limpias = []
    for f in lista_faqs:
        if isinstance(f, list):
            # Si Gemini se confundió y mandó una lista, la unimos en un texto
            texto = "\n".join(str(item) for item in f)
        else:
            # Si mandó texto (lo correcto) o cualquier otra cosa, lo forzamos a texto
            texto = str(f)
            
        if texto.strip():
            faqs_limpias.append(texto)

    if not faqs_limpias: return ""
    if len(faqs_limpias) == 1: return faqs_limpias[0]

    if callback_ui: callback_ui("log", "🔗 Consolidando inteligentemente las secciones de FAQ...")
    client = obtener_cliente_gemini()
    texto_combinado = "\n\n--- PARTE --- \n\n".join(faqs_limpias)
    
    prompt = f"""
    Eres un Business Analyst experto. A continuación tienes varias secciones de "FAQ y Terminología" extraídas de diferentes partes de una misma reunión:
    {texto_combinado}
    TAREA: Unifica todo este contenido en un ÚNICO bloque cohesivo. FORMATO Y ESTRUCTURA ESTRICTA:
    
    ### TERMINOLOGÍA DE NEGOCIO
    * **[Término 1]:** [Definición unificada].
    
    ### FAQ ENFOCADA EN EL ISSUE
    1. **[Pregunta 1]**
       * **Respuesta:** [Respuesta unificada].

    REGLAS ESTRICTAS:
    1. Fusiona los conceptos repetidos.
    2. Mantén máximo 3-4 términos y 3 preguntas clave.
    3. PROHIBIDO agregar términos IT estándar.
    4. Devuelve ÚNICAMENTE el texto final formateado, sin bloques de código ``` ni JSON.
    """
    
    for modelo in MODELOS_A_PROBAR:
        for intento in range(3):
            try:
                response = client.models.generate_content(model=modelo, contents=[prompt])
                return response.text.replace("```markdown", "").replace("```", "").strip()
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg: break
                if "429" in error_msg or "503" in error_msg:
                    if intento < 2:
                        time.sleep(20)
                        continue
                    else: break
                else: raise e
                    
    return "\n\n".join(faqs_limpias)

# ==========================================
# 4. ORQUESTADOR PRINCIPAL
# ==========================================

def analizar_video_con_gemini(ruta_original, callback_ui=None, ticket_context=None):
    if callback_ui: callback_ui("log", "✂️ Dividiendo video en fragmentos de 15 min...")
    chunks = dividir_video(ruta_original, minutos_por_chunk=15)
    
    minuta_consolidada = {
        "OBJETIVO": "",
        "PARTICIPANTES": [],
        "REUNION_INFO": "",
        "COMENT_V": "",
        "FAQ": ""
    }
    faqs_parciales = []
    
    for i, chunk in enumerate(chunks):
        if callback_ui: callback_ui("gemini_progreso", f"Analizando fragmento {i+1} de {len(chunks)}...")
        
        video_file = procesar_video_gemini(chunk, callback_ui)
        
        contexto_previo = ""
        if minuta_consolidada["REUNION_INFO"]:
            contexto_previo = f"Contexto de la parte anterior para continuidad:\n{minuta_consolidada['REUNION_INFO'][-1500:]}"
            
        raw_json = generar_minuta_ia(video_file, ticket_context, contexto_previo, callback_ui)
        
        clean_json = raw_json.strip().strip('`')
        if clean_json.startswith('json\n'): clean_json = clean_json[5:]
        
        try:
            data = json.loads(clean_json)
        except json.JSONDecodeError as e:
            if callback_ui: callback_ui("log", f"⚠️ Error al parsear JSON del fragmento {i+1}. Saltando.")
            continue
            
        if not minuta_consolidada["OBJETIVO"] and data.get("OBJETIVO"):
            minuta_consolidada["OBJETIVO"] = data["OBJETIVO"]
            
        if data.get("PARTICIPANTES"):
            nuevos_participantes = [p.strip() for p in data["PARTICIPANTES"].split(",") if p.strip()]
            for p in nuevos_participantes:
                if p not in minuta_consolidada["PARTICIPANTES"]:
                    minuta_consolidada["PARTICIPANTES"].append(p)
                    
        if data.get("REUNION_INFO"):
            minuta_consolidada["REUNION_INFO"] += f"\n\n{data['REUNION_INFO']}".strip()
            
        if not minuta_consolidada["COMENT_V"] and data.get("COMENT_V"):
            minuta_consolidada["COMENT_V"] = data["COMENT_V"].strip()
            
        if data.get("FAQ"):
            faqs_parciales.append(data["FAQ"])

    minuta_consolidada["PARTICIPANTES"] = ", ".join(minuta_consolidada["PARTICIPANTES"])
    
    if faqs_parciales:
        minuta_consolidada["FAQ"] = consolidar_faqs(faqs_parciales, callback_ui)
        
    if callback_ui: callback_ui("log", "✅ Análisis de todos los fragmentos completado con éxito.")
    return minuta_consolidada