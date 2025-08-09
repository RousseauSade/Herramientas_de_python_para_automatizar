import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, simpledialog
from pathlib import Path
import json
import win32com.client
from tkinter.scrolledtext import ScrolledText
import threading
import datetime

# Ruta fija para informe de búsqueda (ahora configurable)
RUTA_INFORME_BUSQUEDA = r"C:\Users\carlos.montes\OneDrive - Grupo Socofar\Archivos\informe_busqueda.txt"
CONFIG_FILE = "ruta_config.json"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Herramienta de Manejo de Archivos Avanzada")
        self.root.geometry("900x800")
        self.root.resizable(True, True)
        
        # Variables de instancia
        self.patrones_busqueda = []
        self.progress_var = tk.DoubleVar()
        self.progress_label_var = tk.StringVar(value="Listo")
        self.stop_operation = False
        
        # Cargar configuración
        self.config = self.cargar_config()
        
        # Configurar estilo
        self.setup_styles()
        
        # Crear interfaz
        self.setup_ui()
        
    def setup_styles(self):
        """Configura los estilos visuales de la aplicación"""
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#f0f0f0')
        style.configure('TButton', font=('Arial', 10), padding=5, background='#e1e1e1')
        style.configure('TLabel', background='#f0f0f0', font=('Arial', 9))
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'), foreground='#2c3e50')
        style.configure('Subtitle.TLabel', font=('Arial', 11, 'bold'), foreground='#2c3e50')
        style.configure('Info.TLabel', font=('Arial', 8), foreground='#7f8c8d')
        style.configure('TEntry', font=('Arial', 9))
        style.configure('TProgressbar', thickness=20)
        style.map('TButton',
                  background=[('active', '#d5d5d5'), ('pressed', '#c9c9c9')],
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

    def cargar_config(self):
        """Carga la configuración desde el archivo JSON o crea una nueva si no existe"""
        if Path(CONFIG_FILE).exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}

        # Valores por defecto
        defaults = {
            "directorio_busqueda": r"C:\Users\carlos.montes\OneDrive - Grupo Socofar\BANCO DE LA REPUBLICA (CARTAS)\3. MARZO",
            "directorio_busqueda_buscar": r"C:\Users\carlos.montes\OneDrive - Grupo Socofar\BANCO DE LA REPUBLICA (CARTAS)\3. MARZO",
            "directorio_busqueda_copiar": r"C:\Users\carlos.montes\OneDrive - Grupo Socofar\BANCO DE LA REPUBLICA (CARTAS)\3. MARZO",
            "directorio_busqueda_renombrar": r"C:\Users\carlos.montes\OneDrive - Grupo Socofar\BANCO DE LA REPUBLICA (CARTAS)\3. MARZO",
            "directorio_destino_copiar": r"C:\Users\carlos.montes\OneDrive - Grupo Socofar\Archivos\Copiados",
            "directorio_destino_renombrar": r"C:\Users\carlos.montes\OneDrive - Grupo Socofar\Archivos\Renombrados",
            "extension_filtro": "*",
            "patrones_busqueda": [],
            "ruta_informe_busqueda": RUTA_INFORME_BUSQUEDA
        }

        for key, value in defaults.items():
            if key not in config:
                config[key] = value

        # Cargar patrones de búsqueda si existen
        if "patrones_busqueda" in config:
            self.patrones_busqueda = config["patrones_busqueda"]

        return config

    def guardar_config(self):
        """Guarda la configuración en el archivo JSON"""
        self.config["patrones_busqueda"] = self.patrones_busqueda
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    def setup_ui(self):
        """Configura la interfaz de usuario principal"""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Título principal
        ttk.Label(main_frame, text="Herramienta de Manejo de Archivos", style='Title.TLabel').pack(pady=(0, 20))
        
        # Notebook (pestañas)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña de Búsqueda
        self.setup_busqueda_tab(notebook)
        
        # Pestaña de Copia
        self.setup_copiar_tab(notebook)
        
        # Pestaña de Renombrar
        self.setup_renombrar_tab(notebook)
        
        # Configuración general
        self.setup_config_frame(main_frame)
        
        # Barra de progreso y estado
        self.setup_progress_frame(main_frame)
        
        # Pie de página
        self.setup_footer_frame(main_frame)

    def setup_busqueda_tab(self, notebook):
        """Configura la pestaña de búsqueda"""
        tab_buscar = ttk.Frame(notebook)
        notebook.add(tab_buscar, text="Búsqueda")
        
        # Frame de patrones de búsqueda
        patrones_frame = ttk.LabelFrame(tab_buscar, text=" Patrones de Búsqueda ")
        patrones_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Área de texto para patrones
        self.patrones_text = ScrolledText(patrones_frame, height=8, wrap=tk.WORD, font=('Arial', 9))
        self.patrones_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Cargar patrones existentes
        if self.patrones_busqueda:
            self.patrones_text.insert(tk.END, "\n".join(self.patrones_busqueda))
        
        # Frame de configuración de búsqueda
        search_frame = ttk.LabelFrame(tab_buscar, text=" Configuración de Búsqueda ")
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Directorio de búsqueda
        ttk.Label(search_frame, text="Directorio a buscar:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.ruta_buscar_var = tk.StringVar(value=self.config["directorio_busqueda_buscar"])
        ruta_entry = ttk.Entry(search_frame, textvariable=self.ruta_buscar_var, font=('Arial', 9))
        ruta_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Button(search_frame, text="Cambiar...", 
                  command=lambda: self.cambiar_ruta("directorio_busqueda_buscar", self.ruta_buscar_var)).grid(row=0, column=2, padx=5, pady=2)
        
        # Ruta del informe de búsqueda
        ttk.Label(search_frame, text="Ruta del informe:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.ruta_informe_busqueda_var = tk.StringVar(value=self.config["ruta_informe_busqueda"])
        ttk.Entry(search_frame, textvariable=self.ruta_informe_busqueda_var, font=('Arial', 9)).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Button(search_frame, text="Cambiar...", 
                  command=self.cambiar_ruta_informe_busqueda).grid(row=1, column=2, padx=5, pady=2)
        
        # Botón de búsqueda
        ttk.Button(tab_buscar, text="Ejecutar Búsqueda", style='TButton',
                  command=self.ejecutar_busqueda).pack(pady=(5, 10))
        
        # Configurar peso de columnas
        search_frame.columnconfigure(1, weight=1)

    def setup_copiar_tab(self, notebook):
        """Configura la pestaña de copia"""
        tab_copiar = ttk.Frame(notebook)
        notebook.add(tab_copiar, text="Copiar")
        
        # Frame de configuración de copia
        copy_frame = ttk.LabelFrame(tab_copiar, text=" Configuración de Copia ")
        copy_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Directorio de búsqueda
        ttk.Label(copy_frame, text="Directorio a buscar:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.ruta_copiar_var = tk.StringVar(value=self.config["directorio_busqueda_copiar"])
        ttk.Entry(copy_frame, textvariable=self.ruta_copiar_var).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Button(copy_frame, text="Cambiar...", 
                  command=lambda: self.cambiar_ruta("directorio_busqueda_copiar", self.ruta_copiar_var)).grid(row=0, column=2, padx=5, pady=2)
        
        # Directorio destino
        ttk.Label(copy_frame, text="Directorio destino:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.ruta_destino_copiar_var = tk.StringVar(value=self.config["directorio_destino_copiar"])
        ttk.Entry(copy_frame, textvariable=self.ruta_destino_copiar_var).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Button(copy_frame, text="Cambiar...", 
                  command=lambda: self.cambiar_ruta("directorio_destino_copiar", self.ruta_destino_copiar_var)).grid(row=1, column=2, padx=5, pady=2)
        
        # Botón de copia
        ttk.Button(tab_copiar, text="Ejecutar Búsqueda y Copia", style='TButton',
                  command=self.ejecutar_copia).pack(pady=(5, 10))
        
        # Configurar peso de columnas
        copy_frame.columnconfigure(1, weight=1)

    def setup_renombrar_tab(self, notebook):
        """Configura la pestaña de renombrado"""
        tab_renombrar = ttk.Frame(notebook)
        notebook.add(tab_renombrar, text="Renombrar")
        
        # Frame de configuración de renombrado
        rename_frame = ttk.LabelFrame(tab_renombrar, text=" Configuración de Renombrado ")
        rename_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Directorio de búsqueda
        ttk.Label(rename_frame, text="Directorio a buscar:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.ruta_renombrar_var = tk.StringVar(value=self.config["directorio_busqueda_renombrar"])
        ttk.Entry(rename_frame, textvariable=self.ruta_renombrar_var).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Button(rename_frame, text="Cambiar...", 
                  command=lambda: self.cambiar_ruta("directorio_busqueda_renombrar", self.ruta_renombrar_var)).grid(row=0, column=2, padx=5, pady=2)
        
        # Directorio destino
        ttk.Label(rename_frame, text="Directorio destino:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        self.ruta_destino_renombrar_var = tk.StringVar(value=self.config["directorio_destino_renombrar"])
        ttk.Entry(rename_frame, textvariable=self.ruta_destino_renombrar_var).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        
        ttk.Button(rename_frame, text="Cambiar...", 
                  command=lambda: self.cambiar_ruta("directorio_destino_renombrar", self.ruta_destino_renombrar_var)).grid(row=1, column=2, padx=5, pady=2)
        
        # Botón de renombrado
        ttk.Button(tab_renombrar, text="Ejecutar Búsqueda y Renombrar", style='TButton',
                  command=self.ejecutar_renombrado).pack(pady=(5, 10))
        
        # Configurar peso de columnas
        rename_frame.columnconfigure(1, weight=1)

    def setup_config_frame(self, parent):
        """Configura el frame de configuración general"""
        config_frame = ttk.LabelFrame(parent, text=" Configuración General ")
        config_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Filtro por extensión
        ttk.Button(config_frame, text="Configurar Filtro por Extensión", 
                  command=self.cambiar_extension_filtro).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Botón para detener operación
        ttk.Button(config_frame, text="Detener Operación", 
                  command=self.detener_operacion).pack(side=tk.RIGHT, padx=5, pady=5)

    def setup_progress_frame(self, parent):
        """Configura el frame de progreso"""
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Barra de progreso
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        # Etiqueta de estado
        ttk.Label(progress_frame, textvariable=self.progress_label_var, style='Info.TLabel').pack(fill=tk.X, padx=5)

    def setup_footer_frame(self, parent):
        """Configura el pie de página"""
        footer_frame = ttk.Frame(parent)
        footer_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Label(footer_frame, text="Información:", style='Info.TLabel').pack(anchor=tk.W)
        ttk.Label(footer_frame, text=f"Informe de búsqueda: {self.config.get('ruta_informe_busqueda')}", style='Info.TLabel').pack(anchor=tk.W)
        ttk.Label(footer_frame, text=f"Configuración guardada en: {os.path.abspath(CONFIG_FILE)}", style='Info.TLabel').pack(anchor=tk.W)
        ttk.Label(footer_frame, text=f"Extensión filtrada actual: {self.config.get('extension_filtro', '*')}", style='Info.TLabel').pack(anchor=tk.W)

    def cambiar_ruta(self, config_key, variable):
        """Permite al usuario cambiar una ruta y actualiza la configuración"""
        nueva_ruta = filedialog.askdirectory(title="Selecciona nueva carpeta")
        
        if nueva_ruta:
            # Convertir a mayúsculas y normalizar la ruta
            nueva_ruta = os.path.normpath(nueva_ruta).upper()
            ruta_real = self.verificar_y_resolver_ruta(nueva_ruta)
            
            if not ruta_real:
                messagebox.showerror("Error", "La ruta no existe")
                return
                
            self.config[config_key] = ruta_real
            variable.set(ruta_real)
            self.guardar_config()

    def cambiar_ruta_informe_busqueda(self):
        """Permite al usuario cambiar la ruta del informe de búsqueda"""
        ruta_actual = self.config.get("ruta_informe_busqueda", RUTA_INFORME_BUSQUEDA)
        directorio_actual = os.path.dirname(ruta_actual)
        
        nueva_ruta = filedialog.asksaveasfilename(
            title="Guardar informe de búsqueda como",
            initialdir=directorio_actual,
            initialfile=os.path.basename(ruta_actual),
            defaultextension=".txt",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
        )
        
        if nueva_ruta:
            self.config["ruta_informe_busqueda"] = nueva_ruta
            self.ruta_informe_busqueda_var.set(nueva_ruta)
            self.guardar_config()
            
            # Actualizar el pie de página
            self.setup_footer_frame(self.root.winfo_children()[0])

    def verificar_y_resolver_ruta(self, ruta):
        """Verifica si la ruta existe y resuelve accesos directos"""
        if not ruta:
            return None
        
        # Primero intentar resolver si es acceso directo
        ruta_resuelta = self.resolver_acceso_directo(ruta)
        
        # Si no es acceso directo o no se pudo resolver, usar la original
        if not ruta_resuelta:
            ruta_resuelta = ruta
        
        # Verificar si la ruta existe
        if not os.path.exists(ruta_resuelta):
            print(f"La ruta no existe: {ruta_resuelta}")
            return None
        
        return ruta_resuelta

    def resolver_acceso_directo(self, ruta):
        """Resuelve la ruta real de un acceso directo (.lnk)"""
        if ruta.lower().endswith('.lnk'):
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                acceso_directo = shell.CreateShortCut(ruta)
                return acceso_directo.Targetpath
            except Exception as e:
                print(f"Error al resolver acceso directo {ruta}: {e}")
                return None
        return ruta

    def extraer_numeros(self, nombre):
        """Extrae los números iniciales de un nombre de archivo para ordenamiento"""
        match = re.match(r'^(\d+)', nombre)
        return int(match.group(1)) if match else 0

    def generar_informe(self, archivos_ordenados, no_encontrados, ruta_informe, accion="busqueda"):
        """Genera un archivo de informe con los resultados de la operación"""
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(ruta_informe), exist_ok=True)
        
        with open(ruta_informe, 'w', encoding='utf-8') as f:
            f.write(f"INFORME DE {accion.upper()} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"ARCHIVOS ENCONTRADOS ({accion} - orden numérico):\n")
            f.write("=" * 70 + "\n")
            f.write("\n".join(archivos_ordenados) + "\n\n")
            f.write(f"Total encontrados: {len(archivos_ordenados)}\n\n")
            f.write("NO ENCONTRADOS:\n")
            f.write("=" * 70 + "\n")
            f.write("\n".join(no_encontrados) if no_encontrados else "Todos encontrados\n")
            f.write(f"\nTotal no encontrados: {len(no_encontrados)}\n")
        print(f"\nInforme generado: {ruta_informe}")

    def actualizar_patrones(self):
        """Actualiza los patrones de búsqueda desde el cuadro de texto"""
        contenido = self.patrones_text.get("1.0", tk.END).strip()
        self.patrones_busqueda = [linea.strip() for linea in contenido.split("\n") if linea.strip()]
        self.guardar_config()

    def cambiar_extension_filtro(self):
        """Permite al usuario cambiar el filtro por extensión"""
        extension_actual = self.config.get("extension_filtro", "*")
        
        nueva_extension = simpledialog.askstring(
            "Filtro por Extensión",
            "Ingrese la extensión a filtrar (ej: .pdf, .xlsx) o * para todas:",
            initialvalue=extension_actual
        )
        
        if nueva_extension is not None:  # El usuario no canceló
            self.config["extension_filtro"] = nueva_extension.strip().lower()
            self.guardar_config()
            messagebox.showinfo("Configuración", f"Filtro de extensión actualizado a: {nueva_extension}")

    def detener_operacion(self):
        """Detiene la operación en curso"""
        self.stop_operation = True
        self.progress_label_var.set("Operación detenida por el usuario")

    def ejecutar_busqueda(self):
        """Ejecuta la búsqueda de archivos en un hilo separado"""
        self.actualizar_patrones()
        if not self.patrones_busqueda:
            messagebox.showwarning("Advertencia", "No hay patrones de búsqueda definidos")
            return
            
        directorio = self.ruta_buscar_var.get()
        if not directorio:
            messagebox.showerror("Error", "Debe especificar un directorio de búsqueda")
            return
            
        # Ejecutar en un hilo separado para no bloquear la interfaz
        threading.Thread(
            target=self.buscar_nombres,
            args=(self.patrones_busqueda, directorio, self.config.get("extension_filtro", "*")),
            daemon=True
        ).start()

    def ejecutar_copia(self):
        """Ejecuta la copia de archivos en un hilo separado"""
        self.actualizar_patrones()
        if not self.patrones_busqueda:
            messagebox.showwarning("Advertencia", "No hay patrones de búsqueda definidos")
            return
            
        directorio = self.ruta_copiar_var.get()
        destino = self.ruta_destino_copiar_var.get()
        
        if not directorio or not destino:
            messagebox.showerror("Error", "Debe especificar directorio de búsqueda y destino")
            return
            
        # Ejecutar en un hilo separado
        threading.Thread(
            target=self.buscar_y_copiar,
            args=(self.patrones_busqueda, directorio, destino, self.config.get("extension_filtro", "*")),
            daemon=True
        ).start()

    def ejecutar_renombrado(self):
        """Ejecuta el renombrado de archivos en un hilo separado"""
        self.actualizar_patrones()
        if not self.patrones_busqueda:
            messagebox.showwarning("Advertencia", "No hay patrones de búsqueda definidos")
            return
            
        directorio = self.ruta_renombrar_var.get()
        destino = self.ruta_destino_renombrar_var.get()
        
        if not directorio or not destino:
            messagebox.showerror("Error", "Debe especificar directorio de búsqueda y destino")
            return
            
        # Ejecutar en un hilo separado
        threading.Thread(
            target=self.buscar_y_renombrar,
            args=(self.patrones_busqueda, directorio, destino, self.config.get("extension_filtro", "*")),
            daemon=True
        ).start()

    def buscar_nombres(self, patrones, directorio, extension="*"):
        """Busca archivos que coincidan con los patrones en el directorio especificado"""
        self.stop_operation = False
        self.progress_var.set(0)
        self.progress_label_var.set("Iniciando búsqueda...")
        
        directorio = self.verificar_y_resolver_ruta(directorio)
        if not directorio:
            messagebox.showerror("Error", "El directorio de búsqueda no es válido")
            return

        encontrados = []
        no_encontrados = patrones.copy()
        total_archivos = 0
        
        # Primero contar archivos para la barra de progreso
        for raiz, _, archivos in os.walk(directorio):
            if self.stop_operation:
                return
            total_archivos += len(archivos)
        
        if total_archivos == 0:
            self.progress_label_var.set("No se encontraron archivos para buscar")
            return
            
        archivos_procesados = 0
        
        for raiz, _, archivos in os.walk(directorio):
            if self.stop_operation:
                return
                
            for archivo in archivos:
                # Actualizar progreso
                archivos_procesados += 1
                porcentaje = (archivos_procesados / total_archivos) * 100
                self.progress_var.set(porcentaje)
                self.progress_label_var.set(f"Procesando {archivos_procesados} de {total_archivos} archivos...")
                self.root.update_idletasks()
                
                # Verificar extensión si se especificó un filtro
                if extension != "*" and not archivo.lower().endswith(extension.lower()):
                    continue
                    
                for patron in patrones:
                    if patron.lower() in archivo.lower():
                        nombre = os.path.splitext(archivo)[0]
                        encontrados.append((self.extraer_numeros(nombre), nombre))
                        if patron in no_encontrados:
                            no_encontrados.remove(patron)
                        break

        ordenados = [nombre for _, nombre in sorted(encontrados)]
        self.generar_informe(ordenados, no_encontrados, self.config["ruta_informe_busqueda"], "busqueda")
        
        self.progress_var.set(100)
        self.progress_label_var.set(f"Búsqueda completada. Encontrados: {len(encontrados)}, No encontrados: {len(no_encontrados)}")
        messagebox.showinfo("Éxito", "Búsqueda completada. Ver informe para resultados.")

def buscar_y_copiar(self, patrones, directorio, destino, extension="*"):
    """Busca archivos y copia solo el más reciente por patrón al directorio destino"""
    self.stop_operation = False
    self.progress_var.set(0)
    self.progress_label_var.set("Iniciando copia...")

    directorio = self.verificar_y_resolver_ruta(directorio)
    if not directorio:
        messagebox.showerror("Error", "El directorio de búsqueda no es válido")
        return

    try:
        Path(destino).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo crear el directorio destino: {e}")
        return

    nombre_informe = f"informe_copiado_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    ruta_informe_copia = os.path.join(destino, nombre_informe)

    encontrados = []
    no_encontrados = patrones.copy()
    total_archivos = 0

    # Contar archivos para la barra de progreso
    for raiz, _, archivos in os.walk(directorio):
        if self.stop_operation:
            return
        total_archivos += len(archivos)

    if total_archivos == 0:
        self.progress_label_var.set("No se encontraron archivos para copiar")
        return

    archivos_procesados = 0

    # Diccionario para almacenar el archivo más reciente por patrón
    archivos_por_patron = {patron: None for patron in patrones}

    for raiz, _, archivos in os.walk(directorio):
        if self.stop_operation:
            return

        for archivo in archivos:
            archivos_procesados += 1
            porcentaje = (archivos_procesados / total_archivos) * 100
            self.progress_var.set(porcentaje)
            self.progress_label_var.set(f"Procesando {archivos_procesados} de {total_archivos} archivos...")
            self.root.update_idletasks()

            if extension != "*" and not archivo.lower().endswith(extension.lower()):
                continue

            for patron in patrones:
                if patron.lower() in archivo.lower():
                    origen = os.path.join(raiz, archivo)
                    fecha_modificacion = os.path.getmtime(origen)

                    # Verificar si este archivo es más reciente que el almacenado para el patrón
                    actual = archivos_por_patron.get(patron)
                    if actual is None or fecha_modificacion > actual[1]:
                        archivos_por_patron[patron] = (origen, fecha_modificacion, archivo)
                    break

    # Copiar solo los archivos más recientes por patrón
    for patron, info in archivos_por_patron.items():
        if info is not None:
            origen, _, archivo = info
            destino_final = os.path.join(destino, archivo)
            try:
                if os.path.exists(destino_final):
                    os.remove(destino_final)
                shutil.copy2(origen, destino_final)
                print(f"Copiado: {archivo}")
                nombre = os.path.splitext(archivo)[0]
                encontrados.append((self.extraer_numeros(nombre), nombre))
                if patron in no_encontrados:
                    no_encontrados.remove(patron)
            except Exception as e:
                print(f"Error al copiar {archivo}: {e}")

    ordenados = [nombre for _, nombre in sorted(encontrados)]
    self.generar_informe(ordenados, no_encontrados, ruta_informe_copia, "copia")

    self.progress_var.set(100)
    self.progress_label_var.set(f"Copia completada. Copiados: {len(encontrados)}, No encontrados: {len(no_encontrados)}")
    messagebox.showinfo("Éxito", f"Copia completada. Informe generado en: {ruta_informe_copia}")


    def buscar_y_renombrar(self, patrones, directorio, destino, extension="*"):
        """Busca archivos, los copia al destino y los renombra con la penúltima carpeta"""
        self.stop_operation = False
        self.progress_var.set(0)
        self.progress_label_var.set("Iniciando renombrado...")
        
        directorio = self.verificar_y_resolver_ruta(directorio)
        if not directorio:
            messagebox.showerror("Error", "El directorio de búsqueda no es válido")
            return

        try:
            Path(destino).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear el directorio destino: {e}")
            return

        # Crear ruta para el informe en la carpeta de destino
        nombre_informe = f"informe_renombrado_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        ruta_informe_renombrar = os.path.join(destino, nombre_informe)

        encontrados = []
        no_encontrados = patrones.copy()
        total_archivos = 0
        
        # Contar archivos para la barra de progreso
        for raiz, _, archivos in os.walk(directorio):
            if self.stop_operation:
                return
            total_archivos += len(archivos)
        
        if total_archivos == 0:
            self.progress_label_var.set("No se encontraron archivos para renombrar")
            return
            
        archivos_procesados = 0
        
        for raiz, dirs, archivos in os.walk(directorio):
            if self.stop_operation:
                return
                
            for archivo in archivos:
                # Actualizar progreso
                archivos_procesados += 1
                porcentaje = (archivos_procesados / total_archivos) * 100
                self.progress_var.set(porcentaje)
                self.progress_label_var.set(f"Procesando {archivos_procesados} de {total_archivos} archivos...")
                self.root.update_idletasks()
                
                # Verificar extensión si se especificó un filtro
                if extension != "*" and not archivo.lower().endswith(extension.lower()):
                    continue
                    
                for patron in patrones:
                    if patron.lower() in archivo.lower():
                        # Obtener la penúltima carpeta
                        partes_ruta = Path(raiz).parts
                        if len(partes_ruta) >= 2:
                            penultima_carpeta = partes_ruta[-2].upper()  # Convertir a mayúsculas
                        else:
                            penultima_carpeta = "RAIZ"
                        
                        nombre_original = os.path.splitext(archivo)[0]
                        extension_archivo = os.path.splitext(archivo)[1]
                        
                        # Crear nuevo nombre: penultima_carpeta + _ + nombre_original
                        nuevo_nombre = f"{penultima_carpeta}_{nombre_original}{extension_archivo}"
                        
                        encontrados.append((self.extraer_numeros(nombre_original), nuevo_nombre))
                        origen = os.path.join(raiz, archivo)
                        destino_final = os.path.join(destino, nuevo_nombre)
                        
                        try:
                            if os.path.exists(destino_final):
                                os.remove(destino_final)
                            shutil.copy2(origen, destino_final)
                            print(f"Copiado y renombrado: {archivo} -> {nuevo_nombre}")
                        except Exception as e:
                            print(f"Error al copiar/renombrar {archivo}: {e}")
                            continue
                            
                        if patron in no_encontrados:
                            no_encontrados.remove(patron)
                        break

        ordenados = [nombre for _, nombre in sorted(encontrados)]
        self.generar_informe(ordenados, no_encontrados, ruta_informe_renombrar, "renombrado")
        
        self.progress_var.set(100)
        self.progress_label_var.set(f"Renombrado completado. Procesados: {len(encontrados)}, No encontrados: {len(no_encontrados)}")
        messagebox.showinfo("Éxito", f"Renombrado completado. Informe generado en: {ruta_informe_renombrar}")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()