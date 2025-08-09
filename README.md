# Herramientas_de_python_para_automatizar


# Manual de Herramientas de Gestión de Archivos

## 1. Buscador de Archivos Avanzado (Buscador.py)

### Descripción
Herramienta avanzada para buscar archivos en el sistema con múltiples filtros y opciones de visualización.

### Funcionalidades principales:
- Búsqueda por nombre, extensión o tipo de archivo
- Vista previa de archivos (imágenes y PDFs)
- Filtros avanzados (tamaño, fecha, contenido)
- Exportación de resultados a Excel o CSV
- Sistema de caché para búsquedas rápidas
- Indexación de archivos para mayor velocidad

### Instrucciones de uso:
1. **Configurar búsqueda**:
   - Ingrese la ruta a buscar en "Carpeta"
   - Especifique términos de búsqueda en "Nombre"
   - Seleccione extensión o tipo de archivo si es necesario

2. **Opciones avanzadas**:
   - Active "Buscar en contenido" para buscar dentro de los archivos
   - Use filtros de tamaño (pequeño, mediano, grande)
   - Seleccione orden de resultados (más reciente o más antiguo)

3. **Ejecutar búsqueda**:
   - Haga clic en "Buscar Archivos"
   - Use los botones "Pausar", "Reanudar" o "Detener" según necesite

4. **Visualizar resultados**:
   - Seleccione archivos para ver previsualización
   - Use las pestañas para navegar entre miniaturas
   - Para PDFs, use los controles de navegación y zoom

5. **Exportar resultados**:
   - Haga clic en "Exportar" para guardar los resultados
   - Seleccione formato (Excel o CSV)

### Consejos:
- Use el botón "Escanear" para indexar carpetas grandes y acelerar futuras búsquedas
- Active "Usar caché" para mejorar el rendimiento
- Puede abrir archivos directamente con doble clic o Enter

---

## 2. Conversor de Archivos Excel/CSV (Convertidor.py)

### Descripción
Herramienta para convertir entre formatos de hojas de cálculo (Excel, CSV, ODS, XLSB, HTML, PDF).

### Funcionalidades principales:
- Conversión entre múltiples formatos
- Detección automática de codificación y delimitadores (CSV)
- Interfaz de arrastrar y soltar
- Progreso visual de conversión

### Instrucciones de uso:
1. **Seleccionar archivo**:
   - Arrastre y suelte un archivo en el área designada
   - O use el diálogo de archivos (no mostrado en interfaz)

2. **Configurar conversión**:
   - Seleccione formato de salida (XLSX, CSV, PDF, etc.)
   - Especifique codificación si es necesario (UTF-8 por defecto)
   - Use "Detectar" para identificar codificación automáticamente

3. **Especificar destino**:
   - Haga clic en "Guardar en..." para seleccionar ubicación
   - El nombre por defecto incluye la fecha actual

4. **Ejecutar conversión**:
   - Haga clic en "Convertir Archivo"
   - Espere a que la barra de progreso complete la operación

5. **Resultados**:
   - Se mostrará mensaje de éxito o error
   - El archivo convertido se guardará en la ubicación especificada

### Formatos soportados:
- Entrada: XLSX, XLS, ODS, XLSB, CSV
- Salida: XLSX, XLS, ODS, XLSB, CSV, HTML, PDF

### Consejos:
- Para archivos CSV problemáticos, pruebe diferentes delimitadores
- La conversión a PDF requiere wkhtmltopdf instalado
- Use el botón "Resetear" para limpiar la selección actual

---

## 3. Fusionador de PDFs (Unificador.py)

### Descripción
Herramienta simple para combinar dos archivos PDF en uno solo.

### Funcionalidades principales:
- Interfaz de arrastrar y soltar
- Vista previa del orden de fusión
- Control de calidad del PDF resultante

### Instrucciones de uso:
1. **Seleccionar archivos**:
   - Arrastre el primer PDF al área "Primer PDF"
   - Arrastre el segundo PDF al área "Segundo PDF"
   - El nombre del archivo resultante tomará el nombre del segundo PDF

2. **Fusionar**:
   - Haga clic en "Fusionar PDFs" (se activa cuando ambos archivos están cargados)
   - Seleccione ubicación y nombre para el PDF fusionado

3. **Resultado**:
   - Se mostrará confirmación con la ruta del archivo guardado
   - La interfaz se reseteará para nueva operación

### Consejos:
- El orden de fusión es importante: primero el archivo 1, luego el 2
- Puede usar las teclas de flecha para navegar entre páginas en la vista previa
- Ajuste el zoom según necesidad antes de fusionar

---

## 4. Herramienta de Manejo de Archivos Avanzada (Nom_o_copy.py)

### Descripción
Herramienta multifunción para buscar, copiar y renombrar archivos basados en patrones.

### Funcionalidades principales:
- Búsqueda de archivos por patrones de nombre
- Copia de archivos con mantenimiento de estructura
- Renombrado automático basado en estructura de carpetas
- Generación de informes detallados
- Configuración personalizable

### Instrucciones de uso:

#### 1. Configuración inicial:
- Establezca patrones de búsqueda en el cuadro de texto
- Configure rutas predeterminadas en cada pestaña
- Especifique filtro por extensión si es necesario

#### 2. Búsqueda (pestaña Búsqueda):
1. Ingrese patrones a buscar (uno por línea)
2. Especifique directorio a buscar
3. Haga clic en "Ejecutar Búsqueda"
4. Revise el informe generado

#### 3. Copia (pestaña Copiar):
1. Ingrese patrones a buscar
2. Especifique directorio origen y destino
3. Haga clic en "Ejecutar Búsqueda y Copia"
4. Se copiarán los archivos más recientes que coincidan

#### 4. Renombrado (pestaña Renombrar):
1. Ingrese patrones a buscar
2. Especifique directorio origen y destino
3. Haga clic en "Ejecutar Búsqueda y Renombrar"
4. Los archivos se copiarán al destino con nuevo nombre basado en estructura de carpetas

### Características avanzadas:
- **Patrones de búsqueda**: Puede incluir múltiples patrones (uno por línea)
- **Renombrado inteligente**: Usa nombres de carpetas parentales para generar nuevos nombres
- **Gestión de errores**: Genera informes detallados de operaciones
- **Configuración persistente**: Guarda preferencias entre sesiones

### Consejos:
- Use nombres únicos en los patrones para mejores resultados
- Revise siempre los informes generados para verificar operaciones
- Puede detener operaciones largas con el botón "Detener Operación"
- La configuración se guarda automáticamente en `ruta_config.json`

---

## Notas generales:
1. Todas las herramientas tienen interfaz gráfica moderna y responsive
2. Soporte para arrastrar y soltar en varias herramientas
3. Progreso visual en operaciones largas
4. Manejo robusto de errores y notificaciones al usuario
5. Compatible con Windows (algunas funciones pueden requerir software adicional como wkhtmltopdf)
