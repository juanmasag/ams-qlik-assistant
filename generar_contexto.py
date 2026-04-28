import os

def obtener_ruta_versionada(ruta_base):
    """
    Verifica si el archivo ya existe y le agrega un sufijo de versión (_v2, _v3, etc.).
    """
    # Nos aseguramos de que la ruta termine en .txt
    if not ruta_base.lower().endswith('.txt'):
        ruta_base += '.txt'
        
    # Si no existe, usamos el nombre original (sería la v1)
    if not os.path.exists(ruta_base):
        return ruta_base
        
    # Si ya existe, separamos el nombre de la extensión para agregar el número
    nombre_base, extension = os.path.splitext(ruta_base)
    version = 2
    
    while True:
        nueva_ruta = f"{nombre_base}_v{version}{extension}"
        if not os.path.exists(nueva_ruta):
            return nueva_ruta
        version += 1

def consolidar_proyecto(carpeta_origen, ruta_salida):
    # Obtener solo los archivos .py de la carpeta
    archivos_py = [f for f in os.listdir(carpeta_origen) if f.endswith('.py')]
    archivos_py.sort() # Ordenarlos alfabéticamente

    if not archivos_py:
        print(f"No se encontraron archivos .py en la ruta: {carpeta_origen}")
        return

    lineas_indice = []
    lineas_cuerpo = []

    # CORRECCIÓN APLICADA: 1 línea título + N líneas de índice + 2 saltos de línea extra = N + 3 líneas usadas.
    # Por lo tanto, el primer archivo arranca en la línea N + 4.
    linea_actual = len(archivos_py) + 4

    lineas_indice.append("### ÍNDICE DE ARCHIVOS ###\n")

    for i, archivo in enumerate(archivos_py, start=1):
        ruta_completa = os.path.join(carpeta_origen, archivo)
        
        # 1. Registrar el archivo y su línea de inicio en el índice
        lineas_indice.append(f"{archivo} - Inicia en la línea {linea_actual}\n")
        
        # 2. Crear la cabecera del archivo en el cuerpo
        cabecera = f"################ Acá arranca el archivo {i} - {archivo} ################\n"
        lineas_cuerpo.append(cabecera)
        linea_actual += 1
        
        # 3. Leer y volcar el contenido del archivo .py
        try:
            with open(ruta_completa, 'r', encoding='utf-8') as f:
                contenido = f.readlines()
                
                # Asegurar que la última línea tenga un salto de línea limpio
                if contenido and not contenido[-1].endswith('\n'):
                    contenido[-1] += '\n'
                    
                lineas_cuerpo.extend(contenido)
                linea_actual += len(contenido)
        except Exception as e:
            error_msg = f"# ERROR AL LEER ESTE ARCHIVO: {e}\n"
            lineas_cuerpo.append(error_msg)
            linea_actual += 1

        # Añadir un salto de línea extra para separar del siguiente archivo
        lineas_cuerpo.append("\n")
        linea_actual += 1

    # 4. Construir el Prompt Estricto para la IA al final del documento
    prompt_ia = (
        "################ INSTRUCCIONES ESTRICTAS E INQUEBRANTABLES PARA LA IA ################\n"
        "Actúa como un Arquitecto de Software experto. Este documento contiene la base de código ACTUAL, REAL y DEFINITIVA del proyecto.\n\n"
        "ATENCIÓN: Este documento es TU ÚNICA VERDAD ABSOLUTA. Anula y reemplaza cualquier conversación previa, memoria o suposición que tengas sobre este código. "
        "Si tu memoria del chat contradice este archivo, ESTE ARCHIVO TIENE LA RAZÓN.\n\n"
        "REGLAS CRÍTICAS DE OPERACIÓN (CUMPLIMIENTO OBLIGATORIO):\n"
        "1. AMNESIA CONVERSACIONAL: Jamás uses variables, rutas o lógicas de mensajes anteriores si no están escritas exactamente igual en este documento actual.\n"
        "2. VERIFICACIÓN OBLIGATORIA: Antes de proponer un cambio, DEBES leer el bloque de código original en este documento para asegurarte de no borrar variables, diccionarios o rutas que el sistema necesita para funcionar. NO ALUCINES.\n"
        "3. CERO CAMBIOS INNECESARIOS: No modifiques, refactorices ni reescribas código que ya funciona y que no está directamente relacionado con mi solicitud. Mantén el estilo actual intacto.\n"
        "4. CAMBIOS SIMPLES: Si la modificación es pequeña, proporciona SOLO el bloque de código específico que debo reemplazar, incluyendo líneas de contexto (antes y después) para ubicarme fácilmente.\n"
        "5. CAMBIOS COMPLEJOS: Si el cambio altera gran parte de un archivo, genera el CÓDIGO COMPLETO de ese archivo .py para que yo pueda copiarlo y reemplazar el viejo con seguridad.\n"
        "6. FLUJO PASO A PASO: Cuando entregues un bloque de código o archivo, DETENTE INMEDIATAMENTE. Espera mi confirmación explícita (ej. 'OK', 'funciona') antes de generar más código o pasar a otro archivo.\n"
        "7. MODO SEGURO: Tu máxima prioridad es proteger el trabajo ya logrado. Si tienes dudas de cómo un cambio afectará otras partes de este documento, PREGÚNTAME antes de programar.\n"
        "8. BLOQUEO DE CÓDIGO PROACTIVO: Ante el reporte de un error, bug o nuevo requerimiento, TIENES ESTRICTAMENTE PROHIBIDO generar código de solución en tu primera respuesta. Tu única tarea será analizar el problema, explicar conceptualmente la falla y DETENERTE para pedirme que te envíe el archivo .txt con el contexto actualizado. Solo generarás código cuando yo te haya subido el nuevo documento y te dé la orden explícita de programar la solución.\n"
        "9. INTEGRIDAD ESTRUCTURAL INQUEBRANTABLE (ANTI-TRUNCAMIENTO): Tienes ESTRICTAMENTE PROHIBIDO omitir, resumir, truncar o eliminar funciones, botones, variables o bloques de código que no formen parte explícita de la modificación solicitada. Al aplicar la Regla 5 (Archivos Completos), debes reproducir el 100% del código original no modificado. Si por limitaciones de contexto no tienes la EXACTITUD de todo el archivo, DETENTE inmediatamente y solicítame el .txt actualizado antes de omitir una sola línea de código.\n"
    )
    lineas_cuerpo.append(prompt_ia)

    # 5. Escribir todo el contenido consolidado en el archivo final
    try:
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.writelines(lineas_indice)
            f.write("\n\n")
            f.writelines(lineas_cuerpo)
        print(f"✅ ¡Éxito! Documento de contexto generado en: {ruta_salida}")
    except Exception as e:
        print(f"❌ Error al guardar el archivo de salida: {e}")

# --- EJECUCIÓN ---
if __name__ == "__main__":
    # La ruta de tus .py
    carpeta_origen = r"C:\Users\Usuario\ams-qlik-assistant\src" 
    
    # La ruta base donde quieres que se guarde el .txt final
    ruta_base_salida = r"C:\Users\Usuario\Desktop\Contexto IA\Contexto_IA" 
    
    # Obtenemos el nombre versionado automáticamente
    archivo_salida = obtener_ruta_versionada(ruta_base_salida)
    
    consolidar_proyecto(carpeta_origen, archivo_salida)