"""
Módulo: processes.p02_ocr_ia
Descripción: Segundo subproceso del pipeline. Convierte cada PDF a imagen de alta
             resolución y llama a GPT-4o Vision (OpenAI) para extraer los 4 campos
             clave del formulario de autorización médica: id_paciente, autorizacion,
             cod_fact y nombre_paciente. Valida formato y completitud antes de
             aceptar cada resultado. Reintenta hasta 3 veces por archivo.
Autor: Brayand Javier Gomez Plata
"""

import os
import re
import base64
import json
from datetime import datetime
from typing import Any, Tuple

import fitz  # PyMuPDF
from openai import OpenAI


PROMPT_OCR = """Eres un sistema experto en extracción de datos de documentos médicos colombianos escaneados.

Del documento "Autorización de Servicios" extrae EXACTAMENTE estos 4 campos:

1. id_paciente: Número de cédula/identificación del paciente (campo "ID paciente"). Solo dígitos, sin espacios.
2. autorizacion: Número de autorización completo (campo "AUT"). Formato siempre: 5 dígitos, guión, 10 dígitos. Ejemplo: 84267-1628961143. Lee cada dígito con mucho cuidado — este campo es crítico.
3. cod_fact: Código de facturación numérico (campo "Cod fact"). Solo dígitos.
4. nombre_paciente: Nombre completo del paciente (campo "Nombre Paciente"). Tal como aparece escrito.

REGLAS ESTRICTAS:
- Lee CADA dígito del campo AUT individualmente — no adivines ni asumas.
- Si el documento está al revés, espejado o rotado, igual extrae los datos.
- Si un campo no es legible con certeza absoluta, devuelve null para ese campo.
- No completes ni inventes dígitos faltantes.
- Devuelve ÚNICAMENTE JSON válido, sin markdown, sin texto adicional.

Formato exacto:
{"id_paciente": "XXXXXXXX", "autorizacion": "84267-XXXXXXXXXX", "cod_fact": "XXXXXX", "nombre_paciente": "NOMBRE COMPLETO"}"""

# Patrón de validación del AUT: 5 dígitos - 10 dígitos
PATRON_AUT = re.compile(r"^\d{5}-\d{10}$")


def _pdf_a_imagen_base64(ruta_pdf: str, zoom: float = 3.0) -> list[str]:
    """Convierte cada página del PDF a imagen PNG codificada en base64.

    Usa PyMuPDF (fitz) con un factor de zoom 3x (216 dpi efectivos) para
    garantizar suficiente resolución al procesar manuscritos o sellos de baja
    calidad. No depende de Poppler ni de ningún binario externo.

    Args:
        ruta_pdf: Ruta al archivo PDF de entrada.
        zoom: Factor de escala aplicado al renderizar cada página.
              El valor por defecto 3.0 equivale a ~216 dpi.

    Returns:
        Lista de strings base64 (uno por página), listos para adjuntar
        en el payload de OpenAI Vision como ``data:image/png;base64,...``.
    """
    doc = fitz.open(ruta_pdf)
    imagenes_b64 = []
    matrix = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        imagenes_b64.append(b64)

    doc.close()
    return imagenes_b64


def _validar_campos(datos: dict) -> list[str]:
    """Valida presencia y formato de los campos extraídos por la IA.

    Reglas aplicadas:
    - Los 4 campos (``id_paciente``, ``autorizacion``, ``cod_fact``,
      ``nombre_paciente``) no pueden ser nulos ni vacíos.
    - ``autorizacion`` debe coincidir con ``PATRON_AUT`` (5 dígitos-10 dígitos).
    - ``id_paciente`` y ``cod_fact`` deben ser completamente numéricos.

    Args:
        datos: Diccionario retornado por ``_llamar_gpt_vision``.

    Returns:
        Lista de strings describiendo cada error encontrado.
        Lista vacía si todos los campos son válidos.
    """
    errores = []

    campos_requeridos = ["id_paciente", "autorizacion", "cod_fact", "nombre_paciente"]
    for campo in campos_requeridos:
        if not datos.get(campo):
            errores.append(f"{campo}: vacío o nulo")

    # Validar formato del AUT
    aut = datos.get("autorizacion", "") or ""
    aut_limpio = aut.replace(" ", "")
    if aut_limpio and not PATRON_AUT.match(aut_limpio):
        errores.append(
            f"autorizacion: formato inválido '{aut}' — se esperaba 84267-XXXXXXXXXX (5-10 dígitos)"
        )

    # Validar que id_paciente y cod_fact sean numéricos
    id_pac = datos.get("id_paciente", "") or ""
    if id_pac and not id_pac.replace(" ", "").isdigit():
        errores.append(f"id_paciente: contiene caracteres no numéricos '{id_pac}'")

    cod = datos.get("cod_fact", "") or ""
    if cod and not cod.replace(" ", "").isdigit():
        errores.append(f"cod_fact: contiene caracteres no numéricos '{cod}'")

    return errores


def _llamar_gpt_vision(client: OpenAI, imagenes_b64: list[str], model: str) -> dict:
    """Envía las imágenes del PDF a GPT-4o Vision y retorna el JSON extraído.

    Construye un mensaje multimodal con el prompt de instrucciones seguido de
    cada página del PDF como imagen base64 (``detail: high``). Usa
    ``temperature=0`` para reproducibilidad. Limpia markdown extra si el modelo
    envuelve el JSON en bloques de código.

    Args:
        client: Instancia autenticada de ``openai.OpenAI``.
        imagenes_b64: Lista de páginas en base64 (salida de ``_pdf_a_imagen_base64``).
        model: Nombre del modelo OpenAI a invocar, p. ej. ``"gpt-4o"``.

    Returns:
        Diccionario con las claves ``id_paciente``, ``autorizacion``,
        ``cod_fact`` y ``nombre_paciente`` (valores string o ``None``).

    Raises:
        json.JSONDecodeError: Si la respuesta no es JSON válido.
        openai.OpenAIError: Ante fallos de red o límite de tasa.
    """
    content = [{"type": "text", "text": PROMPT_OCR}]

    for b64 in imagenes_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high"
            }
        })

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=300,
        temperature=0
    )

    texto = response.choices[0].message.content.strip()

    # Limpiar markdown si la IA lo incluyó
    texto = re.sub(r"```json|```", "", texto).strip()

    datos = json.loads(texto)

    # Normalizar AUT: quitar espacios internos
    if datos.get("autorizacion"):
        datos["autorizacion"] = datos["autorizacion"].replace(" ", "")

    return datos


def ejecutar(config: dict, logger, datos_entrada: Any = None) -> Tuple[bool, Any]:
    """Ejecuta el proceso OCR sobre la lista de PDFs recibida.

    Para cada PDF: convierte a imagen, llama a GPT-4o Vision, valida los
    campos y reintenta hasta ``config["ocr"]["max_reintentos"]`` veces.
    Acumula resultados en dos listas separadas: exitosos y errores.

    Args:
        config: Configuración cargada de ``config.yaml``. Se usan las claves
                ``config["ocr"]["model"]`` y ``config["ocr"]["max_reintentos"]``.
        logger: Logger centralizado (``utils.logger.get_logger``).
        datos_entrada: Lista de rutas absolutas de PDFs (salida de p01).

    Returns:
        Tupla ``(True, resultado)`` donde ``resultado`` es un dict::

            {
                "exitosos": [
                    {
                        "fecha_hora": str,     # "29/06/2026 11:11:03 am"
                        "archivo": str,        # nombre del PDF
                        "ruta": str,           # ruta absoluta del PDF
                        "id_paciente": str,
                        "nombre_paciente": str,
                        "autorizacion": str,   # formato "84267-XXXXXXXXXX"
                        "cod_fact": str
                    }, ...
                ],
                "errores": [
                    {
                        "fecha_hora": str,
                        "archivo": str,
                        "ruta": str,
                        "motivo": "NO_LEGIBLE",
                        "detalle": str
                    }, ...
                ]
            }

        Retorna ``(False, None)`` si no se recibieron PDFs o la API key
        no está configurada.
    """
    nombre_proceso = "p02_ocr_ia"
    logger.info(">> INICIO subproceso: %s", nombre_proceso)

    pdfs: list[str] = datos_entrada or []
    if not pdfs:
        logger.error("No se recibieron PDFs para procesar")
        return False, None

    model = config["ocr"]["model"]
    max_reintentos = config["ocr"]["max_reintentos"]
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        logger.error("OPENAI_API_KEY no configurada en variables de entorno")
        return False, None

    client = OpenAI(api_key=api_key)

    total = len(pdfs)
    exitosos = []
    errores = []

    for idx, ruta_pdf in enumerate(pdfs, start=1):
        nombre_archivo = os.path.basename(ruta_pdf)
        fecha_hora = datetime.now().strftime("%d/%m/%Y %I:%M:%S %p").lower()
        logger.info("[Archivo %d/%d] Procesando: %s", idx, total, nombre_archivo)

        datos_extraidos = None
        exito = False
        ultimo_error = ""

        for intento in range(1, max_reintentos + 1):
            try:
                imagenes_b64 = _pdf_a_imagen_base64(ruta_pdf)
                datos_extraidos = _llamar_gpt_vision(client, imagenes_b64, model)

                errores_validacion = _validar_campos(datos_extraidos)
                if errores_validacion:
                    ultimo_error = " | ".join(errores_validacion)
                    raise ValueError(f"Validación fallida: {ultimo_error}")

                exito = True
                logger.info("[Archivo %d/%d] OCR exitoso — AUT=%s | ID=%s | Nombre=%s",
                            idx, total,
                            datos_extraidos["autorizacion"],
                            datos_extraidos["id_paciente"],
                            datos_extraidos["nombre_paciente"])
                break

            except Exception as e:
                ultimo_error = str(e)
                logger.warning("[Archivo %d/%d] Intento %d/%d fallido: %s",
                               idx, total, intento, max_reintentos, ultimo_error)

        if exito and datos_extraidos:
            exitosos.append({
                "fecha_hora": fecha_hora,
                "archivo": nombre_archivo,
                "ruta": ruta_pdf,
                "id_paciente": datos_extraidos["id_paciente"].replace(" ", ""),
                "nombre_paciente": datos_extraidos["nombre_paciente"],
                "autorizacion": datos_extraidos["autorizacion"],
                "cod_fact": datos_extraidos["cod_fact"].replace(" ", "")
            })
        else:
            logger.error("[Archivo %d/%d] OCR fallido tras %d intentos: %s — %s",
                         idx, total, max_reintentos, nombre_archivo, ultimo_error)
            errores.append({
                "fecha_hora": fecha_hora,
                "archivo": nombre_archivo,
                "ruta": ruta_pdf,
                "motivo": "NO_LEGIBLE",
                "detalle": ultimo_error or f"No se pudieron extraer todos los campos tras {max_reintentos} intentos"
            })

    logger.info("OCR completado — Exitosos: %d | Errores: %d", len(exitosos), len(errores))
    logger.info("<< FIN subproceso: %s — OK", nombre_proceso)
    return True, {"exitosos": exitosos, "errores": errores}
