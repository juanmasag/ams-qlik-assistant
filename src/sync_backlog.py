import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import glob
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH_CREDS = os.path.join(BASE_DIR, "config", "creds.json") 

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_NAME = "AMS_BI_Assistant_Log"
WORKSHEET_NAME = "Tickets_Activos"

def buscar_ultimo_csv():
    patron = os.path.join(BASE_DIR, "*.csv")
    archivos = [f for f in glob.glob(patron) if "PROCESADO" not in f]
    if not archivos:
        return None
    archivos.sort(key=os.path.getmtime, reverse=True)
    return archivos[0]

def sincronizar_backlog():
    try:
        if not os.path.exists(PATH_CREDS):
            print(f"❌ Error: No se encontró la llave en: {PATH_CREDS}")
            return
        
        # 1. Conexión a Google Sheets para ver el histórico actual
        creds = Credentials.from_service_account_file(PATH_CREDS, scopes=SCOPE)
        client = gspread.authorize(creds)
        spreadsheet = client.open(SHEET_NAME)
        
        try:
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
            datos_nube = worksheet.get_all_records()
            df_nube = pd.DataFrame(datos_nube)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="100", cols="10")
            df_nube = pd.DataFrame()

        # 2. Buscar y procesar el nuevo CSV
        archivo_path = buscar_ultimo_csv()
        if not archivo_path:
            print(f"❌ No se encontró ningún CSV nuevo para procesar.")
            return

        print(f"📂 Procesando e integrando: {os.path.basename(archivo_path)}...")
        df_csv = pd.read_csv(archivo_path, encoding='utf-8-sig')

        # 👉 LA REGLA DE ORO: Afuera los Canceled, adentro todo lo demás (Closed, New, etc.)
        df_csv = df_csv[df_csv['state'] != 'Canceled'].copy()

        df_csv = df_csv[['number', 'short_description', 'state', 'opened_by', 'u_total_time_spent']]
        df_csv.columns = ['ID Ticket', 'Título', 'Estado', 'Asignado Por', 'Horas Acum.']
        df_csv['Horas Acum.'] = pd.to_numeric(df_csv['Horas Acum.'], errors='coerce').fillna(0)
        df_csv['Ultima Sincro'] = datetime.now().strftime("%d/%m/%Y %H:%M")

        # 3. UPSERT: Cruzar la nube con el CSV nuevo
        if not df_nube.empty:
            df_nube['Horas Acum.'] = pd.to_numeric(df_nube['Horas Acum.'], errors='coerce').fillna(0)
            
            # Unimos todo y nos quedamos con la versión más reciente de cada ticket
            df_combinado = pd.concat([df_nube, df_csv], ignore_index=True)
            df_final = df_combinado.drop_duplicates(subset=['ID Ticket'], keep='last')
        else:
            df_final = df_csv

        # Ordenamos: Activos arriba, Cerrados (histórico) abajo
        df_final = df_final.sort_values(by=['Estado', 'ID Ticket'], ascending=[True, False])
        df_final = df_final.fillna("")

        # 4. Subir a Google Sheets
        data = [df_final.columns.values.tolist()] + df_final.values.tolist()
        worksheet.clear()
        worksheet.update(values=data, range_name='A1')
        
        print(f"✅ ¡Histórico limpio actualizado! Total en la bóveda: {len(df_final)} tickets (sin cancelados).")

        # 5. Archivar CSV
        nuevo_nombre = os.path.join(BASE_DIR, f"PROCESADO_{datetime.now().strftime('%Y%m%d_%H%M')}_{os.path.basename(archivo_path)}")
        os.rename(archivo_path, nuevo_nombre)

    except Exception as e:
        print(f"❌ Error crítico: {e}")

if __name__ == "__main__":
    sincronizar_backlog()