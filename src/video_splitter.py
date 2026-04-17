import os
import math
from moviepy.editor import VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

def dividir_video(ruta_original, minutos_por_chunk=10, carpeta_temp="data/temp"):
    """
    Evalúa la duración de un video y, si supera el límite, lo divide en 
    partes más pequeñas (chunks) sin re-renderizar (corte rápido).
    Retorna una lista con las rutas de los videos resultantes.
    """
    # 1. Asegurarnos de que exista la carpeta temporal oculta
    if not os.path.exists(carpeta_temp):
        os.makedirs(carpeta_temp)

    print(f"⏱️ Analizando duración del video: {os.path.basename(ruta_original)}")
    
    # 2. Leer la metadata del video para saber cuánto dura
    clip = VideoFileClip(ruta_original)
    duracion_segundos = clip.duration
    clip.close()  # Importante para no bloquear el archivo en Windows

    duracion_max_segundos = minutos_por_chunk * 60

    # 3. Si es corto, lo devolvemos intacto
    if duracion_segundos <= duracion_max_segundos:
        print("✅ El video es corto (no supera el límite). No necesita división.")
        return [ruta_original]

    # 4. Si es largo, calculamos cuántas partes necesitamos
    cantidad_partes = math.ceil(duracion_segundos / duracion_max_segundos)
    print(f"✂️ El video dura {duracion_segundos/60:.2f} minutos.")
    print(f"🔪 Se dividirá en {cantidad_partes} partes de {minutos_por_chunk} min máximo.")

    archivos_generados = []
    nombre_base = os.path.splitext(os.path.basename(ruta_original))[0]

    # 5. Cortar cada pedacito
    for i in range(cantidad_partes):
        inicio = i * duracion_max_segundos
        # Asegurarnos de que el último corte no intente ir más allá del final del video
        fin = min((i + 1) * duracion_max_segundos, duracion_segundos)
        
        nombre_chunk = f"{nombre_base}_Parte{i+1}.mp4"
        ruta_chunk = os.path.join(carpeta_temp, nombre_chunk)
        
        print(f"   -> Generando Parte {i+1} (de {inicio}s a {fin}s)...")
        # Esta es la función mágica que corta sin demoras
        ffmpeg_extract_subclip(ruta_original, inicio, fin, targetname=ruta_chunk)
        archivos_generados.append(ruta_chunk)

    print("✅ División rápida completada.")
    return archivos_generados

# Bloque de prueba (solo se ejecuta si corremos este archivo directamente)
if __name__ == "__main__":
    # Prueba rápida
    ruta_prueba = input("Pega la ruta de un video largo para probar: ").strip('"')
    if os.path.exists(ruta_prueba):
        pedazos = dividir_video(ruta_prueba, minutos_por_chunk=5) # Cortamos cada 5 min para probar
        print("\nArchivos resultantes:")
        for p in pedazos:
            print("-", p)
    else:
        print("❌ Archivo no encontrado.")