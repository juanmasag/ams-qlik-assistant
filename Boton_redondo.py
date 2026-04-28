import customtkinter as ctk
import time
import sys
import os

# Ajustamos rutas para importar tus módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.grabador_corporativo import GrabadorCorporativo
from src.config_manager import cargar_config

# Configuración de apariencia
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppAsistente(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana
        self.title("Grabador Corporativo AMS Qlik - Pro v2.1")
        self.geometry("650x630")
        self.resizable(False, False)
        
        self.grabador = None
        self.config = cargar_config()
        self.esta_grabando = False
        self.segundos_grabacion = 0
        
        # Variables de control UX
        self.mouse_en_input = False
        self.input_tiene_foco = False

        self.MAX_CARACTERES = 50 

        # --- DISEÑO DE LA INTERFAZ ---
        self.grid_columnconfigure(0, weight=1)
        
        self._crear_cabecera()
        self._crear_barra_control()
        self._crear_panel_progreso()
        self._crear_panel_log()

        # SOLUCIÓN DE FOCO: Reemplazamos la función agresiva por la segura
        self.bind("<Button-1>", self._quitar_foco_seguro)

    def _quitar_foco_seguro(self, event):
        """Evita robar el foco si se hace clic en el recuadro de texto, permitiendo escribir."""
        if "entry" not in str(event.widget).lower():
            self.focus_set()

    def _crear_cabecera(self):
        """Bloque superior: Botón de grabación con colores manuales perfectos."""
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        frame_top.bind("<Button-1>", self._quitar_foco_seguro) 

        self.frame_btn_container = ctk.CTkFrame(frame_top, width=80, height=80, fg_color="transparent")
        self.frame_btn_container.pack(side="left", padx=(0, 20))
        self.frame_btn_container.pack_propagate(False)

        # BOTÓN VACÍO: Desactivamos el hover nativo (hover=False) para controlarlo nosotros
        self.btn_rec = ctk.CTkButton(
            self.frame_btn_container, 
            text="", 
            width=80, height=80, corner_radius=40,
            fg_color="#27ae60", 
            border_width=8, border_color="#1e2024", 
            hover=False, 
            command=self.toggle_grabacion
        )
        self.btn_rec.place(x=0, y=0)

        # ÍCONO FLOTANTE: Le asignamos exactamente el mismo color inicial que el botón
        self.icono_centro = ctk.CTkLabel(
            self.btn_rec, text="▶", text_color="white", font=ctk.CTkFont(size=32),
            fg_color="#27ae60" 
        )
        self.icono_centro.place(relx=0.54, rely=0.5, anchor="center")
        self.icono_centro.bind("<Button-1>", lambda e: self.toggle_grabacion())

        # Textos al lado del botón
        frame_textos = ctk.CTkFrame(frame_top, fg_color="transparent")
        frame_textos.pack(side="left")
        frame_textos.bind("<Button-1>", self._quitar_foco_seguro)

        self.label_titulo = ctk.CTkLabel(frame_textos, text="ASISTENTE DE REUNIONES AMS", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_titulo.pack(anchor="w")

        self.lbl_estado = ctk.CTkLabel(frame_textos, text="Sistema Listo", font=ctk.CTkFont(size=18))
        self.lbl_estado.pack(anchor="w")
        
        self.lbl_timer = ctk.CTkLabel(frame_textos, text="00:00:00", text_color="gray", font=ctk.CTkFont(size=16))
        self.lbl_timer.pack(anchor="w")
        
        # POPUP DE VALIDACIÓN INICIAL
        self.lbl_val_popup = ctk.CTkLabel(
            self, text="", fg_color="#f39c12", text_color="black", 
            corner_radius=4, height=22, font=ctk.CTkFont(size=11, weight="bold")
        )

        self.btn_rec.bind("<Enter>", self._al_entrar_mouse_btn_iniciar)
        self.btn_rec.bind("<Leave>", self._al_salir_mouse_btn_iniciar)
        self.icono_centro.bind("<Enter>", self._al_entrar_mouse_btn_iniciar)
        self.icono_centro.bind("<Leave>", self._al_salir_mouse_btn_iniciar)

    def _crear_barra_control(self):
        """Bloque medio: Pestañas dinámicas y campo de texto."""
        self.frame_ctrl = ctk.CTkFrame(self)
        self.frame_ctrl.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_ctrl.grid_columnconfigure(0, weight=1)
        self.frame_ctrl.bind("<Button-1>", self._quitar_foco_seguro) 
        
        self.seg_perfil = ctk.CTkSegmentedButton(
            self.frame_ctrl, values=["AMS", "GENERAL"], command=self._al_cambiar_perfil
        )
        self.seg_perfil.set("AMS")
        self.seg_perfil.pack(side="left", padx=15, pady=20) 

        self.lbl_input = ctk.CTkLabel(self.frame_ctrl, text="Seleccionar Ticket:", text_color="gray")
        self.lbl_input.pack(side="left", padx=(10, 5))

        self.frame_input_container = ctk.CTkFrame(self.frame_ctrl, fg_color="transparent")
        self.frame_input_container.pack(side="left", fill="x", expand=True)

        self.combo_ticket = ctk.CTkComboBox(
            self.frame_input_container, width=280, values=["Cargando backlog...", "CHG0051798 - Mapas Bolsa Cereales"]
        )
        self.combo_ticket.bind("<<ComboboxSelected>>", self._al_interactuar_con_combo)

        self.var_texto = ctk.StringVar()
        self.var_texto.trace_add("write", self._limitar_caracteres)
        self.entry_input = ctk.CTkEntry(
            self.frame_input_container, width=280, textvariable=self.var_texto, placeholder_text="Ej: Demo cliente externo"
        )
        
        self.lbl_contador_popup = ctk.CTkLabel(
            self.frame_ctrl, text="", fg_color="#2c3e50", text_color="white", 
            corner_radius=4, height=22, font=ctk.CTkFont(size=11, weight="bold")
        )

        self.entry_input.bind("<Enter>", self._al_entrar_mouse_input)     
        self.entry_input.bind("<Leave>", self._al_salir_mouse_input)      
        self.entry_input.bind("<FocusIn>", self._al_ganar_foco_input)   
        self.entry_input.bind("<FocusOut>", self._al_perder_foco_input)   

        self.combo_ticket.pack(side="left", padx=5)

    def _crear_panel_progreso(self):
        """Bloque de barras de carga."""
        frame_progreso = ctk.CTkFrame(self)
        frame_progreso.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        frame_progreso.bind("<Button-1>", self._quitar_foco_seguro) 

        ctk.CTkLabel(frame_progreso, text="Disponible en local", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.pb_local = ctk.CTkProgressBar(frame_progreso, width=550, progress_color="#2ecc71")
        self.pb_local.set(0)
        self.pb_local.grid(row=1, column=0, padx=15, pady=0, sticky="w")
        self.lbl_local_desc = ctk.CTkLabel(frame_progreso, text="Esperando...", text_color="gray", font=ctk.CTkFont(size=11))
        self.lbl_local_desc.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="w")

        ctk.CTkLabel(frame_progreso, text="Disponible en Drive", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, padx=15, pady=(5, 5), sticky="w")
        self.pb_drive = ctk.CTkProgressBar(frame_progreso, width=550, progress_color="#2ecc71")
        self.pb_drive.set(0)
        self.pb_drive.grid(row=4, column=0, padx=15, pady=0, sticky="w")
        self.lbl_drive_desc = ctk.CTkLabel(frame_progreso, text="Esperando...", text_color="gray", font=ctk.CTkFont(size=11))
        self.lbl_drive_desc.grid(row=5, column=0, padx=15, pady=(0, 10), sticky="w")

        ctk.CTkLabel(frame_progreso, text="Análisis en Gemini", font=ctk.CTkFont(weight="bold")).grid(row=6, column=0, padx=15, pady=(5, 5), sticky="w")
        self.pb_gemini = ctk.CTkProgressBar(frame_progreso, width=550, progress_color="#3498db")
        self.pb_gemini.set(0)
        self.pb_gemini.grid(row=7, column=0, padx=15, pady=(0, 15), sticky="w")

    def _crear_panel_log(self):
        """Bloque inferior: Log de actividad."""
        frame_log = ctk.CTkFrame(self)
        frame_log.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.grid_rowconfigure(3, weight=1)
        frame_log.bind("<Button-1>", self._quitar_foco_seguro) 

        ctk.CTkLabel(frame_log, text="🕒 Log de Actividad", text_color="gray", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(5, 0))
        self.textbox_log = ctk.CTkTextbox(frame_log, fg_color="transparent", text_color="#ecf0f1")
        self.textbox_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.log("Sistema de interfaz iniciado correctamente.")

    # --- LÓGICA DE LA INTERFAZ Y EVENTOS ---

    def log(self, mensaje):
        """Escribe mensajes en la consola de la ventana."""
        hora = time.strftime("%H:%M:%S")
        self.textbox_log.insert("end", f"[{hora}] {mensaje}\n")
        self.textbox_log.see("end")

    def toggle_grabacion(self):
        """Maneja el inicio y fin de la grabación."""
        if self.esta_grabando:
            # --- DETENER GRABACIÓN ---
            self.esta_grabando = False
            self.log("Deteniendo motor de grabación...")
            
            self.lbl_estado.configure(text="Consolidando...", text_color="#f39c12")
            
            self.icono_centro.configure(text="⏳", font=ctk.CTkFont(size=24))
            self.icono_centro.place(relx=0.5, rely=0.5, anchor="center")
            
            # Forzamos el camuflaje visual al instante
            self._al_entrar_mouse_btn_iniciar(None) 
            
            # Detener motor de grabación real
            # if self.grabador: self.grabador.detener()
        else:
            # --- INICIAR GRABACIÓN ---
            if self.seg_perfil.get() == "AMS":
                ticket = self.combo_ticket.get()
                if not ticket or ticket == "Despliegue para seleccionar ...":
                    self.lbl_estado.configure(text="⚠️ Faltan datos", text_color="#f39c12")
                    self.log("⛔ Error: Debes seleccionar un ticket de la lista.")
                    return
            else:
                motivo = self.var_texto.get().strip()
                if not motivo:
                    self.lbl_estado.configure(text="⚠️ Faltan datos", text_color="#f39c12")
                    self.log("⛔ Error: Coloque un nombre al video.")
                    self.entry_input.focus_set() 
                    return
            
            self.log("Buscando carpeta en Drive...")
            self.log("▶ Iniciando motor de grabación (Video + Mic + System)...")
            
            # self.grabador = GrabadorCorporativo()
            # self.grabador.iniciar()
            
            self.esta_grabando = True
            self.segundos_grabacion = 0
            
            self.lbl_estado.configure(text="Grabando...", text_color="#e74c3c")
            
            self.icono_centro.configure(text="■", font=ctk.CTkFont(size=26)) 
            self.icono_centro.place(relx=0.5, rely=0.5, anchor="center") 
            
            self.lbl_val_popup.place_forget()
            self.seg_perfil.configure(state="disabled")
            self.combo_ticket.configure(state="disabled")
            self.entry_input.configure(state="disabled")
            
            # Forzamos el camuflaje visual al instante
            self._al_entrar_mouse_btn_iniciar(None) 
            
            self._actualizar_timer()

    def _actualizar_timer(self):
        """Cronómetro de grabación."""
        if self.esta_grabando:
            minutos, segundos = divmod(self.segundos_grabacion, 60)
            horas, minutos = divmod(minutos, 60)
            self.lbl_timer.configure(text=f"{horas:02d}:{minutos:02d}:{segundos:02d}")
            self.segundos_grabacion += 1
            self.after(1000, self._actualizar_timer)

    # --- EVENTOS UX: CAMUFLAJE MANUAL DEL BOTÓN (Nuevo) ---

    def _al_entrar_mouse_btn_iniciar(self, event):
        # Determinamos el color correcto para el efecto HOVER (mouse encima)
        if self.lbl_estado.cget("text") == "Consolidando...":
            color_fondo = "#7f8c8d"  # Gris Hover
        elif self.esta_grabando:
            color_fondo = "#c0392b"  # Rojo Hover
        else:
            color_fondo = "#2ecc71"  # Verde Hover
            
        # MAGIA: Pintamos el botón Y la etiqueta del mismo color exacto
        self.btn_rec.configure(fg_color=color_fondo)
        self.icono_centro.configure(fg_color=color_fondo)

        if not self.esta_grabando and self.lbl_estado.cget("text") != "Consolidando...":
            mensaje = self._obtener_mensaje_validacion_faltante()
            if mensaje:
                self.lbl_val_popup.configure(text=f" {mensaje} ")
                self.lbl_val_popup.place(x=130, y=10) 
            else:
                self.lbl_val_popup.place_forget()

    def _al_salir_mouse_btn_iniciar(self, event):
        # Determinamos el color NORMAL (mouse fuera)
        if self.lbl_estado.cget("text") == "Consolidando...":
            color_fondo = "#7f8c8d"  # Gris Normal
        elif self.esta_grabando:
            color_fondo = "#d63b3b"  # Rojo Normal
        else:
            color_fondo = "#27ae60"  # Verde Normal
            
        # MAGIA: Revertimos ambos elementos juntos
        self.btn_rec.configure(fg_color=color_fondo)
        self.icono_centro.configure(fg_color=color_fondo)

        self.lbl_val_popup.place_forget()


    # --- EVENTOS UX: PESTAÑAS E INPUTS (INTACTOS) ---

    def _al_cambiar_perfil(self, perfil):
        self.combo_ticket.pack_forget()
        self.entry_input.pack_forget()
        self.lbl_contador_popup.place_forget()
        self.lbl_val_popup.place_forget() 

        if perfil == "AMS":
            self.lbl_input.configure(text="Seleccionar Ticket:")
            self.combo_ticket.pack(side="left", padx=5)
        else:
            self.lbl_input.configure(text="Descripción de la reunión:")
            self.var_texto.set("")
            self.entry_input.pack(side="left", padx=5)

    def _al_entrar_mouse_input(self, event):
        self.mouse_en_input = True
        if self.seg_perfil.get() == "GENERAL":
            self._actualizar_contador()
            self.lbl_contador_popup.place(x=350, y=0) 

    def _al_salir_mouse_input(self, event):
        self.mouse_en_input = False
        if not self.input_tiene_foco:
            self.lbl_contador_popup.place_forget()

    def _al_ganar_foco_input(self, event):
        self.input_tiene_foco = True
        if self.seg_perfil.get() == "GENERAL":
            self._actualizar_contador()
            self.lbl_contador_popup.place(x=350, y=0)

    def _al_perder_foco_input(self, event):
        self.input_tiene_foco = False
        if not self.mouse_en_input:
            self.lbl_contador_popup.place_forget()

    def _limitar_caracteres(self, *args):
        self._verificar_y_ocultar_popup_validacion()
        if self.seg_perfil.get() == "GENERAL":
            texto_actual = self.var_texto.get()
            if len(texto_actual) > self.MAX_CARACTERES:
                self.var_texto.set(texto_actual[:self.MAX_CARACTERES])
            self._actualizar_contador()

    def _al_interactuar_con_combo(self, event):
        self._verificar_y_ocultar_popup_validacion()

    def _actualizar_contador(self):
        restantes = self.MAX_CARACTERES - len(self.var_texto.get())
        color = "#c0392b" if restantes <= 5 else "#2c3e50"
        self.lbl_contador_popup.configure(text=f" {restantes}/50 ", fg_color=color)

    # --- LÓGICA: POPUP DE VALIDACIÓN ---

    def _obtener_mensaje_validacion_faltante(self):
        if self.seg_perfil.get() == "AMS":
            ticket = self.combo_ticket.get()
            if not ticket or ticket == "Despliegue para seleccionar ...":
                return "Seleccione un ticket de la lista"
        else:
            motivo = self.var_texto.get().strip()
            if not motivo:
                return "Coloque un nombre al video"
        return None 

    def _verificar_y_ocultar_popup_validacion(self):
        if not self._obtener_mensaje_validacion_faltante():
            self.lbl_val_popup.place_forget()

if __name__ == "__main__":
    app = AppAsistente()
    app.mainloop()