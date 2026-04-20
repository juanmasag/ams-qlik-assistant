import gspread
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Los alcances (scopes) necesarios para Sheets y Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

def obtener_credenciales_usuario():
    """Maneja la autenticación unificada usando el token personal del usuario."""
    creds = None
    ruta_token = os.path.join('config', 'token.json')
    ruta_secret = os.path.join('config', 'gmail_secret.json') 

    if os.path.exists(ruta_token):
        creds = Credentials.from_authorized_user_file(ruta_token, SCOPES)
    
    if not creds or not creds.valid or not set(SCOPES).issubset(set(creds.scopes)):
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
                
        if not creds:
            if not os.path.exists(ruta_secret):
                ruta_secret = 'credentials.json'
                if not os.path.exists(ruta_secret):
                    raise FileNotFoundError("⚠️ Error: Falta el archivo 'gmail_secret.json' en la carpeta config.")
            
            flow = InstalledAppFlow.from_client_secrets_file(ruta_secret, SCOPES)
            
            # MAGIA CORPORATIVA: Forzamos a Google a solo aceptar cuentas @dataiq.com.ar
            print("🔒 Solicitando inicio de sesión corporativo (@dataiq.com.ar)...")
            creds = flow.run_local_server(port=0, hd="dataiq.com.ar")
            
        with open(ruta_token, 'w') as token:
            token.write(creds.to_json())
            
    return creds

def conectar_sheet(nombre_sheet):
    """Establece conexión con la Google Sheet del usuario. Si no existe, la crea con el molde exacto."""
    try:
        creds = obtener_credenciales_usuario()
        client = gspread.authorize(creds)
        
        try:
            return client.open(nombre_sheet)
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"⚠️ No se encontró la planilla '{nombre_sheet}' en tu Drive.")
            print(f"🪄 Creando planilla '{nombre_sheet}' automáticamente...")
            
            nueva_planilla = client.create(nombre_sheet)
            
            # Molde exacto para Tickets_Activos (10 columnas)
            ws_tickets = nueva_planilla.sheet1
            ws_tickets.update_title("Tickets_Activos")
            ws_tickets.append_row([
                "ID Ticket", "Título", "Estado", "Asignado Por", "Horas Acum.", 
                "Ultima Sincro", "Descripcion", "Categoria", "Aplicacion", "Tipo de desarrollo"
            ])
            
            # Molde exacto para Log_Reuniones (5 columnas)
            ws_log = nueva_planilla.add_worksheet(title="Log_Reuniones", rows="1000", cols="5")
            ws_log.append_row([
                "Fecha_Procesamiento", "Nombre_Video", "Status", "Resumen_Ejecutivo", "Link_Minuta"
            ])
            
            print("✅ Planilla y estructura base creadas con éxito.")
            return nueva_planilla

    except Exception as e:
        print(f"❌ Error crítico al conectar/crear Google Sheets: {e}")
        return None

def registrar_log(sheet, datos):
    try:
        ws = sheet.worksheet("Log_Reuniones")
        ws.append_row(datos)
        print("✅ Log registrado en Google Sheets.")
    except Exception as e:
        print(f"⚠️ No se pudo registrar el log: {e}")
        
def obtener_tickets_existentes(sheet, nombre_pestana="Tickets_Activos"):
    try:
        worksheet = sheet.worksheet(nombre_pestana)
        ids_existentes = worksheet.col_values(1) 
        return ids_existentes
    except Exception as e:
        if "WorksheetNotFound" in str(type(e).__name__):
            # Si se debe crear como fallback, usa el molde de 10 columnas
            worksheet = sheet.add_worksheet(title=nombre_pestana, rows="1000", cols="10")
            worksheet.append_row([
                "ID Ticket", "Título", "Estado", "Asignado Por", "Horas Acum.", 
                "Ultima Sincro", "Descripcion", "Categoria", "Aplicacion", "Tipo de desarrollo"
            ])
            return []
        return []

def registrar_ticket_nuevo(sheet, datos_ticket, nombre_pestana="Tickets_Activos"):
    try:
        worksheet = sheet.worksheet(nombre_pestana)
        worksheet.append_row(datos_ticket)
    except Exception as e:
        print(f"Error al registrar ticket: {e}")
        
def obtener_tickets_pendientes(sheet, nombre_pestana="Tickets_Activos"):
    try:
        worksheet = sheet.worksheet(nombre_pestana)
        valores = worksheet.get_all_values()
        if len(valores) <= 1: return []
        
        encabezados = valores[0]
        pendientes = []
        for fila in valores[1:]:
            # Rellenar con vacíos si la fila es más corta que los encabezados
            fila_completa = fila + [''] * (len(encabezados) - len(fila))
            ticket = dict(zip(encabezados, fila_completa))
            
            estado_actual = str(ticket.get('Estado', '')).strip().lower()
            estados_validos = ['new', 'scheduled', 'implement', 'review']
            
            if estado_actual in estados_validos:
                pendientes.append(ticket)
        return pendientes
    except Exception as e:
        return []