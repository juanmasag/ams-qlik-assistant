import sys
import os
import re
import shutil
import json
from datetime import datetime

# 1. PARCHE DE RUTAS: Le decimos a Python dónde está la raíz del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. Importamos nuestros módulos locales
from src.config_manager import cargar_config
from src.google_sheets import conectar_sheet, registrar_log
from src.gemini_engine import procesar_video_gemini, generar_minuta_ia, consolidar_faqs
from src.video_splitter import dividir_video
from src.folder_manager import crear_estructura_ticket, inicializar_documento_requerimiento
from src.doc_updater import actualizar_word_requerimiento

def asegurar_string(dato):
    """Convierte cualquier dato de la IA en string, manejando listas de Gemini 2.5."""
    if isinstance(dato, list):
        return "\n".join([str(item) for item in dato])
    return str(dato) if dato else ""

def ejecutar_pipeline():
    # 3. CARGAMOS LA CONFIGURACIÓN Y EL PERFIL ACTIVO
    config = cargar_config()
    PERFIL_ACTIVO = config.get("PERFIL_ACTIVO", "GENERAL")
    perfil_data = config["PERFILES"].get(PERFIL_ACTIVO, config["PERFILES"]["GENERAL"])
    
    folder_recordings = config["RUTAS_LOCALES"].get("RECORDINGS", "./data/recordings")
    sheet_name = perfil_data.get("GOOGLE_SHEET")
    
    print(f"🚀 Iniciando Asistente v2.0 - Perfil: {PERFIL_ACTIVO}...\n")
    
    if not os.path.exists(folder_recordings):
        os.makedirs(folder_recordings, exist_ok=True)
        return

    archivos = [f for f in os.listdir(folder_recordings) if f.endswith(('.mp4', '.mkv'))]
    if not archivos:
        print(f"❌ No se encontraron videos nuevos en {folder_recordings}")
        return

    ruta_original = max([os.path.join(folder_recordings, f) for f in archivos], key=os.path.getmtime)
    nombre_obs = os.path.basename(ruta_original)
    print(f"🎬 Video detectado: {nombre_obs}")

    # 4. TICKETS
    sheet = None
    tickets_pendientes = []
    ticket_seleccionado = None

    if sheet_name:
        print(f"📊 Conectando a la planilla: {sheet_name}...")
        sheet = conectar_sheet(sheet_name)
        if sheet:
            try:
                worksheet_activos = sheet.worksheet("Tickets_Activos")
                tickets_pendientes = [t for t in worksheet_activos.get_all_records() if t.get('Estado') != 'Closed']
            except: pass

        if tickets_pendientes:
            while True:
                print("\n📋 TICKETS ACTIVOS EN BACKLOG:")
                for i, t in enumerate(tickets_pendientes):
                    print(f"[{i+1}] {t.get('ID Ticket', 'N/A')} - {t.get('Aplicacion','')} - {t.get('Título', '')}")
                opcion = input("\n👉 Selecciona el número (o Enter para manual): ")
                if not opcion.strip(): break
                try:
                    idx = int(opcion) - 1
                    if 0 <= idx < len(tickets_pendientes):
                        ticket_seleccionado = tickets_pendientes[idx]
                        break
                except: pass

    if not ticket_seleccionado:
        print("\n📝 INGRESO MANUAL DE REUNIÓN")
        tema_manual = input("👉 Tema de la reunión: ").strip()
        app_manual = input("👉 Aplicación (opcional): ").strip()
        ticket_seleccionado = {"ID Ticket": "PENDIENTE", "Aplicacion": app_manual, "Título": tema_manual if tema_manual else "Relevamiento General"}

    # 5. FASE DE PROCESAMIENTO
    print("\n--- INICIANDO FASE DE ANÁLISIS DE IA ---")
    minuta_final_json = ""
    respuestas_fragmentos = []
    id_ticket = str(ticket_seleccionado['ID Ticket'])
    
    try:
        chunks = dividir_video(ruta_original, minutos_por_chunk=15)
        for i, chunk in enumerate(chunks):
            print(f"⚙️ Analizando fragmento {i+1}/{len(chunks)} con Gemini...")
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
                print(f"⚠️ Error de parseo en fragmento {i+1}: {e}")
                respuestas_fragmentos.append({"MINUTA_DETALLE": res_ia_raw})
            
        if not respuestas_fragmentos:
            raise ValueError("La IA no devolvió datos.")

        print(f"🔗 Combinando análisis de los {len(chunks)} fragmentos...")
        
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
        print(f"\n❌ Error Crítico durante el análisis: {e}")
        return 

    # 6. FASE DE ESCRITURA
    print("\n--- INICIANDO FASE DE ESCRITURA ---")
    try:
        aplicacion_bruta = str(ticket_seleccionado.get('Aplicacion', '')).strip()
        titulo_bruto = str(ticket_seleccionado['Título'])
        titulo_para_carpeta = f"{aplicacion_bruta} - {titulo_bruto}" if aplicacion_bruta else titulo_bruto
        
        ruta_raiz_drive = crear_estructura_ticket(id_ticket, titulo_para_carpeta, aplicacion_bruta)
        ruta_word_oficial = inicializar_documento_requerimiento(ruta_raiz_drive, id_ticket, titulo_para_carpeta)

        dt = datetime.fromtimestamp(os.path.getmtime(ruta_original))
        timestamp, fecha_reunion = dt.strftime("%Y%m%d_%H%M"), dt.strftime("%d/%m/%Y")
        
        titulo_limpio = re.sub(r'[\\/*?:"<>|]', "", titulo_bruto).replace(" ", "_")
        nombre_dinamico = f"{id_ticket}_{titulo_limpio}_{timestamp}"
        nuevo_nombre_video = f"{nombre_dinamico}.mp4"
        
        try:
            os.rename(ruta_original, os.path.join(folder_recordings, nuevo_nombre_video))
        except: pass

        if ruta_word_oficial:
            actualizar_word_requerimiento(ruta_word_oficial, minuta_final_json, id_ticket, titulo_para_carpeta, fecha_reunion)
            ruta_md = os.path.join(ruta_raiz_drive, "01_Relevamiento", f"Minuta_{nombre_dinamico}.md")
            with open(ruta_md, "w", encoding="utf-8") as f: f.write(minuta_final_json)

        if sheet and id_ticket != "PENDIENTE":
            registrar_log(sheet, [datetime.now().strftime("%Y-%m-%d %H:%M"), nuevo_nombre_video, "OK", "Procesado", f"Minuta_{nombre_dinamico}.md"])
        
        shutil.rmtree("data/temp", ignore_errors=True)
        print(f"\n🎉 ¡Todo listo! Documentación creada en: {ruta_raiz_drive}")

    except Exception as e:
        print(f"\n❌ Error en escritura: {e}")

if __name__ == "__main__":
    ejecutar_pipeline()