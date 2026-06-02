# OCR-LLM Autoself Localization Tool

**Herramienta interna de QA para auditoría de localización**

OCR-LLM Autoself Localization Tool es una plataforma de aseguramiento de calidad (QA) automática orientada a proyectos de localización. Combina procesamiento de OCR en capturas de pantalla de aplicaciones con modelos de lenguaje (LLM) locales (u opcionalmente en la nube) para identificar defectos de traducción, ortografía, inconsistencias de UI, cadenas no traducidas, truncamientos y más. El resultado es un reporte consolidado en Excel con capturas anotadas y 14 columnas listas para revisión por el equipo de desarrollo.

## Contenido

1. [Instalación de Herramientas Base](#01-instalación-de-herramientas-base)
2. [Configuración del Entorno](#02-configuración-del-entorno)
3. [Ejecución](#03-ejecución)
4. [Flujo de Trabajo del Usuario](#04-flujo-de-trabajo-del-usuario)
5. [Arquitectura del Sistema](#05-arquitectura)
6. [Archivo a Archivo](#06-archivo-a-archivo)
7. [Esquema de Excel de Salida](#07-esquema-de-excel-de-salida)
8. [Puntos de Depuración](#08-puntos-de-depuración)
9. [Próximos Pasos](#09-próximos-pasos)

---

## 01. Instalación de Herramientas Base

Ejecuta los instaladores en `./bin` en este orden:

### 1. Python 3.12.10
Durante la instalación, **marca “Add Python 3.12 to PATH”** antes de continuar con "Install Now". Esto simplifica el uso de Python desde la terminal.

### 2. Tesseract OCR
Ejecuta `tesseract-ocr-w64-setup-5.5.0.20241111.exe`. Durante la instalación:
- Selecciona todos los paquetes adicionales de idioma y script. Actualmente el pipeline usa `-l spa` (Español) por defecto.
- Cambia la ruta de instalación a `./tesseract` (relativo a la raíz del proyecto). Esta ruta se resuelve en `Backend/env.py`.
- La línea de idioma (`-l spa`) está codificada en `screenshot_ocr.py` (función `_run_tess()`).

### 3. Ollama
Ejecuta `OllamaSetup.exe` con opciones por defecto. Después, descarga un modelo inicial:

```bash
ollama pull gemma4:e2b
```

Este modelo (`gemma4:e2b`) es el predeterminado en `localQ.py`. La aplicación permite cambiar el modelo en tiempo de ejecución mediante una lista desplegable, sin reiniciar el programa. El botón "+ Add model" abre una terminal con instrucciones de `ollama pull`.

## 02. Configuración del Entorno

Desde la raíz del proyecto, en CMD o PowerShell:

```bash
prepare_env.bat
```

Este script:
- Crea un entorno virtual en `./venv`.
- Instala las dependencias listadas en `requirements.txt`.
- Actualiza el PATH si es necesario.

Tras instalar Python o Tesseract, es posible que debas reiniciar la terminal/IDE para que reconozca las rutas nuevas.

## 03. Ejecución

Lanza la aplicación con:

```bash
launch.bat
```

La secuencia es:
- `launch.bat` activa el entorno `./venv`.
- Ejecuta `main.py`.
- `main.py` levanta el servidor Flask (por defecto en `http://127.0.0.1:5000`) en un hilo.
- Abre una ventana de navegador (via pywebview) apuntando a la UI.

Detén la aplicación cerrando la ventana. El servicio de Ollama corre por separado y no se detiene.

> **Nota:** Al seleccionar carpeta en la app, aparecerá un diálogo nativo (Tkinter). Es normal que sea modal del sistema.

## 04. Flujo de Trabajo del Usuario

### Índice Inicial
La página principal ofrece:
- Modelo Ollama: lista desplegable cargada con `ollama list`.
- + Add model: abre terminal con `ollama pull`.
- Start Fresh: si se activa, borra la caché del workspace seleccionado antes de iniciar.
- Select Directory: abre diálogo nativo para escoger la carpeta de capturas; luego muestra pantalla de carga.

### Pantalla de Carga
Tras elegir el directorio, aparece una tarjeta de loading mientras Ollama carga el modelo seleccionado en memoria. Se consulta `/models/status` cada segundo; cuando responde `"ready"`, se abre el workspace automáticamente. Si falla (modelo no descargado, servicio Ollama detenido, etc.), muestra un mensaje de error con el motivo.

### Pantalla de Workspace
La interfaz tiene tres columnas:
- **Izquierda (Workspace)**: lista de archivos, botones principales (Workspace / Add / Auto / Export) y controles de caché (Reprocess / Clear ws / Clear all / Stats).
- **Centro (Vista previa)**: muestra la captura de pantalla. Inicialmente se ve la imagen limpia. Al presionar OCR, se muestra una animación de carga; luego se visualizan las cajas OCR en verde/naranja. Se puede hacer zoom/pan con la rueda/arrastrando.
- **Derecha (Control)**: botones OCR, Analyze, Prev, Next y contadores de gravedad con la lista de issues.

### Flujo típico (una imagen)
1. En Workspace, elige la carpeta de capturas.
2. Espera a la pantalla de carga → se abre el espacio de trabajo.
3. Clic **OCR** → corre el pipeline Tesseract+MSER.
4. Clic **Analyze** → envía el OCR al LLM y aparecen los resultados.
5. Clic **Add** → indexa los issues de la imagen actual en el reporte.
6. Clic **Next** para la siguiente imagen.

Al finalizar, clic **Export** → guarda el reporte Excel.

El botón **Auto** ejecuta automáticamente (OCR → Analyze → Add → Next) en todas las imágenes y luego exporta.

> **Nota:** El bucle completo es: OCR por imagen → LLM (QA) → índice de resultados. Se garantiza que cada imagen pasa por OCR antes de QA.

## 05. Arquitectura del Sistema

```text
PNG folder
   |
   v
DPI (Backend/DPI.py) ←-- Estado del workspace, caches, prefetch
   |
   +--> screenshot_ocr.py ← MSER + CLAHE + Tesseract multi-PSM
   |
   +--> region_prefilter.py ← Clasificación de regiones por confianza OCR
   |
   +--> localQ.py ← LLM local vía Ollama (o gemini_qa.py en la nube)
   |
   v
Indexer.py ← Acumulador de issues
   |
   v
report_builder.py ← Generación de Excel 14-columnas
   |
   v
`ocr_llm_report.xlsx`
```

**Componentes principales:**

- `DPI.py`: mantiene el estado (cache en memoria y disco, hilos de prefetch, etc).
- `screenshot_ocr.py`: pipeline de OCR nativo (detección MSER, CLAHE, Tesseract).
- `region_prefilter.py`: clasifica regiones por confianza (high/send, mid/context, low/noise).
- `localQ.py`: llama a Ollama para QA lingüística local (JSON estricto, think=False).
- `gemini_qa.py`: backend alternativo en la nube (Google Gemini).
- `Indexer.py`: recibe los resultados por imagen, normaliza filas.
- `report_builder.py`: genera el Excel final con formato (imágenes, filtros, formato condicional).
- `disk_cache.py`: caché en disco (`%APPDATA%/OCR-LLM-Autoself/cache`).
- `ollama_admin.py`: listas de modelos, estado de precarga, etc.
- `logger.py`: logging centralizado.
- `templates/` y `static/`: frontend (Bootstrap, CSS, JS).

> **Sobre el fallback Gemini:** no es automático. Para usarlo, edita `Backend/DPI.py` y reemplaza la línea `from .localQ import analyze_text` por `from .gemini_qa import analyze_text`. Requiere `GEMINI_API_KEY` válida en `env.py`.

**Estrategia de Caché**  
Dos niveles de caché usando `hash_image(path)` (MD5).  
Orden: memoria → disco → procesamiento.

**Filtro de Regiones**
- `SEND_CONF = 0.95`
- `CONTEXT_CONF = 0.80`
- `MAX_REGIONS_TO_LLM=120`

## 06. Archivo a Archivo

| Archivo | Propósito |
|---------|-----------|
| `Backend/__init__.py` | Fabrica de la app Flask y rutas HTTP |
| `Backend/env.py` | Constantes de configuración |
| `Backend/DPI.py` | Abstracción del workspace |
| `Backend/screenshot_ocr.py` | Pipeline de OCR |
| `Backend/region_prefilter.py` | Clasificador de regiones |
| `Backend/localQ.py` | Llamadas al LLM local |
| `Backend/gemini_qa.py` | QA en la nube (Gemini) |
| `Backend/Indexer.py` | Acumula issues |
| `Backend/report_builder.py` | Generación del Excel |
| `Backend/disk_cache.py` | Caché en disco |
| `Backend/ollama_admin.py` | Manejo de modelos Ollama |
| `Backend/logger.py` | Logging centralizado |
| `Backend/templates/*.html` | Plantillas Jinja |
| `Backend/static/js/API.js` | Lógica frontend |
| `Backend/static/css/main.css` | Estilos |
| `main.py` | Punto de entrada |

## 07. Esquema de Excel de Salida

`report_builder.py` genera un Excel con **14 columnas**:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| Type | chip | ISSUE / WARNING |
| Severity | chip | high / medium / low / info |
| Screenshot | texto | Nombre base del archivo |
| Annotated | imagen | Miniatura con cuadro rojo |
| Category | texto | Categoría del issue |
| OCR Text | mono | Texto OCR bruto |
| Suggestion | mono | Sugerencia del LLM |
| Explanation (ES) | texto | Razonamiento en español |
| Explanation (EN) | texto | Razonamiento en inglés |
| LLM Confidence | chip | Confianza del modelo |
| OCR Trust | float | Confianza media OCR |
| Region IDs | texto | IDs de regiones |
| Pre-Filtered | bool | Si fue prefiltrado |
| Source Path | texto | Ruta completa (oculta) |

## 08. Puntos de Depuración

- **Logs**: Formato `[HH:MM:SS] [MÓDULO] mensaje`
- **Caché corrupta**: Borra `%APPDATA%\OCR-LLM-Autoself\cache`
- **Interfaz no actualizada**: Borra caché de pywebview o Ctrl+F5
- **Modelo no encontrado**: `ollama list` y `ollama pull`
- **Warmup detenido**: Revisa `/models/status`

## 09. Próximos Pasos

1. Realizar el commit de este `README.md`.
2. Actualizar el repositorio remoto.
3. (Opcional) Habilitar **GitHub Pages** para servir la documentación completa.

**Repositorio:** [https://github.com/opensierra/OCR-LLM-autoself-localization-tool](https://github.com/opensierra/OCR-LLM-autoself-localization-tool)
