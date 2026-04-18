import customtkinter as ctk
import sys
import os

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppAsistentePremium(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Grabador Corporativo")
        self.geometry("650x600")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)

        self.MAX_CARACTERES = 50 
        self.mouse_en_input = False 

        self._crear_cabecera()
        self._crear_barra_control()
        self._crear_panel_progreso()
        self._crear_panel_log()

    def _crear_cabecera(self):
        """Bloque superior: Botón de grabación circular a prueba de escalado de Windows."""
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # CONTENEDOR LIBRE: Al no fijar height y width, evitamos que Windows recorte el botón.
        self.frame_btn_container = ctk.CTkFrame(frame_top, fg_color="transparent")
        self.frame_btn_container.pack(side="left", padx=(0, 20))

        # EL BOTÓN (Indestructible)
        self.btn_record = ctk.CTkButton(
            self.frame_btn_container, 
            text="", 
            width=80, 
            height=80, 
            corner_radius=40,
            fg_color="#d63b3b", 
            hover_color="#c0392b", 
            border_width=8, 
            border_color="#1e2024",
            command=self._accion_boton_falsa
        )
        self.btn_record.pack() # Usamos pack() en lugar de place() para que no se deforme

        # ICONO STOP (El cuadradito blanco en el centro)
        self.icono_stop = ctk.CTkFrame(
            self.btn_record, 
            width=20, 
            height=20, 
            corner_radius=3, 
            fg_color="white",
            bg_color="transparent"
        )
        self.icono_stop.place(relx=0.5, rely=0.5, anchor="center")
        self.icono_stop.bind("<Button-1>", lambda e: self.btn_record._invoke(e))

        # Textos al lado del botón
        frame_textos = ctk.CTkFrame(frame_top, fg_color="transparent")
        frame_textos.pack(side="left")

        self.lbl_estado = ctk.CTkLabel(frame_textos, text="Sistema Listo", font=ctk.CTkFont(size=22, weight="bold"))
        self.lbl_estado.pack(anchor="w")
        
        self.lbl_timer = ctk.CTkLabel(frame_textos, text="00:00:00", text_color="gray", font=ctk.CTkFont(size=16))
        self.lbl_timer.pack(anchor="w")

    def _crear_barra_control(self):
        """Bloque medio: Pestañas dinámicas y campo de texto con popup inteligente."""
        self.frame_ctrl = ctk.CTkFrame(self)
        self.frame_ctrl.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.seg_perfil = ctk.CTkSegmentedButton(
            self.frame_ctrl, values=["AMS", "GENERAL"], 
            command=self._al_cambiar_perfil
        )
        self.seg_perfil.set("AMS")
        self.seg_perfil.pack(side="left", padx=15, pady=20) 

        self.lbl_input = ctk.CTkLabel(self.frame_ctrl, text="Seleccionar Ticket:", text_color="gray")
        self.lbl_input.pack(side="left", padx=(10, 5))

        self.frame_input_container = ctk.CTkFrame(self.frame_ctrl, fg_color="transparent")
        self.frame_input_container.pack(side="left", fill="x", expand=True)

        self.combo_ticket = ctk.CTkComboBox(
            self.frame_input_container, width=280, 
            values=["Cargando backlog...", "CHG0051798 - Mapas Bolsa Cereales"]
        )

        self.var_texto = ctk.StringVar()
        self.var_texto.trace_add("write", self._limitar_caracteres)
        self.entry_input = ctk.CTkEntry(
            self.frame_input_container, width=280, 
            textvariable=self.var_texto, placeholder_text="Ej: Demo cliente externo"
        )
        
        self.lbl_contador_popup = ctk.CTkLabel(
            self.frame_ctrl, text="", fg_color="#2c3e50", text_color="white", 
            corner_radius=4, height=22, font=ctk.CTkFont(size=11, weight="bold")
        )

        # EVENTOS UX
        self.entry_input.bind("<Enter>", self._al_entrar_mouse)     
        self.entry_input.bind("<Leave>", self._al_salir_mouse)      
        self.entry_input.bind("<FocusIn>", self._al_ganar_foco)   
        self.entry_input.bind("<FocusOut>", self._al_perder_foco)   

        self.combo_ticket.pack(side="left", padx=5)

    # --- LÓGICA DE LA INTERFAZ ---

    def _accion_boton_falsa(self):
        pass

    def _al_cambiar_perfil(self, perfil):
        self.combo_ticket.pack_forget()
        self.entry_input.pack_forget()
        self.lbl_contador_popup.place_forget()

        if perfil == "AMS":
            self.lbl_input.configure(text="Seleccionar Ticket:")
            self.combo_ticket.pack(side="left", padx=5)
        else:
            self.lbl_input.configure(text="Motivo de la grabación:")
            self.var_texto.set("")
            self.entry_input.pack(side="left", padx=5)

    def _al_entrar_mouse(self, event):
        self.mouse_en_input = True
        if self.seg_perfil.get() == "GENERAL":
            self._actualizar_contador()

    def _al_salir_mouse(self, event):
        self.mouse_en_input = False
        # Mantiene el popup si se está escribiendo adentro
        if self.focus_get() != self.entry_input:
            self.lbl_contador_popup.place_forget()

    def _al_ganar_foco(self, event):
        if self.seg_perfil.get() == "GENERAL":
            self._actualizar_contador()

    def _al_perder_foco(self, event):
        # Desaparece al clicar fuera si no tenés el mouse encima
        if not self.mouse_en_input:
            self.lbl_contador_popup.place_forget()

    def _limitar_caracteres(self, *args):
        if self.seg_perfil.get() == "GENERAL":
            texto_actual = self.var_texto.get()
            if len(texto_actual) > self.MAX_CARACTERES:
                self.var_texto.set(texto_actual[:self.MAX_CARACTERES])
            
            # Forzar actualización visual mientras se teclea
            self._actualizar_contador()

    def _actualizar_contador(self):
        restantes = self.MAX_CARACTERES - len(self.var_texto.get())
        if restantes <= 5:
            self.lbl_contador_popup.configure(text=f" {restantes} restantes ", fg_color="#c0392b")
        else:
            self.lbl_contador_popup.configure(text=f" {restantes} restantes ", fg_color="#2c3e50")
        
        # Muestra el popup si no estaba visible
        self.lbl_contador_popup.place(x=350, y=0)

    # --- RESTO DEL DISEÑO ---

    def _crear_panel_progreso(self):
        frame_progreso = ctk.CTkFrame(self)
        frame_progreso.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        lbl_local = ctk.CTkLabel(frame_progreso, text="Disponible en local", font=ctk.CTkFont(weight="bold"))
        lbl_local.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.pb_local = ctk.CTkProgressBar(frame_progreso, width=550, progress_color="#2ecc71")
        self.pb_local.set(0)
        self.pb_local.grid(row=1, column=0, padx=15, pady=0, sticky="w")
        lbl_local_desc = ctk.CTkLabel(frame_progreso, text="Esperando grabación...", text_color="gray", font=ctk.CTkFont(size=11))
        lbl_local_desc.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="w")

        lbl_drive = ctk.CTkLabel(frame_progreso, text="Disponible en Drive", font=ctk.CTkFont(weight="bold"))
        lbl_drive.grid(row=3, column=0, padx=15, pady=(5, 5), sticky="w")
        self.pb_drive = ctk.CTkProgressBar(frame_progreso, width=550, progress_color="#2ecc71")
        self.pb_drive.set(0)
        self.pb_drive.grid(row=4, column=0, padx=15, pady=0, sticky="w")
        lbl_drive_desc = ctk.CTkLabel(frame_progreso, text="Esperando...", text_color="gray", font=ctk.CTkFont(size=11))
        lbl_drive_desc.grid(row=5, column=0, padx=15, pady=(0, 10), sticky="w")

        lbl_gemini = ctk.CTkLabel(frame_progreso, text="Análisis en Gemini", font=ctk.CTkFont(weight="bold"))
        lbl_gemini.grid(row=6, column=0, padx=15, pady=(5, 5), sticky="w")
        self.pb_gemini = ctk.CTkProgressBar(frame_progreso, width=550, progress_color="#3498db")
        self.pb_gemini.set(0)
        self.pb_gemini.grid(row=7, column=0, padx=15, pady=(0, 15), sticky="w")

    def _crear_panel_log(self):
        frame_log = ctk.CTkFrame(self)
        frame_log.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.grid_rowconfigure(3, weight=1)

        lbl_tit_log = ctk.CTkLabel(frame_log, text="🕒 Log de Actividad", text_color="gray", font=ctk.CTkFont(size=12))
        lbl_tit_log.pack(anchor="w", padx=10, pady=(5, 0))

        self.textbox_log = ctk.CTkTextbox(frame_log, fg_color="transparent", text_color="#ecf0f1")
        self.textbox_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.textbox_log.insert("end", "Sistema de interfaz iniciado correctamente.\n")

if __name__ == "__main__":
    app = AppAsistentePremium()
    app.mainloop()