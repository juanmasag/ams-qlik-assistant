import customtkinter as ctk
import threading
import time
import sys
import os
import webbrowser
from PIL import Image, ImageTk

# 1. ESTA ES LA LÍNEA MÁGICA (Debe ir ANTES de tus imports de src)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. AHORA SÍ, TUS IMPORTS PERSONALIZADOS
from src.google_drive import listar_unidades_y_compartidas, listar_subcarpetas
from src.grabador_corporativo import GrabadorCorporativo, obtener_dispositivos_audio
from src.config_manager import cargar_config, guardar_config
from src.google_sheets import obtener_tickets_usuario
from src.main import procesar_reunion
from src.cola_manager import cargar_cola, obtener_pendientes, actualizar_estado_item, eliminar_item_cola

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AplicacionGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SandIA")
        self.geometry("400x550") 
        self.resizable(False, False)
        
        self.eval('tk::PlaceWindow . center')
        
        # 📌 FIX: Interceptar el botón [X] de Windows (Cierre Inteligente)
        self.protocol("WM_DELETE_WINDOW", self._manejar_cierre_app)
        
        self.color_fondo = "#1A1C21"
        self.color_panel = "#1E2024"
        self.configure(fg_color=self.color_fondo)

        self.withdraw()

        self.config = cargar_config()

        self.grabador = None
        self.esta_grabando = False
        
        self.esta_procesando_cola = False
        self.item_actual_id = None 
        self.evento_abortar_actual = None
        self.cola_pausada = True 
        
        self.segundos_grabacion = 0
        self.tickets_cargados = []

        self.ruta_local_actual = ""
        self.url_drive_actual = ""
        self.ticket_data_actual = None
        
        self.carpeta_general_id = ""
        self.requiere_confirmar_carpeta = False

        self.ticket_seleccionado_str = ""
        self.log_visible = False
        self.current_btn_state = "READY" # Estados: READY, RECORDING, PROCESSING, ERROR
        
        self.mics_dict, self.spks_dict = obtener_dispositivos_audio()
        n_mics = list(self.mics_dict.keys()) if self.mics_dict else ["Default"]
        n_spks = list(self.spks_dict.keys()) if self.spks_dict else ["Default"]
        self.mic_name_selected = n_mics[0]
        self.spk_name_selected = n_spks[0]
        
        self.tooltip_central = None
        self.timer_tooltip_central = None
        self.footer_tooltip = None 
        self.tooltip_timer = None
        
        # 📌 Variable auxiliar para el retorno de los diálogos custom
        self._resultado_dialogo = None

        self._cargar_imagenes()
        self._set_app_icon()
        
        # --- CONFIGURACIÓN DEL GRID PRINCIPAL ---
        self.grid_columnconfigure(0, weight=1) 
        self.grid_columnconfigure(1, weight=0) 
        
        self.grid_rowconfigure(0, weight=0) 
        self.grid_rowconfigure(1, weight=1) 
        self.grid_rowconfigure(2, weight=0) 

        self._construir_ui()
        self._al_cambiar_perfil(self.config.get("PERFIL_ACTIVO", "AMS"))

        self.after(0, self._mostrar_splash)
        
        self.hilo_cola_activo = True
        threading.Thread(target=self._hilo_consumidor_cola, daemon=True).start()

    def _resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def _set_app_icon(self):
        icon_path = self._resource_path("assets/img/splash_logo.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

    def _cargar_imagenes(self):
        def load_img(path, size):
            full_path = self._resource_path(path)
            if os.path.exists(full_path):
                return ctk.CTkImage(light_image=Image.open(full_path), size=size)
            return None
        
        self.img_splash_logo = load_img("assets/img/splash_logo.png", (200, 200))
        self.img_splash_text = load_img("assets/img/splash_text.png", (250, 60))
        
        btn_size = (250, 250)
        img_vacia = load_img("assets/img/audio_btn.png", btn_size) 
        
        self.img_btn_grabar = load_img("assets/img/boton_grabar.png", btn_size) or img_vacia
        self.img_btn_grabar_shiny = load_img("assets/img/boton_grabar_shiny.png", btn_size) or self.img_btn_grabar
        
        self.img_btn_grabando = load_img("assets/img/boton_grabando.png", btn_size) or img_vacia
        self.img_btn_grabando_shiny = load_img("assets/img/boton_grabando_shiny.png", btn_size) or self.img_btn_grabando
        
        self.img_btn_procesando = load_img("assets/img/boton_procesando.png", btn_size) or img_vacia
        self.img_btn_procesando_shiny = load_img("assets/img/boton_procesando_shiny.png", btn_size) or self.img_btn_procesando
        
        self.img_btn_error = load_img("assets/img/boton_pendientes_error.png", btn_size) or img_vacia
        self.img_btn_error_shiny = load_img("assets/img/boton_pendientes_error_shiny.png", btn_size) or self.img_btn_error

        icon_size = (48, 48)
        self.img_audio = load_img("assets/img/audio_btn.png", icon_size)
        
        self.img_hdd_off = load_img("assets/img/status_hdd_off.png", icon_size) or self.img_audio
        self.img_hdd_mid = load_img("assets/img/status_hdd_mid.png", icon_size) or self.img_hdd_off
        self.img_hdd_on = load_img("assets/img/status_hdd_on.png", icon_size) or self.img_hdd_off
        
        self.img_drive_off = load_img("assets/img/status_drive_off.png", icon_size) or self.img_audio
        self.img_drive_mid = load_img("assets/img/status_drive_mid.png", icon_size) or self.img_drive_off
        self.img_drive_on = load_img("assets/img/status_drive_on.png", icon_size) or self.img_drive_off
        
        self.img_gemini_off = load_img("assets/img/status_gemini_off.png", icon_size) or self.img_audio
        self.img_gemini_mid = load_img("assets/img/status_gemini_mid.png", icon_size) or self.img_gemini_off
        self.img_gemini_on = load_img("assets/img/status_gemini_on.png", icon_size) or self.img_gemini_off
        
        self.img_ams_btn = load_img("assets/img/perfil_ams_btn.png", icon_size) or self.img_audio
        self.img_gen_btn = load_img("assets/img/perfil_gen_btn.png", icon_size) or self.img_audio
        self.img_log_btn = load_img("assets/img/log_btn.png", icon_size) or self.img_audio

        modal_icon_size = (96, 96)
        self.img_icon_ticket = load_img("assets/img/icon_ticket.png", modal_icon_size) or self.img_audio
        self.img_icon_mic = load_img("assets/img/icon_mic.png", modal_icon_size) or self.img_audio
        self.img_icon_speaker = load_img("assets/img/icon_speaker.png", modal_icon_size) or self.img_audio
        self.img_icon_folder = load_img("assets/img/icon_folder_drive.png", modal_icon_size) or self.img_audio

    def _hacer_arrastrable(self, *widgets, ventana):
        def start_move(event):
            ventana.x = event.x
            ventana.y = event.y
        def stop_move(event):
            ventana.x = None
            ventana.y = None
        def do_move(event):
            deltax = event.x - ventana.x
            deltay = event.y - ventana.y
            x = ventana.winfo_x() + deltax
            y = ventana.winfo_y() + deltay
            ventana.geometry(f"+{x}+{y}")

        for w in widgets:
            w.bind("<ButtonPress-1>", start_move)
            w.bind("<ButtonRelease-1>", stop_move)
            w.bind("<B1-Motion>", do_move)

    def _mostrar_splash(self):
        self.splash = ctk.CTkToplevel(self)
        self.splash.overrideredirect(True) 
        self.splash.geometry("350x450") 
        self.splash.configure(fg_color="#1a1c21")
        self.splash.attributes('-topmost', True)
        
        self.splash.update_idletasks()
        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()
        x = (ancho_pantalla // 2) - (350 // 2)
        y = (alto_pantalla // 2) - (450 // 2)
        self.splash.geometry(f"+{x}+{y}")

        if self.img_splash_logo:
            ctk.CTkLabel(self.splash, image=self.img_splash_logo, text="").pack(pady=(60, 20))
        if self.img_splash_text:
            ctk.CTkLabel(self.splash, image=self.img_splash_text, text="").pack(pady=10)
            
        ctk.CTkLabel(self.splash, text="Graba y documenta inteligentemente  ", text_color="gray", font=ctk.CTkFont(size=13, slant="italic")).pack(pady=10, padx=10)

        self.after(3500, self._cerrar_splash_y_arrancar)

    def _cerrar_splash_y_arrancar(self):
        if hasattr(self, 'splash') and self.splash.winfo_exists():
            self.splash.destroy()
        self._verificar_primer_inicio()

    def _hilo_consumidor_cola(self):
        while self.hilo_cola_activo:
            time.sleep(3)
            if self.esta_procesando_cola or self.esta_grabando or self.cola_pausada:
                continue
                
            pendientes = obtener_pendientes()
            items_sanos = [p for p in pendientes if p.get("estado") != "error"]
            
            if items_sanos:
                item = items_sanos[0] 
                self.esta_procesando_cola = True
                self.item_actual_id = item["id"]
                actualizar_estado_item(self.item_actual_id, "procesando")
                
                self.evento_abortar_actual = threading.Event()
                self._actualizar_ui_thread_safe("inicio_procesamiento", item['id'])

                threading.Thread(
                    target=procesar_reunion,
                    args=(
                        item["ruta_video"], 
                        item.get("url_drive", ""), 
                        item["ticket_data"], 
                        self._actualizar_ui_thread_safe, 
                        item.get("custom_folder_id"), 
                        None,
                        self.item_actual_id,
                        self.evento_abortar_actual,
                        item.get("perfil", "AMS")
                    ),
                    daemon=True
                ).start()

    def _verificar_primer_inicio(self):
        api_key = self.config.get("GEMINI_API_KEY", "").strip()
        
        if not api_key or api_key == "CLAVE_FALSA_PARA_PASAR":
            self.withdraw()
            self._mostrar_asistente_api_key()
        else:
            self.deiconify() 
            self._verificar_pendientes_inicio()

    def _verificar_pendientes_inicio(self):
        pendientes = obtener_pendientes()
        items_sanos = [p for p in pendientes if p.get("estado") != "error"]
        items_error = [p for p in pendientes if p.get("estado") == "error"]
        
        if items_sanos:
            # 📌 Reemplazo por Diálogo Custom Premium
            respuesta = self._mostrar_dialogo_custom(
                "Videos Pendientes", 
                f"Tienes {len(items_sanos)} video(s) en cola esperando para ser documentado(s).\n\n¿Deseas iniciar el procesamiento automático ahora?",
                tipo="yesno"
            )
            if respuesta:
                self.cola_pausada = False
                self.log("▶️ Cola activada por el usuario.")
            else:
                self.log("⏸️ Cola pausada en el inicio.")
        elif items_error:
            self._set_btn_state("ERROR")
            self.cola_pausada = True
            self.log("⚠️ Elementos con error detectados en la cola.")
        else:
            self.cola_pausada = False 

    def _centrar_modal(self, modal, width, height):
        modal.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (height // 2) - 20 
        modal.geometry(f"{width}x{height}+{x}+{y}")

    # 📌 COMPONENTE MAESTRO: DIÁLOGO CUSTOM PREMIUM
    def _mostrar_dialogo_custom(self, titulo, mensaje, tipo="info"):
        """Reemplaza los messagebox nativos con el estilo de la app."""
        self._resultado_dialogo = None
        dialogo = ctk.CTkToplevel(self)
        dialogo.overrideredirect(True)
        dialogo.attributes('-topmost', True)
        
        bg_frame = ctk.CTkFrame(dialogo, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)

        self._centrar_modal(dialogo, 400, 220)
        self._hacer_arrastrable(bg_frame, ventana=dialogo)
        dialogo.grab_set()

        lbl_tit = ctk.CTkLabel(bg_frame, text=titulo, font=ctk.CTkFont(weight="bold", size=16))
        lbl_tit.pack(pady=(15, 10))
        self._hacer_arrastrable(lbl_tit, ventana=dialogo)

        lbl_msg = ctk.CTkLabel(bg_frame, text=mensaje, font=ctk.CTkFont(size=13), wraplength=350, justify="center")
        lbl_msg.pack(pady=10, padx=20)

        def click(res):
            self._resultado_dialogo = res
            dialogo.destroy()

        frame_btn = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_btn.pack(pady=(10, 20))

        if tipo == "yesno":
            ctk.CTkButton(frame_btn, text="No", width=100, fg_color="#7f8c8d", hover_color="#636e72", command=lambda: click(False)).pack(side="left", padx=10)
            ctk.CTkButton(frame_btn, text="Sí", width=100, fg_color="#27ae60", hover_color="#1e8449", command=lambda: click(True)).pack(side="left", padx=10)
        else:
            ctk.CTkButton(frame_btn, text="Entendido", width=120, fg_color="#27ae60", hover_color="#1e8449", command=lambda: click(True)).pack()

        self.wait_window(dialogo)
        return self._resultado_dialogo

    def _mostrar_asistente_api_key(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.overrideredirect(True)
        dialogo.attributes('-topmost', True)
        
        bg_frame = ctk.CTkFrame(dialogo, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)

        self._centrar_modal(dialogo, 550, 420)
        self._hacer_arrastrable(bg_frame, ventana=dialogo)
        dialogo.transient(self)
        dialogo.grab_set()
        dialogo.focus_force()

        btn_close = ctk.CTkButton(bg_frame, text="✖", width=25, height=25, fg_color="transparent", hover_color="#c0392b", command=sys.exit)
        btn_close.place(relx=0.95, rely=0.08, anchor="center")

        lbl_titulo = ctk.CTkLabel(bg_frame, text="API Key", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_titulo.pack(pady=(20, 5))
        self._hacer_arrastrable(lbl_titulo, ventana=dialogo)

        instrucciones = "Para generar minutas, el asistente necesita conectarse a la IA.\nSigue estos pasos para obtener tu acceso gratuito:"
        lbl_info = ctk.CTkLabel(bg_frame, text=instrucciones, font=ctk.CTkFont(size=12))
        lbl_info.pack(pady=5)

        frame_pasos = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_pasos.pack(pady=10)
        
        pasos_texto = (
            "1. Haz clic en el botón azul para ir a Google AI Studio.\n"
            "2. Iniciar sesión con tu cuenta de Google.\n"
            "3. Haz clic en 'Crear clave de API'.\n"
            "4. Haz clic en 'Crear clave'.\n"
            "5. Haz clic en 'Copiar clave'.\n"
            "6. Pégalo en el recuadro de abajo.\n"
            "7. Haz clic en 'Continuar'."
        )
        ctk.CTkLabel(frame_pasos, text=pasos_texto, justify="left").pack()

        btn_link = ctk.CTkButton(
            bg_frame, text="🌐 Abrir Google AI Studio", fg_color="#2980b9", hover_color="#1f618d",
            command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey")
        )
        btn_link.pack(pady=10)

        entry_key = ctk.CTkEntry(bg_frame, width=450, placeholder_text="Pega tu API Key aquí (Ej: AIzaSy...)")
        entry_key.pack(pady=15)

        def guardar_y_cerrar():
            nueva_key = entry_key.get().strip()
            
            if not nueva_key or len(nueva_key) <= 20:
                self._mostrar_dialogo_custom("Error", "Por favor, ingresa una API Key válida.", tipo="info")
                return
                
            ruta_automatica = os.path.join(os.path.expanduser("~"), "Videos", "AsistenteIA")
            if not os.path.exists(ruta_automatica):
                os.makedirs(ruta_automatica)
        
            self.config["GEMINI_API_KEY"] = nueva_key
            if "RUTAS_LOCALES" not in self.config:
                self.config["RUTAS_LOCALES"] = {}
            self.config["RUTAS_LOCALES"]["RECORDINGS"] = ruta_automatica
            
            guardar_config(self.config)
            
            self.deiconify() 
            dialogo.destroy()
            self.after(200, self._verificar_pendientes_inicio)

        frame_botones = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_botones.pack(pady=(10, 0))
        
        ctk.CTkButton(frame_botones, text="Cancelar", fg_color="gray", command=sys.exit, width=100).pack(side="left", padx=10)
        ctk.CTkButton(frame_botones, text="Continuar", fg_color="#2ecc71", hover_color="#27ae60", command=guardar_y_cerrar).pack(side="left", padx=10)

    def _programar_tooltip_footer(self, widget, texto):
        self._cancelar_tooltip_footer()
        self.tooltip_timer = self.after(400, lambda: self._mostrar_tooltip_footer(widget, texto))

    def _cancelar_tooltip_footer(self, event=None):
        if self.tooltip_timer:
            self.after_cancel(self.tooltip_timer)
            self.tooltip_timer = None
        self._ocultar_tooltip_footer()

    def _mostrar_tooltip_footer(self, widget, texto):
        self._ocultar_tooltip_footer()
            
        self.footer_tooltip = ctk.CTkToplevel(self)
        self.footer_tooltip.withdraw() 
        self.footer_tooltip.overrideredirect(True)
        self.footer_tooltip.attributes('-topmost', True)
        
        bg_frame = ctk.CTkFrame(self.footer_tooltip, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=8)
        bg_frame.pack(fill="both", expand=True)
        
        lbl = ctk.CTkLabel(bg_frame, text=texto, font=ctk.CTkFont(size=14, slant="italic"), text_color="#bdc3c7", padx=15, pady=10)
        lbl.pack()

        self.footer_tooltip.update_idletasks()
        
        x_widget = widget.winfo_rootx()
        y_widget = widget.winfo_rooty()
        w_widget = widget.winfo_width()
        
        w_tooltip = lbl.winfo_reqwidth()
        h_tooltip = lbl.winfo_reqheight()

        x_final = x_widget + (w_widget // 2) - (w_tooltip // 2)
        y_final = y_widget - h_tooltip - 8 
        
        self.footer_tooltip.geometry(f"+{x_final}+{y_final}")
        self.footer_tooltip.deiconify() 

    def _ocultar_tooltip_footer(self, event=None):
        if self.footer_tooltip:
            self.footer_tooltip.destroy()
            self.footer_tooltip = None

    def _construir_ui(self):
        
        # === FILA 0: TIMER ===
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.grid(row=0, column=0, pady=(15, 10), sticky="ew") 
        self.frame_top.grid_columnconfigure(0, weight=1)

        self.lbl_timer = ctk.CTkLabel(self.frame_top, text="00:00:00", font=ctk.CTkFont(family="Helvetica", size=32, weight="bold"))
        self.lbl_timer.grid(row=0, column=0)

        # === FILA 1: BOTÓN CENTRAL ===
        self.btn_central = ctk.CTkButton(
            self, text="", width=250, height=250,
            fg_color="transparent", hover_color=self.color_fondo, 
            image=self.img_btn_grabar,
            command=self._manejar_clic_boton_redondo
        )
        self.btn_central.grid(row=1, column=0, pady=(10, 20))
        
        self.btn_central.bind("<Enter>", self._al_entrar_mouse_btn)
        self.btn_central.bind("<Leave>", self._al_salir_mouse_btn)

        # === FILA 2: PANEL INFERIOR (GRID DE 6 SIMÉTRICO) ===
        self.frame_bottom = ctk.CTkFrame(self, height=85, corner_radius=18, fg_color=self.color_panel) 
        self.frame_bottom.grid(row=2, column=0, padx=15, pady=20, sticky="ew") 
        self.frame_bottom.grid_propagate(False) 

        for i in range(6):
            self.frame_bottom.grid_columnconfigure(i, weight=1, uniform="footer_col")

        # 🌟 NUEVO ORDEN DE ÍCONOS 🌟
        self.btn_perfil = self._crear_icono_footer(self.img_ams_btn, 0, self._abrir_modal_perfil)
        self.btn_audio = self._crear_icono_footer(self.img_audio, 1, self._abrir_modal_audio)
        self.btn_log = self._crear_icono_footer(self.img_log_btn, 2, self._toggle_log)
        self.lbl_status_hdd = self._crear_status_footer(self.img_hdd_off, 3)
        self.lbl_status_drive = self._crear_status_footer(self.img_drive_off, 4)
        self.lbl_status_gemini = self._crear_status_footer(self.img_gemini_off, 5)

        self.btn_perfil.bind("<Enter>", lambda e: self._programar_tooltip_footer(self.btn_perfil, "Permite seleccionar los distintos perfiles de grabación  "))
        self.btn_perfil.bind("<Leave>", self._cancelar_tooltip_footer)
        
        self.btn_audio.bind("<Enter>", lambda e: self._programar_tooltip_footer(self.btn_audio, "Permite configurar los dispositivos de I/O de audio  "))
        self.btn_audio.bind("<Leave>", self._cancelar_tooltip_footer)
        
        self.btn_log.bind("<Enter>", lambda e: self._programar_tooltip_footer(self.btn_log, "Visualiza la magia en el 💚 de la 🍉  "))
        self.btn_log.bind("<Leave>", self._cancelar_tooltip_footer)

        # === TERMINAL DE LOGS ===
        self.frame_log = ctk.CTkFrame(self, fg_color="#15171a", corner_radius=12)
        self.textbox_log = ctk.CTkTextbox(self.frame_log, fg_color="transparent", text_color="#00FF00", font=ctk.CTkFont(family="Consolas", size=11))
        self.textbox_log.pack(fill="both", expand=True, padx=10, pady=10)

    def _crear_icono_footer(self, img, col, cmd):
        btn = ctk.CTkButton(self.frame_bottom, text="", image=img, width=48, height=48, fg_color="transparent", hover_color="#2c3e50", command=cmd)
        btn.grid(row=0, column=col, pady=18) 
        return btn

    def _crear_status_footer(self, img, col):
        lbl = ctk.CTkLabel(self.frame_bottom, text="", image=img, width=48, height=48)
        lbl.grid(row=0, column=col, pady=18)
        return lbl

    def _toggle_log(self):
        if not self.log_visible:
            self.geometry("750x550") 
            self.grid_columnconfigure(1, weight=1) 
            self.frame_log.grid(row=0, column=1, rowspan=3, padx=(0, 15), pady=20, sticky="nsew")
            self.log_visible = True
        else:
            self.geometry("400x550") 
            self.grid_columnconfigure(1, weight=0)
            self.frame_log.grid_forget()
            self.log_visible = False

    def _manejar_cierre_app(self):
        if self.log_visible:
            self._toggle_log()
        else:
            self.hilo_cola_activo = False
            self.destroy()
            sys.exit()

    def _abrir_modal_perfil(self):
        modal = ctk.CTkToplevel(self)
        modal.overrideredirect(True) 
        modal.attributes('-topmost', True) 
        
        bg_frame = ctk.CTkFrame(modal, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)
        
        self._centrar_modal(modal, 420, 250)
        self._hacer_arrastrable(bg_frame, ventana=modal)
        modal.transient(self)
        modal.grab_set()

        btn_close = ctk.CTkButton(bg_frame, text="✖", width=25, height=25, fg_color="transparent", hover_color="#c0392b", command=modal.destroy)
        btn_close.place(relx=0.92, rely=0.15, anchor="center")

        lbl_titulo = ctk.CTkLabel(bg_frame, text="Perfil", font=ctk.CTkFont(weight="bold", size=15))
        lbl_titulo.pack(pady=(15, 5))
        self._hacer_arrastrable(lbl_titulo, ventana=modal)

        def set_ams():
            self._al_cambiar_perfil("AMS")
            modal.destroy()
            self._abrir_modal_tickets() 

        def set_gen():
            self._al_cambiar_perfil("GENERAL")
            modal.destroy()
            self._abrir_explorador_drive() 

        frame_btns = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_btns.pack(pady=10)

        btn_ams = ctk.CTkButton(frame_btns, image=self.img_icon_ticket, text="", width=110, height=110, fg_color="transparent", hover_color="#2c3e50", command=set_ams)
        btn_ams.pack(side="left", padx=20)
        
        btn_gen = ctk.CTkButton(frame_btns, image=self.img_icon_folder, text="", width=110, height=110, fg_color="transparent", hover_color="#2c3e50", command=set_gen)
        btn_gen.pack(side="left", padx=20)

        lbl_tooltip = ctk.CTkLabel(bg_frame, text=" ", font=ctk.CTkFont(size=12, slant="italic"), text_color="#bdc3c7", wraplength=360)
        lbl_tooltip.pack(pady=(5, 15), padx=20)

        btn_ams.bind("<Enter>", lambda e: lbl_tooltip.configure(text="Listado de tickets activos para seleccionar  "))
        btn_ams.bind("<Leave>", lambda e: lbl_tooltip.configure(text=" "))
        btn_gen.bind("<Enter>", lambda e: lbl_tooltip.configure(text="Permite seleccionar una carpeta de Drive a elección  "))
        btn_gen.bind("<Leave>", lambda e: lbl_tooltip.configure(text=" "))

    def _abrir_modal_tickets(self):
        modal = ctk.CTkToplevel(self)
        modal.overrideredirect(True) 
        modal.attributes('-topmost', True) 
        
        bg_frame = ctk.CTkFrame(modal, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)

        self._centrar_modal(modal, 400, 240)
        self._hacer_arrastrable(bg_frame, ventana=modal)
        modal.transient(self)
        modal.grab_set()

        btn_close = ctk.CTkButton(bg_frame, text="✖", width=25, height=25, fg_color="transparent", hover_color="#c0392b", command=modal.destroy)
        btn_close.place(relx=0.92, rely=0.12, anchor="center")

        lbl_titulo = ctk.CTkLabel(bg_frame, text="Tickets", font=ctk.CTkFont(weight="bold", size=15))
        lbl_titulo.pack(pady=(15, 0))
        self._hacer_arrastrable(lbl_titulo, ventana=modal)

        lbl = ctk.CTkLabel(bg_frame, text="🔄 Sincronizando con Drive...", text_color="gray")
        lbl.pack(pady=(5, 10))

        cmb = ctk.CTkComboBox(bg_frame, width=350, values=["Cargando..."])
        cmb.pack(pady=10)

        def update_ui(tickets):
            self.tickets_cargados = tickets
            lista = [f"{t['ID Ticket']} - {t['Título']}" for t in tickets]
            lbl.configure(text="✅ Backlog Sincronizado. Elige un ticket:")
            if lista:
                cmb.configure(values=lista)
                cmb.set(lista[0])
            else:
                cmb.configure(values=["No hay tickets en curso"])
                cmb.set("No hay tickets en curso")

        def cargar_hilo():
            try:
                tickets = obtener_tickets_usuario()
                self.after(0, lambda: update_ui(tickets))
            except Exception as e:
                self.after(0, lambda: lbl.configure(text="⚠️ Error sincronizando.", text_color="red"))

        threading.Thread(target=cargar_hilo, daemon=True).start()

        def confirmar():
            self.ticket_seleccionado_str = cmb.get()
            modal.destroy()
            self._mostrar_dialogo_custom("Ticket Activo", f"Se asignó el ticket:\n{self.ticket_seleccionado_str}", tipo="info")

        frame_btns = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_btns.pack(pady=20)
        ctk.CTkButton(frame_btns, text="Cancelar", fg_color="gray", hover_color="#7f8c8d", command=modal.destroy).pack(side="left", padx=10)
        ctk.CTkButton(frame_btns, text="Confirmar", command=confirmar, fg_color="#2ecc71", hover_color="#27ae60").pack(side="left", padx=10)

    def _abrir_modal_audio(self):
        modal = ctk.CTkToplevel(self)
        modal.overrideredirect(True) 
        modal.attributes('-topmost', True) 
        
        bg_frame = ctk.CTkFrame(modal, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)
        
        self._centrar_modal(modal, 420, 260)
        self._hacer_arrastrable(bg_frame, ventana=modal)
        modal.transient(self)
        modal.grab_set()

        btn_close = ctk.CTkButton(bg_frame, text="✖", width=25, height=25, fg_color="transparent", hover_color="#c0392b", command=modal.destroy)
        btn_close.place(relx=0.92, rely=0.12, anchor="center")

        lbl_titulo = ctk.CTkLabel(bg_frame, text="Dispositivos", font=ctk.CTkFont(weight="bold", size=15))
        lbl_titulo.pack(pady=(15, 0))
        self._hacer_arrastrable(lbl_titulo, ventana=modal)

        lbl_sub = ctk.CTkLabel(bg_frame, text="Toca un ícono para configurar", font=ctk.CTkFont(size=10, slant="italic"), text_color="gray")
        lbl_sub.pack(pady=(0, 10))

        frame_icons = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_icons.pack(pady=5)
        
        frame_content = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_content.pack(fill="x", padx=20, pady=5)
        
        cmb_mic = ctk.CTkComboBox(frame_content, width=360, values=["Cargando..."])
        cmb_spk = ctk.CTkComboBox(frame_content, width=360, values=["Cargando..."])
        
        cmb_mic.configure(command=lambda c: setattr(self, 'mic_name_selected', c))
        cmb_spk.configure(command=lambda c: setattr(self, 'spk_name_selected', c))

        def refresh():
            self.mics_dict, self.spks_dict = obtener_dispositivos_audio()
            n_mics = list(self.mics_dict.keys()) if self.mics_dict else ["Default"]
            n_spks = list(self.spks_dict.keys()) if self.spks_dict else ["Default"]
            
            cmb_mic.configure(values=n_mics)
            cmb_spk.configure(values=n_spks)
            
            cmb_mic.set(self.mic_name_selected if self.mic_name_selected in n_mics else n_mics[0])
            cmb_spk.set(self.spk_name_selected if self.spk_name_selected in n_spks else n_spks[0])

        def show_mic():
            refresh()
            cmb_spk.pack_forget() 
            cmb_mic.pack(pady=5)  
            lbl_sub.configure(text="Selecciona el Micrófono:")
            
        def show_spk():
            refresh()
            cmb_mic.pack_forget() 
            cmb_spk.pack(pady=5)  
            lbl_sub.configure(text="Selecciona el Altavoz:")

        btn_mic = ctk.CTkButton(frame_icons, image=self.img_icon_mic, text="", width=110, height=110, fg_color="transparent", hover_color="#2c3e50", command=show_mic)
        btn_mic.pack(side="left", padx=20)
        
        btn_spk = ctk.CTkButton(frame_icons, image=self.img_icon_speaker, text="", width=110, height=110, fg_color="transparent", hover_color="#2c3e50", command=show_spk)
        btn_spk.pack(side="left", padx=20)


    def _set_btn_state(self, state):
        self.current_btn_state = state
        if state == "READY":
            self.btn_central.configure(image=self.img_btn_grabar)
        elif state == "RECORDING":
            self.btn_central.configure(image=self.img_btn_grabando)
        elif state == "PROCESSING":
            self.btn_central.configure(image=self.img_btn_procesando)
        elif state == "ERROR":
            self.btn_central.configure(image=self.img_btn_error)
            
        self._cancelar_tooltip_central()

    def _al_entrar_mouse_btn(self, event):
        if self.current_btn_state == "READY":
            self.btn_central.configure(image=self.img_btn_grabar_shiny)
        elif self.current_btn_state == "RECORDING":
            self.btn_central.configure(image=self.img_btn_grabando_shiny)
        elif self.current_btn_state == "PROCESSING":
            self.btn_central.configure(image=self.img_btn_procesando_shiny)
        elif self.current_btn_state == "ERROR":
            self.btn_central.configure(image=self.img_btn_error_shiny)
            
        self._programar_tooltip_central()

    def _al_salir_mouse_btn(self, event):
        self._set_btn_state(self.current_btn_state)
        self._cancelar_tooltip_central()

    def _programar_tooltip_central(self):
        self._cancelar_tooltip_central()
        self.timer_tooltip_central = self.after(400, self._mostrar_tooltip_central)

    def _cancelar_tooltip_central(self, event=None):
        if self.timer_tooltip_central:
            self.after_cancel(self.timer_tooltip_central)
            self.timer_tooltip_central = None
        if self.tooltip_central:
            self.tooltip_central.destroy()
            self.tooltip_central = None

    def _mostrar_tooltip_central(self):
        self._cancelar_tooltip_central() 

        if self.current_btn_state == "PROCESSING":
            texto = "Posponer a Cola"
            color_texto = "#f39c12" 
        elif self.current_btn_state == "RECORDING":
            texto = "Detener Grabación"
            color_texto = "#e74c3c" 
        elif self.current_btn_state == "ERROR":
            texto = "Ver/Limpiar Errores"
            color_texto = "#e74c3c"
        else:
            texto = "Listo para grabar"
            color_texto = "#bdc3c7" 

        self.tooltip_central = ctk.CTkToplevel(self)
        self.tooltip_central.withdraw()
        self.tooltip_central.overrideredirect(True)
        self.tooltip_central.attributes('-topmost', True)
        
        bg_frame = ctk.CTkFrame(self.tooltip_central, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=8)
        bg_frame.pack(fill="both", expand=True)

        lbl = ctk.CTkLabel(bg_frame, text=texto, font=ctk.CTkFont(size=14, slant="italic"), text_color=color_texto, padx=15, pady=10)
        lbl.pack()

        self.tooltip_central.update_idletasks()
        
        x_btn = self.btn_central.winfo_rootx()
        y_btn = self.btn_central.winfo_rooty()
        
        ancho_btn = self.btn_central.winfo_width()
        alto_popup = lbl.winfo_reqheight()
        ancho_popup = lbl.winfo_reqwidth()

        x_final = x_btn + (ancho_btn // 2) - (ancho_popup // 2)
        y_final = y_btn - alto_popup - 10 

        self.tooltip_central.geometry(f"+{x_final}+{y_final}")
        self.tooltip_central.deiconify()

    def _manejar_clic_boton_redondo(self, event=None):
        if self.current_btn_state == "PROCESSING":
            self.posponer_procesamiento()
        elif self.current_btn_state == "ERROR":
            self._manejar_clic_error()
        else:
            self.toggle_grabacion()
            
    def _manejar_clic_error(self):
        pendientes = obtener_pendientes()
        items_error = [p for p in pendientes if p.get("estado") == "error"]
        
        if items_error:
            respuesta = self._mostrar_dialogo_custom(
                "Purgar Errores", 
                f"Tienes {len(items_error)} elemento(s) estancado(s) con error en la cola.\n\n¿Deseas descartarlos definitivamente y limpiar el sistema?",
                tipo="yesno"
            )
            if respuesta:
                for item in items_error:
                    eliminar_item_cola(item["id"])
                self.log("🗑️ Cola purgada de errores. Sistema limpio.")
                self._reset_indicators()
                self._set_btn_state("READY")
        else:
            self._set_btn_state("READY")

    def posponer_procesamiento(self):
        self.cola_pausada = True 
        
        if self.evento_abortar_actual:
            self.evento_abortar_actual.set()
            
        self.log("⏸️ Señal de posponer enviada. Liberando interfaz...")
        
        self._set_btn_state("READY")

    def _al_cambiar_perfil(self, valor):
        self.config["PERFIL_ACTIVO"] = valor
        guardar_config(self.config)
        
        if hasattr(self, 'btn_perfil'):
            if valor == "AMS" and self.img_ams_btn:
                self.btn_perfil.configure(image=self.img_ams_btn)
            elif valor == "GENERAL" and self.img_gen_btn:
                self.btn_perfil.configure(image=self.img_gen_btn)
                
        self.log(f"🔄 Perfil cambiado a: {valor}")
    
    def _abrir_explorador_drive(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.overrideredirect(True) 
        dialogo.attributes('-topmost', True) 
        
        bg_frame = ctk.CTkFrame(dialogo, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)
        
        self._centrar_modal(dialogo, 500, 500)
        self._hacer_arrastrable(bg_frame, ventana=dialogo)
        dialogo.transient(self)
        dialogo.grab_set()

        self.historial_navegacion = []

        btn_close = ctk.CTkButton(bg_frame, text="✖", width=25, height=25, fg_color="transparent", hover_color="#c0392b", command=dialogo.destroy)
        btn_close.place(relx=0.95, rely=0.06, anchor="center")

        lbl_titulo = ctk.CTkLabel(bg_frame, text="Destino", font=ctk.CTkFont(weight="bold", size=15))
        lbl_titulo.pack(pady=(15, 0))
        self._hacer_arrastrable(lbl_titulo, ventana=dialogo)

        lbl_ruta = ctk.CTkLabel(bg_frame, text="Ruta: Inicio", font=ctk.CTkFont(size=12), text_color="#bdc3c7", wraplength=480)
        lbl_ruta.pack(pady=(2, 10), padx=10, fill="x")
        self._hacer_arrastrable(lbl_ruta, ventana=dialogo)

        frame_botones_top = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_botones_top.pack(fill="x", padx=10)

        btn_atras = ctk.CTkButton(frame_botones_top, text="⬅ Atrás", width=60, height=25, fg_color="transparent", hover_color="#2c3e50", state="disabled")
        btn_atras.pack(side="left", pady=0)

        frame_lista = ctk.CTkScrollableFrame(bg_frame, width=460, height=320, fg_color="transparent")
        frame_lista.pack(pady=5, padx=10, fill="both", expand=True)

        def actualizar_vista():
            for widget in frame_lista.winfo_children(): widget.destroy()

            lbl_cargando = ctk.CTkLabel(frame_lista, text="⏳ Obteniendo carpetas...", text_color="gray")
            lbl_cargando.pack(pady=20)
            dialogo.update()

            def buscar_carpetas_hilo():
                try:
                    if not self.historial_navegacion:
                        carpetas = listar_unidades_y_compartidas()
                        es_raiz = True
                    else:
                        parent_id = self.historial_navegacion[-1][1]
                        carpetas = listar_subcarpetas(parent_id)
                        es_raiz = False
                    self.after(0, lambda: dibujar_carpetas(carpetas, es_raiz))
                except Exception as e:
                    self.after(0, lambda: dibujar_carpetas([], False, str(e)))

            def dibujar_carpetas(carpetas, es_raiz, error_msg=None):
                if not dialogo.winfo_exists(): return 

                lbl_cargando.destroy()
                
                if es_raiz:
                    lbl_ruta.configure(text="Ruta: Inicio")
                    btn_atras.configure(state="disabled")
                else:
                    ruta_str = " > ".join([item[0] for item in self.historial_navegacion])
                    lbl_ruta.configure(text=f"Ruta: {ruta_str}")
                    btn_atras.configure(state="normal")

                if error_msg:
                    ctk.CTkLabel(frame_lista, text=f"⚠️ Error: {error_msg}", text_color="#e74c3c").pack(pady=20)
                    return

                if not carpetas:
                    ctk.CTkLabel(frame_lista, text="📂 Carpeta vacía", text_color="gray").pack(pady=20)
                else:
                    for nombre, id_carpeta in carpetas:
                        btn = ctk.CTkButton(
                            frame_lista, text=f"📁 {nombre}", fg_color="transparent",
                            text_color=("black", "white"), hover_color=("#1A1C21", "#2a2d2e"), anchor="w", font=ctk.CTkFont(size=14),
                            command=lambda n=nombre, i=id_carpeta: entrar_carpeta(n, i)
                        )
                        btn.pack(fill="x", pady=2)

            threading.Thread(target=buscar_carpetas_hilo, daemon=True).start()

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
                self._mostrar_dialogo_custom("Atención", "Debes entrar a una carpeta para seleccionarla.", tipo="info")
                return
            nombre, id_carpeta = self.historial_navegacion[-1]
            
            self.carpeta_general_id = id_carpeta
            self.requiere_confirmar_carpeta = False
            self.log(f"📁 Destino GENERAL fijado en: {nombre}")
            
            dialogo.destroy()
            self._mostrar_dialogo_custom("Listo", f"Carpeta seleccionada exitosamente:\n{nombre}", tipo="info")

        btn_seleccionar = ctk.CTkButton(
            bg_frame, text="✅ Seleccionar esta carpeta", fg_color="#27ae60", hover_color="#1e8449", height=40, font=ctk.CTkFont(weight="bold"),
            command=seleccionar_carpeta
        )
        btn_seleccionar.pack(pady=(10, 15))

        actualizar_vista()        

    def log(self, mensaje):
        timestamp = time.strftime('%H:%M:%S')
        texto_formateado = f"[{timestamp}] {mensaje}"
        print(texto_formateado) 
        
        if hasattr(self, 'textbox_log'):
            self.textbox_log.insert("end", texto_formateado + "\n")
            self.textbox_log.see("end")

    def _pedir_motivo_obligatorio(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.overrideredirect(True) 
        dialogo.attributes('-topmost', True) 
        
        bg_frame = ctk.CTkFrame(dialogo, fg_color="#0D0F12", border_width=1, border_color="#34495e", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)
        
        self._centrar_modal(dialogo, 400, 240)
        self._hacer_arrastrable(bg_frame, ventana=dialogo)
        dialogo.transient(self)
        dialogo.grab_set()
        
        btn_close = ctk.CTkButton(bg_frame, text="✖", width=25, height=25, fg_color="transparent", hover_color="#c0392b", command=dialogo.destroy)
        btn_close.place(relx=0.92, rely=0.15, anchor="center")

        lbl_titulo = ctk.CTkLabel(bg_frame, text="Motivo", font=ctk.CTkFont(weight="bold", size=15))
        lbl_titulo.pack(pady=(15, 5))
        self._hacer_arrastrable(lbl_titulo, ventana=dialogo)

        ctk.CTkLabel(bg_frame, text="Requerido para el registro:", font=ctk.CTkFont(size=12), text_color="#bdc3c7").pack()
        
        entry_motivo = ctk.CTkEntry(bg_frame, width=300, placeholder_text="Ej: Demo_Cliente, Daily_Sync...")
        entry_motivo.pack(pady=10)
        entry_motivo.focus_force()
        
        motivo_final = [""]
        
        def continuar():
            texto = entry_motivo.get().strip()
            if not texto:
                self._mostrar_dialogo_custom("Falta Motivo", "Debes ingresar un motivo para continuar.", tipo="info")
                return
            motivo_final[0] = texto
            dialogo.destroy()
            
        frame_btns = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_btns.pack(pady=10)
        ctk.CTkButton(frame_btns, text="Cancelar", fg_color="gray", hover_color="#7f8c8d", command=dialogo.destroy).pack(side="left", padx=10)
        ctk.CTkButton(frame_btns, text="Continuar", fg_color="#2980b9", hover_color="#1f618d", command=continuar).pack(side="left", padx=10)
        dialogo.bind('<Return>', lambda e: continuar()) 
        
        self.wait_window(dialogo)
        return motivo_final[0]

    def toggle_grabacion(self):
        
        if not self.esta_grabando:
            perfil_actual = self.config.get("PERFIL_ACTIVO", "AMS")
            ticket_data = None
            custom_folder_id = None

            if perfil_actual == "AMS":
                seleccion = self.ticket_seleccionado_str
                if not seleccion or "No hay tickets" in seleccion:
                    self._mostrar_dialogo_custom("Aviso", "No hay un ticket válido seleccionado.\n\nHaz clic en el botón 'AMS' para elegir uno.", tipo="info")
                    return
                id_ticket = seleccion.split(" - ")[0]
                ticket_data = next((t for t in self.tickets_cargados if t["ID Ticket"] == id_ticket), None)
            else:
                custom_folder_id = self.carpeta_general_id 
                
                if custom_folder_id:
                    if self.requiere_confirmar_carpeta:
                        confirmar = self._mostrar_dialogo_custom(
                            "Confirmar Carpeta", 
                            "Actualmente tienes una carpeta de Drive seleccionada.\n¿Deseas guardar la nueva grabación en esa misma carpeta?",
                            tipo="yesno"
                        )
                        if not confirmar:
                            self.carpeta_general_id = "" 
                            return 
                else:
                    self._mostrar_dialogo_custom("Aviso", "Primero debes seleccionar una carpeta destino en Google Drive.", tipo="info")
                    self._abrir_explorador_drive()
                    return 

                ticket_motivo = self._pedir_motivo_obligatorio()
                if not ticket_motivo: 
                    return 
                    
                ticket_data = {"ID Ticket": "GEN-" + time.strftime("%H%M"), "Título": ticket_motivo, "Aplicacion": "General"}

            # Validación Audio
            mic_name = self.mic_name_selected
            spk_name = self.spk_name_selected
            
            es_mic_llamada = "Hands-Free" in mic_name or "Manos libres" in mic_name
            es_spk_llamada = "Hands-Free" in spk_name or "Manos libres" in spk_name

            if es_mic_llamada != es_spk_llamada:
                respuesta = self._mostrar_dialogo_custom(
                    "⚠️ Advertencia de Audio Bluetooth", 
                    "Estás mezclando un canal de Manos Libres (Llamadas) con un canal Estéreo.\n\nTeams o Meet no grabarán la voz del cliente.\n\n¿Deseas continuar?",
                    tipo="yesno"
                )
                if not respuesta: 
                    return

            self.ticket_data_actual = ticket_data
            self.custom_folder_id_actual = custom_folder_id
            
            if self.img_hdd_mid: self.lbl_status_hdd.configure(image=self.img_hdd_mid)

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
            
            self._set_btn_state("RECORDING")

            self.segundos_grabacion = 0
            self._actualizar_timer()
            self.log("▶️ Grabación iniciada.")
        else:
            self.grabador.detener()
            self.esta_grabando = False
            self.requiere_confirmar_carpeta = True
            
            self.cola_pausada = False 
            
            self._set_btn_state("PROCESSING")
            
            self.log("⏹ Grabación detenida.")

    def _actualizar_timer(self):
        if self.esta_grabando:
            self.segundos_grabacion += 1
            mins, secs = divmod(self.segundos_grabacion, 60)
            hours, mins = divmod(mins, 60)
            self.lbl_timer.configure(text=f"{hours:02d}:{mins:02d}:{secs:02d}")
            self.after(1000, self._actualizar_timer)

    def _lanzar_reintento(self):
        self._actualizar_ui_thread_safe("log", "🔄 Reintentando análisis de IA desde la cola...")
        if self.item_actual_id:
            actualizar_estado_item(self.item_actual_id, "pendiente")
            self.esta_procesando_cola = False
            self.cola_pausada = False 

    def _lanzar_eliminacion_error(self):
        if self.item_actual_id:
            eliminar_item_cola(self.item_actual_id)
            self.item_actual_id = None
            
        self.esta_procesando_cola = False
        self.cola_pausada = False 
        self._reset_indicators()

    def _mostrar_popup_error_fatal(self, mensaje):
        dialogo = ctk.CTkToplevel(self)
        dialogo.overrideredirect(True) 
        dialogo.attributes('-topmost', True) 
        
        bg_frame = ctk.CTkFrame(dialogo, fg_color="#0D0F12", border_width=1, border_color="#e74c3c", corner_radius=12)
        bg_frame.pack(fill="both", expand=True)
        
        self._centrar_modal(dialogo, 500, 260)
        self._hacer_arrastrable(bg_frame, ventana=dialogo)
        dialogo.transient(self)
        dialogo.grab_set()
        dialogo.focus_force()

        ruta_archivo = mensaje.split("disco:")[1].strip() if "disco:" in mensaje else (mensaje.split(":")[-1].strip() if ":" in mensaje else mensaje)

        lbl_titulo = ctk.CTkLabel(bg_frame, text="Error", font=ctk.CTkFont(weight="bold", size=15), text_color="#e74c3c")
        lbl_titulo.pack(pady=(15, 5))
        self._hacer_arrastrable(lbl_titulo, ventana=dialogo)
        
        ctk.CTkLabel(bg_frame, text="El sistema intentó documentar una reunión anterior, pero el archivo de video ya no existe en tu PC:", wraplength=460).pack(pady=(0, 5), padx=20)
        ctk.CTkLabel(bg_frame, text=ruta_archivo, font=ctk.CTkFont(size=11, slant="italic"), text_color="#bdc3c7", wraplength=460).pack(pady=(0, 15), padx=20)
        ctk.CTkLabel(bg_frame, text="¿Deseas descartar este registro de la cola para continuar?", font=ctk.CTkFont(weight="bold")).pack(pady=(0, 15))

        frame_botones = ctk.CTkFrame(bg_frame, fg_color="transparent")
        frame_botones.pack()

        def accion_descartar():
            self._lanzar_eliminacion_error()
            dialogo.destroy()
            self._set_btn_state("READY")

        def accion_cancelar():
            dialogo.destroy()
            self._set_btn_state("ERROR")

        ctk.CTkButton(frame_botones, text="Cancelar (Pausar Cola)", fg_color="gray", hover_color="#7f8c8d", command=accion_cancelar).pack(side="left", padx=10)
        ctk.CTkButton(frame_botones, text="🗑️ Descartar y Continuar", fg_color="#e74c3c", hover_color="#c0392b", command=accion_descartar).pack(side="left", padx=10)

    def _actualizar_ui_thread_safe(self, tipo, mensaje):
        self.after(0, lambda: self._procesar_evento_ui(tipo, mensaje))

    def _reset_indicators(self):
        if not self.esta_procesando_cola and not self.esta_grabando:
            if self.img_hdd_off: self.lbl_status_hdd.configure(image=self.img_hdd_off)
            if self.img_drive_off: self.lbl_status_drive.configure(image=self.img_drive_off)
            if self.img_gemini_off: self.lbl_status_gemini.configure(image=self.img_gemini_off)

    def _procesar_evento_ui(self, tipo, mensaje):
        if tipo == "log":
            self.log(mensaje)
            
            if "Subiendo video a Google Drive" in mensaje:
                if self.img_drive_mid: self.lbl_status_drive.configure(image=self.img_drive_mid)
                
            if "⏸️ Proceso pausado" in mensaje:
                self.esta_procesando_cola = False
                
        elif tipo == "inicio_procesamiento":
            self._set_btn_state("PROCESSING")
            
        elif tipo == "local_ok":
            self.ruta_local_actual = mensaje
            if self.img_hdd_on: self.lbl_status_hdd.configure(image=self.img_hdd_on)
            
        elif tipo == "en_cola":
            pass
            
        elif tipo == "drive_ok":
            self.url_drive_actual = mensaje
            if self.img_drive_on: self.lbl_status_drive.configure(image=self.img_drive_on)
            
        elif tipo == "gemini_inicio":
            if self.img_gemini_mid: self.lbl_status_gemini.configure(image=self.img_gemini_mid)
            
        elif tipo == "gemini_ok":
            if self.img_gemini_on: self.lbl_status_gemini.configure(image=self.img_gemini_on)
            
            # 📌 Actualización del Mensaje de Éxito solicitado
            res = self._mostrar_dialogo_custom(
                "¡Documentación Exitosa!", 
                "SandIA procesó el video y la minuta está lista.\n\n¿Deseas abrirla ahora?", 
                tipo="yesno"
            )
            if res: webbrowser.open(mensaje)
            
            if self.item_actual_id:
                eliminar_item_cola(self.item_actual_id)
                self.item_actual_id = None
                
            self.esta_procesando_cola = False
            self.after(3000, self._reset_indicators)
            
            if not self.esta_grabando:
                self._set_btn_state("READY")
                
        elif tipo == "error":
            if self.img_gemini_off: self.lbl_status_gemini.configure(image=self.img_gemini_off)
            
            mensaje_min = mensaje.lower()
            es_fatal = "ya no existe" in mensaje_min or "no se encuentra" in mensaje_min

            self.log(f"⚠️ {mensaje}")

            if es_fatal:
                self.cola_pausada = True 
                self._mostrar_popup_error_fatal(mensaje)
            else:
                respuesta = self._mostrar_dialogo_custom("Error en Procesamiento IA", f"Ocurrió un error:\n{mensaje}\n\n¿Deseas reintentar?", tipo="yesno")
                if respuesta:
                    self._lanzar_reintento()
                else:
                    if self.item_actual_id:
                        actualizar_estado_item(self.item_actual_id, "error", mensaje)
                    self.esta_procesando_cola = False
                    self._set_btn_state("ERROR")

if __name__ == "__main__":
    app = AplicacionGUI()
    app.mainloop()