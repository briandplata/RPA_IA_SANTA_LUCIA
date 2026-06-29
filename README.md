# RPA IA Santa Lucía

## Descripción general

Pipeline automatizado que procesa autorizaciones médicas manuscritas de pacientes IPS Santa Lucía. Usa visión artificial (GPT-4o) para extraer datos de documentos manuscritos, los consolida en Excel y verifica la información en la plataforma web de Salud Total EPS mediante automatización web (RPA).

## Stack tecnológico

- **Python 3.11+**
- **OpenAI GPT-4o Vision** — OCR de documentos manuscritos
- **Playwright** — Automatización web (RPA)
- **openpyxl** — Generación y edición de Excel
- **pdf2image / Pillow** — Conversión de PDFs a imagen
- **PyYAML + python-dotenv** — Configuración y variables de entorno

## Instalación y ejecución

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/RPA_IA_SANTA_LUCIA.git
cd RPA_IA_SANTA_LUCIA

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
playwright install chromium

# 4. Configurar credenciales
cp .env.example .env
# Editar .env con tu contraseña y API key de OpenAI

# 5. Colocar PDFs de pacientes en la carpeta /pacientes

# 6. Ejecutar
python main.py
```

## Estructura del proyecto

```
RPA_IA_SANTA_LUCIA/
├── main.py              # Orquestador principal
├── config.yaml          # Configuración general (no sensible)
├── .env.example         # Template de variables de entorno
├── .gitignore
├── requirements.txt
├── README.md
├── modules/
│   ├── ocr.py           # Módulo IA: extracción de datos manuscritos
│   ├── excel.py         # Módulo Excel: generación y actualización
│   └── rpa.py           # Módulo RPA: automatización web SaludTotal
├── pacientes/           # Carpeta de entrada (PDFs — no incluida en repo)
├── output/              # Archivos Excel generados (no incluida en repo)
└── logs/                # Logs de ejecución (no incluida en repo)
```

## Funcionalidades principales

1. **Extracción IA**: Lee PDFs manuscritos y extrae ID paciente, autorización, código de facturación y nombre usando GPT-4o Vision.
2. **Generación Excel**: Consolida los datos extraídos en un archivo Excel estructurado.
3. **Verificación RPA**: Accede a la plataforma de Salud Total EPS, verifica existencia del paciente, validez de la autorización y coincidencia del código de facturación.
4. **Actualización Excel**: Agrega los datos obtenidos de la plataforma al Excel de trabajo.

## Despliegue

*(Por completar)*

## Slides

*(Por completar)*

## Video

*(Por completar)*
