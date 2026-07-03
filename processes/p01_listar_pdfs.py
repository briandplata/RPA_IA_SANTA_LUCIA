"""
Módulo: processes.p01_listar_pdfs
Descripción: Primer subproceso del pipeline. Escanea la carpeta de pacientes
             y retorna la lista de archivos PDF pendientes de procesamiento.
             Si no hay PDFs el flujo continúa directamente a la verificación web.
Autor: Brayand Javier Gomez Plata
"""

import os
from typing import Any, Tuple


def ejecutar(config: dict, logger, datos_entrada: Any = None) -> Tuple[bool, list]:
    """Lista los archivos PDF disponibles en la carpeta de pacientes.

    Escanea en el primer nivel (no recursivo) la carpeta definida en
    ``config["rutas"]["pacientes"]``. Retorna siempre ``True`` para no
    interrumpir el pipeline cuando no hay PDFs nuevos — en ese caso el
    robot procede directamente a la verificación web (p05).

    Args:
        config: Diccionario de configuración cargado desde ``config.yaml``.
                Debe contener ``config["rutas"]["pacientes"]``.
        logger: Instancia del logger centralizado (``utils.logger.get_logger``).
        datos_entrada: No utilizado en este subproceso. Existe por convención
                       de la arquitectura RPA.

    Returns:
        Tupla ``(True, lista_de_rutas)`` donde ``lista_de_rutas`` es una lista
        de strings con las rutas absolutas de los PDFs encontrados, o lista
        vacía si no hay archivos. Retorna ``(False, None)`` solo ante errores
        críticos (carpeta inaccesible, permisos, etc.).

    Raises:
        No lanza excepciones directamente; las captura y retorna ``(False, None)``.

    Example:
        >>> exito, pdfs = ejecutar(config, logger)
        >>> if pdfs:
        ...     print(f"{len(pdfs)} PDFs para procesar")
    """
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
