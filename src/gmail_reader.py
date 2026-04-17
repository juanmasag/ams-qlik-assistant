import os
import re
import sys
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Asegurar que Python encuentre la carpeta 'src'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.google_sheets import conectar_sheet, obtener_tickets_existentes, registrar_ticket_nuevo

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def autenticar_gmail():
    """Maneja la autenticación y crea el servicio de la API de Gmail."""
    creds = None
    ruta_token = os.path.join('config', 'token.json')
    ruta_secret = os.path.join('config', 'gmail_secret.json')

    if os.path.exists(ruta_token):
        creds = Credentials.from_authorized_user_file(ruta_token, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(ruta_secret, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(ruta_token, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Error al conectar con Gmail: {e}")
        return None

def obtener_tickets_pendientes():
    """Busca correos de ServiceNow y extrae el ID del Ticket, Título y Descripción."""
    service = autenticar_gmail()
    if not service:
        return []

    # Buscamos los últimos 10 correos para tener más historial
    query = "from:viterraglobal@service-now.com subject:Change"
    resultados = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
    mensajes = resultados.get('messages', [])
    
    tickets_procesados = {} # Usamos un diccionario para evitar duplicados por ID
    
    if mensajes:
        for msg in mensajes:
            # Obtenemos el correo completo para extraer el snippet
            detalles = service.users().messages().get(userId='me', id=msg['id']).execute()
            snippet = detalles.get('snippet', '')
            
            # Buscamos el ID (CHG seguido de números) en el snippet o asunto
            match_id = re.search(r'(CHG\d+)', snippet) 
            
            # Extraemos un título provisional del snippet (lo que sigue al CHG)
            titulo = "Sin título específico"
            # Cortamos el título si aparece "has been assigned", "Priority", "State", etc.
            match_titulo = re.search(r'CHG\d+\s*-\s*(.*?)(?:\s+has been assigned|\s+Priority|\s+State|\s+Description|$)', snippet, re.IGNORECASE)
            if match_titulo:
                titulo = match_titulo.group(1).strip()
            
            # Intentamos extraer la descripción si existe
            descripcion = "Sin descripción"
            match_desc = re.search(r'Description:\s*(.*?)(?:Click here|$)', snippet)
            if match_desc:
                descripcion = match_desc.group(1).strip()

            if match_id:
                ticket_id = match_id.group(1)
                # Solo agregamos si no lo hemos procesado antes
                if ticket_id not in tickets_procesados:
                    tickets_procesados[ticket_id] = {
                        "id": ticket_id,
                        "titulo": titulo,
                        "descripcion": descripcion,
                        "snippet": snippet
                    }
                
    return list(tickets_procesados.values())

if __name__ == '__main__':
    print("🚀 Iniciando sincronización de tickets de Gmail a Google Sheets...\n")
    
    # 1. Conectar a Google Sheets
    nombre_planilla = "AMS_BI_Assistant_Log" # Asegúrate de que sea tu nombre exacto
    sheet = conectar_sheet(nombre_planilla)
    
    if sheet:
        # 2. Obtener IDs que ya están en la planilla
        ids_guardados = obtener_tickets_existentes(sheet)
        # Limpiamos el encabezado por las dudas
        if "ID Ticket" in ids_guardados:
            ids_guardados.remove("ID Ticket")
            
        print(f"📂 Encontrados {len(ids_guardados)} tickets registrados en la base.")

        # 3. Leer correos de Gmail
        print("🔍 Escaneando la bandeja de entrada...")
        tickets_gmail = obtener_tickets_pendientes()
        
        # 4. Comparar y guardar los nuevos
        nuevos_guardados = 0
        if tickets_gmail:
            for t in tickets_gmail:
                if t['id'] not in ids_guardados:
                    print(f"✨ Nuevo ticket encontrado: {t['id']}. Registrando...")
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                    # Columnas: ID Ticket, Título, Descripción, Estado, Fecha Alta
                    datos_fila = [t['id'], t['titulo'], t['descripcion'], "Pendiente", fecha_actual]
                    
                    registrar_ticket_nuevo(sheet, datos_fila)
                    nuevos_guardados += 1
                    ids_guardados.append(t['id']) # Evitar duplicados en la misma pasada
                else:
                    print(f"⏭️ El ticket {t['id']} ya existe. Omitiendo.")
                    
            print(f"\n✅ Proceso completado. Se agregaron {nuevos_guardados} tickets nuevos al Backlog.")
        else:
            print("No se encontraron tickets en el correo.")