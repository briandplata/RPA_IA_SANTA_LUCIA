"""
Subproceso: p04_mover_archivos
Descripción: Mueve cada PDF desde pacientes/ hacia procesados/ (si fue exitoso)
             o no_procesados/ (si falló o es duplicado).
"""

import os
import shutil
from typing import Any, Tuple


def _mover(ruta_origen: str, ruta_destino_dir: str, nombre_archivo: str, logger) -> bool:
    """Mueve un archivo al directorio destino, evitando sobreescritura con sufijo numérico."""
    os.makedirs(ruta_destino_dir, exist_ok=True)
    destino = os.path.join(ruta_destino_dir, nombre_archivo)

    # Si ya existe un archivo con el mismo nombre, agregar sufijo
    if os.path.exists(destino):
        base, ext = os.path.splitext(nombre_archivo)
        contador = 1
        while os.path.exists(destino):
            destino = os.path.join(ruta_destino_dir, f"{base}_{contador}{ext}")
            contador += 1

    shutil.move(ruta_origen, destino)
    logger.info("Movido: %s → %s", nombre_archivo, ruta_destino_dir)
    return True


def ejecutar(config: dict, logger, datos_entrada: Any = None) -> Tuple[bool, Any]:
    nombre_proceso = "p04_mover_archivos"
    logger.info(">> INICIO subproceso: %s", nombre_proceso)

    if not datos_entrada:
        logger.error("No se recibieron datos para mover archivos")
        return False, None

    ruta_procesados = config["rutas"]["procesados"]
    ruta_no_procesados = config["rutas"]["no_procesados"]

    exitosos: list[dict] = datos_entrada.get("exitosos", [])
    errores: list[dict] = datos_entrada.get("errores", [])

    movidos_ok = 0
    movidos_error = 0

    try:
        # Archivos exitosos sin duplicado → procesados/
        for item in exitosos:
            if item.get("_duplicado", False):
                _mover(item["ruta"], ruta_no_procesados, item["archivo"], logger)
                movidos_error += 1
            else:
                _mover(item["ruta"], ruta_procesados, item["archivo"], logger)
                movidos_ok += 1

        # Archivos con error OCR → no_procesados/
        for item in errores:
            if os.path.exists(item["ruta"]):
                _mover(item["ruta"], ruta_no_procesados, item["archivo"], logger)
                movidos_error += 1

        resumen = {
            "movidos_procesados": movidos_ok,
            "movidos_no_procesados": movidos_error
        }

        logger.info("Archivos movidos — procesados/: %d | no_procesados/: %d",
                    movidos_ok, movidos_error)
        logger.info("<< FIN subproceso: %s — OK", nombre_proceso)
        return True, resumen

    except Exception as e:
        logger.error("<< FIN subproceso: %s — ERROR: %s", nombre_proceso, str(e))
        return False, None
