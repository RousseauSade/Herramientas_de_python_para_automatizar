import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import pandas as pd
import os
import chardet
import threading
import time
import csv
import re
import sys
from datetime import datetime

# PDF
import pdfkit

# XLSB vía Excel
import win32com.client


class ExcelConverterApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Conversor de Excel/CSV - Professional")
        self.geometry("750x550")
        self.configure(bg="#f0f0f0")
        
        # Establecer estilo
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background="#f0f0f0")
        self.style.configure('TLabel', background="#f0f0f0", font=('Segoe UI', 10))
        self.style.configure('TButton', font=('Segoe UI', 10), padding=6)
        self.style.configure('Accent.TButton', foreground="white", background="#4CAF50", font=('Segoe UI', 10, 'bold'))
        self.style.configure('Title.TLabel', font=('Segoe UI', 12, 'bold'), foreground="#333333")
        self.style.map('Accent.TButton', background=[('active', '#45a049')])
        self.style.configure('TProgressbar', thickness=20, troughcolor='#e0e0e0', background='#4CAF50')

        self.input_file = tk.StringVar()
        self.output_format = tk.StringVar(value="xlsx")
        self.save_path = tk.StringVar()
        self.encoding_var = tk.StringVar(value="utf-8")
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Listo")

        self.wkhtmltopdf_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        self.create_widgets()
        
        # Bloquear redimensionamiento
        self.resizable(False, False)

    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # Título
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(title_frame, text="Conversor de Archivos Excel/CSV", style="Title.TLabel").pack()

        # Área de arrastre
        drop_frame = ttk.LabelFrame(main_frame, text=" Arrastra tu archivo aquí ", padding=10)
        drop_frame.pack(fill="both", expand=True, pady=(0, 15))
        drop_label = ttk.Label(drop_frame, text="Suelta tu archivo Excel o CSV aquí", font=("Segoe UI", 10), 
                             relief="groove", padding=30)
        drop_label.pack(pady=10, expand=True, fill="both")
        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind('<<Drop>>', self.on_drop)

        # Info del archivo
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(file_frame, text="Archivo seleccionado:").pack(side="left")
        file_label = ttk.Label(file_frame, textvariable=self.input_file, foreground="#0066cc", 
                             wraplength=500, font=('Segoe UI', 9))
        file_label.pack(side="left", padx=10)

        # Opciones de formato
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill="x", pady=10)
        
        format_frame = ttk.LabelFrame(options_frame, text=" Formato de salida ", padding=10)
        format_frame.pack(side="left", fill="y", padx=(0, 10))
        formats = ["xlsx", "xls", "ods", "xlsb", "csv", "html", "pdf"]
        format_menu = ttk.OptionMenu(format_frame, self.output_format, "xlsx", *formats)
        format_menu.pack()

        encoding_frame = ttk.LabelFrame(options_frame, text=" Codificación ", padding=10)
        encoding_frame.pack(side="left", fill="y", padx=10)
        encodings = ["utf-8", "latin-1", "utf-16", "iso-8859-1", "cp1252", "auto"]
        encoding_menu = ttk.OptionMenu(encoding_frame, self.encoding_var, "utf-8", *encodings)
        encoding_menu.pack(side="left", padx=(0, 5))
        ttk.Button(encoding_frame, text="Detectar", command=self.detect_encoding).pack(side="left")

        # Ruta de guardado
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill="x", pady=10)
        ttk.Button(path_frame, text="Guardar en...", command=self.select_save_path).pack(side="left")
        ttk.Label(path_frame, textvariable=self.save_path, foreground="#009933", 
                 wraplength=500, font=('Segoe UI', 9)).pack(side="left", padx=10)

        # Barra de progreso
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill="x", pady=(10, 5))
        ttk.Label(progress_frame, textvariable=self.status_var, font=('Segoe UI', 9)).pack(anchor="w")
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 5))

        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(button_frame, text="Convertir Archivo", command=self.start_conversion_thread, 
                  style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(button_frame, text="Resetear", command=self.reset_app).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Salir", command=self.destroy).pack(side="right")

    def detect_encoding(self):
        if not self.input_file.get():
            messagebox.showerror("Error", "No hay archivo seleccionado")
            return
        try:
            with open(self.input_file.get(), 'rb') as f:
                rawdata = f.read(10000)
                result = chardet.detect(rawdata)
                self.encoding_var.set(result['encoding'])
                messagebox.showinfo("Codificación detectada",
                                  f"Codificación detectada: {result['encoding']}\nConfianza: {result['confidence']:.2%}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo detectar la codificación:\n{str(e)}")

    def detect_delimiter(self, file_path, encoding):
        """Detecta automáticamente el delimitador del CSV"""
        delimiters = [',', ';', '\t', '|', ' ']
        
        # Primero intentamos con las primeras líneas
        with open(file_path, 'r', encoding=encoding) as f:
            first_lines = [f.readline() for _ in range(5)]
        
        # Contamos ocurrencias de posibles delimitadores
        delimiter_counts = {delim: 0 for delim in delimiters}
        for line in first_lines:
            for delim in delimiters:
                delimiter_counts[delim] += line.count(delim)
        
        # Seleccionamos el delimitador más frecuente
        detected_delim = max(delimiter_counts.items(), key=lambda x: x[1])[0]
        
        # Validación adicional para casos ambiguos
        if detected_delim == ' ' and max(delimiter_counts.values()) < 3:
            # Probablemente no es un delimitador de espacio
            for delim in [',', ';', '\t']:
                if delimiter_counts[delim] > 0:
                    detected_delim = delim
                    break
        
        return detected_delim if max(delimiter_counts.values()) > 0 else ','

    def ask_delimiter(self):
        """Pide al usuario que seleccione el delimitador"""
        dialog = tk.Toplevel(self)
        dialog.title("Seleccionar delimitador")
        dialog.resizable(False, False)
        
        tk.Label(dialog, text="El delimitador no pudo detectarse automáticamente.\nSeleccione el carácter separador:").pack(pady=10)
        
        delimiter_var = tk.StringVar(value=',')
        
        frame = tk.Frame(dialog)
        frame.pack(pady=5)
        
        options = [('Coma (,)', ','), ('Punto y coma (;)', ';'), ('Tabulador', '\t'), ('Pipe (|)', '|'), ('Espacio', ' ')]
        for text, value in options:
            tk.Radiobutton(frame, text=text, variable=delimiter_var, value=value).pack(anchor='w')
        
        result = None
        
        def on_ok():
            nonlocal result
            result = delimiter_var.get()
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        tk.Button(dialog, text="Aceptar", command=on_ok).pack(side='right', padx=5)
        tk.Button(dialog, text="Cancelar", command=on_cancel).pack(side='right')
        
        dialog.transient(self)
        dialog.grab_set()
        self.wait_window(dialog)
        
        return result

    def reset_app(self):
        self.input_file.set("")
        self.save_path.set("")
        self.output_format.set("xlsx")
        self.encoding_var.set("utf-8")
        self.progress_var.set(0)
        self.status_var.set("Listo")

    def on_drop(self, event):
        file_path = event.data.strip("{}")
        if file_path.endswith(('.xlsx', '.xls', '.ods', '.xlsb', '.csv')):
            self.input_file.set(file_path)
            if file_path.endswith('.csv'):
                self.detect_encoding()
        else:
            messagebox.showerror("Error", "Formato de archivo no soportado. Usa Excel (.xlsx, .xls, .ods, .xlsb) o CSV (.csv)")

    def select_save_path(self):
        if not self.input_file.get():
            messagebox.showerror("Error", "Primero selecciona un archivo")
            return
            
        extension = self.output_format.get()
        
        # Obtener el nombre base del archivo sin extensión
        base_name = os.path.splitext(os.path.basename(self.input_file.get()))[0]
        
        # Obtener la fecha actual en formato DD-MM-YYYY
        today = datetime.now().strftime("%d-%m-%Y")
        
        # Crear el nombre por defecto con el formato: nombrebase-DD-MM-YYYY.ext
        default_name = f"{base_name}-{today}.{extension}"
        
        file_types = (
            (f"Archivos {extension.upper()}", f"*.{extension}"),
            ("Todos los archivos", "*.*")
        )
        path = filedialog.asksaveasfilename(
            defaultextension=f".{extension}",
            filetypes=file_types,
            initialfile=default_name
        )
        if path:
            self.save_path.set(path)

    def start_conversion_thread(self):
        if not self.input_file.get():
            messagebox.showerror("Error", "Primero selecciona un archivo")
            return

        if not self.save_path.get():
            messagebox.showerror("Error", "Selecciona una ubicación de guardado")
            return

        # Deshabilitar botones durante la conversión
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.state(['disabled'])

        # Iniciar hilo de conversión
        thread = threading.Thread(target=self.convert_file, daemon=True)
        thread.start()

        # Verificar progreso
        self.check_progress()

    def check_progress(self):
        if self.progress_var.get() < 100:
            self.after(100, self.check_progress)
        else:
            # Habilitar botones al finalizar
            for widget in self.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.state(['!disabled'])

    def update_progress(self, value, message):
        self.progress_var.set(value)
        self.status_var.set(message)
        self.update_idletasks()

    def convert_file(self):
        try:
            self.update_progress(0, "Iniciando conversión...")
            
            input_path = self.input_file.get()
            output_path = self.save_path.get()
            output_format = self.output_format.get()
            encoding = self.encoding_var.get() if self.encoding_var.get() != "auto" else None

            self.update_progress(10, "Leyendo archivo de entrada...")
            
            if input_path.endswith('.csv'):
                if encoding is None:
                    with open(input_path, 'rb') as f:
                        result = chardet.detect(f.read())
                    encoding = result['encoding']
                    self.encoding_var.set(encoding)
                
                # Detectar delimitador
                try:
                    delimiter = self.detect_delimiter(input_path, encoding)
                    
                    # Verificar si el delimitador funciona
                    test_df = pd.read_csv(input_path, encoding=encoding, delimiter=delimiter, nrows=5)
                    if len(test_df.columns) < 2:
                        raise pd.errors.EmptyDataError
                    
                except (pd.errors.ParserError, pd.errors.EmptyDataError):
                    delimiter = self.ask_delimiter()
                    if delimiter is None:
                        self.update_progress(0, "Conversión cancelada")
                        return
                
                # Leer el archivo CSV con manejo robusto de errores
                try:
                    df = pd.read_csv(
                        input_path,
                        encoding=encoding,
                        delimiter=delimiter,
                        engine='python',
                        quotechar='"',
                        quoting=csv.QUOTE_MINIMAL,
                        on_bad_lines='warn'
                    )
                    sheets = {'Datos': df}
                except pd.errors.ParserError as e:
                    error_line = str(e).split("line ")[1].split(",")[0] if "line " in str(e) else "desconocida"
                    messagebox.showwarning(
                        "Problema en el archivo",
                        f"Error en línea {error_line}. Se intentará omitir líneas problemáticas."
                    )
                    df = pd.read_csv(
                        input_path,
                        encoding=encoding,
                        delimiter=delimiter,
                        engine='python',
                        error_bad_lines=False,
                        warn_bad_lines=True
                    )
                    sheets = {'Datos': df}
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo leer el archivo CSV:\n{e}")
                    self.update_progress(0, "Error al leer CSV")
                    return
            else:
                with pd.ExcelFile(input_path) as excel:
                    sheets = {name: pd.read_excel(excel, sheet_name=name) for name in excel.sheet_names}

            self.update_progress(30, "Procesando datos...")
            time.sleep(0.5)

            # --- CSV ---
            if output_format == "csv":
                list(sheets.values())[0].to_csv(output_path, index=False, encoding=encoding or "utf-8")
                self.update_progress(100, f"CSV guardado en: {output_path}")
                messagebox.showinfo("Éxito", f"CSV guardado en:\n{output_path}")
                return

            # --- HTML ---
            if output_format == "html":
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write("<html><body>")
                    for name, df in sheets.items():
                        f.write(f"<h2>{name}</h2>")
                        f.write(df.to_html(index=False))
                    f.write("</body></html>")
                self.update_progress(100, f"HTML guardado en: {output_path}")
                messagebox.showinfo("Éxito", f"HTML guardado en:\n{output_path}")
                return

            # --- PDF ---
            if output_format == "pdf":
                temp_html = output_path.replace(".pdf", ".html")
                with open(temp_html, 'w', encoding='utf-8') as f:
                    f.write("<html><body>")
                    for name, df in sheets.items():
                        f.write(f"<h2>{name}</h2>")
                        f.write(df.to_html(index=False))
                    f.write("</body></html>")
                try:
                    self.update_progress(60, "Generando PDF...")
                    config = pdfkit.configuration(wkhtmltopdf=self.wkhtmltopdf_path)
                    pdfkit.from_file(temp_html, output_path, configuration=config)
                    os.remove(temp_html)
                    self.update_progress(100, f"PDF guardado en: {output_path}")
                    messagebox.showinfo("Éxito", f"PDF guardado en:\n{output_path}")
                except Exception as e:
                    self.update_progress(0, f"Error al generar PDF")
                    messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}")
                return

            # --- XLSB (por conversión) ---
            if output_format == "xlsb":
                temp_xlsx = output_path.replace(".xlsb", "_temporal.xlsx")
                with pd.ExcelWriter(temp_xlsx, engine="openpyxl") as writer:
                    for name, df in sheets.items():
                        df.to_excel(writer, sheet_name=name, index=False)

                self.update_progress(70, "Convirtiendo a XLSB...")
                self.convertir_xlsx_a_xlsb(temp_xlsx, output_path)
                os.remove(temp_xlsx)
                self.update_progress(100, f"Archivo XLSB guardado en: {output_path}")
                messagebox.showinfo("Éxito", f"Archivo XLSB guardado en:\n{output_path}")
                return

            # --- Formatos nativos Excel (xlsx, xls, ods) ---
            engine = self.get_engine(output_format)
            if engine is None:
                self.update_progress(0, f"Error: Motor no disponible")
                messagebox.showerror("Error", f"Motor no disponible para el formato {output_format}")
                return

            self.update_progress(50, "Guardando archivo...")
            with pd.ExcelWriter(output_path, engine=engine) as writer:
                for name, df in sheets.items():
                    df.to_excel(writer, sheet_name=name, index=False)

            self.update_progress(100, f"Archivo guardado en: {output_path}")
            messagebox.showinfo("Éxito", f"Archivo guardado en:\n{output_path}")

        except Exception as e:
            self.update_progress(0, f"Error en la conversión")
            messagebox.showerror("Error", f"Error en la conversión:\n{e}")
        finally:
            self.progress_var.set(100)

    def convertir_xlsx_a_xlsb(self, ruta_xlsx, ruta_xlsb):
        try:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            wb = excel.Workbooks.Open(os.path.abspath(ruta_xlsx))
            wb.SaveAs(os.path.abspath(ruta_xlsb), FileFormat=50)
            wb.Close(False)
            excel.Quit()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo convertir a XLSB:\n{e}")
            raise

    def get_engine(self, format):
        engines = {
            "xlsx": "openpyxl",
            "xls": "xlwt",
            "ods": "odf"
        }
        return engines.get(format, None)


if __name__ == "__main__":
    app = ExcelConverterApp()
    app.mainloop()