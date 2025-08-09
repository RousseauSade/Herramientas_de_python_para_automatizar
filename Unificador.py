import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
from PyPDF2 import PdfMerger

class PDFMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fusionador de PDFs")
        self.root.geometry("550x450")
        self.root.resizable(False, False)
        
        # Estilo moderno
        self.style = ttk.Style()
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
        self.style.configure('TButton', font=('Arial', 10), padding=5)
        
        # Variables para almacenar los archivos
        self.file1 = None
        self.file2 = None
        
        # Crear widgets
        self.create_widgets()
    
    def create_widgets(self):
        # Marco principal con estilo
        main_frame = ttk.Frame(self.root, padding=(20, 15))
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Título
        title_label = ttk.Label(main_frame, 
                              text="Fusionador de Documentos PDF", 
                              font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 15))
        
        # Área para arrastrar el primer PDF
        file1_frame = ttk.Frame(main_frame)
        file1_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file1_frame, text="Primer PDF:").pack(anchor=tk.W)
        self.drop_area1 = tk.Label(file1_frame, 
                                 text="Arrastra el primer PDF aquí", 
                                 relief=tk.GROOVE, 
                                 width=60, 
                                 height=4, 
                                 bg="white",
                                 font=('Arial', 9),
                                 fg="#666666")
        self.drop_area1.pack(pady=5)
        self.drop_area1.drop_target_register(DND_FILES)
        self.drop_area1.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, 1))
        
        # Área para arrastrar el segundo PDF
        file2_frame = ttk.Frame(main_frame)
        file2_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file2_frame, text="Segundo PDF (nombre del resultado):").pack(anchor=tk.W)
        self.drop_area2 = tk.Label(file2_frame, 
                                 text="Arrastra el segundo PDF aquí", 
                                 relief=tk.GROOVE, 
                                 width=60, 
                                 height=4, 
                                 bg="white",
                                 font=('Arial', 9),
                                 fg="#666666")
        self.drop_area2.pack(pady=5)
        self.drop_area2.drop_target_register(DND_FILES)
        self.drop_area2.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, 2))
        
        # Botón para fusionar con estilo moderno
        self.merge_button = ttk.Button(main_frame, 
                                     text="Fusionar PDFs", 
                                     command=self.merge_pdfs, 
                                     state=tk.DISABLED,
                                     style='Accent.TButton')
        self.merge_button.pack(pady=20)
        
        # Barra de estado
        self.status_bar = ttk.Frame(main_frame, height=20)
        self.status_bar.pack(fill=tk.X, pady=(10, 0))
        self.status_label = ttk.Label(self.status_bar, 
                                    text="Arrastra dos archivos PDF para comenzar", 
                                    foreground="#666666")
        self.status_label.pack(side=tk.LEFT)
        
        # Configurar estilo para el botón cuando está activo
        self.style.map('Accent.TButton', 
                      foreground=[('active', 'white'), ('!active', 'white')],
                      background=[('active', '#45a049'), ('!active', '#4CAF50')])
        self.style.configure('Accent.TButton', foreground='white', background='#4CAF50')
    
    def on_drop(self, event, file_num):
        # Obtener la ruta del archivo (eliminar llaves si es necesario)
        file_path = event.data.strip('{}')
        
        # Verificar si es un PDF
        if not file_path.lower().endswith('.pdf'):
            messagebox.showerror("Error", "Por favor, arrastra solo archivos PDF")
            return
        
        # Actualizar la interfaz según qué archivo se arrastró
        if file_num == 1:
            self.file1 = file_path
            self.drop_area1.config(text=os.path.basename(file_path), fg="black")
        else:
            self.file2 = file_path
            self.drop_area2.config(text=os.path.basename(file_path), fg="black")
        
        # Habilitar el botón si ambos archivos están listos
        if self.file1 and self.file2:
            self.merge_button.config(state=tk.NORMAL)
            self.status_label.config(text="Listo para fusionar", foreground="#4CAF50")
    
    def merge_pdfs(self):
        try:
            # Crear el fusionador
            merger = PdfMerger()
            
            # Agregar los PDFs en orden
            merger.append(self.file1)
            merger.append(self.file2)
            
            # Obtener el nombre base del segundo archivo (sin extensión)
            base_name = os.path.splitext(os.path.basename(self.file2))[0]
            default_filename = f"{base_name}.pdf"
            
            # Pedir al usuario dónde guardar
            save_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                initialfile=default_filename,
                title="Guardar PDF fusionado"
            )
            
            if save_path:
                # Guardar el PDF fusionado
                merger.write(save_path)
                merger.close()
                
                # Mostrar mensaje de éxito con estilo
                success_window = tk.Toplevel(self.root)
                success_window.title("Éxito")
                success_window.geometry("400x150")
                success_window.resizable(False, False)
                
                ttk.Label(success_window, 
                         text="PDFs fusionados con éxito", 
                         font=('Arial', 11, 'bold')).pack(pady=(20, 10))
                
                file_label = ttk.Label(success_window, 
                                     text=f"Archivo guardado como:\n{os.path.basename(save_path)}",
                                     wraplength=350)
                file_label.pack(pady=5)
                
                ttk.Button(success_window, 
                          text="Aceptar", 
                          command=success_window.destroy).pack(pady=10)
                
                # Resetear la interfaz
                self.reset_interface()
            else:
                merger.close()
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo fusionar los PDFs:\n{str(e)}")
    
    def reset_interface(self):
        self.file1 = None
        self.file2 = None
        self.drop_area1.config(text="Arrastra el primer PDF aquí", fg="#666666")
        self.drop_area2.config(text="Arrastra el segundo PDF aquí", fg="#666666")
        self.merge_button.config(state=tk.DISABLED)
        self.status_label.config(text="Arrastra dos archivos PDF para comenzar", foreground="#666666")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = PDFMergerApp(root)
    root.mainloop()
