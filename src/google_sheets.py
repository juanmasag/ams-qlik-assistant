import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

def conectar_sheet(nombre_sheet):
    """Establece conexión con la Google Sheet usando las credenciales locales."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Ruta al archivo de credenciales en la carpeta config
    ruta_creds = os.path.join('config', 'creds.json')
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(ruta_creds, scope)
        client = gspread.authorize(creds)
        return client.open(nombre_sheet)
    except Exception as e:
        print(f"❌ Error al conectar con Google Sheets: {e}")
        return None

def registrar_log(sheet, datos):
    """
    Escribe una fila en la pestaña Log_Reuniones.
    datos: lista con [Fecha, Video, Status, Resumen, Link]
    """
    try:
        ws = sheet.worksheet("Log_Reuniones")
        ws.append_row(datos)
        print("✅ Log registrado en Google Sheets.")
    except Exception as e:
        print(f"⚠️ No se pudo registrar el log: {e}")
        
def obtener_tickets_existentes(sheet, nombre_pestana="Tickets_Activos"):
    """Lee la planilla para saber qué tickets ya están guardados y evitar duplicados."""
    try:
        worksheet = sheet.worksheet(nombre_pestana)
        # Trae todos los valores de la primera columna (Columna A) donde guardaremos los CHG
        ids_existentes = worksheet.col_values(1) 
        return ids_existentes
    except Exception as e:
        # Si la pestaña "Tickets_Activos" no existe, la crea con los encabezados
        if "WorksheetNotFound" in str(type(e).__name__):
            print(f"🔧 Creando nueva pestaña: {nombre_pestana}")
            worksheet = sheet.add_worksheet(title=nombre_pestana, rows="1000", cols="5")
            worksheet.append_row(["ID Ticket", "Título", "Descripción", "Estado", "Fecha Alta"])
            return []
        print(f"Error al leer tickets existentes: {e}")
        return []

def registrar_ticket_nuevo(sheet, datos_ticket, nombre_pestana="Tickets_Activos"):
    """Guarda una nueva fila en la pestaña de tickets."""
    try:
        worksheet = sheet.worksheet(nombre_pestana)
        worksheet.append_row(datos_ticket)
    except Exception as e:
        print(f"Error al registrar ticket: {e}")
        
        
def obtener_tickets_pendientes(sheet, nombre_pestana="Tickets_Activos"):
    """Obtiene los tickets en estado Pendiente para el menú interactivo."""
    try:
        worksheet = sheet.worksheet(nombre_pestana)
        valores = worksheet.get_all_values()
        if len(valores) <= 1: return []
        
        encabezados = valores[0]
        pendientes = []
        for fila in valores[1:]:
            # Convertimos la fila en un diccionario fácil de leer
            ticket = dict(zip(encabezados, fila))
            if ticket.get('Estado') == 'Pendiente':
                pendientes.append(ticket)
        return pendientes
    except Exception as e:
        print(f"Error al leer tickets pendientes: {e}")
        return []