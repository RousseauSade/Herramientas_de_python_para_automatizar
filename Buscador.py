import os
import sys
import threading
import time
import pickle
import shutil
import sqlite3
import hashlib
import re
from tkinter import *
from tkinter import ttk, messagebox, filedialog, Menu, simpledialog
from tkinter.font import Font
from PIL import Image, ImageTk
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Pool, cpu_count
from collections import defaultdict
try:
    from pybloom_live import ScalableBloomFilter
except ImportError:
    ScalableBloomFilter = None  # Fallback si no está instalado
import pandas as pd

# ==================== VALIDADOR DE RUTAS ====================
class PathValidator:
    @staticmethod
    def is_safe_path(base_path, target_path):
        """Verifica que la ruta objetivo esté dentro de la ruta base permitida."""
        try:
            base_path = os.path.abspath(base_path)
            target_path = os.path.abspath(target_path)
            return os.path.commonpath([base_path, target_path]) == base_path
        except:
            return False

    @staticmethod
    def sanitize_filename(filename):
        """Limpia un nombre de archivo para que sea seguro."""
        return re.sub(r'[\\/*?:"<>|]', "_", filename)

# ==================== BUSCADOR DE CONTENIDO ====================
class ContentSearcher:
    @staticmethod
    def search_in_file(file_path, pattern, chunk_size=4096):
        """Busca un patrón regex en un archivo de manera eficiente."""
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    if compiled_pattern.search(chunk.decode('utf-8', errors='ignore')):
                        return True
        except Exception as e:
            print(f"Error buscando en {file_path}: {str(e)}")
        return False

# ==================== EXPORTADOR DE RESULTADOS ====================
class Exporter:
    @staticmethod
    def to_excel(results, filename):
        """Exporta resultados a un archivo Excel con estadísticas."""
        try:
            # Convertir resultados a DataFrame
            df = pd.DataFrame(results)
            
            # Convertir tamaño a KB para cálculo
            def size_to_kb(size_str):
                parts = size_str.split()
                if len(parts) != 2:
                    return 0
                value, unit = float(parts[0]), parts[1]
                if unit == 'B':
                    return value / 1024
                elif unit == 'KB':
                    return value
                elif unit == 'MB':
                    return value * 1024
                elif unit == 'GB':
                    return value * 1024 * 1024
                else:
                    return 0
            
            # Crear copia para no modificar los datos originales
            df_stats = df.copy()
            df_stats['size_kb'] = df_stats['size'].apply(size_to_kb)
            
            with pd.ExcelWriter(filename) as writer:
                # Hoja de resultados
                df.to_excel(writer, sheet_name='Resultados', index=False)
                
                # Hoja de estadísticas
                stats = df_stats.groupby('type').agg({
                    'size_kb': ['count', 'sum'],
                    'modified': ['min', 'max']
                })
                stats.columns = ['Cantidad', 'Tamaño Total (KB)', 'Fecha Mínima', 'Fecha Máxima']
                stats.to_excel(writer, sheet_name='Estadísticas')
            return True
        except Exception as e:
            print(f"Error al exportar a Excel: {str(e)}")
            return False

    @staticmethod
    def to_csv(results, filename):
        """Exporta resultados a un archivo CSV."""
        try:
            df = pd.DataFrame(results)
            df.to_csv(filename, index=False, encoding='utf-8')
            return True
        except Exception as e:
            print(f"Error al exportar a CSV: {str(e)}")
            return False

# ==================== VISOR DE MINIATURAS ====================
class ThumbnailViewer(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True)
        self.tabs = {}
        self.current_images = []  # Para mantener referencias a las imágenes
        
    def add_thumbnail_tab(self, file_path):
        """Añade una pestaña con vista previa del archivo."""
        if file_path in self.tabs:
            self.notebook.select(self.tabs[file_path])
            return
            
        tab = ttk.Frame(self.notebook)
        self.tabs[file_path] = tab
        
        try:
            # Vista previa para imágenes
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                img = Image.open(file_path)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                label = Label(tab, image=photo)
                label.image = photo  # Mantener referencia
                self.current_images.append(photo)  # Evitar garbage collection
                label.pack(pady=10)
                
            # Vista previa para PDF (primera página)
            elif file_path.lower().endswith('.pdf'):
                doc = fitz.open(file_path)
                page = doc.load_page(0)
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                label = Label(tab, image=photo)
                label.image = photo
                self.current_images.append(photo)
                label.pack(pady=10)
                doc.close()
                
            # Vista previa para otros tipos de archivo
            else:
                Label(tab, text=f"Vista previa no disponible\n{os.path.basename(file_path)}", 
                     font=Font(size=10)).pack(pady=20)
                
            Label(tab, text=os.path.basename(file_path), font=Font(weight="bold")).pack()
            
        except Exception as e:
            Label(tab, text=f"Error al cargar vista previa: {str(e)}").pack()
            
        self.notebook.add(tab, text=os.path.basename(file_path)[:15] + ("..." if len(os.path.basename(file_path)) > 15 else ""))
        self.notebook.select(tab)
        
    def clear(self):
        """Limpia todas las pestañas y miniaturas."""
        for tab_id in list(self.tabs.keys()):
            self.notebook.forget(self.tabs[tab_id])
            del self.tabs[tab_id]
        self.current_images = []

# ==================== CACHÉ DE BASE DE DATOS MEJORADO ====================
class EnhancedFileCacheDB:
    def __init__(self):
        self.db_path = "file_search_cache.db"
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-10000")  # 10MB cache
            
            cursor = conn.cursor()
            # Tabla principal
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_cache (
                    path_hash TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    full_path TEXT NOT NULL,
                    last_scanned REAL NOT NULL,
                    indexed_at REAL NOT NULL
                )
            """)
            
            # Tabla FTS5 para búsqueda rápida
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS file_cache_fts 
                USING fts5(path, name, type, content=file_cache)
            """)
            
            # Índices adicionales
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_size ON file_cache(size)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_modified ON file_cache(modified)")
            conn.commit()
    
    def get_cached_results(self, path, max_age_days=7):
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Búsqueda más eficiente usando FTS5
            cursor.execute("""
                SELECT path, name, size, modified, type, full_path 
                FROM file_cache
                WHERE path LIKE ? AND last_scanned > ?
                LIMIT 1000
            """, (f"{path}%", cutoff_time))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def update_cache(self, results):
        current_time = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for result in results:
                path_hash = hashlib.md5(result['full_path'].encode()).hexdigest()
                try:
                    # Convertir tamaño a KB para almacenamiento
                    size_parts = result['size'].split()
                    if len(size_parts) == 2:
                        size_val, unit = float(size_parts[0]), size_parts[1]
                        if unit == 'B':
                            size_kb = size_val / 1024
                        elif unit == 'KB':
                            size_kb = size_val
                        elif unit == 'MB':
                            size_kb = size_val * 1024
                        elif unit == 'GB':
                            size_kb = size_val * 1024 * 1024
                        else:
                            size_kb = 0
                    else:
                        size_kb = 0
                    
                    # Convertir fecha a timestamp
                    try:
                        modified_time = time.mktime(time.strptime(result['modified'], '%Y-%m-%d %H:%M:%S'))
                    except:
                        modified_time = time.time()
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO file_cache 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        path_hash, result['path'], result['name'], size_kb,
                        modified_time, result['type'], result['full_path'],
                        current_time, current_time
                    ))
                except Exception as e:
                    print(f"Error actualizando caché para {result.get('full_path', '')}: {str(e)}")
            conn.commit()
    
    def clear_old_entries(self, max_age_days=30):
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_cache WHERE last_scanned < ?", (cutoff_time,))
            conn.commit()
    
    def clear_cache(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            self._init_db()  # Recrear la base de datos
            return True
        except Exception as e:
            print(f"Error al limpiar caché: {str(e)}")
            return False

# ==================== SISTEMA DE INDEXACIÓN MEJORADO ====================
class EnhancedFileIndexer:
    def __init__(self):
        self.index = defaultdict(list)
        self.type_index = defaultdict(list)
        self.path_index = defaultdict(list)
        self.bloom_filter = ScalableBloomFilter(initial_capacity=100000, error_rate=0.001) if ScalableBloomFilter else None
        self.last_index_time = 0
        
    def build_index(self, root_path):
        """Construye el índice usando multiprocesamiento."""
        start_time = time.time()
        self.index.clear()
        self.type_index.clear()
        self.path_index.clear()
        if self.bloom_filter:
            self.bloom_filter = ScalableBloomFilter(initial_capacity=100000, error_rate=0.001)
        
        # Procesamiento en paralelo
        with Pool(cpu_count()) as pool:
            file_list = list(self._get_all_files(root_path))
            results = pool.map(self._process_file_for_index, file_list)
            
        for file_path, file_name, file_ext in results:
            if file_path and file_name and file_ext:
                file_lower = file_name.lower()
                file_type = self._get_file_type(file_ext)
                
                self.index[file_lower].append(file_path)
                self.type_index[file_type].append(file_path)
                self.path_index[os.path.dirname(file_path)].append(file_name)
                if self.bloom_filter:
                    self.bloom_filter.add(file_lower)
        
        self.last_index_time = time.time()
        print(f"Índice construido en {self.last_index_time - start_time:.2f} segundos")
    
    def _get_all_files(self, root_path):
        """Generador para obtener todos los archivos de forma eficiente."""
        for root, _, files in os.walk(root_path):
            for file in files:
                yield os.path.join(root, file), file
    
    def _process_file_for_index(self, file_info):
        """Procesa un archivo para indexación (usado en multiprocesamiento)."""
        try:
            file_path, file_name = file_info
            file_ext = os.path.splitext(file_name.lower())[1]
            return file_path, file_name.lower(), file_ext
        except:
            return None, None, None
    
    def search_index(self, name_part=None, file_type=None, path_part=None):
        """Busca en el índice usando el filtro Bloom para descartes rápidos."""
        results = set()
        
        # Búsqueda por nombre con Bloom filter primero
        if name_part:
            name_part = name_part.lower()
            if self.bloom_filter and not any(name_part in key for key in self.index.keys() if self.bloom_filter.contains(name_part)):
                return results
                
            for file_name, paths in self.index.items():
                if name_part in file_name:
                    results.update(paths)
        
        # Búsqueda por tipo
        if file_type:
            results.update(self.type_index.get(file_type, []))
        
        # Búsqueda por ruta
        if path_part:
            path_part = path_part.lower()
            for path, files in self.path_index.items():
                if path_part in path.lower():
                    results.update(os.path.join(path, f) for f in files)
        
        return results
    
    def get_all_files(self):
        """Obtiene todos los archivos indexados con información completa."""
        all_files = []
        for paths in self.index.values():
            for path in paths:
                try:
                    stat = os.stat(path)
                    all_files.append({
                        'name': os.path.basename(path),
                        'path': os.path.dirname(path),
                        'size': self._format_size(stat.st_size),
                        'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                        'type': self._get_file_type(os.path.splitext(path)[1]),
                        'full_path': path
                    })
                except:
                    continue
        return all_files
    
    def _get_file_type(self, extension):
        """Determina el tipo de archivo basado en la extensión."""
        types = {
            'Imágenes': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
            'Documentos': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
            'Hojas de cálculo': ['.xls', '.xlsx', '.csv', '.ods'],
            'Presentaciones': ['.ppt', '.pptx', '.odp'],
            'Videos': ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'],
            'Audio': ['.mp3', '.wav', '.ogg', '.flac', '.aac'],
            'Archivos comprimidos': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'Ejecutables': ['.exe', '.msi', '.bat', '.sh'],
            'Código fuente': ['.py', '.java', '.cpp', '.c', '.h', '.html', '.css', '.js']
        }
        for typ, exts in types.items():
            if extension.lower() in exts:
                return typ
        return "Otro"
    
    def _format_size(self, size):
        """Formatea el tamaño del archivo para mostrarlo."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

# ==================== VISOR DE PDF ====================
class PDFViewer:
    def __init__(self, parent_frame, bg_color="white"):
        self.parent = parent_frame
        self.bg_color = bg_color
        self.doc = None
        self.page_index = 0
        self.photo = None
        self.image_on_canvas = None
        self.canvas_width = 0
        self.canvas_height = 0
        self.zoom_factor = 1.0
        self.current_path = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.container = Frame(self.parent, bg=self.bg_color)
        self.container.pack(fill=BOTH, expand=True)
        
        self.hscroll = ttk.Scrollbar(self.container, orient=HORIZONTAL)
        self.vscroll = ttk.Scrollbar(self.container, orient=VERTICAL)
        
        self.canvas = Canvas(
            self.container,
            bg='#f0f0f0',
            xscrollcommand=self.hscroll.set,
            yscrollcommand=self.vscroll.set,
            highlightthickness=0
        )
        
        self.hscroll.pack(side=BOTTOM, fill=X)
        self.vscroll.pack(side=RIGHT, fill=Y)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        
        self.hscroll.config(command=self.canvas.xview)
        self.vscroll.config(command=self.canvas.yview)

        self._create_navigation_controls()
        
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.parent.bind("<Left>", lambda e: self.change_page(-1))
        self.parent.bind("<Right>", lambda e: self.change_page(1))
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
    
    def _create_navigation_controls(self):
        self.controls_frame = Frame(self.parent, bg="#4e8cff", height=30)
        self.controls_frame.pack(fill=X, side=BOTTOM)
        
        self.prev_btn = ttk.Button(self.controls_frame, text="◀ Anterior", 
                                 command=lambda: self.change_page(-1), state=DISABLED)
        self.prev_btn.pack(side=LEFT, padx=5)
        
        self.page_label = Label(self.controls_frame, text="Página 0/0", 
                              bg="#4e8cff", fg="white", font=Font(size=10))
        self.page_label.pack(side=LEFT, padx=5)
        
        self.next_btn = ttk.Button(self.controls_frame, text="Siguiente ▶", 
                                 command=lambda: self.change_page(1), state=DISABLED)
        self.next_btn.pack(side=LEFT, padx=5)
        
        zoom_frame = Frame(self.controls_frame, bg="#4e8cff")
        zoom_frame.pack(side=RIGHT, padx=10)
        
        ttk.Button(zoom_frame, text="--", width=2, 
                  command=lambda: self.adjust_zoom(0.5)).pack(side=LEFT, padx=1)
        ttk.Button(zoom_frame, text="-", width=2, 
                  command=lambda: self.adjust_zoom(0.8)).pack(side=LEFT, padx=1)
        
        self.zoom_label = Label(zoom_frame, text="100%", 
                               bg="#4e8cff", fg="white", font=Font(size=10))
        self.zoom_label.pack(side=LEFT, padx=5)
        
        ttk.Button(zoom_frame, text="+", width=2, 
                  command=lambda: self.adjust_zoom(1.2)).pack(side=LEFT, padx=1)
        ttk.Button(zoom_frame, text="++", width=2, 
                  command=lambda: self.adjust_zoom(1.5)).pack(side=LEFT, padx=1)
        
        ttk.Button(zoom_frame, text="Ajustar", width=6, 
                  command=self.fit_to_width).pack(side=LEFT, padx=5)
    
    def load_pdf(self, path):
        if path == self.current_path:
            return
            
        self.current_path = path
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(path)
            self.page_index = 0
            self.zoom_factor = 1.0
            self._render_page()
            self.prev_btn.config(state=NORMAL)
            self.next_btn.config(state=NORMAL)
            self._update_page_controls()
            self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el PDF:\n{str(e)}")
    
    def _render_page(self):
        if not self.doc:
            return
            
        page = self.doc.load_page(self.page_index)
        
        if self.canvas_width > 0 and self.canvas_height > 0:
            zoom_x = (self.canvas_width / page.rect.width) * self.zoom_factor
            zoom_y = ((self.canvas_height - 20) / page.rect.height) * self.zoom_factor
            zoom = min(zoom_x, zoom_y)
            zoom = max(0.1, min(zoom, 4.0))
        else:
            zoom = 1.0 * self.zoom_factor
            
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.photo = ImageTk.PhotoImage(image)
        
        self.canvas.delete("all")
        
        x = (self.canvas_width - pix.width) / 2 if self.canvas_width > pix.width else 0
        y = (self.canvas_height - pix.height) / 2 if self.canvas_height > pix.height else 0
        
        self.image_on_canvas = self.canvas.create_image(x, y, anchor=NW, image=self.photo)
        
        self.canvas.config(scrollregion=(
            0, 0, 
            max(self.canvas_width, pix.width), 
            max(self.canvas_height, pix.height)
        ))
        
        self.page_label.config(text=f"Página {self.page_index + 1} de {len(self.doc)}")
    
    def change_page(self, delta):
        if not self.doc:
            return
            
        new_page = self.page_index + delta
        if 0 <= new_page < len(self.doc):
            self.page_index = new_page
            self._render_page()
            self._update_page_controls()
    
    def _update_page_controls(self):
        if self.doc:
            self.page_label.config(text=f"Página {self.page_index + 1}/{len(self.doc)}")
            self.prev_btn.config(state=NORMAL if self.page_index > 0 else DISABLED)
            self.next_btn.config(state=NORMAL if self.page_index < len(self.doc) - 1 else DISABLED)
    
    def adjust_zoom(self, factor):
        self.zoom_factor = max(0.1, min(self.zoom_factor * factor, 4.0))
        self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        if self.doc:
            self._render_page()
    
    def fit_to_width(self):
        self.zoom_factor = 1.0
        self.zoom_label.config(text="100%")
        if self.doc:
            self._render_page()
    
    def _on_canvas_configure(self, event):
        self.canvas_width = event.width
        self.canvas_height = event.height
        if self.doc:
            self._render_page()
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

# ==================== BUSCADOR MEJORADO PARA RED ====================
class NetworkOptimizedSearcher:
    def __init__(self):
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.max_results = 10000
        self.timeout = 600  # 10 minutos para redes lentas
        self.batch_size = 500  # Tamaño de lote reducido para red
        self.file_cache = {}
        self.cache_limit = 100000
        self.cache_hits = 0
        self.cache_misses = 0
        self.max_retries = 3  # Reintentos para operaciones de red
        self.db = EnhancedFileCacheDB()
        self.indexer = EnhancedFileIndexer()
        self.use_cache = True
        self.use_index = True
        self.path_validator = PathValidator()

    def search(self, path, search_term, extension, type_extensions, callback, progress_callback, 
              search_content=False, content_pattern=None):
        """Realiza una búsqueda optimizada para red."""
        self.stop_event.clear()
        self.pause_event.clear()
        self.file_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        
        start_time = time.time()
        result_count = 0
        
        search_term = search_term.lower() if search_term else None
        extension = extension.lower() if extension else None
        
        try:
            if not os.path.isdir(path):
                progress_callback(0, 0)
                return

            # Fase 1: Buscar en el índice
            if self.use_index:
                indexed_results = self.indexer.search_index(
                    search_term,
                    None if not type_extensions else self.indexer._get_file_type(extension) if extension else None,
                    path
                )
                
                for full_path in indexed_results:
                    if self.stop_event.is_set():
                        break
                    
                    # Validar ruta segura
                    if not self.path_validator.is_safe_path(path, full_path):
                        continue
                    
                    file = os.path.basename(full_path)
                    file_lower = file.lower()
                    file_ext = os.path.splitext(file_lower)[1]
                    
                    if extension and file_ext != extension:
                        continue
                    if type_extensions and file_ext not in type_extensions:
                        continue
                    if search_term and search_term not in file_lower:
                        continue
                    if search_content and content_pattern:
                        if not ContentSearcher.search_in_file(full_path, content_pattern):
                            continue
                    
                    try:
                        stat = os.stat(full_path)
                        callback({
                            'name': file,
                            'path': os.path.dirname(full_path),
                            'size': self._format_size(stat.st_size),
                            'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                            'type': self._get_file_type(file_ext),
                            'full_path': full_path
                        })
                        result_count += 1
                    except:
                        continue

            # Fase 2: Buscar en la caché de la base de datos
            if self.use_cache and result_count < 100:
                cached_results = self.db.get_cached_results(path)
                for result in cached_results:
                    if self.stop_event.is_set():
                        break
                    
                    file_lower = result['name'].lower()
                    file_ext = os.path.splitext(file_lower)[1]
                    
                    if extension and file_ext != extension:
                        continue
                    if type_extensions and file_ext not in type_extensions:
                        continue
                    if search_term and search_term not in file_lower:
                        continue
                    
                    callback(result)
                    result_count += 1

            # Fase 3: Búsqueda en disco si es necesario
            if result_count < 50 or not self.use_index:
                total_files = self._count_files(path)
                if total_files == 0:
                    progress_callback(100, result_count)
                    return

                processed_files = 0
                last_update_time = time.time()
                
                for root, dirs, files in os.walk(path):
                    if self.stop_event.is_set() or (time.time() - start_time) > self.timeout:
                        break
                        
                    batch = []
                    for file in files:
                        if self.stop_event.is_set() or result_count >= self.max_results:
                            break
                            
                        while self.pause_event.is_set():
                            time.sleep(0.1)
                            if self.stop_event.is_set():
                                break
                        
                        batch.append((root, file))
                        processed_files += 1
                        
                        if len(batch) >= self.batch_size:
                            self._process_batch(batch, search_term, extension, 
                                             type_extensions, callback, search_content, content_pattern)
                            result_count = len(self.file_cache)
                            batch = []
                            
                            current_time = time.time()
                            if current_time - last_update_time > 0.5:
                                progress = min(100, processed_files / total_files * 100)
                                progress_callback(progress, result_count)
                                last_update_time = current_time
                    
                    if batch:
                        self._process_batch(batch, search_term, extension, 
                                         type_extensions, callback, search_content, content_pattern)
                        result_count = len(self.file_cache)
                
                # Actualizar la caché de la base de datos
                if self.file_cache:
                    self.db.update_cache(self.file_cache.values())
            
            progress_callback(100, result_count)
        except Exception as e:
            progress_callback(0, 0)
            print(f"Error en la búsqueda: {str(e)}")

    def _process_batch(self, batch, search_term, extension, type_extensions, 
                     callback, search_content=False, content_pattern=None):
        """Procesa un lote de archivos con reintentos para red."""
        futures = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            for root, file in batch:
                futures.append(executor.submit(
                    self._process_network_file,
                    root, file, search_term, extension, 
                    type_extensions, search_content, content_pattern
                ))
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        file_id = f"{result['path']}/{result['name']}"
                        if file_id not in self.file_cache:
                            self.file_cache[file_id] = result
                            if len(self.file_cache) > self.cache_limit:
                                oldest = sorted(self.file_cache.items(), 
                                              key=lambda x: x[1]['modified'])[:self.cache_limit//10]
                                for key, _ in oldest:
                                    del self.file_cache[key]
                except Exception as e:
                    print(f"Error procesando lote: {str(e)}")

    def _process_network_file(self, root, file, search_term, extension, 
                            type_extensions, search_content, content_pattern):
        """Procesa un archivo con reintentos para operaciones de red."""
        retries = 0
        while retries < self.max_retries:
            try:
                return self._process_file(root, file, search_term, extension, 
                                       type_extensions, search_content, content_pattern)
            except (OSError, TimeoutError) as e:
                retries += 1
                time.sleep(1)  # Esperar antes de reintentar
        return None

    def _process_file(self, root, file, search_term, extension, 
                     type_extensions, search_content, content_pattern):
        """Procesa un archivo individual con todas las comprobaciones."""
        try:
            file_lower = file.lower()
            file_ext = os.path.splitext(file_lower)[1]
            
            if extension and file_ext != extension:
                return None
            if type_extensions and file_ext not in type_extensions:
                return None
            if search_term and search_term not in file_lower:
                return None
            
            full_path = os.path.join(root, file)
            if not os.path.isfile(full_path):
                return None
                
            # Validar ruta segura
            if not self.path_validator.is_safe_path(root, full_path):
                return None
                
            # Búsqueda en contenido si está habilitada
            if search_content and content_pattern:
                if not ContentSearcher.search_in_file(full_path, content_pattern):
                    return None
                
            file_id = f"{root}/{file}"
            
            if file_id in self.file_cache:
                self.cache_hits += 1
                return self.file_cache[file_id]
            
            self.cache_misses += 1
            info = self._get_file_info(full_path)
            if not info:
                return None
                
            return {
                'name': file,
                'path': root,
                'size': self._format_size(info['size']),
                'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['modified'])),
                'type': self._get_file_type(file_ext),
                'full_path': full_path
            }
        except Exception as e:
            print(f"Error procesando archivo {file}: {str(e)}")
            return None

    def _get_file_info(self, full_path):
        """Obtiene información del archivo con manejo de errores."""
        try:
            stat = os.stat(full_path)
            return {
                'size': stat.st_size,
                'modified': stat.st_mtime
            }
        except:
            return None
    
    def _format_size(self, size):
        """Formatea el tamaño del archivo para mostrarlo."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def _get_file_type(self, extension):
        """Determina el tipo de archivo basado en la extensión."""
        types = {
            'Imágenes': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
            'Documentos': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
            'Hojas de cálculo': ['.xls', '.xlsx', '.csv', '.ods'],
            'Presentaciones': ['.ppt', '.pptx', '.odp'],
            'Videos': ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'],
            'Audio': ['.mp3', '.wav', '.ogg', '.flac', '.aac'],
            'Archivos comprimidos': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'Ejecutables': ['.exe', '.msi', '.bat', '.sh'],
            'Código fuente': ['.py', '.java', '.cpp', '.c', '.h', '.html', '.css', '.js']
        }
        
        for typ, exts in types.items():
            if extension.lower() in exts:
                return typ
        return "Otro"
    
    def _count_files(self, path):
        """Cuenta archivos de forma eficiente con manejo de errores."""
        count = 0
        try:
            for root, dirs, files in os.walk(path):
                if self.stop_event.is_set():
                    return 0
                count += len(files)
        except Exception as e:
            print(f"Error al contar archivos: {str(e)}")
            return 0
        return count
    
    def stop(self):
        """Detiene la búsqueda actual."""
        self.stop_event.set()
        self.executor.shutdown(wait=False)
    
    def pause(self):
        """Pausa la búsqueda actual."""
        self.pause_event.set()
    
    def resume(self):
        """Reanuda la búsqueda pausada."""
        self.pause_event.clear()

# ==================== BARRA DE PROGRESO ====================
class ProgressBar:
    def __init__(self, parent):
        self.parent = parent
        self._setup_ui()
    
    def _setup_ui(self):
        self.frame = Frame(self.parent, bg="#f5f5f5")
        self.frame.pack(fill=X, pady=(0, 15))
        
        status_frame = Frame(self.frame, bg="#f5f5f5")
        status_frame.pack(fill=X)
        
        self.progress_label = Label(status_frame, text="Listo", bg="#f5f5f5", 
                                  fg="#777777", font=Font(family="Segoe UI", size=10))
        self.progress_label.pack(side=LEFT, anchor=W)
        
        self.time_label = Label(status_frame, text="Tiempo: 0s", bg="#f5f5f5", 
                              fg="#777777", font=Font(family="Segoe UI", size=10))
        self.time_label.pack(side=LEFT, anchor=W, padx=20)
        
        self.progress = ttk.Progressbar(self.frame, orient=HORIZONTAL, 
                                      mode='determinate', style="Horizontal.TProgressbar")
        self.progress.pack(fill=X, pady=(5, 0))
        
        self.result_count = Label(self.frame, text="0 archivos encontrados", 
                                bg="#f5f5f5", fg="#777777", font=Font(family="Segoe UI", size=10))
        self.result_count.pack(side=TOP, anchor=E)
    
    def update_progress(self, value):
        self.progress['value'] = value
    
    def update_status(self, text, color="#4e8cff"):
        self.progress_label.config(text=text, fg=color)
    
    def update_time(self, elapsed_time):
        self.time_label.config(text=f"Tiempo: {elapsed_time:.1f}s")
    
    def update_result_count(self, count):
        self.result_count.config(text=f"{count} archivos encontrados")

# ==================== PANEL DE BÚSQUEDA MEJORADO ====================
class EnhancedSearchPanel:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        self._setup_ui()
    
    def _setup_ui(self):
        self.frame = Frame(self.parent, bg="white", bd=0, highlightthickness=0,
                         relief=RAISED, padx=15, pady=15)
        self.frame.pack(fill=X, pady=(0, 15))
        
        self.frame.grid_columnconfigure(1, weight=1)
        self.frame.grid_columnconfigure(3, weight=1)
        
        Label(self.frame, text="BUSCADOR AVANZADO DE ARCHIVOS", 
             bg="white", fg="#4e8cff", font=Font(family="Segoe UI", size=12, weight="bold")
             ).grid(row=0, column=0, columnspan=7, pady=(0, 10), sticky=W)
        
        self._create_search_controls()
        self._create_advanced_filters()
    
    def _create_search_controls(self):
        Label(self.frame, text="Carpeta:", bg="white", fg="#333333").grid(row=1, column=0, sticky=W)
        self.path_entry = ttk.Entry(self.frame, width=40, font=Font(family="Segoe UI", size=10))
        self.path_entry.grid(row=1, column=1, sticky=EW, padx=5)
        ttk.Button(self.frame, text="Examinar...", command=self._browse_path).grid(row=1, column=2, padx=5)
        ttk.Button(self.frame, text="Escanear", command=self.controller.scan_folder).grid(row=1, column=3, padx=5)
        
        Label(self.frame, text="Nombre:", bg="white", fg="#333333").grid(row=2, column=0, sticky=W, pady=(10, 0))
        self.search_entry = ttk.Entry(self.frame, width=40, font=Font(family="Segoe UI", size=10))
        self.search_entry.grid(row=2, column=1, sticky=EW, padx=5, pady=(10, 0))
        self.search_entry.bind('<Return>', lambda e: self.controller.start_search())
        
        Label(self.frame, text="Extensión:", bg="white", fg="#333333").grid(row=3, column=0, sticky=W, pady=(10, 0))
        self.extension_combobox = ttk.Combobox(self.frame, width=15, font=Font(family="Segoe UI", size=10))
        self.extension_combobox['values'] = ['', '.pdf', '.docx', '.xlsx', '.jpg', '.png', '.mp3', '.mp4', '.zip']
        self.extension_combobox.grid(row=3, column=1, sticky=W, padx=5, pady=(10, 0))
        
        Label(self.frame, text="Tipo:", bg="white", fg="#333333").grid(row=3, column=2, sticky=W, padx=(10, 5), pady=(10, 0))
        self.doc_type_combobox = ttk.Combobox(self.frame, width=20, font=Font(family="Segoe UI", size=10))
        self.doc_type_combobox['values'] = [''] + list(self.controller.document_types.keys())
        self.doc_type_combobox.grid(row=3, column=3, sticky=W, padx=5, pady=(10, 0))
        
        self.search_btn = ttk.Button(self.frame, text="Buscar Archivos", 
                                   command=self.controller.start_search)
        self.search_btn.grid(row=2, column=4, padx=5, pady=(10, 0), rowspan=2, sticky=NSEW)
        
        self.stop_btn = ttk.Button(self.frame, text="Detener", 
                                 command=self.controller.stop_search, state=DISABLED)
        self.stop_btn.grid(row=2, column=5, padx=5, pady=(10, 0), rowspan=2, sticky=NSEW)
        
        self.sort_order = StringVar(value="reciente")
        ttk.Radiobutton(self.frame, text="Más reciente", variable=self.sort_order, 
                       value="reciente").grid(row=4, column=1, sticky=W, pady=(5, 0))
        ttk.Radiobutton(self.frame, text="Más antiguo", variable=self.sort_order, 
                       value="antiguo").grid(row=4, column=2, sticky=W, pady=(5, 0))
    
    def _create_advanced_filters(self):
        Label(self.frame, text="Tamaño:", bg="white", fg="#333333").grid(row=5, column=0, sticky=W, pady=(5, 0))
        self.size_combobox = ttk.Combobox(self.frame, width=15, font=Font(family="Segoe UI", size=10))
        self.size_combobox['values'] = ['', 'pequeño (<1MB)', 'mediano (1-10MB)', 'grande (>10MB)']
        self.size_combobox.grid(row=5, column=1, sticky=W, padx=5, pady=(5, 0))
        
        self.search_content_var = BooleanVar()
        ttk.Checkbutton(self.frame, text="Buscar en contenido", variable=self.search_content_var).grid(
            row=5, column=2, sticky=W, padx=5, pady=(5, 0))
        
        self.content_pattern_entry = ttk.Entry(self.frame, width=20, font=Font(family="Segoe UI", size=10))
        self.content_pattern_entry.grid(row=5, column=3, sticky=W, padx=5, pady=(5, 0))
        self.content_pattern_entry.insert(0, ".*")  # Patrón por defecto: cualquier contenido
        
        self.use_cache_var = BooleanVar(value=True)
        ttk.Checkbutton(self.frame, text="Usar caché", variable=self.use_cache_var,
                       command=self.toggle_cache).grid(row=5, column=4, sticky=W, padx=5, pady=(5, 0))
        
        self.pause_btn = ttk.Button(self.frame, text="Pausar", command=self.controller.pause_search, state=DISABLED)
        self.pause_btn.grid(row=2, column=6, padx=5, pady=(10, 0))
        self.resume_btn = ttk.Button(self.frame, text="Reanudar", command=self.controller.resume_search, state=DISABLED)
        self.resume_btn.grid(row=3, column=6, padx=5, pady=(5, 0))
        
        ttk.Button(self.frame, text="Exportar", command=self.controller.export_results).grid(
            row=5, column=5, padx=5, pady=(5, 0))
    
    def toggle_cache(self):
        """Activa/desactiva el uso de caché."""
        self.controller.searcher.use_cache = self.use_cache_var.get()
    
    def _browse_path(self):
        """Abre un diálogo para seleccionar una carpeta."""
        path = filedialog.askdirectory(initialdir=self.path_entry.get())
        if path:
            self.path_entry.delete(0, END)
            self.path_entry.insert(0, path)
    
    def get_search_params(self):
        """Obtiene los parámetros de búsqueda del panel."""
        return {
            'path': self.path_entry.get().strip(),
            'search_term': self.search_entry.get().strip(),
            'extension': self.extension_combobox.get().strip().lower(),
            'doc_type': self.doc_type_combobox.get().strip(),
            'size_filter': self.size_combobox.get().strip(),
            'search_content': self.search_content_var.get(),
            'content_pattern': self.content_pattern_entry.get().strip(),
            'sort_order': self.sort_order.get()
        }
    
    def set_search_state(self, active):
        """Actualiza el estado de los controles durante la búsqueda."""
        self.search_btn.config(state=DISABLED if active else NORMAL)
        self.stop_btn.config(state=NORMAL if active else DISABLED)
        self.pause_btn.config(state=NORMAL if active else DISABLED)
        self.resume_btn.config(state=NORMAL if active else DISABLED)

# ==================== PANEL DE RESULTADOS MEJORADO ====================
class EnhancedResultsPanel:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        self.current_preview_path = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.container = PanedWindow(self.parent, orient=HORIZONTAL, bg="#f5f5f5", sashwidth=8, sashrelief=RAISED)
        self.container.pack(fill=BOTH, expand=True)
        
        self._create_results_tree()
        self._create_preview_panel()
        
        if hasattr(self.controller, 'panel_sizes') and 'results_panel' in self.controller.panel_sizes:
            self.container.sash_place(0, self.controller.panel_sizes['results_panel'], 0)
    
    def _create_results_tree(self):
        self.tree_frame = Frame(self.container, bg="#f5f5f5")
        self.container.add(self.tree_frame, minsize=300, stretch='always')
        
        self.tree = ttk.Treeview(self.tree_frame, columns=('name', 'path', 'size', 'modified', 'type'), 
                                selectmode='extended', style="Treeview")
        
        self.tree.column('#0', width=50, stretch=NO)
        self.tree.column('name', width=200, minwidth=100, stretch=NO)
        self.tree.column('path', width=250, minwidth=100, stretch=YES)
        self.tree.column('size', width=100, minwidth=80, stretch=NO)
        self.tree.column('modified', width=150, minwidth=100, stretch=NO)
        self.tree.column('type', width=100, minwidth=80, stretch=NO)
        
        self.tree.heading('#0', text='#', anchor=W)
        self.tree.heading('name', text='Nombre', anchor=W)
        self.tree.heading('path', text='Ruta', anchor=W)
        self.tree.heading('size', text='Tamaño', anchor=W)
        self.tree.heading('modified', text='Modificado', anchor=W)
        self.tree.heading('type', text='Tipo', anchor=W)
        
        self.vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")
        
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)
        
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.controller.update_preview())
        self.tree.bind("<Configure>", lambda e: self._adjust_tree_columns())
        self.tree.bind("<Double-1>", lambda e: self.controller._open_selected_file())  # Doble click
        self.tree.bind("<Return>", lambda e: self.controller._open_selected_file())     # Enter
    def _adjust_tree_columns(self):
        """Ajusta dinámicamente el ancho de las columnas."""
        total_width = self.tree.winfo_width()
        if total_width < 50:
            return
            
        self.tree.column('#0', width=int(total_width * 0.05))
        self.tree.column('name', width=int(total_width * 0.2))
        self.tree.column('path', width=int(total_width * 0.35))
        self.tree.column('size', width=int(total_width * 0.1))
        self.tree.column('modified', width=int(total_width * 0.15))
        self.tree.column('type', width=int(total_width * 0.15))
    
    def _create_preview_panel(self):
        """Crea el panel de vista previa con pestañas de miniaturas."""
        self.preview_frame = Frame(self.container, bg="white", bd=1, relief=SUNKEN)
        self.container.add(self.preview_frame, minsize=200, stretch='always')
        
        title_frame = Frame(self.preview_frame, bg="#4e8cff")
        title_frame.pack(fill=X)
        
        Label(title_frame, text="Vista Previa", bg="#4e8cff", 
             fg="white", font=Font(family="Segoe UI", size=12, weight="bold")).pack(side=LEFT, padx=5)
        
        self.preview_content = Frame(self.preview_frame, bg="white")
        self.preview_content.pack(fill=BOTH, expand=True)
        
        # Vista previa de PDF
        self.pdf_viewer = PDFViewer(self.preview_content)
        self.pdf_viewer.container.pack_forget()
        
        # Visor de miniaturas
        self.thumbnail_viewer = ThumbnailViewer(self.preview_content)
        self.thumbnail_viewer.pack_forget()
        
        # Etiqueta cuando no hay vista previa
        self.no_preview_label = Label(self.preview_content, 
                                    text="Seleccione un archivo para previsualizar", 
                                    bg="white", fg="#777777", font=Font(family="Segoe UI", size=10))
        self.no_preview_label.pack(expand=True)
    
    def clear_results(self):
        """Limpia todos los resultados mostrados."""
        self.tree.delete(*self.tree.get_children())
    
    def add_result(self, idx, result):
        """Añade un resultado al árbol de visualización."""
        self.tree.insert('', 'end', text=str(idx), values=(
            result['name'], result['path'], result['size'],
            result['modified'], result['type']))
    
    def show_pdf_preview(self, file_path):
        """Muestra la vista previa de un PDF."""
        if file_path != self.current_preview_path:
            self._hide_all_previews()
            self.pdf_viewer.container.pack(fill=BOTH, expand=True)
            self.pdf_viewer.load_pdf(file_path)
            self.current_preview_path = file_path
    
    def show_thumbnail_preview(self, file_path):
        """Muestra la vista previa como miniatura."""
        if file_path != self.current_preview_path:
            self._hide_all_previews()
            self.thumbnail_viewer.pack(fill=BOTH, expand=True)
            self.thumbnail_viewer.add_thumbnail_tab(file_path)
            self.current_preview_path = file_path
    
    def show_no_preview(self):
        """Muestra el mensaje cuando no hay vista previa disponible."""
        self._hide_all_previews()
        self.current_preview_path = None
        self.no_preview_label.pack(expand=True)
    
    def _hide_all_previews(self):
        """Oculta todas las vistas previas."""
        self.no_preview_label.pack_forget()
        self.pdf_viewer.container.pack_forget()
        self.thumbnail_viewer.pack_forget()
        self.thumbnail_viewer.clear()

# ==================== CONTROLADOR PRINCIPAL MEJORADO ====================
class EnhancedFileSearchController:
    def __init__(self, root):
        self.root = root
        self.search_active = False
        self.searcher = NetworkOptimizedSearcher()
        self.results = []
        self.document_types = {
            "Imágenes": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"],
            "Documentos": [".doc", ".docx", ".odt", ".pdf", ".rtf", ".txt"],
            "Hojas de cálculo": [".xls", ".xlsx", ".ods", ".csv"],
            "Presentaciones": [".ppt", ".pptx", ".odp"],
            "Videos": [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"],
            "Audio": [".mp3", ".wav", ".ogg", ".flac", ".aac"],
            "Archivos comprimidos": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Ejecutables": [".exe", ".msi", ".bat", ".sh"],
            "Código fuente": [".py", ".java", ".cpp", ".c", ".h", ".html", ".css", ".js"]
        }
        
        self._load_config()
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after_id = None
    
    def _load_config(self):
        try:
            with open('advanced_file_searcher_config.pkl', 'rb') as f:
                config = pickle.load(f)
                self.last_path = config.get('last_path', os.path.expanduser('~'))
                self.last_search = config.get('last_search', '')
                self.last_extension = config.get('last_extension', '')
                self.last_doc_type = config.get('last_doc_type', '')
                self.panel_sizes = config.get('panel_sizes', {})
        except (FileNotFoundError, EOFError, pickle.PickleError):
            self.last_path = os.path.expanduser('~')
            self.last_search = ''
            self.last_extension = ''
            self.last_doc_type = ''
            self.panel_sizes = {}
    
    def _save_config(self):
        if hasattr(self, 'results_panel'):
            sash_pos = self.results_panel.container.sash_coord(0)[0]
            self.panel_sizes['results_panel'] = sash_pos
        
        config = {
            'last_path': self.search_panel.path_entry.get(),
            'last_search': self.search_panel.search_entry.get(),
            'last_extension': self.search_panel.extension_combobox.get(),
            'last_doc_type': self.search_panel.doc_type_combobox.get(),
            'panel_sizes': self.panel_sizes
        }
        with open('advanced_file_searcher_config.pkl', 'wb') as f:
            pickle.dump(config, f)
    
    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('.', background="#f5f5f5", foreground="#333333", 
                       font=Font(family="Segoe UI", size=10))
        style.configure('TButton', background="#4e8cff", foreground="white", borderwidth=1)
        style.map('TButton',
                background=[('active', "#3a6bc8"), ('pressed', "#3a6bc8")],
                foreground=[('active', 'white'), ('pressed', 'white')])
        
        style.configure("Horizontal.TProgressbar", thickness=10, troughcolor="#e0e0e0",
                      background="#4e8cff", lightcolor="#4e8cff")
        
        style.configure("Treeview", background="white", foreground="#333333", rowheight=25)
        style.configure("Treeview.Heading", background="#4e8cff", foreground="white",
                      font=Font(family="Segoe UI", size=9, weight="bold"))
        
        main_frame = Frame(self.root, bg="#f5f5f5", padx=20, pady=20)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        self.search_panel = EnhancedSearchPanel(main_frame, self)
        self.progress_bar = ProgressBar(main_frame)
        self.results_panel = EnhancedResultsPanel(main_frame, self)
        
        self.search_panel.path_entry.insert(0, self.last_path)
        self.search_panel.search_entry.insert(0, self.last_search)
        self.search_panel.extension_combobox.set(self.last_extension)
        self.search_panel.doc_type_combobox.set(self.last_doc_type)
        
        self._setup_context_menu()
    
    def _setup_context_menu(self):
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Abrir archivo(s)", command=self._open_selected_file)
        self.context_menu.add_command(label="Abrir ubicación", command=self._open_file_location)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copiar con nombres personalizados...", command=self._copy_selected_files)
        self.context_menu.add_command(label="Copiar con prefijo...", command=self._copy_with_new_name)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Exportar selección...", command=self._export_selected_files)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Seleccionar todos", command=self._select_all_files)
        self.context_menu.add_command(label="Deseleccionar todos", command=self._deselect_all_files)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Limpiar caché", command=self._clear_cache)
        self.results_panel.tree.bind("<Button-3>", self._show_context_menu)
    
    def _clear_cache(self):
        if messagebox.askyesno("Limpiar caché", "¿Está seguro que desea limpiar toda la caché de búsqueda?"):
            if self.searcher.db.clear_cache():
                messagebox.showinfo("Éxito", "La caché ha sido limpiada correctamente")
            else:
                messagebox.showerror("Error", "No se pudo limpiar la caché")
    
    def scan_folder(self):
        path = self.search_panel.path_entry.get().strip()
        if not path or not os.path.isdir(path):
            messagebox.showerror("Error", "Por favor, seleccione una ruta válida para escanear")
            return
        
        # Mostrar diálogo de progreso
        progress_dialog = Toplevel(self.root)
        progress_dialog.title("Escaneando carpeta...")
        progress_dialog.geometry("400x100")
        progress_dialog.resizable(False, False)
        
        Label(progress_dialog, text="Indexando archivos, por favor espere...").pack(pady=10)
        progress_var = DoubleVar()
        progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
        progress_bar.pack(fill=X, padx=20, pady=10)
        
        def do_scan():
            try:
                self.searcher.indexer.build_index(path)
                self.searcher.db.update_cache(self.searcher.indexer.get_all_files())
                progress_dialog.after(100, lambda: progress_dialog.destroy())
                messagebox.showinfo("Éxito", f"Carpeta indexada correctamente\nArchivos indexados: {len(self.searcher.indexer.index)}")
            except Exception as e:
                progress_dialog.after(100, lambda: progress_dialog.destroy())
                messagebox.showerror("Error", f"No se pudo indexar la carpeta: {str(e)}")
        
        threading.Thread(target=do_scan, daemon=True).start()
    
    def start_search(self):
        """Inicia una búsqueda con los parámetros actuales."""
        params = self.search_panel.get_search_params()
        
        if not params['path'] or not os.path.isdir(params['path']):
            messagebox.showerror("Error", "Por favor, seleccione una ruta válida")
            return
        
        self.results_panel.clear_results()
        self.results = []
        
        self.progress_bar.update_progress(0)
        self.progress_bar.update_status("Buscando...")
        self.progress_bar.update_result_count(0)
        self.progress_bar.update_time(0)
        self.search_panel.set_search_state(True)
        self.search_active = True
        self.search_start_time = time.time()
        self._update_time_label()
        
        type_extensions = []
        if params['doc_type'] and params['doc_type'] in self.document_types:
            type_extensions = [ext.lower() for ext in self.document_types[params['doc_type']]]
        
        self.search_thread = threading.Thread(
            target=self._run_search,
            args=(params['path'], params['search_term'], params['extension'], 
                 type_extensions, params['search_content'], params['content_pattern']),
            daemon=True
        )
        self.search_thread.start()
    
    def _run_search(self, path, search_term, extension, type_extensions, search_content, content_pattern):
        """Ejecuta la búsqueda mejorada con todas las características."""
        def callback(result):
            self.results.append(result)
            if len(self.results) % 100 == 0:
                self.root.after(0, self._update_ui)
        
        def progress_callback(progress, count):
            current_time = time.time() - self.search_start_time
            self.root.after(0, lambda: [
                self.progress_bar.update_progress(progress),
                self.progress_bar.update_result_count(count),
                self.progress_bar.update_time(current_time),
                self._update_ui()
            ])
        
        self.searcher.search(
            path,
            search_term,
            extension,
            type_extensions,
            callback,
            progress_callback,
            search_content,
            content_pattern
        )
        
        self.root.after(0, self._finalize_search)
    
    def _update_ui(self):
        """Actualiza la interfaz de usuario con los resultados actuales."""
        self.results_panel.tree.delete(*self.results_panel.tree.get_children())
        
        reverse_order = self.search_panel.sort_order.get() == "reciente"
        self.results.sort(
            key=lambda x: os.path.getmtime(x['full_path']) if os.path.exists(x['full_path']) else 0,
            reverse=reverse_order
        )
        
        for idx, result in enumerate(self.results, 1):
            self.results_panel.add_result(idx, result)
    
    def _finalize_search(self):
        """Finaliza la búsqueda y actualiza la interfaz."""
        current_time = time.time() - self.search_start_time
        self.progress_bar.update_time(current_time)
        self.search_active = False
        self.search_panel.set_search_state(False)
        self.progress_bar.update_status("Búsqueda completada", "#4e8cff")
        self._update_ui()
    
    def _update_time_label(self):
        """Actualiza la etiqueta de tiempo durante la búsqueda."""
        if self.search_active:
            current_time = time.time() - self.search_start_time
            self.progress_bar.update_time(current_time)
            self.after_id = self.root.after(1000, self._update_time_label)
    
    def pause_search(self):
        """Pausa la búsqueda actual."""
        if hasattr(self, 'searcher'):
            self.searcher.pause()
            self.progress_bar.update_status("Búsqueda pausada", "#ffaa00")
    
    def resume_search(self):
        """Reanuda la búsqueda pausada."""
        if hasattr(self, 'searcher'):
            self.searcher.resume()
            self.progress_bar.update_status("Buscando...", "#4e8cff")
    
    def stop_search(self):
        """Detiene la búsqueda actual."""
        if hasattr(self, 'searcher'):
            self.searcher.stop()
        if self.after_id:
            self.root.after_cancel(self.after_id)
        current_time = time.time() - self.search_start_time
        self.progress_bar.update_time(current_time)
        self.search_active = False
        self.progress_bar.update_status("Búsqueda detenida", "#ff5555")
        self.search_panel.set_search_state(False)
    
    def update_preview(self):
        """Actualiza la vista previa basada en la selección actual."""
        selected_items = self.results_panel.tree.selection()
        
        if not selected_items or len(selected_items) > 1:
            self.results_panel.show_no_preview()
            return
        
        item = selected_items[0]
        values = self.results_panel.tree.item(item, 'values')
        full_path = os.path.join(values[1], values[0])
        file_type = values[4]
        
        if not os.path.exists(full_path):
            self.results_panel.show_no_preview()
            return
        
        # Vista previa para PDF
        if file_type == "Documentos" and values[0].lower().endswith('.pdf'):
            self.results_panel.show_pdf_preview(full_path)
        # Vista previa para imágenes
        elif file_type == "Imágenes":
            self.results_panel.show_thumbnail_preview(full_path)
        else:
            self.results_panel.show_no_preview()
    
    def export_results(self):
        """Exporta todos los resultados a un archivo."""
        if not self.results:
            messagebox.showwarning("Advertencia", "No hay resultados para exportar")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        
        if filename:
            if filename.endswith('.xlsx'):
                success = Exporter.to_excel(self.results, filename)
            else:
                success = Exporter.to_csv(self.results, filename)
            
            if success:
                messagebox.showinfo("Éxito", f"Resultados exportados a {filename}")
            else:
                messagebox.showerror("Error", "No se pudieron exportar los resultados")
    
    def _export_selected_files(self):
        """Exporta los archivos seleccionados a un archivo."""
        selected_items = self.results_panel.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "No hay archivos seleccionados")
            return
        
        selected_results = []
        for item in selected_items:
            values = self.results_panel.tree.item(item, 'values')
            selected_results.append({
                'name': values[0],
                'path': values[1],
                'size': values[2],
                'modified': values[3],
                'type': values[4],
                'full_path': os.path.join(values[1], values[0])
            })
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        
        if filename:
            if filename.endswith('.xlsx'):
                success = Exporter.to_excel(selected_results, filename)
            else:
                success = Exporter.to_csv(selected_results, filename)
            
            if success:
                messagebox.showinfo("Éxito", f"Archivos seleccionados exportados a {filename}")
            else:
                messagebox.showerror("Error", "No se pudieron exportar los archivos seleccionados")
    
    def _open_selected_file(self):
        selected_items = self.results_panel.tree.selection()
        if not selected_items:
            return
        
        for item in selected_items:
            values = self.results_panel.tree.item(item, 'values')
            full_path = os.path.join(values[1], values[0])
            
            if not os.path.exists(full_path):
                messagebox.showerror("Error", f"El archivo no existe: {full_path}")
                continue
            
            try:
                os.startfile(full_path)
            except:
                try:
                    import subprocess
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, full_path])
                except:
                    messagebox.showerror("Error", f"No se pudo abrir el archivo: {full_path}")
    
    def _open_file_location(self):
        selected_items = self.results_panel.tree.selection()
        if not selected_items:
            return
        
        item = selected_items[0]
        values = self.results_panel.tree.item(item, 'values')
        folder_path = values[1]
        
        if not os.path.exists(folder_path):
            messagebox.showerror("Error", f"La ubicación no existe: {folder_path}")
            return
        
        try:
            os.startfile(folder_path)
        except:
            try:
                import subprocess
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, folder_path])
            except:
                messagebox.showerror("Error", f"No se pudo abrir la ubicación: {folder_path}")
    
    def _copy_selected_files(self):
        selected_items = self.results_panel.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "No hay archivos seleccionados")
            return
        
        dest_folder = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not dest_folder:
            return
        
        total_files = len(selected_items)
        copied_files = 0
        errors = []
        
        for item in selected_items:
            values = self.results_panel.tree.item(item, 'values')
            full_path = os.path.join(values[1], values[0])
            original_name = values[0]
            
            if not os.path.exists(full_path):
                errors.append(f"{original_name}: El archivo no existe")
                continue
            
            new_name = filedialog.asksaveasfilename(
                title=f"Guardar copia de {original_name}",
                initialdir=dest_folder,
                initialfile=original_name,
                defaultextension=os.path.splitext(original_name)[1]
            )
            
            if not new_name:
                continue
            
            try:
                shutil.copy2(full_path, new_name)
                copied_files += 1
            except Exception as e:
                errors.append(f"{original_name}: {str(e)}")
        
        message = f"Se copiaron {copied_files} de {total_files} archivos."
        if errors:
            message += "\n\nErrores:\n" + "\n".join(errors)
        
        messagebox.showinfo("Resultado", message)
    
    def _copy_with_new_name(self):
        selected_items = self.results_panel.tree.selection()
        if not selected_items:
            messagebox.showwarning("Advertencia", "No hay archivos seleccionados")
            return
        
        dest_folder = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not dest_folder:
            return
        
        prefix = simpledialog.askstring("Prefijo", "Ingrese un prefijo para los archivos:")
        if prefix is None:
            return
        
        total_files = len(selected_items)
        copied_files = 0
        errors = []
        
        for idx, item in enumerate(selected_items, 1):
            values = self.results_panel.tree.item(item, 'values')
            full_path = os.path.join(values[1], values[0])
            name, ext = os.path.splitext(values[0])
            
            if not os.path.exists(full_path):
                errors.append(f"{values[0]}: El archivo no existe")
                continue
            
            new_name = f"{prefix}_{idx}{ext}"
            dest_path = os.path.join(dest_folder, new_name)
            
            try:
                shutil.copy2(full_path, dest_path)
                copied_files += 1
            except Exception as e:
                errors.append(f"{values[0]}: {str(e)}")
        
        message = f"Se copiaron {copied_files} de {total_files} archivos."
        if errors:
            message += "\n\nErrores:\n" + "\n".join(errors)
        
        messagebox.showinfo("Resultado", message)
    
    def _select_all_files(self):
        self.results_panel.tree.selection_set(self.results_panel.tree.get_children())
    
    def _deselect_all_files(self):
        self.results_panel.tree.selection_set([])
    
    def _show_context_menu(self, event):
        item = self.results_panel.tree.identify_row(event.y)
        if item:
            if not self.results_panel.tree.selection():
                self.results_panel.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def on_close(self):
        if self.search_active:
            if messagebox.askyesno("Salir", "Hay una búsqueda en curso. ¿Desea detenerla y salir?"):
                self.stop_search()
                time.sleep(0.5)
            else:
                return
        
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self._save_config()
        self.root.destroy()

# ==================== EJECUCIÓN PRINCIPAL ====================
if __name__ == "__main__":
    root = Tk()
    root.title("🔍 Buscador Avanzado de Archivos (Optimizado)")
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{int(screen_width*0.8)}x{int(screen_height*0.8)}")
    root.minsize(int(screen_width*0.5), int(screen_height*0.5))
    
    if os.name == 'nt':
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    
    app = EnhancedFileSearchController(root)
    root.mainloop()