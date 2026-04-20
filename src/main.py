import sys
import os
import re
import shutil
import json
from datetime import datetime
import unicodedata

# 1. PARCHE DE RUTAS: Le decimos a Python dónde está la raíz del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. Importamos nuestros módulos locales
from src.config_manager import cargar_config
from src.google_sheets import conectar_sheet, registrar_log
from src.gemini_engine import procesar_video_gemini, generar_minuta_ia, consolidar_faqs
from src.video_splitter import dividir_video
from src.folder_manager import crear_estructura_ticket, inicializar_documento_requerimiento
from src.doc_updater import actualizar_word_requerimiento

def sanitizar_nombre(texto):
    """Elimina acentos, eñes y caracteres inválidos para nombrar archivos de forma segura."""
    if not texto: return "Sin_Titulo"
    texto_limpio = ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\\/*?:"<>|]', "", texto_limpio).replace(" ", "_")

def asegurar_string(dato):
    """Convierte cualquier dato de la IA en string, manejando listas."""
    if isinstance(dato, list):
        return "\n".join([str(item) for item in dato])
    return str(dato) if dato else ""

def procesar_reunion(ruta_original, link_drive="", ticket_desde_gui=None, callback_ui=None):
    """
    Función Maestra: Orquesta la IA, los documentos y el log de Sheets.
    Recibe la ruta del video recién grabado y el link de Google Drive.
    """
    # 3. CARGAMOS LA CONFIGURACIÓN Y EL PERFIL ACTIVO
    config = cargar_config()
    PERFIL_ACTIVO = config.get("PERFIL_ACTIVO", "GENERAL")
    perfil_data = config["PERFILES"].get(PERFIL_ACTIVO, config["PERFILES"]["GENERAL"])
    
    sheet_name = perfil_data.get("GOOGLE_SHEET")
    
    if callback_ui: callback_ui("log", f"🎬 Procesando video local: {os.path.basename(ruta_original)}")

    sheet = conectar_sheet(sheet_name) if sheet_name else None

    # 4. SELECCIÓN DE TICKET (Ahora desde la GUI)
    if ticket_desde_gui:
        ticket_seleccionado = ticket_desde_gui
    else:
        # Fallback por si lo corrés a mano
        ticket_seleccionado = {"ID Ticket": "PENDIENTE", "Aplicacion": "", "Título": "Relevamiento General"}

    # 5. FASE DE PROCESAMIENTO IA (Blindaje Principal)
    if callback_ui: callback_ui("gemini_inicio", "Iniciando análisis de IA...")
    minuta_final_json = ""
    respuestas_fragmentos = []
    id_ticket = str(ticket_seleccionado['ID Ticket'])
    minuta_final_dict = {} # Inicializamos para asegurar acceso en la fase de documentación
    
    try:
        # Tu excelente función que evita el límite de tiempo de Gemini cortando el video en pedazos
        chunks = dividir_video(ruta_original, minutos_por_chunk=15)
        for i, chunk in enumerate(chunks):
            if callback_ui: callback_ui("gemini_progreso", f"Analizando fragmento {i+1}/{len(chunks)} con Gemini...")
            video_file = procesar_video_gemini(chunk)
            res_ia_raw = generar_minuta_ia(video_file, ticket_seleccionado)
            
            try:
                clean_json = res_ia_raw.strip()
                if clean_json.startswith("```json"): 
                    clean_json = clean_json[7:-3].strip()
                elif clean_json.startswith("```"): 
                    clean_json = clean_json[3:-3].strip()
                
                data = json.loads(clean_json)
                respuestas_fragmentos.append(data[0] if isinstance(data, list) else data)
            except Exception as e:
                # Mejora del Try/Except interno del parseo JSON
                if callback_ui: callback_ui("log", f"⚠️ Error de lectura en fragmento {i+1}: {e}")
                respuestas_fragmentos.append({"MINUTA_DETALLE": res_ia_raw})
            
        # Validación de salida de IA
        if not respuestas_fragmentos:
            raise ValueError("La IA no devolvió datos válidos tras los reintentos.")

        if callback_ui: callback_ui("log", f"🔗 Combinando análisis de los {len(chunks)} fragmentos...")
        
        lista_p = []
        for r in respuestas_fragmentos:
            p = r.get("PARTICIPANTES", "")
            if isinstance(p, list): lista_p.extend([str(item) for item in p])
            else: lista_p.extend([i.strip() for i in str(p).split(",") if i.strip()])
        participantes_unicos = ", ".join(sorted(set(lista_p)))

        # Consolidación inteligente de FAQs
        lista_faqs_brutas = [asegurar_string(r.get("FAQ", "")) for r in respuestas_fragmentos if r.get("FAQ", "")]
        faq_consolidada = consolidar_faqs(lista_faqs_brutas)

        minuta_final_dict = {
            "OBJETIVO": asegurar_string(respuestas_fragmentos[0].get("OBJETIVO", "")),
            "PARTICIPANTES": participantes_unicos,
            "MINUTA_DETALLE": "\n\n--- CONTINUACIÓN ---\n\n".join([asegurar_string(r.get("MINUTA_DETALLE", "")) for r in respuestas_fragmentos]),
            "COMENT_V": asegurar_string(respuestas_fragmentos[-1].get("COMENT_V", "")),
            "FAQ": faq_consolidada
        }
        minuta_final_json = json.dumps(minuta_final_dict, ensure_ascii=False, indent=4)
            
    except Exception as e:
        # Salvavidas para la interfaz gráfica en Fase IA
        if callback_ui:
            callback_ui("log", f"❌ Fallo en Gemini tras reintentos: {str(e)}")
            callback_ui("gemini_fin", "Proceso detenido por error crítico en la IA.")
        return 

    # 6. FASE DE ESCRITURA Y DOCUMENTACIÓN (Blindaje Independiente)
    try:
        if callback_ui: callback_ui("log", "📝 Generando documento Word...")
        
        aplicacion_bruta = str(ticket_seleccionado.get('Aplicacion', '')).strip()
        titulo_bruto = str(ticket_seleccionado['Título'])
        titulo_para_carpeta = f"{aplicacion_bruta} - {titulo_bruto}" if aplicacion_bruta else titulo_bruto
        
        # Crea carpetas físicas usando tu folder_manager
        ruta_raiz_drive = crear_estructura_ticket(id_ticket, titulo_para_carpeta, aplicacion_bruta)
        ruta_word_oficial = inicializar_documento_requerimiento(ruta_raiz_drive, id_ticket, titulo_para_carpeta)

        dt = datetime.fromtimestamp(os.path.getmtime(ruta_original))
        timestamp, fecha_reunion = dt.strftime("%Y%m%d_%H%M"), dt.strftime("%d/%m/%Y")
        
        # Limpiamos acentos y caracteres inválidos
        titulo_limpio = sanitizar_nombre(titulo_bruto)
        nombre_dinamico = f"{id_ticket}_{titulo_limpio}_{timestamp}"
        nuevo_nombre_video = f"{nombre_dinamico}.mp4"
        
        try:
            # Renombramos el archivo local de "GRABACION_XXX" al formato corporativo
            os.rename(ruta_original, nuevo_nombre_video)
        except Exception:
            pass

        ruta_md = ""
        if ruta_word_oficial:
            actualizar_word_requerimiento(ruta_word_oficial, minuta_final_json, id_ticket, titulo_para_carpeta, fecha_reunion)
            ruta_md = os.path.join(ruta_raiz_drive, "01_Relevamiento", f"Minuta_{nombre_dinamico}.md")
            with open(ruta_md, "w", encoding="utf-8") as f: 
                f.write(f"**Link del Video en la Nube:** {link_drive}\n\n")
                f.write(minuta_final_json)

        # Registro en Log de Google Sheets (Estructura de 5 columnas)
        if sheet and id_ticket != "PENDIENTE" and "GEN-" not in id_ticket:
            # 4. Resumen Ejecutivo: Extraer OBJETIVO y recortar a 150 chars
            resumen_ejecutivo = minuta_final_dict.get("OBJETIVO", "Sin objetivo definido")
            if len(resumen_ejecutivo) > 150:
                resumen_ejecutivo = resumen_ejecutivo[:150] + "..."
            
            # 5. Link Minuta: link_drive o fallback a ruta local
            link_final = link_drive if link_drive else f"Local: {ruta_md}"

            datos_log = [
                datetime.now().strftime("%Y-%m-%d %H:%M"), # 1. Fecha_Procesamiento
                nuevo_nombre_video,                         # 2. Nombre_Video
                "OK",                                       # 3. Status
                resumen_ejecutivo,                          # 4. Resumen_Ejecutivo
                link_final                                  # 5. Link_Minuta
            ]
            registrar_log(sheet, datos_log)
        
        shutil.rmtree("data/temp", ignore_errors=True)
        if callback_ui: callback_ui("gemini_fin", f"¡Todo listo! Documentación creada en: {ruta_raiz_drive}")

    except Exception as e:
        # Manejo de errores en Fase de Documentación
        if callback_ui:
            callback_ui("log", f"❌ Error en generación de documentos: {e}")
            callback_ui("gemini_fin", "Proceso finalizado con errores en documentación.")

if __name__ == "__main__":
    print("ℹ️ Este módulo ahora funciona como Director de Orquesta y debe ser llamado por el grabador.")