import customtkinter as ctk
import tkinter.messagebox as messagebox
import threading
import time
import sys
import os
import webbrowser

# 1. ESTA ES LA LÍNEA MÁGICA (Debe ir ANTES de tus imports de src)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. AHORA SÍ, TUS IMPORTS PERSONALIZADOS
from src.google_drive import listar_unidades_y_compartidas, listar_subcarpetas
from src.grabador_corporativo import GrabadorCorporativo, obtener_dispositivos_audio
from src.config_manager import cargar_config, guardar_config
from src.google_sheets import obtener_tickets_usuario
from src.main import procesar_reunion

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AplicacionGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Asistente BI - DataIQ")
        self.geometry("850x680") # Ligeramente más alto para acomodar los links
        self.resizable(False, False)

        self.config = cargar_config()
        self._verificar_primer_inicio()

        self.grabador = None
        self.esta_grabando = False
        self.segundos_grabacion = 0
        self.tickets_cargados = []

        self.ruta_local_actual = ""
        self.url_drive_actual = ""
        self.ticket_data_actual = None
        self.custom_folder_id_actual = None

        self.mics_dict, self.spks_dict = obtener_dispositivos_audio()

        self._construir_ui()
        self._al_cambiar_perfil(self.config.get("PERFIL_ACTIVO", "AMS"))

    def _verificar_primer_inicio(self):
        """Onboarding: Pide la API Key con una guía paso a paso si es la primera vez que se instala."""
        api_key = self.config.get("GEMINI_API_KEY", "").strip()
        
        if not api_key or api_key == "CLAVE_FALSA_PARA_PASAR":
            self._mostrar_asistente_api_key()

    def _mostrar_asistente_api_key(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Configuración Inicial (1/2) - API Key")
        dialogo.geometry("550x350")
        dialogo.resizable(False, False)
        dialogo.transient(self)
        dialogo.grab_set()

        lbl_titulo = ctk.CTkLabel(dialogo, text="¡Bienvenido a DataIQ BI Assistant!", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_titulo.pack(pady=(20, 5))

        instrucciones = "Para generar minutas, el asistente necesita conectarse a la IA.\nSigue estos pasos para obtener tu acceso gratuito:"
        lbl_info = ctk.CTkLabel(dialogo, text=instrucciones, font=ctk.CTkFont(size=12))
        lbl_info.pack(pady=5)

        frame_pasos = ctk.CTkFrame(dialogo, fg_color="transparent")
        frame_pasos.pack(pady=10)
        ctk.CTkLabel(frame_pasos, text="1. Haz clic en el botón azul para ir a Google AI Studio.\n2. Inicia sesión con tu cuenta de Google.\n3. Haz clic en 'Create API Key' y copia el código.\n4. Pégalo en el recuadro de abajo.", justify="left").pack()

        btn_link = ctk.CTkButton(
            dialogo, text="🌐 Abrir Google AI Studio", fg_color="#2980b9", hover_color="#1f618d",
            command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey")
        )
        btn_link.pack(pady=10)

        entry_key = ctk.CTkEntry(dialogo, width=450, placeholder_text="Pega tu API Key aquí (Ej: AIzaSy...)")
        entry_key.pack(pady=5)

        def guardar_y_cerrar():
            nueva_key = entry_key.get().strip()
            if nueva_key and len(nueva_key) > 20:
                self.config["GEMINI_API_KEY"] = nueva_key
                guardar_config(self.config)
                dialogo.destroy()
            else:
                messagebox.showerror("Error", "Por favor, ingresa una API Key válida.")

        frame_botones = ctk.CTkFrame(dialogo, fg_color="transparent")
        frame_botones.pack(pady=(15, 0))
        
        ctk.CTkButton(frame_botones, text="Cancelar", fg_color="gray", command=sys.exit, width=100).pack(side="left", padx=10)
        ctk.CTkButton(frame_botones, text="Guardar y Continuar", command=guardar_y_cerrar).pack(side="left", padx=10)

        self.wait_window(dialogo)
        if not self.config.get("GEMINI_API_KEY") or self.config.get("GEMINI_API_KEY") == "CLAVE_FALSA_PARA_PASAR":
            sys.exit()

    def _construir_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================= PANEL LATERAL =================
        self.frame_sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.frame_sidebar.grid(row=0, column=0, sticky="nsew")
        self.frame_sidebar.grid_rowconfigure(8, weight=1)

        self.lbl_logo = ctk.CTkLabel(self.frame_sidebar, text="DataIQ | AMS", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_logo.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.lbl_perfil = ctk.CTkLabel(self.frame_sidebar, text="Perfil Activo:")
        self.lbl_perfil.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.cmb_perfil = ctk.CTkComboBox(self.frame_sidebar, values=["AMS", "GENERAL"], command=self._al_cambiar_perfil)
        self.cmb_perfil.grid(row=2, column=0, padx=20, pady=(5, 20))
        self.cmb_perfil.set(self.config.get("PERFIL_ACTIVO", "AMS"))

        self.btn_sincronizar = ctk.CTkButton(self.frame_sidebar, text="🔄 Sincronizar Tickets", command=self._sincronizar_manual)
        self.btn_sincronizar.grid(row=3, column=0, padx=20, pady=10)

        # ================= PANEL PRINCIPAL =================
        self.frame_main = ctk.CTkFrame(self, corner_radius=10)
        self.frame_main.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.frame_main.grid_columnconfigure(0, weight=1)

        # 1. Zona de Tickets / Carpeta
        self.lbl_ticket = ctk.CTkLabel(self.frame_main, text="Seleccionar Ticket a trabajar:", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_ticket.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        self.cmb_tickets = ctk.CTkComboBox(self.frame_main, width=500, values=["Cargando tickets..."])
        self.cmb_tickets.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
        
        # Campo oculto para ID de Carpeta (Modo General) con botón de Explorador
        self.frame_general = ctk.CTkFrame(self.frame_main, fg_color="transparent")
        self.entry_folder_id = ctk.CTkEntry(self.frame_general, width=400, placeholder_text="ID de Carpeta o buscar en explorador ->")
        self.entry_folder_id.pack(side="left", padx=(0, 10))
        
        self.btn_explorar_drive = ctk.CTkButton(
            self.frame_general, text="📁 Explorar Drive", width=100, 
            fg_color="#8e44ad", hover_color="#732d91", command=self._abrir_explorador_drive
        )
        self.btn_explorar_drive.pack(side="left")

        # 2. Zona de Audio con Botón de Refresh
        self.lbl_audio = ctk.CTkLabel(self.frame_main, text="🎙️ Configuración de Audio Bluetooth:", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_audio.grid(row=2, column=0, padx=20, pady=(5, 0), sticky="w")

        # Sub-frame para agrupar combos y botón
        self.frame_audio = ctk.CTkFrame(self.frame_main, fg_color="transparent")
        self.frame_audio.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="w")

        self.cmb_mic = ctk.CTkComboBox(self.frame_audio, values=["Cargando..."], width=350)
        self.cmb_mic.grid(row=0, column=0, pady=(5, 5), sticky="w")
        
        self.cmb_spk = ctk.CTkComboBox(self.frame_audio, values=["Cargando..."], width=350)
        self.cmb_spk.grid(row=1, column=0, pady=(5, 5), sticky="w")

        self.btn_refresh_audio = ctk.CTkButton(
            self.frame_audio, text="🔄 Refresh", width=80, height=55,
            fg_color="#7f8c8d", hover_color="#636e72", command=self._refrescar_audio
        )
        self.btn_refresh_audio.grid(row=0, column=1, rowspan=2, padx=10, pady=5)
        
        self._cargar_combos_audio() # Carga inicial

        # 3. Botón de Grabación (COLORES RESTAURADOS)
        self.btn_grabar = ctk.CTkButton(
            self.frame_main, text="⏺ Iniciar Grabación", fg_color="#2ecc71", hover_color="#27ae60",
            font=ctk.CTkFont(size=16, weight="bold"), height=50, command=self.toggle_grabacion
        )
        self.btn_grabar.grid(row=4, column=0, padx=20, pady=10)

        self.lbl_timer = ctk.CTkLabel(self.frame_main, text="00:00:00", font=ctk.CTkFont(size=14))
        self.lbl_timer.grid(row=5, column=0, pady=(0, 10))

        # 4. Barras de Progreso y LINKS
        self.frame_progreso = ctk.CTkFrame(self.frame_main, fg_color="transparent")
        self.frame_progreso.grid(row=6, column=0, padx=20, pady=10, sticky="ew")
        self.frame_progreso.grid_columnconfigure(1, weight=1)

        # Disco Local
        ctk.CTkLabel(self.frame_progreso, text="Disco Local").grid(row=0, column=0, sticky="w")
        self.pb_local = ctk.CTkProgressBar(self.frame_progreso); self.pb_local.grid(row=0, column=1, sticky="ew", padx=10, pady=5); self.pb_local.set(0)

        # Drive + Link
        ctk.CTkLabel(self.frame_progreso, text="Google Drive").grid(row=1, column=0, sticky="w")
        self.pb_drive = ctk.CTkProgressBar(self.frame_progreso); self.pb_drive.grid(row=1, column=1, sticky="ew", padx=10, pady=5); self.pb_drive.set(0)
        self.lbl_drive_link = ctk.CTkLabel(self.frame_progreso, text="", font=ctk.CTkFont(size=11, slant="italic"))
        self.lbl_drive_link.grid(row=2, column=1, sticky="w", padx=10)

        # Gemini + Link
        ctk.CTkLabel(self.frame_progreso, text="IA Gemini").grid(row=3, column=0, sticky="w")
        self.pb_gemini = ctk.CTkProgressBar(self.frame_progreso); self.pb_gemini.grid(row=3, column=1, sticky="ew", padx=10, pady=5); self.pb_gemini.set(0)
        self.lbl_gemini_link = ctk.CTkLabel(self.frame_progreso, text="", font=ctk.CTkFont(size=11, slant="italic"))
        self.lbl_gemini_link.grid(row=4, column=1, sticky="w", padx=10)

        # Consola de Logs
        self.textbox_log = ctk.CTkTextbox(self.frame_main, height=100, font=ctk.CTkFont(size=11))
        self.textbox_log.grid(row=7, column=0, padx=20, pady=10, sticky="nsew")

    def _refrescar_audio(self):
        """Vuelve a escanear los dispositivos de audio de Windows."""
        self.log("🔄 Buscando dispositivos de audio (Auriculares/Micrófonos)...")
        self.mics_dict, self.spks_dict = obtener_dispositivos_audio()
        self._cargar_combos_audio()
        self.log("✅ Lista de dispositivos actualizada.")

    def _cargar_combos_audio(self):
        """Llena los combos con los diccionarios de audio actuales."""
        nombres_mics = list(self.mics_dict.keys()) if self.mics_dict else ["Default"]
        nombres_spks = list(self.spks_dict.keys()) if self.spks_dict else ["Default"]
        
        self.cmb_mic.configure(values=nombres_mics)
        if nombres_mics: self.cmb_mic.set(nombres_mics[0])
        
        self.cmb_spk.configure(values=nombres_spks)
        if nombres_spks: self.cmb_spk.set(nombres_spks[0])

    def _al_cambiar_perfil(self, valor):
        self.config["PERFIL_ACTIVO"] = valor
        guardar_config(self.config)
        self.log(f"🔄 Perfil cambiado a: {valor}")
        
        if valor == "AMS":
            self.lbl_ticket.configure(text="Seleccionar Ticket a trabajar:")
            self.frame_general.grid_forget() # Oculta el frame de explorador
            self.cmb_tickets.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
            self.btn_sincronizar.configure(state="normal")
            self._sincronizar_manual()
        else:
            self.lbl_ticket.configure(text="Selecciona la Carpeta Destino (GENERAL):")
            self.cmb_tickets.grid_forget()
            self.frame_general.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w") # Muestra el frame
            self.btn_sincronizar.configure(state="disabled")
    
    def _abrir_explorador_drive(self):
        """Explorador jerárquico estilo Windows para Google Drive."""
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Explorador de Google Drive")
        dialogo.geometry("500x500")
        dialogo.resizable(False, False)
        dialogo.transient(self)
        dialogo.grab_set()

        # Historial para saber en qué ruta estamos: lista de tuplas (Nombre, ID)
        self.historial_navegacion = []

        # Interfaz superior: Ruta y Botón Atrás
        lbl_ruta = ctk.CTkLabel(dialogo, text="Ruta: Inicio", font=ctk.CTkFont(weight="bold"), wraplength=480)
        lbl_ruta.pack(pady=(15, 5), padx=10, fill="x")

        frame_botones_top = ctk.CTkFrame(dialogo, fg_color="transparent")
        frame_botones_top.pack(fill="x", padx=10)

        btn_atras = ctk.CTkButton(frame_botones_top, text="⬅ Atrás", width=80, state="disabled")
        btn_atras.pack(side="left", pady=5)

        # Panel desplazable que mostrará las carpetas
        frame_lista = ctk.CTkScrollableFrame(dialogo, width=460, height=320)
        frame_lista.pack(pady=10, padx=10, fill="both", expand=True)

        def actualizar_vista():
            # Limpiamos las carpetas anteriores
            for widget in frame_lista.winfo_children():
                widget.destroy()

            # Mostramos estado de carga
            lbl_cargando = ctk.CTkLabel(frame_lista, text="Cargando carpetas...", text_color="gray")
            lbl_cargando.pack(pady=20)
            dialogo.update()

            if not self.historial_navegacion:
                # Nivel 0: Raíz (Mi Unidad + Compartidas)
                lbl_ruta.configure(text="Ruta: Inicio")
                btn_atras.configure(state="disabled")
                carpetas = listar_unidades_y_compartidas()
            else:
                # Nivel 1+: Entramos a una carpeta específica
                ruta_str = " > ".join([item[0] for item in self.historial_navegacion])
                lbl_ruta.configure(text=f"Ruta: {ruta_str}")
                btn_atras.configure(state="normal")
                parent_id = self.historial_navegacion[-1][1]
                carpetas = listar_subcarpetas(parent_id)

            lbl_cargando.destroy()

            # Dibujamos las carpetas como botones cliqueables
            if not carpetas:
                ctk.CTkLabel(frame_lista, text="📂 Carpeta vacía", text_color="gray").pack(pady=20)
            else:
                for nombre, id_carpeta in carpetas:
                    btn = ctk.CTkButton(
                        frame_lista, text=f"📁 {nombre}", fg_color="transparent",
                        text_color=("black", "white"), hover_color=("#e0e0e0", "#2a2d2e"),
                        anchor="w", font=ctk.CTkFont(size=14),
                        # La función lambda captura las variables para navegar hacia adentro
                        command=lambda n=nombre, i=id_carpeta: entrar_carpeta(n, i)
                    )
                    btn.pack(fill="x", pady=2)

        def entrar_carpeta(nombre, id_carpeta):
            self.historial_navegacion.append((nombre, id_carpeta))
            actualizar_vista()

        def ir_atras():
            if self.historial_navegacion:
                self.historial_navegacion.pop()
                actualizar_vista()

        btn_atras.configure(command=ir_atras)

        def seleccionar_carpeta():
            if not self.historial_navegacion:
                messagebox.showwarning("Atención", "Debes entrar a una carpeta para seleccionarla.")
                return
            nombre, id_carpeta = self.historial_navegacion[-1]
            self.entry_folder_id.delete(0, "end")
            self.entry_folder_id.insert(0, id_carpeta)
            self.log(f"📁 Destino GENERAL fijado en: {nombre}")
            dialogo.destroy()

        # Botón principal para confirmar
        btn_seleccionar = ctk.CTkButton(
            dialogo, text="✅ Seleccionar esta carpeta", 
            fg_color="#2ecc71", hover_color="#27ae60", height=40, font=ctk.CTkFont(weight="bold"),
            command=seleccionar_carpeta
        )
        btn_seleccionar.pack(pady=(0, 15))

        # Carga inicial
        actualizar_vista()        

    def log(self, mensaje):
        self.textbox_log.insert("end", f"{time.strftime('%H:%M:%S')} - {mensaje}\n")
        self.textbox_log.see("end")

    def _sincronizar_manual(self):
        self.cmb_tickets.set("Actualizando desde Drive...")
        threading.Thread(target=self._cargar_tickets).start()

    def _cargar_tickets(self):
        try:
            tickets = obtener_tickets_usuario()
            self.tickets_cargados = tickets
            lista_formateada = [f"{t['ID Ticket']} - {t['Título']}" for t in tickets]
            
            def update_ui():
                if lista_formateada:
                    self.cmb_tickets.configure(values=lista_formateada)
                    self.cmb_tickets.set(lista_formateada[0])
                else:
                    self.cmb_tickets.configure(values=["No hay tickets en curso"])
                    self.cmb_tickets.set("No hay tickets en curso")
            self.after(0, update_ui)
        except Exception as e:
            self.after(0, lambda: self.log(f"Error cargando tickets: {e}"))

    def toggle_grabacion(self):
        if not self.esta_grabando:
            perfil_actual = self.cmb_perfil.get()
            ticket_data = None
            custom_folder_id = None

            if perfil_actual == "AMS":
                seleccion = self.cmb_tickets.get()
                if not seleccion or "No hay tickets" in seleccion:
                    messagebox.showwarning("Aviso", "No hay un ticket válido seleccionado.")
                    return
                id_ticket = seleccion.split(" - ")[0]
                ticket_data = next((t for t in self.tickets_cargados if t["ID Ticket"] == id_ticket), None)
            else:
                custom_folder_id = self.entry_folder_id.get().strip()
                ticket_motivo = ctk.CTkInputDialog(text="Breve motivo de la reunión (para nombrar los archivos):", title="Motivo GENERAL").get_input()
                if not ticket_motivo: ticket_motivo = "Reunion_General"
                ticket_data = {"ID Ticket": "GEN-" + time.strftime("%H%M"), "Título": ticket_motivo, "Aplicacion": "General"}

            # Validación de canal de audio (Bluetooth Alerta)
            mic_name = self.cmb_mic.get()
            spk_name = self.cmb_spk.get()
            
            es_mic_llamada = "Hands-Free" in mic_name or "Manos libres" in mic_name
            es_spk_llamada = "Hands-Free" in spk_name or "Manos libres" in spk_name

            if es_mic_llamada != es_spk_llamada:
                respuesta = messagebox.askyesno(
                    "⚠️ Advertencia de Audio Bluetooth", 
                    "Estás mezclando un canal de Manos Libres (Llamadas) con un canal Estéreo (Música).\n\n"
                    "En Teams o Meet, esto hará que no se grabe la voz del cliente.\n"
                    "Te sugerimos Cancelar y elegir el perfil 'Hands-Free' en ambos selectores.\n\n"
                    "¿Deseas continuar bajo tu propio riesgo?"
                )
                if not respuesta: return

            self.ticket_data_actual = ticket_data
            self.custom_folder_id_actual = custom_folder_id
            if hasattr(self, 'btn_reintentar'): self.btn_reintentar.grid_forget()
            
            # Reset de interfaz y links
            self.pb_local.set(0); self.pb_drive.set(0); self.pb_gemini.set(0)
            self.pb_gemini.configure(progress_color=["#3a7ebf", "#1f538d"])
            
            self.lbl_drive_link.configure(text="", cursor="")
            self.lbl_drive_link.unbind("<Button-1>")
            self.lbl_gemini_link.configure(text="", cursor="")
            self.lbl_gemini_link.unbind("<Button-1>")
            
            self.textbox_log.delete("1.0", "end")

            mic_id = self.mics_dict.get(mic_name)
            spk_id = self.spks_dict.get(spk_name)

            self.grabador = GrabadorCorporativo(
                ticket_data=ticket_data, 
                callback_ui=self._actualizar_ui_thread_safe,
                mic_id=mic_id, 
                spk_id=spk_id,
                perfil=perfil_actual,
                custom_folder_id=custom_folder_id
            )
            
            self.grabador.iniciar()
            self.esta_grabando = True
            
            # BOTÓN CAMBIA A ROJO (DETENER)
            self.btn_grabar.configure(text="⏹ Detener Grabación", fg_color="#e74c3c", hover_color="#c0392b")
            self.segundos_grabacion = 0
            self._actualizar_timer()
            self.log("▶️ Grabación iniciada. Canal de audio bloqueado y grabando.")
        else:
            self.grabador.detener()
            self.esta_grabando = False
            
            # BOTÓN VUELVE A VERDE (INICIAR)
            self.btn_grabar.configure(text="⏺ Iniciar Grabación", fg_color="#2ecc71", hover_color="#27ae60")
            self.log("⏹ Grabación detenida. Procesando archivos...")

    def _actualizar_timer(self):
        if self.esta_grabando:
            self.segundos_grabacion += 1
            mins, secs = divmod(self.segundos_grabacion, 60)
            hours, mins = divmod(mins, 60)
            self.lbl_timer.configure(text=f"{hours:02d}:{mins:02d}:{secs:02d}")
            self.after(1000, self._actualizar_timer)

    def _lanzar_reintento(self):
        self.btn_reintentar.grid_forget()
        self.pb_gemini.configure(progress_color=["#3a7ebf", "#1f538d"])
        self._actualizar_ui_thread_safe("gemini_inicio", "🔄 Reintentando análisis de IA...")
        
        threading.Thread(
            target=procesar_reunion, 
            # NOTA: Agregamos 'None' al final porque el reintento usará custom_folder_id_actual
            args=(self.ruta_local_actual, self.url_drive_actual, self.ticket_data_actual, self._actualizar_ui_thread_safe, self.custom_folder_id_actual, None)
        ).start()

    def _actualizar_ui_thread_safe(self, tipo, mensaje):
        self.after(0, lambda: self._procesar_evento_ui(tipo, mensaje))

    def _procesar_evento_ui(self, tipo, mensaje):
        if tipo == "log":
            self.log(mensaje)
        elif tipo == "local_ok":
            self.pb_local.set(1)
            self.ruta_local_actual = mensaje
        elif tipo == "drive_ok":
            self.pb_drive.set(1)
            self.url_drive_actual = mensaje
            # ACTIVA EL LINK CLIQUEABLE DE DRIVE
            self.lbl_drive_link.configure(text="▶️ Ver Video en Drive", text_color="#3498db", cursor="hand2")
            self.lbl_drive_link.bind("<Button-1>", lambda e: webbrowser.open(mensaje))
        elif tipo == "gemini_inicio":
            self.pb_gemini.set(0.5)
            self.lbl_gemini_link.configure(text=mensaje, text_color="white", cursor="")
            self.lbl_gemini_link.unbind("<Button-1>")
        elif tipo == "gemini_ok":
            self.pb_gemini.set(1)
            # ACTIVA EL LINK CLIQUEABLE DEL DOCUMENTO
            self.lbl_gemini_link.configure(text="📄 Abrir Minuta en Google Docs", text_color="#2ecc71", cursor="hand2")
            self.lbl_gemini_link.bind("<Button-1>", lambda e: webbrowser.open(mensaje))
        elif tipo == "error":
            mensaje_min = mensaje.lower()
            if "error" in mensaje_min or "fallo" in mensaje_min or "detenido" in mensaje_min:
                self.lbl_gemini_link.configure(text="⚠️ Falló la IA. ¿Reintentar?", text_color="#f39c12", cursor="")
                self.lbl_gemini_link.unbind("<Button-1>")
                self.pb_gemini.configure(progress_color="#f39c12")
                self.log(f"⚠️ {mensaje}")
                
                if not hasattr(self, 'btn_reintentar'):
                    self.btn_reintentar = ctk.CTkButton(
                        self.frame_progreso, text="🔄 Reintentar", width=80, height=20,
                        fg_color="#f39c12", hover_color="#d68910", command=self._lanzar_reintento
                    )
                self.btn_reintentar.grid(row=4, column=2, padx=10)

if __name__ == "__main__":
    app = AplicacionGUI()
    app.mainloop()