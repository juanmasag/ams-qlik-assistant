import os
import imageio_ffmpeg
import time
import threading
import subprocess
import wave
import cv2
import numpy as np
import mss
from datetime import datetime
import soundcard as sc
import warnings
from main import procesar_reunion

# Nuestros módulos personalizados (AQUÍ AGREGAMOS esta_video_procesado)
from google_drive import subir_archivo_drive, obtener_o_crear_carpeta_raiz, esta_video_procesado

# Silenciamos avisos de discontinuidad
warnings.filterwarnings("ignore", message="data discontinuity in recording")

# --- CONFIGURACIÓN DE ALTA DISPONIBILIDAD ---
FPS_VIDEO = 15
RES_VIDEO = (1920, 1080)
SAMPLE_RATE_AUDIO = 44100

class GrabadorCorporativo:
    def __init__(self, folder_id=None):
        # 1. Lógica de Carpeta Inteligente
        if not folder_id:
            print("🔍 Buscando carpeta de destino en Drive...")
            self.folder_id_drive = obtener_o_crear_carpeta_raiz()
        else:
            self.folder_id_drive = folder_id
            
        # 2. Variables críticas del motor
        self.grabando = False
        self.filename_base = ""
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def _grabar_audio_stream(self, device, filename, multiplicador_volumen=1.0):
        """Graba audio directamente a disco usando el módulo wave para no consumir RAM."""
        try:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) 
                wf.setframerate(SAMPLE_RATE_AUDIO)
                
                with device.recorder(samplerate=SAMPLE_RATE_AUDIO, channels=1) as recorder:
                    while self.grabando:
                        data = recorder.record(numframes=4096)
                        # LA MAGIA: Multiplicamos por la ganancia elegida antes de limitar los picos
                        data_int16 = np.clip(data * 32767 * multiplicador_volumen, -32768, 32767).astype(np.int16)
                        wf.writeframes(data_int16.tobytes())
        except Exception as e:
            print(f"⚠️ Error en stream de audio ({filename}): {e}")

    def _grabar_motor(self):
        """Motor blindado con tubería directa a FFmpeg y streaming de audio."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        self.filename_base = f"GRABACION_{timestamp}"
        temp_audio_mic = f"{self.filename_base}_mic.wav"
        temp_audio_spk = f"{self.filename_base}_spk.wav"
        temp_video = f"{self.filename_base}_v.mp4"
        output_final = f"{self.filename_base}.mp4"

        print(f"🚀 INICIANDO GRABACIÓN RESILIENTE (1080p @ {FPS_VIDEO} FPS)")
        print("Presione Ctrl+C para finalizar con seguridad.")

        command = [
            self.ffmpeg_exe,
            '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{RES_VIDEO[0]}x{RES_VIDEO[1]}',
            '-pix_fmt', 'bgr24', '-r', str(FPS_VIDEO),
            '-i', '-',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '25',
            '-pix_fmt', 'yuv420p', temp_video
        ]
        
        proc_video = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.grabando = True

        # Iniciar hilos de audio. Le damos un multiplicador de x4.0 al micrófono.
        # El parlante (spk) lo dejamos en x1.0 (normal).
        t_mic = threading.Thread(target=self._grabar_audio_stream, args=(sc.default_microphone(), temp_audio_mic, 4.0))
        t_spk = threading.Thread(target=self._grabar_audio_stream, args=(sc.get_microphone(sc.default_speaker().id, include_loopback=True), temp_audio_spk, 1.0))
        t_mic.start()
        t_spk.start()

        sct = mss.mss()
        monitor = sct.monitors[1]
        start_time_total = time.time()
        frames_captured = 0

        try:
            while self.grabando:
                try:
                    img = sct.grab(monitor)
                    frame = np.array(img)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    frame_resized = cv2.resize(frame, RES_VIDEO, interpolation=cv2.INTER_AREA)
                    raw_frame = frame_resized.tobytes()
                except Exception:
                    time.sleep(0.01)
                    continue

                proc_video.stdin.write(raw_frame)
                frames_captured += 1
                
                target_time = start_time_total + (frames_captured / FPS_VIDEO)
                while time.time() > target_time + (1.0 / FPS_VIDEO):
                    proc_video.stdin.write(raw_frame)
                    frames_captured += 1
                    target_time = start_time_total + (frames_captured / FPS_VIDEO)
                
                sleep_time = target_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            self.grabando = False
            proc_video.stdin.close()
            proc_video.wait()
            t_mic.join()
            t_spk.join()

        print("\n⏹ Grabación finalizada. Consolidando archivos...")

        cmd_final = [
            self.ffmpeg_exe, '-y',
            '-i', temp_video,
            '-i', temp_audio_mic,
            '-i', temp_audio_spk,
            '-filter_complex', '[1:a][2:a]amix=inputs=2:duration=first[aout]',
            '-map', '0:v', '-map', '[aout]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            output_final
        ]
        subprocess.run(cmd_final, stderr=subprocess.DEVNULL)

        for f in [temp_video, temp_audio_mic, temp_audio_spk]:
            if os.path.exists(f): os.remove(f)

        print(f"✅ PRODUCTO FINAL LISTO: {output_final} ({os.path.getsize(output_final) / (1024*1024):.2f} MB)")
        self._asegurar_en_nube(output_final)

    def _asegurar_en_nube(self, ruta_archivo):
        # ESTADO 1: Local listo
        print(f"\n✅ [VIDEO DISPONIBLE EN LOCAL]: {ruta_archivo}")
        print(f"🕒 [PROCESANDO EN DRIVE]: Subiendo archivo...")

        file_id, link = subir_archivo_drive(ruta_archivo, self.folder_id_drive)
        
        if file_id:
            # ESTADO 2: Subido pero procesando
            print(f"✅ [SUBIDA EXITOSA]: El archivo ya está en la nube.")
            print(f"🕒 [ESPERANDO A GEMINI]: Google Drive está procesando el video para habilitar la IA...")
            
            # Bucle de espera (Polling)
            # Aumentamos a 400 intentos (aprox. 100 minutos de espera máxima)
            intentos = 0
            while intentos < 400: 
                if esta_video_procesado(file_id):
                    # ESTADO 3: Todo listo
                    print(f"✅ [DRIVE PROCESADO]: El video ya es legible por la IA.")
                    print(f"🔗 Link final: {link}")
                    
                    # AQUÍ LANZAREMOS EL ANÁLISIS DE GEMINI
                    self._iniciar_analisis_gemini(file_id, link)
                    return
                
                intentos += 1
                time.sleep(15) # Esperamos 15 segundos antes de volver a preguntar
                
                # Ajuste para larga duración: Solo mostramos mensaje cada 4 intentos (1 minuto exacto)
                if intentos % 4 == 0:
                    minutos_espera = intentos // 4
                    print(f"⏳ [REUNIÓN LARGA]: Google sigue procesando... ({minutos_espera} min. transcurridos)")

            # Si llegamos a los 100 minutos y sigue procesando
            print("\n⚠️ El video es muy largo y Google aún no termina.")
            print("El análisis de Gemini deberá iniciarse manualmente.")
            print(f"🔗 Podés revisarlo más tarde en: {link}")
        else:
            print("❌ Error en la subida a Drive.")

    def _iniciar_analisis_gemini(self, file_id, link):
        print("🤖 [GEMINI]: Iniciando análisis de contenido y generación de documento...")
        
        # El archivo local sigue en nuestra carpeta principal
        video_local = f"{self.filename_base}.mp4"
        
        # Le pasamos el mando al Director de Orquesta (main.py)
        procesar_reunion(video_local, link)

    def iniciar(self):
        if not self.grabando:
            self.thread_motor = threading.Thread(target=self._grabar_motor)
            self.thread_motor.start()

    def detener(self):
        if self.grabando:
            self.grabando = False

if __name__ == "__main__":
    # Para probar la lógica inteligente, pasamos None.
    # Esto creará la carpeta "Grabaciones AMS" si no existe.
    FOLDER_ID = None 
    
    grabador = GrabadorCorporativo(FOLDER_ID)
    grabador.iniciar()
    
    try:
        while True: time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[Parada solicitada]")
        grabador.detener()