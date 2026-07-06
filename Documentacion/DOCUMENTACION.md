# Documentación Técnica — RPA IA Santa Lucía

**Versión:** 1.0.0  
**Autor:** Brayand Javier Gomez Plata  
**Fecha:** 2026-06-29  
**Proyecto:** Trabajo de Fin de Máster — Máster en Desarrollo de Inteligencia Artificial  
**Repositorio:** https://github.com/briandplata/RPA_IA_SANTA_LUCIA  
**Video demo:** https://www.youtube.com/watch?v=cfsQEmF1t2w

---

## 1. Descripción general del proyecto

RPA IA Santa Lucía es un pipeline de automatización robótica de procesos (RPA) con inteligencia artificial integrada, desarrollado para el Laboratorio Clínico Santa Lucía IPS S.A.S. El sistema automatiza completamente el flujo de verificación de autorizaciones médicas ante la EPS Salud Total, eliminando el trabajo manual de un proceso que históricamente requería que el personal administrativo consultara cada formulario físico de manera individual en la plataforma web.

El robot ejecuta cinco subprocesos secuenciales: lee documentos PDF manuscritos y escaneados, extrae datos clave usando visión artificial (GPT-4o), consolida los resultados en Excel, organiza los archivos en carpetas de destino y verifica cada autorización directamente en la plataforma transaccional de Salud Total EPS mediante automatización web con Playwright.

---

## 2. Problema que resuelve

La IPS recibe diariamente formularios físicos de autorización de servicios médicos. Antes del robot, el proceso era:

1. El personal recibía los formularios en papel.
2. Los transcribía manualmente a una hoja de cálculo.
3. Ingresaba a la plataforma web de Salud Total y consultaba cada autorización de forma individual.
4. Copiaba los resultados de vuelta al Excel.

Este proceso era lento, propenso a errores de transcripción y ocupaba tiempo valioso del personal administrativo. El robot reemplaza los pasos 2, 3 y 4 completamente, requiriendo solo que el personal digitalice (escanee) los formularios y los coloque en la carpeta `pacientes/`.

---

## 3. Arquitectura del sistema

### 3.1 Vista general del pipeline

```
pacientes/ (PDFs)
     │
     ▼
[p01] Listar PDFs
     │
     ├── Sin PDFs ──────────────────────────────┐
     │                                          │
     ▼                                          │
[p02] OCR con GPT-4o Vision                    │
     │ (extrae 4 campos + valida formato)       │
     ▼                                          │
[p03] Escribir Excel                            │
     │ (consolidado.xlsx + errores.xlsx)        │
     ▼                                          │
[p04] Mover archivos                            │
     │ (procesados/ o no_procesados/)           │
     │                                          │
     └──────────────────────────────────────────┤
                                                │
                                                ▼
                                    [p05] Verificación web
                                    (Salud Total EPS · Playwright)
                                         │
                                         ▼
                                    consolidado.xlsx
                                    (columnas G-L actualizadas)
```

### 3.2 Estructura de carpetas

```
RPA_IA_SANTA_LUCIA/
├── main.py                        # Orquestador — sin lógica de negocio
├── config.yaml                    # Configuración centralizada (sin credenciales)
├── .env.example                   # Template de variables de entorno
├── .gitignore                     # Excluye .env, pacientes/, logs/
├── requirements.txt               # Dependencias Python
├── README.md                      # Guía de instalación y uso
├── DOCUMENTACION.md               # Este documento
│
├── processes/
│   ├── p01_listar_pdfs.py         # Escanea pacientes/ y retorna rutas de PDF
│   ├── p02_ocr_ia.py              # GPT-4o Vision: extracción y validación
│   ├── p03_excel.py               # Escribe consolidado.xlsx y errores.xlsx
│   ├── p04_mover_archivos.py      # Mueve PDFs según resultado del pipeline
│   └── p05_navegacion_web.py      # RPA web: verifica en SaludTotal
│
├── utils/
│   └── logger.py                  # Logger dual: archivo (DEBUG) + consola (INFO)
│
├── pacientes/                     # NO incluida en repositorio (datos reales)
│   ├── procesados/
│   │   └── consolidado.xlsx
│   └── no_procesados/
│       └── errores.xlsx
│
└── logs/
    └── main.log
```

---

## 4. Descripción de módulos

### 4.1 `main.py` — Orquestador principal

Punto de entrada del robot. No contiene lógica de negocio; su única responsabilidad es coordinar la ejecución secuencial de los cinco subprocesos y gestionar el flujo de errores.

**Responsabilidades:**
- Cerrar procesos `EXCEL.EXE` al inicio para evitar bloqueos de archivo (Windows).
- Cargar variables de entorno desde `.env` con `python-dotenv`.
- Cargar configuración centralizada desde `config.yaml` con PyYAML.
- Inicializar el logger centralizado.
- Llamar a cada subproceso en orden y detener la ejecución con `sys.exit(1)` si alguno falla.
- Garantizar que `p05` siempre se ejecute, incluso cuando no hay PDFs nuevos.

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `cerrar_excel()` | Ejecuta `taskkill /F /IM EXCEL.EXE` para liberar bloqueos |
| `cargar_config(ruta)` | Lee y parsea `config.yaml` |
| `main()` | Orquesta p01→p05 con control de errores |

---

### 4.2 `utils/logger.py` — Logger centralizado

Configura y retorna una instancia única de `logging.Logger` con dos handlers simultáneos:

| Handler | Nivel | Destino | Formato |
|---------|-------|---------|---------|
| `FileHandler` | DEBUG | `logs/main.log` | Timestamp \| nivel \| mensaje |
| `StreamHandler` | INFO | Consola | Mismo formato |

Es idempotente: si el logger ya tiene handlers configurados no los duplica (evita mensajes repetidos en recargas de módulo).

**Uso:**
```python
from utils.logger import get_logger
logger = get_logger("logs/main.log")
logger.info("Mensaje informativo")
logger.error("Error con detalle: %s", str(e))
```

---

### 4.3 `processes/p01_listar_pdfs.py` — Listar PDFs

Escanea el primer nivel de la carpeta `pacientes/` y retorna las rutas absolutas de todos los archivos `.pdf` encontrados.

**Comportamiento clave:** retorna siempre `(True, [])` cuando no hay PDFs (en lugar de `(False, None)`), lo que permite que el pipeline continúe hasta `p05` para verificar filas pendientes del Excel.

**Interfaz:**
```python
exito, pdfs = ejecutar(config, logger)
# exito: bool
# pdfs: list[str] | [] si no hay PDFs | None si error crítico
```

---

### 4.4 `processes/p02_ocr_ia.py` — OCR con IA

Extrae los datos de cada formulario PDF usando GPT-4o Vision de OpenAI. Es el componente de inteligencia artificial del pipeline.

**Tecnologías utilizadas:**
- **PyMuPDF (fitz):** Convierte cada página del PDF a imagen PNG sin depender de Poppler ni de drivers externos. Usa zoom 3x (≈216 dpi) para garantizar resolución suficiente en documentos manuscritos.
- **OpenAI GPT-4o:** Modelo multimodal de visión que analiza la imagen y extrae texto estructurado en formato JSON.

**Campos extraídos:**

| Campo | Descripción | Validación |
|-------|-------------|------------|
| `id_paciente` | Cédula del paciente | Solo dígitos |
| `autorizacion` | Número AUT | Regex: `^\d{5}-\d{10}$` |
| `cod_fact` | Código de facturación | Solo dígitos |
| `nombre_paciente` | Nombre completo | No vacío |

**Prompt de OCR:** Incluye instrucciones explícitas para leer cada dígito individualmente, manejar documentos rotados o espejados, y devolver `null` (no inventar) si un campo no es legible con certeza absoluta.

**Reintentos:** Hasta 3 intentos por archivo. Si falla los 3, el archivo va a `errores.xlsx` con motivo `NO_LEGIBLE`.

**Seguridad:** La `OPENAI_API_KEY` se lee exclusivamente desde la variable de entorno, nunca del código ni del `config.yaml`.

---

### 4.5 `processes/p03_excel.py` — Escritura de Excel

Gestiona los dos archivos Excel del sistema y controla la deduplicación por número de autorización.

**Archivo consolidado.xlsx — 12 columnas:**

| Col | Nombre | Fuente |
|-----|--------|--------|
| A | Fecha_Hora | p02 (hora de lectura del PDF) |
| B | Archivo | p02 (nombre del PDF) |
| C | ID_Paciente | p02 (GPT-4o) |
| D | Nombre_Paciente | p02 (GPT-4o) |
| E | Autorizacion | p02 (GPT-4o) |
| F | Cod_Fact | p02 (GPT-4o) |
| G | ESTADO_ROBOT | p05 (vacío = pendiente) |
| H | Paquete | p05 (web SaludTotal) |
| I | Cantidad | p05 (web SaludTotal) |
| J | Sede | p05 (web SaludTotal) |
| K | Nombre_Convenio | p05 (web SaludTotal) |
| L | Fecha_Vencimiento | p05 (web SaludTotal) |

**Archivo errores.xlsx — 4 columnas:**

| Col | Nombre | Descripción |
|-----|--------|-------------|
| A | Fecha_Hora | Hora del error |
| B | Archivo | Nombre del PDF |
| C | Motivo_Error | `NO_LEGIBLE` o `DUPLICADO` |
| D | Detalle | Descripción técnica del error |

**Estilo de cabecera:** fondo azul oscuro (#1F4E79), texto blanco en negrita.

**Deduplicación:** Antes de insertar una fila nueva, verifica que el número AUT no exista ya en `consolidado.xlsx`. Los duplicados se registran en `errores.xlsx` y el flag `_duplicado=True` se adjunta al item para que `p04` lo mueva a `no_procesados/`.

---

### 4.6 `processes/p04_mover_archivos.py` — Organización de archivos

Mueve los PDFs desde la raíz de `pacientes/` a sus carpetas de destino según el resultado del pipeline:

| Condición | Destino |
|-----------|---------|
| OCR exitoso + sin duplicado | `pacientes/procesados/` |
| OCR exitoso + duplicado | `pacientes/no_procesados/` |
| OCR fallido | `pacientes/no_procesados/` |

Incluye protección contra sobreescritura: si el destino ya tiene un archivo con el mismo nombre, agrega sufijo numérico (`_1`, `_2`, ...).

Tras su ejecución la carpeta raíz `pacientes/` queda vacía, lista para recibir nuevos documentos del cliente.

---

### 4.7 `processes/p05_navegacion_web.py` — Verificación RPA web

Es el subproceso más complejo del pipeline. Abre una sesión de Playwright Chromium, hace login en la plataforma transaccional de Salud Total EPS y verifica secuencialmente cada autorización con `ESTADO_ROBOT` vacío en `consolidado.xlsx`.

**Tecnología:** Playwright (Python) con Chromium. No requiere ChromeDriver ni actualizaciones manuales ante cambios de versión del navegador.

**Flujo de verificación por fila:**

1. Ingresa el ID del paciente en el campo de consulta.
2. Detecta popup "No se encontró el afiliado" (timeout 3000 ms) → retorna `ESTADO_PAC_NO_EXISTE`.
3. Cierra alerta "AFILIADO PAC PLAN ALFA" si aparece.
4. Valida nombre: compara los primeros 5 caracteres del nombre en la web vs. el Excel.
5. Navega a CONSULTAR DIRECCIONAMIENTO y filtra por número AUT.
6. "Truco de fechas": si no hay resultados, retrocede 6 meses en el rango de fechas y vuelve a consultar (maneja autorizaciones de final de año).
7. Extrae los códigos de la tabla con paginación (hasta 20 páginas, evaluación JS).
8. Busca `cod_fact` entre los códigos con `startsWith`.
9. Si coincide, extrae los 5 campos adicionales (paquete, cantidad, sede, convenio, vencimiento).

**Escritura en tiempo real:** Cada fila se escribe y guarda en Excel inmediatamente después de procesarla, sin esperar a que el lote completo finalice. Esto garantiza que ante una interrupción (corte de luz, cierre del programa) el progreso no se pierde.

**Reutilización de sesión:** Si el paciente siguiente tiene el mismo ID que el anterior, el robot no navega de vuelta al formulario; si cambia de paciente, navega sin cerrar el browser.

**Reintentos con reinicio de sesión:** Si una fila falla, el robot recarga la página, hace login de nuevo y reintenta (hasta `reintentos_max` veces según config).

**Estados posibles en columna G:**

| ESTADO_ROBOT | Significado |
|---|---|
| `Registro encontrado` | AUT y código verificados correctamente |
| `Examen NO se encuentra en Salud Total` | El cod_fact no coincide con ningún servicio |
| `Paciente NO existe en el sistema` | La cédula no fue encontrada |
| `Nombre del paciente NO coincide` | Los primeros 5 caracteres del nombre difieren |
| `ERROR - MAX REINTENTOS` | Fallo técnico tras todos los reintentos |

**Extracción de tabla (kendo-grid):** Usa `page.evaluate()` con JavaScript para leer directamente el DOM del componente Angular/Kendo UI, evitando selectores CSS frágiles que cambiarían si la plataforma actualiza su interfaz.

---

## 5. Configuración centralizada

### 5.1 `config.yaml`

```yaml
robot_name: "RPA IA Santa Lucía"
version: "1.0.0"
log_path: "logs/main.log"

rutas:
  pacientes: "pacientes"
  procesados: "pacientes/procesados"
  no_procesados: "pacientes/no_procesados"

archivos:
  consolidado: "pacientes/procesados/consolidado.xlsx"
  errores: "pacientes/no_procesados/errores.xlsx"

url_plataforma: "https://transaccional.saludtotal.com.co/OficinaVirtual/#/"
tipo_doc_ips: "NIT"
nit_ips: "900434332"
tipo_doc_usuario: "CEDULA DE CIUDADANIA"
id_usuario: "9004343321"

ocr:
  model: "gpt-4o"
  max_reintentos: 3

navegacion:
  headless: false          # true en producción
  slow_mo: 0
  browser: "chromium"
  sucursal: "BOLIVAR"
  sede: "LAB CLINICO SANTA LUCIA IPS SAS"

tiempos:
  timeout_general: 120
  espera_carga_pagina: 10

parametros:
  reintentos_max: 3
  guardar_cada_n_registros: 5
```

### 5.2 Variables de entorno (`.env`)

Las credenciales **nunca** se almacenan en el código ni en `config.yaml`. Se manejan exclusivamente por variables de entorno:

```
OPENAI_API_KEY=sk-...
PASSWORD_USUARIO=tu_contraseña_aqui
```

El archivo `.env` está incluido en `.gitignore` y **no se sube nunca al repositorio**.

---

## 6. Seguridad y privacidad

El sistema maneja datos médicos sensibles de pacientes. Las medidas de seguridad implementadas son:

**Credenciales:** Contraseña de la plataforma SaludTotal y API key de OpenAI se manejan exclusivamente por variables de entorno (`python-dotenv`). El archivo `.env` está en `.gitignore`.

**Datos de pacientes:** La carpeta `pacientes/` y sus subcarpetas están excluidas del repositorio Git mediante `.gitignore`. Los PDFs con información médica real nunca se suben a control de versiones.

**Sin logs de credenciales:** El logger no registra contraseñas ni API keys en ningún momento.

**Datos en tránsito:** Las imágenes de los PDFs se envían a OpenAI via HTTPS. La comunicación con la plataforma de SaludTotal también es HTTPS.

---

## 7. Stack tecnológico

| Biblioteca | Versión mínima | Uso |
|---|---|---|
| Python | 3.11+ | Lenguaje base |
| openai | ≥ 1.30 | GPT-4o Vision (OCR) |
| pymupdf | ≥ 1.24 | PDF → imagen (sin Poppler) |
| playwright | ≥ 1.40 | Automatización web RPA |
| openpyxl | ≥ 3.1 | Lectura/escritura Excel |
| pyyaml | ≥ 6.0 | Configuración YAML |
| python-dotenv | ≥ 1.0 | Variables de entorno |
| pandas | ≥ 2.0 | Manipulación de fechas (p05) |
| python-dateutil | ≥ 2.8 | Parsing de fechas |
| uv | — | Gestor de entorno virtual |

---

## 8. Instalación y despliegue

### 8.1 Requisitos previos

- Windows 10/11
- Conexión a internet (API de OpenAI + portal SaludTotal EPS)
- Clave API de OpenAI activa

> No es necesario instalar Python ni ninguna dependencia manualmente. El script `INSTALAR_LUCIA.bat` se encarga de todo.

### 8.2 Scripts de distribución

El proyecto se entrega con dos archivos `.bat` en la raíz del repositorio:

**`INSTALAR_LUCIA.bat` — Configuración inicial (ejecutar una sola vez)**

Realiza automáticamente:
1. Verifica si `uv` está instalado; si no, lo instala vía `winget`.
2. Ejecuta `uv sync` para instalar todas las dependencias Python.
3. Ejecuta `uv run playwright install chromium` para descargar el navegador.
4. Crea la estructura de carpetas: `pacientes/pendientes/`, `pacientes/procesados/`, `pacientes/no_procesados/`, `logs/`, `output/`.
5. Genera un archivo `.env` de plantilla si no existe.

**`EJECUTAR_LUCIA.bat` — Lanzador diario del robot**

Realiza automáticamente:
1. Verifica que `uv` esté disponible.
2. Verifica que el archivo `.env` con credenciales exista.
3. Lanza `uv run python main.py`.
4. Muestra mensaje de éxito o error al terminar.

### 8.3 Pasos de instalación para el usuario final

1. Descargar el código fuente desde [Releases](https://github.com/briandplata/RPA_IA_SANTA_LUCIA/releases) y extraer la carpeta.
2. Editar el archivo `.env` con las credenciales reales:
   ```
   OPENAI_API_KEY=sk-...
   WEB_USER=usuario_saludtotal
   WEB_PASSWORD=contraseña_saludtotal
   ```
3. Hacer doble clic en `INSTALAR_LUCIA.bat` (solo la primera vez).
4. Colocar los PDFs de pacientes en `pacientes/pendientes/`.
5. Hacer doble clic en `EJECUTAR_LUCIA.bat` para iniciar el robot.

### 8.4 Modo producción

Para ejecutar sin abrir ventana del navegador, cambiar en `config.yaml`:

```yaml
navegacion:
  headless: true
```

---

## 9. Convenciones de código

El proyecto sigue las siguientes convenciones para garantizar mantenibilidad:

**Interfaz uniforme de subprocesos:** Todos los módulos en `processes/` exponen exactamente una función pública `ejecutar(config, logger, datos_entrada=None)` que retorna `(bool, Any)`. Esto permite al orquestador (`main.py`) tratarlos de forma homogénea.

**Sin `print()`:** Todo output va exclusivamente al logger centralizado. Nunca se usa `print()` en producción.

**Sin lógica en `main.py`:** El orquestador solo llama subprocesos y evalúa resultados. La lógica de negocio vive en los módulos `processes/`.

**Selectores centralizados:** En `p05_navegacion_web.py` todos los selectores web se definen en el diccionario `SELECTORES` al inicio del módulo. Cambiar un selector requiere editar un solo lugar.

**Docstrings Google-style:** Todos los módulos y funciones públicas y privadas tienen docstrings con secciones `Args`, `Returns` y `Raises` en formato Google.

**Seguridad primero:** Ninguna credencial aparece en el código. Las variables sensibles se leen siempre con `os.getenv()`.

---

## 10. Mantenimiento y extensibilidad

**Cambio de modelo IA:** Para usar otro modelo de OpenAI, editar `config.yaml` → `ocr.model`. No es necesario tocar código.

**Agregar nuevos campos del formulario:** Modificar el `PROMPT_OCR` en `p02_ocr_ia.py`, la función `_validar_campos()`, las cabeceras en `p03_excel.py` y las columnas en `p05_navegacion_web.py`.

**Cambio de EPS o plataforma web:** Los selectores están centralizados en `SELECTORES` en `p05`. El login y la navegación están en funciones privadas separadas (`_login`, `_ir_a_registro_dir`, `_seleccionar_sede`) para facilitar su actualización independiente.

**Escalabilidad:** El robot procesa un PDF a la vez (no paralelo) para respetar los límites de tasa de la API de OpenAI y evitar condiciones de carrera en la escritura del Excel. Para volúmenes mayores se puede implementar procesamiento por lotes con throttling controlado.

---

## 11. Diagrama de flujo de decisiones — p05

```
Para cada fila con ESTADO_ROBOT vacío:
    │
    ├─ Ingresa cédula → CONSULTAR
    │
    ├─ ¿Popup "No se encontró el afiliado"?
    │   └─ SÍ → ESTADO = "Paciente NO existe en el sistema"
    │
    ├─ ¿Aparece alerta PAC PLAN ALFA?
    │   └─ SÍ → cerrar y continuar
    │
    ├─ ¿Nombre en web vacío?
    │   └─ SÍ → ESTADO = "Paciente NO existe en el sistema"
    │
    ├─ ¿Primeros 5 chars nombre coinciden?
    │   └─ NO → ESTADO = "Nombre del paciente NO coincide"
    │
    ├─ Consultar direccionamientos → filtrar por AUT
    │
    ├─ ¿Sin resultados?
    │   └─ SÍ → "truco fechas" -6 meses → consultar de nuevo
    │
    ├─ ¿cod_fact en tabla (con paginación)?
    │   ├─ SÍ → extraer 5 campos adicionales
    │   │       → ESTADO = "Registro encontrado"
    │   └─ NO → ESTADO = "Examen NO se encuentra en Salud Total"
    │
    └─ Escribir Excel en tiempo real → wb.save()
```

---

*Documento generado como parte del TFM — Máster en Desarrollo de Inteligencia Artificial.*
