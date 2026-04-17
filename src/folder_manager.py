import os
import shutil
import re
from src.config_manager import cargar_config

# Cargamos la configuración global
config = cargar_config()
PERFIL_ACTIVO = config.get("PERFIL_ACTIVO", "GENERAL")
perfil_data = config["PERFILES"].get(PERFIL_ACTIVO, config["PERFILES"]["GENERAL"])

# 1. Definimos las rutas base dinámicamente
# DRIVE_PATH ahora es el OUTPUT_PATH del perfil (Ej: G:/Mi unidad/PROYECTOS_AMS)
DRIVE_PATH = perfil_data.get("OUTPUT_PATH", "./data/output")
# TEMPLATE_PATH se arma con la carpeta de templates + el nombre del archivo del perfil
FOLDER_TEMPLATES = config["RUTAS_LOCALES"].get("TEMPLATES", "./templates")
NOMBRE_TEMPLATE = perfil_data.get("TEMPLATE", "PLANTILLA_REQ.docx")
TEMPLATE_PATH = os.path.join(FOLDER_TEMPLATES, NOMBRE_TEMPLATE)

def crear_estructura_ticket(id_ticket, titulo_ticket, aplicacion):
    """
    Crea la jerarquía: Aplicacion > Ticket > 4 Subcarpetas.
    Usa la ruta base definida en el perfil activo del config.json.
    """
    # 1. Limpiar strings de caracteres inválidos en Windows
    titulo_limpio = re.sub(r'[\\/*?:"<>|]', "", titulo_ticket).replace(" ", "_")
    
    # 2. Manejo de la Aplicación (Agrupador Principal)
    if not aplicacion or str(aplicacion).strip() == "None" or str(aplicacion).strip() == "":
        app_limpia = "General_Sin_Aplicacion"
    else:
        app_limpia = re.sub(r'[\\/*?:"<>|]', "", str(aplicacion)).strip()

    # 3. Construir las rutas usando la base dinámica
    ruta_app = os.path.join(DRIVE_PATH, app_limpia)
    nombre_carpeta_ticket = f"[{id_ticket}] {titulo_limpio}"
    ruta_raiz_ticket = os.path.join(ruta_app, nombre_carpeta_ticket)

    # 4. Definir subcarpetas oficiales
    subcarpetas = [
        "01_Relevamiento",
        "02_Documentacion",
        "03_Entregables_Tecnicos",
        "04_Pasaje_Produccion"
    ]

    print(f"📁 Organizando en la ruta: '{DRIVE_PATH}'...")
    print(f"📂 Carpeta de Aplicación: '{app_limpia}'")

    # 5. Crear estructura de carpetas física
    try:
        if not os.path.exists(ruta_app):
            os.makedirs(ruta_app, exist_ok=True)
            print(f"   📂 Nueva subcarpeta de Aplicación creada.")

        if not os.path.exists(ruta_raiz_ticket):
            os.makedirs(ruta_raiz_ticket, exist_ok=True)
            for sub in subcarpetas:
                os.makedirs(os.path.join(ruta_raiz_ticket, sub), exist_ok=True)
            print(f"   ✅ Estructura del ticket {id_ticket} creada exitosamente.")
        else:
            print(f"   ℹ️ La carpeta del ticket ya existe. Saltando creación.")
            
    except Exception as e:
        print(f"   ❌ Error al crear carpetas en el destino: {e}")
        # Si falla el destino (ej: G: no conectado), intentamos en local por seguridad
        print("   ⚠️ Intentando crear estructura en carpeta local './data/fallback'...")
        ruta_raiz_ticket = os.path.join("./data/fallback", nombre_carpeta_ticket)
        os.makedirs(ruta_raiz_ticket, exist_ok=True)

    return ruta_raiz_ticket

def inicializar_documento_requerimiento(ruta_raiz, id_ticket, titulo_ticket):
    """
    Copia la plantilla .docx a la carpeta 02_Documentacion con el nombre correcto.
    La plantilla se elige según el perfil activo.
    """
    ruta_doc = os.path.join(ruta_raiz, "02_Documentacion")
    
    # Aseguramos que la carpeta 02 exista antes de copiar
    os.makedirs(ruta_doc, exist_ok=True)
    
    nombre_archivo = f"[{id_ticket}] {titulo_ticket[:40]} - Documento de Requerimiento.docx"
    destino_final = os.path.join(ruta_doc, nombre_archivo)

    if not os.path.exists(destino_final):
        try:
            if os.path.exists(TEMPLATE_PATH):
                shutil.copy2(TEMPLATE_PATH, destino_final)
                print(f"   📄 Plantilla '{NOMBRE_TEMPLATE}' inicializada: {nombre_archivo}")
            else:
                print(f"   ⚠️ No se encontró la plantilla en {TEMPLATE_PATH}.")
                print(f"   👉 Asegurate de tener el archivo en la carpeta '{FOLDER_TEMPLATES}'")
        except Exception as e:
            print(f"   ❌ Error al copiar la plantilla: {e}")
    else:
        print(f"   ℹ️ El Documento de Requerimiento ya existe. No se sobrescribió.")
    
    return destino_final