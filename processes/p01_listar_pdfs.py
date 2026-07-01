"""
Subproceso: p01_listar_pdfs
Descripción: Lista todos los archivos PDF en la carpeta de pacientes para procesamiento.
"""

import os
from typing import Any, Tuple


def ejecutar(config: dict, logger, datos_entrada: Any = None) -> Tuple[bool, Any]:
    nombre_proceso = "p01_listar_pdfs"
    logger.info(">> INICIO subproceso: %s", nombre_proceso)

    try:
        ruta_pacientes = config["rutas"]["pacientes"]

        if not os.path.exists(ruta_pacientes):
            logger.error("La carpeta de pacientes no existe: %s", ruta_pacientes)
            return False, None

        pdfs = [
            os.path.join(ruta_pacientes, f)
            for f in os.listdir(ruta_pacientes)
            if f.lower().endswith(".pdf")
        ]

        if not pdfs:
            logger.info("Sin archivos PDF en: %s — se procederá directo a verificación web.", ruta_pacientes)
            return True, []

        logger.info("PDFs encontrados: %d", len(pdfs))
        for pdf in pdfs:
            logger.info("  - %s", os.path.basename(pdf))

        logger.info("<< FIN subproceso: %s — OK", nombre_proceso)
        return True, pdfs

    except Exception as e:
        logger.error("<< FIN subproceso: %s — ERROR: %s", nombre_proceso, str(e))
        return False, None
