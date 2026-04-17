import os
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Permisos: 'drive.file' permite subir archivos y ver solo los que la app creó
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def obtener_servicio():
    """Maneja la autenticación y devuelve el objeto para hablar con Drive."""
    creds = None
    # El archivo token.json guarda los permisos del usuario de forma local
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si no hay credenciales válidas, pedimos al usuario que inicie sesión
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Aquí es donde se abre el navegador (necesitás credentials.json en la carpeta raíz)
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("⚠️ Error: Falta el archivo 'credentials.json'. Obtenelo en Google Cloud Console.")
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Guardamos el token para la próxima vez
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def obtener_o_crear_carpeta_raiz(nombre_carpeta="Grabaciones AMS"):
    """Busca una carpeta por nombre. Si no existe, la crea."""
    service = obtener_servicio()
    query = f"name = '{nombre_carpeta}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    
    # Intentar buscar la carpeta
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if items:
        return items[0]['id'] # Retorna el ID de la que ya existe
    else:
        # No existe, vamos a crearla
        print(f"📁 Creando carpeta nueva: '{nombre_carpeta}' en tu unidad...")
        file_metadata = {
            'name': nombre_carpeta,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        file = service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')

def subir_archivo_drive(ruta_local, folder_id=None):
    """Sube un archivo a una carpeta específica en Drive."""
    try:
        service = obtener_servicio()
        nombre_archivo = os.path.basename(ruta_local)
        
        metadatos = {'name': nombre_archivo}
        if folder_id:
            metadatos['parents'] = [folder_id]

        media = MediaFileUpload(ruta_local, mimetype='video/mp4', resumable=True)
        
        print(f"🚀 Subiendo {nombre_archivo} a Drive...")
        file = service.files().create(
            body=metadatos,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return file.get('id'), file.get('webViewLink')

    except Exception as e:
        print(f"❌ Error subiendo a Drive: {e}")
        return None, None

def esta_video_procesado(file_id):
    """Verifica si Google Drive terminó de procesar el video y generó los metadatos."""
    try:
        service = obtener_servicio()
        # Pedimos el campo 'videoMediaMetadata'. Si Google ya lo tiene, el video es legible para Gemini.
        file = service.files().get(fileId=file_id, fields='videoMediaMetadata, thumbnailLink').execute()
        
        # Si tiene metadatos de video (duración, ancho, alto), significa que ya se procesó
        if 'videoMediaMetadata' in file:
            return True
        return False
    except Exception:
        # Si hay un error (ej. el archivo aún no existe en el índice), asumimos que no está listo
        return False