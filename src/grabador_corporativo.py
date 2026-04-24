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
import re
import unicodedata

# Importamos las funciones actualizadas
from src.main import procesar_reunion
from src.google_drive import subir_archivo_drive, esta_video_procesado
from src.folder_manager import obtener_carpetas_destino

warnings.filterwarnings("ignore", message="data discontinuity in recording")

FPS_VIDEO = 15
RES_VIDEO = (1920, 1080)
SAMPLE_RATE_AUDIO = 44100

def sanitizar_nombre(texto):
    """Elimina acentos, eñes y caracteres inválidos para nombrar archivos de forma segura."""
    if not texto: return "Sin_Titulo"
    texto_limpio = ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\\/*?:"<>|]', "", texto_limpio).replace(" ", "_")

def obtener_dispositivos_audio():
    """Obtiene diccionarios de micrófonos y altavoces disponibles en Windows para la UI."""
    try:
        mics = sc.all_microphones()
        spks = sc.all_speakers()
        lista_mics = {m.name: m.id for m in mics}
        lista_spks = {s.name: s.id for s in spks}
        return lista_mics, lista_spks
    except Exception as e:
        print(f"Error obteniendo dispositivos: {e}")
        return {}, {}

class GrabadorCorporativo:
    def __init__(self, ticket_data=None, callback_ui=None, mic_id=None, spk_id=None, perfil="AMS", custom_folder_id=None):
        self.ticket_data = ticket_data
        self.callback_ui = callback_ui
        self.mic_id = mic_id
        self.spk_id = spk_id
        self.perfil = perfil
        self.custom_folder_id = custom_folder_id
        
        self.grabando = False
        self.filename_base = ""
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def _grabar_audio_stream(self, device, filename, multiplicador_volumen=1.0):
        try:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) 
                wf.setframerate(SAMPLE_RATE_AUDIO)
                with device.recorder(samplerate=SAMPLE_RATE_AUDIO, channels=1) as recorder:
                    while self.grabando:
                        data = recorder.record(numframes=4096)
                        data_int16 = np.clip(data * 32767 * multiplicador_volumen, -32768, 32767).astype(np.int16)
                        wf.writeframes(data_int16.tobytes())
        except Exception as e:
            if self.callback_ui: self.callback_ui("log", f"⚠️ Error en stream de audio ({filename}): {e}")

    def _grabar_motor(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        if self.ticket_data:
            id_ticket = str(self.ticket_data.get("ID Ticket", "PENDIENTE"))
            titulo_bruto = str(self.ticket_data.get("Título", "Relevamiento"))
            titulo_limpio = sanitizar_nombre(titulo_bruto)
            self.filename_base = f"{id_ticket}_{titulo_limpio}_{timestamp}"
        else:
            self.filename_base = f"GRABACION_{timestamp}"

        temp_audio_mic = f"{self.filename_base}_mic.wav"
        temp_audio_spk = f"{self.filename_base}_spk.wav"
        temp_video = f"{self.filename_base}_v.mp4"
        output_final = f"{self.filename_base}.mp4"

        command = [
            self.ffmpeg_exe, '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{RES_VIDEO[0]}x{RES_VIDEO[1]}', '-pix_fmt', 'bgr24', '-r', str(FPS_VIDEO),
            '-i', '-', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '25',
            '-pix_fmt', 'yuv420p', temp_video
        ]
        
        proc_video = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.grabando = True

        # Selección de dispositivos de audio (Aplica los elegidos en la interfaz)
        mic_device = sc.get_microphone(self.mic_id) if self.mic_id else sc.default_microphone()
        spk_device = sc.get_microphone(self.spk_id, include_loopback=True) if self.spk_id else sc.get_microphone(sc.default_speaker().id, include_loopback=True)

        t_mic = threading.Thread(target=self._grabar_audio_stream, args=(mic_device, temp_audio_mic, 4.0))
        t_spk = threading.Thread(target=self._grabar_audio_stream, args=(spk_device, temp_audio_spk, 1.0))
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

        if self.callback_ui: self.callback_ui("log", "⏹ Consolidando audio y video...")

        # MIX DE AUDIO: fix applied -> duration=longest
        cmd_final = [
            self.ffmpeg_exe, '-y',
            '-i', temp_video, '-i', temp_audio_mic, '-i', temp_audio_spk,
            '-filter_complex', '[1:a][2:a]amix=inputs=2:duration=longest[aout]',
            '-map', '0:v', '-map', '[aout]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', output_final
        ]
        subprocess.run(cmd_final, stderr=subprocess.DEVNULL)

        for f in [temp_video, temp_audio_mic, temp_audio_spk]:
            if os.path.exists(f): os.remove(f)

        if self.callback_ui: self.callback_ui("log", f"✅ Grabación local guardada: {output_final}")
        self._asegurar_en_nube(output_final)

    def _asegurar_en_nube(self, ruta_archivo):
        if self.callback_ui: self.callback_ui("local_ok", ruta_archivo)

        # 1. Calculamos dónde debe guardarse el video en la nube
        if self.callback_ui: self.callback_ui("log", "📁 Evaluando estructura en Drive...")
        carpetas = obtener_carpetas_destino(self.ticket_data, self.perfil, self.custom_folder_id)
        id_carpeta_video = carpetas.get("01_Grabacion")

        
        # 2. Usamos el ID de la carpeta '02_Documentacion' que el grabador ya descubrió unos pasos arriba
        # (Asegúrate de que la variable de arriba se llame 'carpetas', o ajusta el nombre si se llama distinto)
        id_docs = carpetas.get("02_Documentacion") if carpetas else self.custom_folder_id
        
        # 2. Hilo secundario para analizar con IA y crear Doc (agregamos id_docs al final)
        hilo_ia = threading.Thread(
            target=procesar_reunion, 
            args=(ruta_archivo, "Generando link en Drive...", self.ticket_data, self.callback_ui, self.custom_folder_id, id_docs)
        )
        hilo_ia.start()

        # 3. Subir el video a su carpeta final
        if self.callback_ui: self.callback_ui("log", "☁️ Subiendo video a Google Drive...")
        file_id, link = subir_archivo_drive(ruta_archivo, id_carpeta_video)
        
        if file_id:
            if self.callback_ui: self.callback_ui("drive_ok", link)
            if self.callback_ui: self.callback_ui("log", f"✅ Video disponible en nube: {link}")
        else:
            if self.callback_ui: self.callback_ui("error", "❌ Error subiendo a Drive.")

    def iniciar(self):
        if not self.grabando:
            self.thread_motor = threading.Thread(target=self._grabar_motor)
            self.thread_motor.start()

    def detener(self):
        if self.grabando:
            self.grabando = False