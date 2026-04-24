import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes necesarios para Drive (Lectura, escritura y creación)
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

# ID Maestro de la carpeta PROYECTOS_AMS que proporcionaste
ID_CARPETA_RAIZ_MAESTRA = "1PVc82A7GRK0ga8JSx7sLDx852Vzw2hOH"

def obtener_credenciales_usuario():
    """Maneja la autenticación OAuth2 del usuario y retorna las credenciales."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def obtener_id_raiz():
    """Retorna el ID maestro configurado para la estructura AMS."""
    return ID_CARPETA_RAIZ_MAESTRA

def obtener_o_crear_subcarpeta(nombre, parent_id):
    """
    Busca una carpeta por nombre dentro de una carpeta padre específica.
    Si no existe, la crea. Retorna el ID de la carpeta encontrada o creada.
    """
    creds = obtener_credenciales_usuario()
    service = build('drive', 'v3', credentials=creds)

    query = (f"name = '{nombre}' and '{parent_id}' in parents "
             f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    
    results = service.files().list(
        q=query, 
        spaces='drive', 
        fields='files(id, name)', 
        includeItemsFromAllDrives=True, 
        supportsAllDrives=True
    ).execute()
    items = results.get('files', [])

    if items:
        return items[0]['id']
    
    file_metadata = {
        'name': nombre,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    
    try:
        folder = service.files().create(
            body=file_metadata, 
            fields='id', 
            supportsAllDrives=True
        ).execute()
        # CORRECCIÓN 1 APLICADA: folder.get en lugar de file.get
        return folder.get('id')
    except Exception as e:
        print(f"❌ Error al crear subcarpeta '{nombre}': {e}")
        return None

def subir_archivo_drive(ruta_local, folder_id):
    """Sube un archivo local a una carpeta específica de Drive (por ID)."""
    creds = obtener_credenciales_usuario()
    service = build('drive', 'v3', credentials=creds)

    nombre_archivo = os.path.basename(ruta_local)
    file_metadata = {
        'name': nombre_archivo,
        'parents': [folder_id]
    }
    
    media = MediaFileUpload(ruta_local, resumable=True)
    
    try:
        # CORRECCIÓN 2 APLICADA: supportsAllDrives agregado a la subida
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()
        
        return file.get('id'), file.get('webViewLink')
    except Exception as e:
        print(f"❌ Error al subir el archivo {nombre_archivo}: {e}")
        return None, None

def esta_video_procesado(nombre_video, folder_id=None):
    """
    Verifica si un video ya existe en Drive para evitar duplicidad.
    """
    creds = obtener_credenciales_usuario()
    service = build('drive', 'v3', credentials=creds)
    
    destino = folder_id if folder_id else ID_CARPETA_RAIZ_MAESTRA

    query = f"name = '{nombre_video}' and '{destino}' in parents and trashed = false"
    
    # CORRECCIÓN 3 APLICADA: Parámetros de Unidades Compartidas agregados
    results = service.files().list(
        q=query, 
        spaces='drive', 
        fields='files(id)',
        includeItemsFromAllDrives=True, 
        supportsAllDrives=True
    ).execute()
    
    return len(results.get('files', [])) > 0

def listar_unidades_y_compartidas():
    """Obtiene la raíz de Drive: 'Mi Unidad' y las 'Unidades Compartidas'."""
    creds = obtener_credenciales_usuario()
    service = build('drive', 'v3', credentials=creds)
    
    # La raíz personal siempre es 'root'
    unidades = [("Mi Unidad", "root")]
    
    try:
        # Buscamos las unidades compartidas de la empresa
        results = service.drives().list(pageSize=100).execute()
        for d in results.get('drives', []):
            unidades.append((f"🏢 {d['name']}", d['id']))
    except Exception as e:
        print(f"Error al listar unidades compartidas: {e}")
        
    return unidades

def listar_subcarpetas(parent_id):
    """Busca todas las carpetas que estén ADENTRO de la carpeta padre indicada."""
    creds = obtener_credenciales_usuario()
    service = build('drive', 'v3', credentials=creds)
    
    query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    
    try:
        results = service.files().list(
            q=query, spaces='drive', fields='files(id, name)',
            includeItemsFromAllDrives=True, supportsAllDrives=True,
            pageSize=1000, orderBy="folder, name"
        ).execute()
        
        return [(f['name'], f['id']) for f in results.get('files', [])]
    except Exception as e:
        print(f"Error al listar subcarpetas: {e}")
        return []