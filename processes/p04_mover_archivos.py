"""
Módulo: processes.p04_mover_archivos
Descripción: Cuarto subproceso del pipeline. Organiza los PDFs procesados
             moviéndolos desde la raíz de pacientes/ hacia las subcarpetas
             correspondientes según el resultado del OCR y la verificación
             de duplicados realizada en p03.
Autor: Brayand Javier Gomez Plata
"""

import os
import shutil
from typing import Any, Tuple


def _mover(ruta_origen: str, ruta_destino_dir: str, nombre_archivo: str, logger) -> bool:
    """Mueve un archivo a un directorio destino con protección contra sobreescritura.

    Si en el destino ya existe un archivo con el mismo nombre, agrega un
    sufijo numérico incremental (``_1``, ``_2``, ...) para preservar ambos.

    Args:
        ruta_origen: Ruta absoluta del archivo a mover.
        ruta_destino_dir: Directorio destino. Se crea si no existe.
        nombre_archivo: Nombre del archivo (sin ruta).
        logger: Instancia del logger centralizado.

    Returns:
        ``True`` si el movimiento fue exitoso.

    Raises:
        OSError: Si hay problemas de permisos o el origen no existe.
    """
    os.makedirs(ruta_destino_dir, exist_ok=True)
    destino = os.path.join(ruta_destino_dir, nombre_archivo)

    if os.path.exists(destino):
        base, ext = os.path.splitext(nombre_archivo)
        contador = 1
        while os.path.exists(destino):
            destino = os.path.join(ruta_destino_dir, f"{base}_{contador}{ext}")
            contador += 1

    shutil.move(ruta_origen, destino)
    logger.info("Movido: %s → %s", nombre_archivo, ruta_destino_dir)
    return True


def ejecutar(config: dict, logger, datos_entrada: Any = None) -> Tuple[bool, dict]:
    """Mueve los PDFs procesados a sus carpetas de destino según resultado.

    Reglas de enrutamiento:
    - PDF con OCR exitoso y sin duplicado → ``pacientes/procesados/``
    - PDF con OCR exitoso pero autorización duplicada → ``pacientes/no_procesados/``
    - PDF con fallo de OCR → ``pacientes/no_procesados/``

    Esta lógica garantiza que la carpeta raíz ``pacientes/`` quede vacía
    después de cada ejecución, lista para recibir nuevos documentos del cliente.

    Args:
        config: Diccionario de configuración. Debe contener
                ``config["rutas"]["procesados"]`` y
                ``config["rutas"]["no_procesados"]``.
        logger: Instancia del logger centralizado.
        datos_entrada: Dict con claves ``"exitosos"`` y ``"errores"``,
                       tal como lo retorna ``p03_excel.ejecutar()``.

    Returns:
        Tupla ``(True, resumen)`` donde ``resumen`` es un dict con:
        ``{"movidos_procesados": int, "movidos_no_procesados": int}``.
        Retorna ``(False, None)`` ante errores críticos.
    """
    nombre_proceso = "p04_mover_archivos"
    logger.info(">> INICIO subproceso: %s", nombre_proceso)

    if not datos_entrada:
        logger.error("No se recibieron datos para mover archivos")
        return False, None

    ruta_procesados    = config["rutas"]["procesados"]
    ruta_no_procesados = config["rutas"]["no_procesados"]

    exitosos: list[dict] = datos_entrada.get("exitosos", [])
    errores: list[dict]  = datos_entrada.get("errores", [])

    movidos_ok    = 0
    movidos_error = 0

    try:
        for item in exitosos:
            if item.get("_duplicado", False):
                _mover(item["ruta"], ruta_no_procesados, item["archivo"], logger)
                movidos_error += 1
            else:
                _mover(item["ruta"], ruta_procesados, item["archivo"], logger)
                movidos_ok += 1

        for item in errores:
            if os.path.exists(item["ruta"]):
                _mover(item["ruta"], ruta_no_procesados, item["archivo"], logger)
                movidos_error += 1

        resumen = {
            "movidos_procesados":    movidos_ok,
            "movidos_no_procesados": movidos_error
        }

        logger.info("Archivos movidos — procesados/: %d | no_procesados/: %d",
                    movidos_ok, movidos_error)
        logger.info("<< FIN subproceso: %s — OK", nombre_proceso)
        return True, resumen

    except Exception as e:
        logger.error("<< FIN subproceso: %s — ERROR: %s", nombre_proceso, str(e))
        return False, None
