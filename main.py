"""
Robot: RPA IA Santa Lucía
Descripción: Pipeline automatizado que lee autorizaciones médicas manuscritas en PDF,
             extrae datos con IA (GPT-4o Vision), los consolida en Excel y verifica
             la información en la plataforma web de Salud Total EPS.
Autor: Brayand javier gomez plata- estudiante master de desarrollo IA
Fecha: 2026-06-29
"""

import sys
import subprocess
import yaml
from dotenv import load_dotenv

from utils.logger import get_logger
from processes.p01_listar_pdfs import ejecutar as listar_pdfs
from processes.p02_ocr_ia import ejecutar as ocr_ia
from processes.p03_excel import ejecutar as actualizar_excel
from processes.p04_mover_archivos import ejecutar as mover_archivos
from processes.p05_navegacion_web import ejecutar as navegar_web


def cerrar_excel() -> None:
    """Cierra todos los procesos de Excel abiertos para evitar bloqueos de archivo."""
    resultado = subprocess.run(
        ["taskkill", "/F", "/IM", "EXCEL.EXE"],
        capture_output=True, text=True
    )
    # No lanzar error si no había Excel abierto


def cargar_config(ruta: str = "config.yaml") -> dict:
    """Carga y retorna el archivo de configuración YAML del robot.

    Args:
        ruta: Ruta al archivo ``config.yaml``. Por defecto busca en el
              directorio de trabajo actual.

    Returns:
        Diccionario con toda la configuración del robot.

    Raises:
        FileNotFoundError: Si el archivo no existe en la ruta indicada.
        yaml.YAMLError: Si el archivo no es YAML válido.
    """
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    """Orquesta la ejecución secuencial de los cinco subprocesos del pipeline.

    Flujo:
    1. Cierra procesos ``EXCEL.EXE`` abiertos para evitar bloqueos de archivo.
    2. Carga variables de entorno (``.env``) y configuración (``config.yaml``).
    3. **p01** — Lista PDFs en ``pacientes/``.
    4. **p02-p04** — Solo si hay PDFs nuevos: OCR con IA, escritura en Excel
       y movimiento de archivos a sus carpetas de destino.
    5. **p05** — Siempre: verifica autorizaciones pendientes en SaludTotal web.

    Si cualquier subproceso retorna ``(False, ...)`` el robot se detiene
    con ``sys.exit(1)`` y registra el punto de fallo en el log.

    Note:
        - Las credenciales se cargan exclusivamente desde ``.env``;
          nunca se pasan por argumentos ni se hardcodean en el código.
        - p05 se ejecuta aunque p01 retorne lista vacía, permitiendo
          reprocesar filas si el cliente borra manualmente el ESTADO_ROBOT.
    """
    cerrar_excel()
    load_dotenv()
    config = cargar_config()
    logger = get_logger(config.get("log_path", "logs/main.log"))
    logger.info("Procesos de Excel cerrados.")

    logger.info("=" * 60)
    logger.info("INICIO DEL ROBOT: %s", config.get("robot_name", "SIN NOMBRE"))
    logger.info("Versión: %s", config.get("version", "N/A"))
    logger.info("=" * 60)

    # --- Subproceso 1: Listar PDFs ---
    exito, pdfs = listar_pdfs(config, logger)
    if not exito:
        logger.error("FLUJO DETENIDO en: p01_listar_pdfs")
        sys.exit(1)

    # --- Subprocesos 2-4: Solo si hay PDFs nuevos ---
    if pdfs:
        logger.info("PDFs nuevos detectados: %d — iniciando proceso OCR", len(pdfs))

        exito, resultados = ocr_ia(config, logger, pdfs)
        if not exito:
            logger.error("FLUJO DETENIDO en: p02_ocr_ia")
            sys.exit(1)

        exito, resultados = actualizar_excel(config, logger, resultados)
        if not exito:
            logger.error("FLUJO DETENIDO en: p03_excel")
            sys.exit(1)

        exito, resumen_mov = mover_archivos(config, logger, resultados)
        if not exito:
            logger.error("FLUJO DETENIDO en: p04_mover_archivos")
            sys.exit(1)

        logger.info("PDFs procesados — OK: %d | Errores: %d",
                    resumen_mov.get("movidos_procesados", 0),
                    resumen_mov.get("movidos_no_procesados", 0))
    else:
        logger.info("Sin PDFs nuevos — pasando directo a verificación web.")

    # --- Subproceso 5: Verificación web (siempre se ejecuta) ---
    exito, resumen_web = navegar_web(config, logger)
    if not exito:
        logger.error("FLUJO DETENIDO en: p05_navegacion_web")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("ROBOT FINALIZADO EXITOSAMENTE")
    logger.info("Filas verificadas en web: %d", resumen_web.get("verificados", 0))
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
