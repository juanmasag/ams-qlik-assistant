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

# Nuevos imports
from src.main import procesar_reunion
from src.google_drive import subir_archivo_drive, obtener_o_crear_carpeta_raiz, esta_video_procesado

warnings.filterwarnings("ignore", message="data discontinuity in recording")

FPS_VIDEO = 15
RES_VIDEO = (1920, 1080)
SAMPLE_RATE_AUDIO = 44100

def sanitizar_nombre(texto):
    """Elimina acentos, eñes y caracteres inválidos para nombrar archivos de forma segura."""
    if not texto: return "Sin_Titulo"
    texto_limpio = ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\\/*?:"<>|]', "", texto_limpio).replace(" ", "_")

class GrabadorCorporativo:
    def __init__(self, folder_id=None, ticket_data=None, callback_ui=None):
        self.ticket_data = ticket_data
        self.callback_ui = callback_ui
        
        if not folder_id:
            if self.callback_ui: self.callback_ui("log", "🔍 Buscando carpeta en Drive...")
            self.folder_id_drive = obtener_o_crear_carpeta_raiz()
        else:
            self.folder_id_drive = folder_id
            
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
        
        # --- NUEVA LÓGICA DE BAUTISMO CORPORATIVO ---
        if self.ticket_data:
            id_ticket = str(self.ticket_data.get("ID Ticket", "PENDIENTE"))
            titulo_bruto = str(self.ticket_data.get("Título", "Relevamiento"))
            # Limpiamos los caracteres inválidos y acentos para que Windows/Gemini no colapsen
            titulo_limpio = sanitizar_nombre(titulo_bruto)
            self.filename_base = f"{id_ticket}_{titulo_limpio}_{timestamp}"
        else:
            # Fallback por seguridad
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

        if self.callback_ui: self.callback_ui("log", "⏹ Consolidando audio y video con FFmpeg...")

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

        # HILO SECUNDARIO PARA QUE LA UI NO SE CONGELE
        hilo_ia = threading.Thread(
            target=procesar_reunion, 
            args=(ruta_archivo, "Generando link en Drive...", self.ticket_data, self.callback_ui)
        )
        hilo_ia.start()

        if self.callback_ui: self.callback_ui("log", "☁️ Subiendo a Google Drive...")
        
        file_id, link = subir_archivo_drive(ruta_archivo, self.folder_id_drive)
        if file_id:
            if self.callback_ui: self.callback_ui("drive_ok", link)
            if self.callback_ui: self.callback_ui("log", f"✅ Archivo disponible en nube: {link}")
        else:
            if self.callback_ui: self.callback_ui("log", "❌ Error subiendo a Drive.")

    def iniciar(self):
        if not self.grabando:
            self.thread_motor = threading.Thread(target=self._grabar_motor)
            self.thread_motor.start()

    def detener(self):
        if self.grabando:
            self.grabando = False