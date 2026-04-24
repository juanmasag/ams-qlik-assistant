import os
import time
from googleapiclient.discovery import build
from src.google_drive import obtener_credenciales_usuario

# ID de la plantilla maestra de Google Docs que me proporcionaste
ID_PLANTILLA_MAESTRA = "1LK2ilf3-CcO8VBX8_YtQen2YcVjQO5ynZ66N1DxZR7Q"

def crear_minuta(folder_id, ticket_data, minuta_dict):
    """
    Copia la plantilla de Google Docs en la carpeta de destino y 
    reemplaza las etiquetas {{ETIQUETA}} con la información de la IA y del Ticket.
    """
    creds = obtener_credenciales_usuario()
    # Usamos tanto el servicio de Drive (para copiar) como el de Docs (para editar)
    service_drive = build('drive', 'v3', credentials=creds)
    service_docs = build('docs', 'v1', credentials=creds)

    # 1. Definir el nombre del nuevo documento
    id_ticket = str(ticket_data.get("ID Ticket", "SR-PENDIENTE"))
    titulo_ticket = str(ticket_data.get("Título", "Minuta_Reunion"))
    nombre_doc = f"Minuta_{id_ticket}_{titulo_ticket}"

    print(f"📄 Clonando plantilla para el ticket {id_ticket}...")

    # 2. Copiar la plantilla a la carpeta '02_Documentacion' (o la carpeta destino)
    copia_metadata = {
        'name': nombre_doc,
        'parents': [folder_id]
    }
    
    try:
        archivo_copiado = service_drive.files().copy(
            fileId=ID_PLANTILLA_MAESTRA,
            body=copia_metadata,
            supportsAllDrives=True
        ).execute()
        
        doc_id = archivo_copiado.get('id')
        link_doc = f"https://docs.google.com/document/d/{doc_id}/edit"

        # 3. Preparar las solicitudes de reemplazo (Batch Update)
        requests = []
        
        # --- A. TAGS FIJOS DE BACKEND (Datos de AMS) ---
        fecha_actual = time.strftime("%d/%m/%Y")
        
        # Extraemos los datos del diccionario ticket_data
        val_ticket = ticket_data.get("ID Ticket", "GEN-TKT")
        val_app = ticket_data.get("Aplicacion", "General")
        val_resp = ticket_data.get("Asignado Por", "Consultor BI")
        val_fecha = ticket_data.get("Fecha_Procesamiento", fecha_actual)

        reemplazos_fijos = {
            "TICKET": val_ticket,
            "APP": val_app,
            "RESP_V": val_resp,
            "FECHA_V": val_fecha
        }

        for clave, valor in reemplazos_fijos.items():
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': f"{{{{{clave}}}}}", 'matchCase': True},
                    'replaceText': str(valor)
                }
            })

        # --- B. TAGS DINÁMICOS DE IA (minuta_dict) ---
        for clave, valor in minuta_dict.items():
            # Si el valor es una lista (ej. Temas Tratados), lo convertimos a texto con viñetas
            if isinstance(valor, list):
                texto_reemplazo = "\n".join([f"• {item}" for item in valor])
            else:
                texto_reemplazo = str(valor)

            requests.append({
                'replaceAllText': {
                    'containsText': {
                        'text': f"{{{{{clave}}}}}", # Busca {{NOMBRE_CAMPO}}
                        'matchCase': True
                    },
                    'replaceText': texto_reemplazo
                }
            })

        # 4. Ejecutar la actualización masiva
        if requests:
            service_docs.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            
        print(f"✨ Minuta generada con éxito en Google Docs: {link_doc}")
        return doc_id, link_doc

    except Exception as e:
        print(f"❌ Error al crear el Google Doc: {e}")
        return None, None