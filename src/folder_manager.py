import re
import unicodedata
from src.google_drive import obtener_o_crear_subcarpeta, obtener_id_raiz

def sanitizar_nombre_carpeta(texto):
    """Elimina acentos, eñes y caracteres inválidos para nombrar carpetas de forma segura."""
    if not texto: return "Sin_Titulo"
    texto_limpio = ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\\/*?:"<>|]', "", texto_limpio).replace(" ", "_")

def obtener_carpetas_destino(ticket_data=None, perfil="AMS", custom_folder_id=None):
    """
    Calcula y crea (si no existen) las carpetas en Google Drive según el perfil.
    Retorna un diccionario con los IDs de destino para grabaciones y documentos.
    """
    
    # ---------------------------------------------------------
    # CASO 1: PERFIL GENERAL (Navegación Libre - Los nuevos "Superpoderes")
    # ---------------------------------------------------------
    if perfil != "AMS":
        # Si el usuario eligió una carpeta en la interfaz, usamos ese ID.
        # Si por algún motivo falló, usamos el ID Maestro como fallback de seguridad.
        destino_id = custom_folder_id if custom_folder_id else obtener_id_raiz()
        
        print(f"📁 Modo GENERAL activo. Guardando en carpeta ID: {destino_id}")
        
        # Devolvemos el MISMO ID para todo, así se guarda "plano" sin subcarpetas
        return {
            "01_Grabacion": destino_id,
            "02_Documentacion": destino_id,
            "03_Entregables": destino_id,
            "04_Otros": destino_id
        }

    # ---------------------------------------------------------
    # CASO 2: PERFIL AMS (Estructura Jerárquica Automatizada)
    # ---------------------------------------------------------
    print("📁 Modo AMS activo. Construyendo árbol de directorios en la nube...")
    id_padre_maestro = obtener_id_raiz() 

    # Nivel 1: Carpeta de Aplicación (Extraída del Sheet, ej: "Viterra")
    app_bruta = ticket_data.get("Aplicacion", "General") if ticket_data else "General"
    app_limpia = sanitizar_nombre_carpeta(app_bruta)
    id_app = obtener_o_crear_subcarpeta(app_limpia, id_padre_maestro)

    # Nivel 2: Carpeta del Ticket (Ej: "GEN-8822_Error_Carga")
    id_ticket_str = str(ticket_data.get("ID Ticket", "SR-PENDIENTE")) if ticket_data else "SR-PENDIENTE"
    titulo_bruto = str(ticket_data.get("Título", "Relevamiento")) if ticket_data else "Relevamiento"
    titulo_limpio = sanitizar_nombre_carpeta(titulo_bruto)
    
    nombre_carpeta_ticket = f"{id_ticket_str}_{titulo_limpio}"
    id_ticket = obtener_o_crear_subcarpeta(nombre_carpeta_ticket, id_app)

    # Nivel 3: Subcarpetas Estándar (01, 02, 03, 04)
    carpetas_ids = {}
    subcarpetas = ["01_Grabacion", "02_Documentacion", "03_Entregables", "04_Otros"]
    
    for sub in subcarpetas:
        # Se crean dentro del ID del ticket y guardamos sus IDs
        carpetas_ids[sub] = obtener_o_crear_subcarpeta(sub, id_ticket)

    return carpetas_ids