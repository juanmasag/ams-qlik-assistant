import pandas as pd
import gspread
import os
import glob
from datetime import datetime

# Importamos la función de autenticación centralizada
from src.google_sheets import obtener_credenciales_usuario

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHEET_NAME = "AMS_BI_Assistant_Log"
WORKSHEET_NAME = "Tickets_Activos"

# Las 10 columnas oficiales
COLUMNAS_SERVICENOW = ['ID Ticket', 'Título', 'Estado', 'Asignado Por', 'Horas Acum.', 'Ultima Sincro']
COLUMNAS_MANUALES = ['Descripcion', 'Categoria', 'Aplicacion', 'Tipo de desarrollo']
COLUMNAS_TOTALES = COLUMNAS_SERVICENOW + COLUMNAS_MANUALES

def buscar_ultimo_csv():
    patron = os.path.join(BASE_DIR, "*.csv")
    archivos = [f for f in glob.glob(patron) if "PROCESADO" not in f]
    if not archivos:
        return None
    archivos.sort(key=os.path.getmtime, reverse=True)
    return archivos[0]

def sincronizar_backlog():
    try:
        # 1. Autenticación con Token Personal
        print("🔐 Verificando credenciales del usuario...")
        creds = obtener_credenciales_usuario()
        if not creds:
            print("❌ Error: No se pudo autenticar al usuario.")
            return
            
        client = gspread.authorize(creds)
        
        try:
            spreadsheet = client.open(SHEET_NAME)
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ Error: La planilla '{SHEET_NAME}' no existe aún.")
            print("💡 Inicia la aplicación principal una vez para que se cree automáticamente.")
            return
        
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

        # Filtramos los cancelados
        df_csv = df_csv[df_csv['state'] != 'Canceled'].copy()

        # Mapeamos las columnas de ServiceNow
        df_csv = df_csv[['number', 'short_description', 'state', 'opened_by', 'u_total_time_spent']]
        df_csv.columns = ['ID Ticket', 'Título', 'Estado', 'Asignado Por', 'Horas Acum.']
        df_csv['Horas Acum.'] = pd.to_numeric(df_csv['Horas Acum.'], errors='coerce').fillna(0)
        df_csv['Ultima Sincro'] = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Agregamos las columnas manuales vacías al CSV (por si son tickets nuevos)
        for col in COLUMNAS_MANUALES:
            df_csv[col] = ""

        # 3. UPSERT INTELIGENTE: Cruzar Nube y CSV protegiendo los datos manuales
        if not df_nube.empty:
            # Aseguramos que la nube tenga todas las columnas oficiales
            for col in COLUMNAS_TOTALES:
                if col not in df_nube.columns:
                    df_nube[col] = ""
                    
            df_nube['Horas Acum.'] = pd.to_numeric(df_nube['Horas Acum.'], errors='coerce').fillna(0)
            
            # Usamos el ID Ticket como índice para que Pandas sepa quién es quién
            df_nube.set_index('ID Ticket', inplace=True)
            df_csv.set_index('ID Ticket', inplace=True)
            
            # Actualizamos SOLO los datos automáticos de ServiceNow
            cols_a_actualizar = ['Título', 'Estado', 'Asignado Por', 'Horas Acum.', 'Ultima Sincro']
            df_nube.update(df_csv[cols_a_actualizar])
            
            # Identificamos tickets nuevos que vinieron en el CSV y no estaban en la nube
            nuevos_ids = df_csv.index.difference(df_nube.index)
            if not nuevos_ids.empty:
                df_nuevos = df_csv.loc[nuevos_ids]
                # Los agregamos al final
                df_nube = pd.concat([df_nube, df_nuevos])
                
            df_final = df_nube.reset_index()
        else:
            df_final = df_csv

        # 4. Ordenar y Limpiar
        # Mantenemos el orden estricto de las 10 columnas
        df_final = df_final[COLUMNAS_TOTALES]
        df_final = df_final.sort_values(by=['Estado', 'ID Ticket'], ascending=[True, False])
        df_final = df_final.fillna("")

        # 5. Subir a Google Sheets
        data = [df_final.columns.values.tolist()] + df_final.values.tolist()
        worksheet.clear()
        worksheet.update(values=data, range_name='A1')
        
        print(f"✅ ¡Histórico limpio actualizado! Total en la bóveda: {len(df_final)} tickets.")

        # 6. Archivar CSV
        nuevo_nombre = os.path.join(BASE_DIR, f"PROCESADO_{datetime.now().strftime('%Y%m%d_%H%M')}_{os.path.basename(archivo_path)}")
        os.rename(archivo_path, nuevo_nombre)

    except Exception as e:
        print(f"❌ Error crítico: {e}")

if __name__ == "__main__":
    sincronizar_backlog()