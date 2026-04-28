import os
from src.gemini_engine import analizar_video_con_gemini
from src.doc_updater import crear_minuta
from src.config_manager import cargar_config

# Importamos las dependencias para mover la subida a Drive al motor de fondo
from src.google_drive import subir_archivo_drive
from src.folder_manager import obtener_carpetas_destino
from src.cola_manager import actualizar_estado_item

def procesar_reunion(ruta_video_local, url_drive_video, ticket_data, callback_ui=None, custom_folder_id=None, id_carpeta_doc=None, id_item_cola=None, evento_abortar=None, perfil="AMS"):
    """
    Función maestra que coordina la IA y la creación de la minuta en Google Docs.
    Ahora incluye subida a Drive y Puntos de Control (Checkpoints) para Aborto Suave.
    """
    try:
        # 🛡️ FIX VALIDACIÓN TEMPRANA: Evitamos crasheos por archivos fantasma
        if not os.path.exists(ruta_video_local):
            mensaje_error = f"El archivo original ya no existe en el disco: {os.path.basename(ruta_video_local)}"
            if callback_ui: callback_ui("error", mensaje_error)
            return

        # 1. ESTABLECER CARPETAS DESTINO
        if callback_ui: callback_ui("log", "📁 Evaluando estructura de carpetas en Drive...")
        carpetas = obtener_carpetas_destino(ticket_data, perfil, custom_folder_id)
        
        id_carpeta_video = carpetas.get("01_Grabacion") if carpetas else custom_folder_id
        destino_doc = id_carpeta_doc if id_carpeta_doc else (carpetas.get("02_Documentacion") if carpetas else custom_folder_id)

        # 2. SUBIDA A DRIVE (Solo si no se subió previamente)
        if not url_drive_video:
            if callback_ui: callback_ui("log", "☁️ Subiendo video a Google Drive...")
            file_id, link = subir_archivo_drive(ruta_video_local, id_carpeta_video)
            
            if not file_id:
                if callback_ui: callback_ui("error", "❌ Error subiendo a Drive.")
                return
                
            url_drive_video = link
            if callback_ui: callback_ui("drive_ok", url_drive_video)
            if callback_ui: callback_ui("log", f"✅ Video disponible en nube: {url_drive_video}")
            
            # Checkpoint Interno: Guardamos la URL en la cola por si la PC se apaga o hay error
            if id_item_cola:
                actualizar_estado_item(id_item_cola, "procesando", url_drive=url_drive_video)
        else:
            if callback_ui: callback_ui("log", "⏩ Saltando subida a Drive (El video ya estaba en la nube).")
            if callback_ui: callback_ui("drive_ok", url_drive_video)

        # --- PUNTO DE CONTROL 1 (Aborto Suave) ---
        if evento_abortar and evento_abortar.is_set():
            if callback_ui: callback_ui("log", "⏸️ Proceso pausado por el usuario. El video está a salvo en Drive. Se documentará luego.")
            if id_item_cola:
                actualizar_estado_item(id_item_cola, "drive_ok_esperando_gemini", url_drive=url_drive_video)
            return

        # 3. ANÁLISIS DE IA
        if callback_ui: 
            callback_ui("gemini_inicio", "🤖 Iniciando análisis con IA...")
            callback_ui("log", "🔍 Extrayendo conocimiento del video...")

        minuta_json = analizar_video_con_gemini(ruta_video_local, callback_ui)

        if not minuta_json:
            if callback_ui: callback_ui("error", "❌ La IA no pudo generar la minuta.")
            return

        # --- PUNTO DE CONTROL 2 (Aborto Suave) ---
        if evento_abortar and evento_abortar.is_set():
            if callback_ui: callback_ui("log", "⏸️ Proceso pausado tras análisis de IA. (Se guardó en cola para retomarlo).")
            if id_item_cola:
                actualizar_estado_item(id_item_cola, "drive_ok_esperando_gemini", url_drive=url_drive_video)
            return

        # 4. CREACIÓN DEL DOCUMENTO
        if not destino_doc:
             if callback_ui: callback_ui("error", "❌ No se especificó una carpeta de destino válida para el documento.")
             return

        if callback_ui: callback_ui("log", "📑 Escribiendo resultados en la plantilla de Google Docs...")
        
        doc_id, link_doc = crear_minuta(destino_doc, ticket_data, minuta_json)

        # 5. FINALIZACIÓN Y AUTO-LIMPIEZA
        if doc_id:
            if callback_ui: 
                callback_ui("gemini_ok", link_doc)
                callback_ui("log", f"✨ ¡Proceso completado con éxito!")
            
            # 🛡️ NUEVA LÓGICA: Auto-borrado seguro (Solo se ejecuta si TODO lo anterior no falló)
            try:
                if os.path.exists(ruta_video_local):
                    os.remove(ruta_video_local)
                    if callback_ui: callback_ui("log", f"🗑️ Auto-limpieza: Video local borrado para liberar espacio.")
            except Exception as e:
                if callback_ui: callback_ui("log", f"⚠️ No se pudo auto-borrar el video local: {e}")
                
        else:
             if callback_ui: callback_ui("error", "❌ Error al generar el documento en la nube.")

    except Exception as e:
        mensaje_error = f"⚠️ Error crítico en el procesamiento: {str(e)}"
        print(mensaje_error)
        if callback_ui: callback_ui("error", mensaje_error)