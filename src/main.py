import os
from src.gemini_engine import analizar_video_con_gemini
from src.doc_updater import crear_minuta
from src.config_manager import cargar_config

# NOTA: Ya no importamos 'obtener_carpetas_destino' porque el grabador nos pasará el ID directamente.

def procesar_reunion(ruta_video_local, url_drive_video, ticket_data, callback_ui=None, custom_folder_id=None, id_carpeta_doc=None):
    """
    Función maestra que coordina la IA y la creación de la minuta en Google Docs.
    """
    try:
        # 1. Informar a la UI que empezamos el análisis
        if callback_ui: 
            callback_ui("gemini_inicio", "🤖 Iniciando análisis con IA...")
            callback_ui("log", "🔍 Extrayendo conocimiento del video...")

        # 2. Ejecutar el análisis de la IA
        minuta_json = analizar_video_con_gemini(ruta_video_local, callback_ui)

        if not minuta_json:
            if callback_ui: callback_ui("error", "❌ La IA no pudo generar la minuta.")
            return

        # 3. Crear el Google Doc a partir de la plantilla maestra
        # Si por algún motivo id_carpeta_doc viene vacío (ej. reintento manual), usamos el fallback
        destino_doc = id_carpeta_doc if id_carpeta_doc else custom_folder_id

        if not destino_doc:
             if callback_ui: callback_ui("error", "❌ No se especificó una carpeta de destino válida para el documento.")
             return

        if callback_ui: callback_ui("log", "📑 Escribiendo resultados en la plantilla de Google Docs...")
        
        doc_id, link_doc = crear_minuta(destino_doc, ticket_data, minuta_json)

        # 4. Finalizar y entregar el link a la interfaz
        if doc_id:
            if callback_ui: 
                callback_ui("gemini_ok", link_doc)
                callback_ui("log", f"✨ ¡Proceso completado con éxito!")
        else:
            if callback_ui: callback_ui("error", "❌ Error al generar el documento en la nube.")

    except Exception as e:
        mensaje_error = f"⚠️ Error crítico en el procesamiento: {str(e)}"
        print(mensaje_error)
        if callback_ui: callback_ui("error", mensaje_error)