"""
Módulo: utils.logger
Descripción: Configura y retorna el logger centralizado del robot RPA.
             Escribe simultáneamente a archivo (DEBUG) y consola (INFO).
Autor: Brayand Javier Gomez Plata
"""

import logging
import os


def get_logger(log_path: str = "logs/main.log") -> logging.Logger:
    """Inicializa y retorna el logger del robot RPA.

    Crea el directorio de logs si no existe. Configura dos handlers:
    uno para archivo (nivel DEBUG, registro completo) y uno para consola
    (nivel INFO, solo mensajes relevantes). Es idempotente: si el logger
    ya tiene handlers configurados no los duplica.

    Args:
        log_path: Ruta relativa o absoluta del archivo de log.
                  Por defecto ``logs/main.log``.

    Returns:
        Instancia de ``logging.Logger`` lista para usar.

    Example:
        >>> logger = get_logger("logs/main.log")
        >>> logger.info("Robot iniciado")
        >>> logger.error("Fallo en subproceso: %s", "p02_ocr_ia")
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    logger = logging.getLogger("RobotRPA")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger
