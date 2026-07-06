# RPA IA Santa Lucía

## Descripción general

Pipeline automatizado que procesa autorizaciones médicas manuscritas de pacientes IPS Santa Lucía. El robot lee PDFs escaneados (incluyendo documentos manuscritos), usa visión artificial con GPT-4o para extraer los datos clave, los consolida en un Excel estructurado y verifica cada autorización en la plataforma web de Salud Total EPS mediante automatización web (RPA) con Playwright.

El sistema está diseñado para ejecutarse de forma continua: si hay PDFs nuevos los procesa primero, y luego siempre verifica las filas pendientes del consolidado en la web, permitiendo al cliente reprocesar registros con error simplemente borrando el estado manualmente.

## Stack tecnológico

- **Python 3.11+**
- **OpenAI GPT-4o Vision** — OCR de documentos manuscritos y escaneados
- **Playwright** — Automatización web RPA (sin ChromeDriver, sin dependencias externas)
- **PyMuPDF (fitz)** — Conversión de PDFs a imagen de alta resolución
- **openpyxl** — Generación y edición de Excel en tiempo real
- **PyYAML + python-dotenv** — Configuración centralizada y variables de entorno seguras

## Instalación y uso

El proyecto se distribuye con dos archivos `.bat` para simplificar el uso en Windows:

| Archivo | Cuándo usarlo |
|---|---|
| `INSTALAR_LUCIA.bat` | **Una sola vez** — instala `uv`, dependencias, Chromium y crea la estructura de carpetas |
| `EJECUTAR_LUCIA.bat` | **Cada vez** que se quiera correr el robot |

### Pasos

1. Descarga el código fuente desde [Releases](https://github.com/briandplata/RPA_IA_SANTA_LUCIA/releases) y extrae la carpeta.
2. Crea el archivo `.env` con tus credenciales (ver sección Seguridad).
3. Ejecuta `INSTALAR_LUCIA.bat` con doble clic (solo la primera vez).
4. Coloca los PDFs de pacientes en `pacientes/pendientes/`.
5. Ejecuta `EJECUTAR_LUCIA.bat` con doble clic.

> **Nota:** La carpeta `pacientes/` no se incluye en el repositorio por contener datos médicos reales.

## Estructura del proyecto

```
RPA_IA_SANTA_LUCIA/
├── main.py                        # Orquestador principal (solo coordina subprocesos)
├── config.yaml                    # Configuración centralizada (no sensible)
├── .env.example                   # Template de variables de entorno
├── .gitignore
├── requirements.txt
├── README.md
│
├── processes/
│   ├── p01_listar_pdfs.py         # Lista PDFs disponibles en pacientes/
│   ├── p02_ocr_ia.py              # Extracción de datos con GPT-4o Vision
│   ├── p03_excel.py               # Escribe consolidado.xlsx y errores.xlsx
│   ├── p04_mover_archivos.py      # Mueve PDFs a procesados/ o no_procesados/
│   └── p05_navegacion_web.py      # RPA: verifica autorizaciones en SaludTotal
│
├── utils/
│   └── logger.py                  # Logger unificado (archivo + consola)
│
├── pacientes/                     # ⚠️ No incluida en repo (datos reales)
│   ├── procesados/
│   │   └── consolidado.xlsx       # Registros procesados correctamente
│   └── no_procesados/
│       └── errores.xlsx           # Registros con error OCR o duplicados
│
└── logs/
    └── main.log                   # Log completo de cada ejecución
```

## Funcionalidades principales

**1. Cierre automático de Excel**
Al iniciar, el robot mata cualquier proceso `EXCEL.EXE` abierto para evitar bloqueos de archivo.

**2. Extracción IA (OCR)**
Convierte cada PDF a imagen de alta resolución (zoom 3x) y llama a GPT-4o Vision para extraer los 4 campos clave: ID paciente, número de autorización, código de facturación y nombre. Valida el formato del AUT (`84267-XXXXXXXXXX`) antes de aceptar el resultado. Si falla tras 3 intentos, el archivo va a `no_procesados/` y se registra en `errores.xlsx`.

**3. Control de duplicados**
Antes de escribir en el consolidado verifica que el número de autorización no exista ya. Los duplicados se registran en `errores.xlsx` y el PDF va a `no_procesados/`.

**4. Excel en tiempo real**
`consolidado.xlsx` tiene 12 columnas:

| Col | Campo | Descripción |
|-----|-------|-------------|
| A | Fecha_Hora | Fecha y hora de lectura del PDF |
| B | Archivo | Nombre del PDF original |
| C | ID_Paciente | Cédula extraída por IA |
| D | Nombre_Paciente | Nombre extraído por IA |
| E | Autorizacion | Número AUT extraído por IA |
| F | Cod_Fact | Código de facturación extraído por IA |
| G | ESTADO_ROBOT | Estado de verificación web (vacío = pendiente) |
| H | Paquete | Clasificación obtenida de SaludTotal |
| I | Cantidad | Cantidad de servicios en SaludTotal |
| J | Sede | Sede IPS en SaludTotal |
| K | Nombre_Convenio | Convenio en SaludTotal |
| L | Fecha_Vencimiento | Fecha de vencimiento de la autorización |

**5. Verificación RPA web**
El robot siempre verifica las filas con `ESTADO_ROBOT` vacío, sin importar si hubo PDFs nuevos. Si el cliente borra manualmente un estado de error, el robot lo reprocesa en la siguiente ejecución. Los posibles estados son:

- `Registro encontrado` — autorización y código verificados ✅
- `Examen NO se encuentra en Salud Total` — código no coincide ❌
- `Paciente NO existe en el sistema` — cédula no encontrada ❌
- `Nombre del paciente NO coincide` — validación de nombre falló ❌
- `ERROR - MAX REINTENTOS` — fallo técnico tras 3 intentos ⚠️

**6. Seguridad**
Las credenciales (contraseña web y API key de OpenAI) se manejan exclusivamente por variables de entorno (`.env`), nunca en el código ni en el repositorio.

## Usuario y contraseña de prueba

- **Plataforma:** https://transaccional.saludtotal.com.co/OficinaVirtual/#/
- **Usuario y contraseña:** disponibles en el formulario de entrega del TFM.

## Despliegue

Herramienta RPA de escritorio. No requiere servidor ni infraestructura cloud — corre localmente en la máquina del usuario con acceso a la carpeta de pacientes.

**Descarga:**
👉 https://github.com/briandplata/RPA_IA_SANTA_LUCIA/releases

**Requisitos mínimos:**
- Windows 10/11
- Conexión a internet (API OpenAI + portal SaludTotal)
- Clave API de OpenAI

`INSTALAR_LUCIA.bat` se encarga automáticamente de instalar `uv`, las dependencias Python y el navegador Chromium.

## Slides

La presentación del proyecto se encuentra en:

📁 [`Documentacion/LUC-IA-PRESENTACION MASTER.pptx`](Documentacion/LUC-IA-PRESENTACION%20MASTER.pptx)

## Video

Demo completa del robot en funcionamiento:

▶️ [https://www.youtube.com/watch?v=cfsQEmF1t2w](https://www.youtube.com/watch?v=cfsQEmF1t2w)
