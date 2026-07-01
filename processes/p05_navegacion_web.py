"""
Subproceso: p05_navegacion_web
Descripción: Lee consolidado.xlsx fila por fila, verifica en la plataforma web de
             Salud Total EPS cada autorización con ESTADO_ROBOT vacío y registra
             el resultado en la columna G del Excel en tiempo real.
             Si el cliente borra manualmente el estado, el robot lo reprocesa.
"""

import os
import re
from typing import Any, Tuple

import openpyxl
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# ─── Selectores centralizados (REGLA 7) ───────────────────────────────────────
SELECTORES = {
    "tab_ips":                  'IPS',
    "tipo_doc_ips":             "TIPO DE DOCUMENTO DE LA IPS",
    "nit_ips":                  "NÚMERO DE IDENTIFICACIÓN DE",
    "tipo_doc_usuario":         "TIPO DE DOCUMENTO DEL USUARIO",
    "id_usuario":               "NÚMERO DEL USUARIO",
    "password":                 "CONTRASEÑA",
    "btn_ingresar":             "INGRESAR",
    "btn_direccionamientos":    "DIRECCIONAMIENTOS",
    "registrar_direccionamiento": "REGISTRAR DIRECCIONAMIENTO",
    "ventana_sede":             "DATOS SEDESUCURSAL SEDE",
    "combobox_sucursal":        "SELECCIONE UNA SUCURSAL",
    "combobox_sede":            "SELECCIONE UNA SEDE",
    "btn_aceptar":              "ACEPTAR",
    "campo_id_paciente":        "DIGITE NÚMERO DE IDENTIFICACI",
    "btn_consultar":            "CONSULTAR",
    "campo_nombre":             "DIGITE NOMBRE DEL PROTEGIDO",
    "consultar_dir":            "CONSULTAR DIRECCIONAMIENTO",
    "filtro_aut":               "DIRECCIONAMIENTO Filter",
}

# ─── Estados del robot ────────────────────────────────────────────────────────
ESTADO_ENCONTRADO    = "Registro encontrado"
ESTADO_NO_ENCONTRADO = "Examen NO se encuentra en Salud Total"
ESTADO_PAC_NO_EXISTE = "Paciente NO existe en el sistema"
ESTADO_NOMBRE_NO_OK  = "Nombre del paciente NO coincide"
ESTADO_ERROR         = "ERROR - MAX REINTENTOS"

# Columnas en consolidado.xlsx (1-based para openpyxl)
COL_ID_PACIENTE   = 3   # C
COL_NOMBRE        = 4   # D
COL_AUTORIZACION  = 5   # E
COL_COD_FACT      = 6   # F
COL_ESTADO_ROBOT  = 7   # G


# ─── Helpers de navegación ────────────────────────────────────────────────────

def _seleccionar_combobox(page, nombre: str, opcion: str, contenedor=None) -> None:
    """Selecciona una opción en un combobox de la plataforma SaludTotal."""
    base = contenedor if contenedor else page
    cb = base.get_by_role("combobox", name=nombre)
    cb.wait_for(state="visible")
    cb.click()
    cb.fill("")
    cb.type(opcion, delay=30)

    opcion_lista = page.get_by_role("option", name=opcion, exact=True).first
    try:
        opcion_lista.wait_for(state="visible", timeout=2500)
        opcion_lista.click()
    except PlaywrightTimeout:
        cb.press("ArrowDown")
        cb.press("Enter")

    valor = cb.input_value().strip().upper()
    if opcion.strip().upper() not in valor:
        raise RuntimeError(
            f"No se pudo seleccionar '{opcion}' en '{nombre}'. Valor actual: '{valor}'"
        )


def _login(page, config: dict) -> None:
    """Realiza el login en la plataforma SaludTota"""
    password = os.getenv("PASSWORD_USUARIO", "")
    tiempos = config.get("tiempos", {})

    page.goto(config["url_plataforma"])
    page.wait_for_load_state("networkidle")

    page.get_by_role("tab", name=SELECTORES["tab_ips"]).locator("span").click()

    _seleccionar_combobox(page, SELECTORES["tipo_doc_ips"], config["tipo_doc_ips"])
    page.get_by_role("textbox", name=SELECTORES["nit_ips"]).fill(config["nit_ips"])

    _seleccionar_combobox(page, SELECTORES["tipo_doc_usuario"], config["tipo_doc_usuario"])
    page.get_by_role("textbox", name=SELECTORES["id_usuario"]).fill(config["id_usuario"])

    page.get_by_role("textbox", name=SELECTORES["password"]).fill(password)
    page.get_by_role("button", name=SELECTORES["btn_ingresar"]).click()
    page.wait_for_load_state("networkidle")


def _ir_a_registro_dir(page) -> None:
    """Navega al módulo de Registro de Direccionamiento."""
    page.get_by_role("button", name=SELECTORES["btn_direccionamientos"], exact=True).click()
    el = page.get_by_text(SELECTORES["registrar_direccionamiento"])
    el.wait_for(state="visible")
    el.click()
    page.wait_for_load_state("networkidle")


def _seleccionar_sede(page, config: dict) -> None:
    """Selecciona sucursal y sede en el modal inicial."""
    sucursal = config["navegacion"]["sucursal"]
    sede = config["navegacion"]["sede"]

    ventana = page.locator("kendo-window div").filter(has_text=SELECTORES["ventana_sede"])
    ventana.wait_for(state="visible")

    _seleccionar_combobox(page, SELECTORES["combobox_sucursal"], sucursal, contenedor=ventana)
    _seleccionar_combobox(page, SELECTORES["combobox_sede"], sede, contenedor=ventana)
    page.get_by_role("button", name=SELECTORES["btn_aceptar"]).click()


def _obtener_codigos_web(page) -> list[str]:
    """Extrae todos los códigos de servicio de la tabla kendo-grid (con paginación)."""
    codigos = []
    limite_paginas = 0

    while limite_paginas < 20:
        codigos_pagina = page.evaluate('''() => {
            const ths = Array.from(document.querySelectorAll('kendo-grid th'));
            const colIndex = ths.findIndex(th => th.innerText.includes('CÓDIGO SERVICIO'));
            if (colIndex === -1) return [];
            const trs = Array.from(document.querySelectorAll(
                'kendo-grid-list table tbody tr:not(.k-grid-norecords)'
            ));
            return trs.map(tr => {
                const tds = tr.querySelectorAll('td');
                return tds[colIndex] ? tds[colIndex].textContent.trim() : '';
            }).filter(c => c !== '');
        }''')

        codigos.extend(codigos_pagina)

        avanzo = page.evaluate('''() => {
            const pager = document.querySelector(
                "#k-tabstrip-tabpanel-1 > form > div.row.ng-star-inserted > kendo-grid > kendo-pager"
            ) || document;
            const nextGroup = pager.querySelector('kendo-pager-next-buttons');
            const nextBtn = nextGroup
                ? nextGroup.querySelector('button')
                : pager.querySelector('button[title*="next" i], .k-pager-nav:not(.k-pager-last)');
            if (nextBtn && !nextBtn.disabled && !nextBtn.classList.contains('k-disabled')) {
                nextBtn.click();
                return true;
            }
            return false;
        }''')

        if avanzo:
            page.wait_for_timeout(2000)
            limite_paginas += 1
        else:
            break

    return list(set(codigos))


def _procesar_fila(page, fila: dict, config: dict, logger, idx: int, total: int) -> str:
    """
    Consulta un paciente en la web y retorna el estado a registrar.
    Retorna el texto del estado (ESTADO_*).
    """
    id_pac  = str(fila["id_paciente"]).strip()
    nombre  = str(fila["nombre_paciente"]).strip().upper()
    aut     = str(fila["autorizacion"]).strip()
    cod     = str(fila["cod_fact"]).strip()
    tiempos = config.get("tiempos", {})

    logger.info("[Fila %d/%d] Consultando paciente ID=%s | AUT=%s", idx, total, id_pac, aut)

    # Ingresar cédula y consultar
    page.get_by_role("textbox", name=SELECTORES["campo_id_paciente"]).fill(id_pac)
    page.get_by_role("button", name=SELECTORES["btn_consultar"]).first.click()

    # Manejar popup "No se encontró el afiliado"
    try:
        dialogo_no_afiliado = page.locator("kendo-dialog").filter(
            has_text=re.compile(r"No se encontró el afiliado", re.IGNORECASE)
        )
        dialogo_no_afiliado.wait_for(state="visible", timeout=3000)
        dialogo_no_afiliado.get_by_role("button", name="Aceptar").click()
        logger.warning("[Fila %d/%d] Afiliado no encontrado en sistema: ID=%s", idx, total, id_pac)
        return ESTADO_PAC_NO_EXISTE
    except PlaywrightTimeout:
        pass  # No apareció el popup → el afiliado existe, continuar

    # Manejar alerta PAC PLAN ALFA si aparece
    try:
        dialogo = page.locator("app-info-afiliado app-ventana kendo-dialog").filter(
            has_text=re.compile(r"AFILIADO PAC PLAN ALFA", re.IGNORECASE)
        )
        dialogo.wait_for(state="visible", timeout=2500)
        dialogo.locator("kendo-dialog-actions button").click()
    except PlaywrightTimeout:
        pass

    page.wait_for_timeout(1500)

    # Validar nombre (primeros 5 caracteres)
    nombre_web = page.get_by_role(
        "textbox", name=SELECTORES["campo_nombre"]
    ).input_value().strip().upper()

    if not nombre_web:
        logger.warning("[Fila %d/%d] Paciente no encontrado: ID=%s", idx, total, id_pac)
        return ESTADO_PAC_NO_EXISTE

    if nombre_web[:5] != nombre[:5]:
        logger.warning("[Fila %d/%d] Nombre no coincide. Web='%s' | Excel='%s'",
                       idx, total, nombre_web, nombre)
        return ESTADO_NOMBRE_NO_OK

    # Consultar direccionamientos
    page.get_by_text(SELECTORES["consultar_dir"]).click()
    page.get_by_role("button", name=SELECTORES["btn_consultar"]).last.click()

    # Truco de fechas si no hay resultados
    try:
        alerta = page.locator("div").filter(
            has_text=re.compile(r"^No se encontraron coincidencias en la consulta$")
        )
        alerta.wait_for(state="visible", timeout=3000)
        page.get_by_role("button", name="Aceptar").click()

        import pandas as pd
        fecha1 = page.get_by_role("spinbutton", name="null").first
        fecha2 = page.get_by_role("spinbutton", name="null").nth(1)
        v1, v2 = fecha1.input_value(), fecha2.input_value()

        if v1 and v2:
            d1 = pd.to_datetime(v1, dayfirst=True) - pd.DateOffset(months=6)
            d2 = pd.to_datetime(v2, dayfirst=True) - pd.DateOffset(months=6)

            for campo, valor in [(fecha1, d1), (fecha2, d2)]:
                campo.click()
                page.keyboard.press("Control+a")
                page.keyboard.press("Backspace")
                campo.type(valor.strftime("%d/%m/%Y"), delay=50)

            page.keyboard.press("Enter")
            page.get_by_role("button", name=SELECTORES["btn_consultar"]).last.click()

            try:
                page.locator("kendo-grid .k-loading-mask").wait_for(state="visible", timeout=1000)
            except PlaywrightTimeout:
                pass
            try:
                page.locator("kendo-grid .k-loading-mask").wait_for(state="hidden", timeout=8000)
            except PlaywrightTimeout:
                pass
            page.wait_for_timeout(1000)

    except PlaywrightTimeout:
        pass  # Resultados encontrados sin necesidad del truco de fechas

    # Filtrar por autorización
    filtro = page.get_by_role("textbox", name=SELECTORES["filtro_aut"], exact=True)
    filtro.wait_for(state="visible")
    filtro.click()
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(2500)
    filtro.fill(aut)
    page.wait_for_timeout(3500)

    # Extraer códigos de la tabla
    codigos_web = _obtener_codigos_web(page)
    logger.info("[Fila %d/%d] Códigos en web para AUT=%s: %s", idx, total, aut, codigos_web)

    # Validar si cod_fact está en los resultados
    if any(str(cw).startswith(cod) for cw in codigos_web):
        logger.info("[Fila %d/%d] ENCONTRADO: cod_fact=%s en AUT=%s", idx, total, cod, aut)
        return ESTADO_ENCONTRADO
    else:
        logger.warning("[Fila %d/%d] NO ENCONTRADO: cod_fact=%s en AUT=%s", idx, total, cod, aut)
        return ESTADO_NO_ENCONTRADO


def ejecutar(config: dict, logger, datos_entrada: Any = None) -> Tuple[bool, Any]:
    nombre_proceso = "p05_navegacion_web"
    logger.info(">> INICIO subproceso: %s", nombre_proceso)

    ruta_consolidado = config["archivos"]["consolidado"]
    reintentos_max   = config["parametros"]["reintentos_max"]
    guardar_cada     = config["parametros"]["guardar_cada_n_registros"]
    tiempos          = config.get("tiempos", {})

    if not os.path.exists(ruta_consolidado):
        logger.info("consolidado.xlsx no existe aún. No hay filas que verificar.")
        logger.info("<< FIN subproceso: %s — OK (sin datos)", nombre_proceso)
        return True, {"verificados": 0, "pendientes": 0}

    # Cargar Excel y detectar filas pendientes (ESTADO_ROBOT vacío)
    wb = openpyxl.load_workbook(ruta_consolidado)
    ws = wb.active

    filas_pendientes = []
    for row_idx in range(2, ws.max_row + 1):
        estado = ws.cell(row=row_idx, column=COL_ESTADO_ROBOT).value
        if not estado or str(estado).strip() == "":
            filas_pendientes.append({
                "row_idx":        row_idx,
                "id_paciente":    str(ws.cell(row=row_idx, column=COL_ID_PACIENTE).value or "").strip(),
                "nombre_paciente":str(ws.cell(row=row_idx, column=COL_NOMBRE).value or "").strip(),
                "autorizacion":   str(ws.cell(row=row_idx, column=COL_AUTORIZACION).value or "").strip(),
                "cod_fact":       str(ws.cell(row=row_idx, column=COL_COD_FACT).value or "").strip(),
            })

    if not filas_pendientes:
        logger.info("No hay filas pendientes de verificar en consolidado.xlsx")
        logger.info("<< FIN subproceso: %s — OK", nombre_proceso)
        return True, {"verificados": 0, "pendientes": 0}

    total = len(filas_pendientes)
    logger.info("Filas pendientes de verificación web: %d", total)

    pw = None
    browser = None

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=config["navegacion"]["headless"],
            slow_mo=config["navegacion"]["slow_mo"],
            args=["--start-maximized"]
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()
        page.set_default_timeout(tiempos.get("timeout_general", 120) * 1000)

        logger.info("Iniciando login en SaludTotal...")
        _login(page, config)
        logger.info("Login exitoso.")

        logger.info("Navegando a REGISTRAR DIRECCIONAMIENTO...")
        _ir_a_registro_dir(page)
        _seleccionar_sede(page, config)
        logger.info("Sede configurada: %s", config["navegacion"]["sede"])

        verificados = 0
        paciente_actual = None

        for contador, fila in enumerate(filas_pendientes, start=1):
            estado_resultado = ESTADO_ERROR
            id_pac = fila["id_paciente"]

            for intento in range(1, reintentos_max + 1):
                try:
                    # Si cambia el paciente, navegar de vuelta al formulario
                    if paciente_actual is not None and id_pac != paciente_actual:
                        logger.info("[Fila %d/%d] Nuevo paciente — volviendo al formulario",
                                    contador, total)
                        el = page.get_by_text(SELECTORES["registrar_direccionamiento"])
                        el.wait_for(state="visible")
                        el.click()
                        page.wait_for_load_state("networkidle")

                    estado_resultado = _procesar_fila(page, fila, config, logger, contador, total)
                    paciente_actual = id_pac
                    break

                except Exception as e:
                    logger.warning("[Fila %d/%d] Intento %d/%d fallido: %s",
                                   contador, total, intento, reintentos_max, str(e))
                    if intento < reintentos_max:
                        # Reiniciar sesión web
                        try:
                            logger.info("Reiniciando sesión web...")
                            page.reload()
                            page.wait_for_load_state("networkidle")
                            _login(page, config)
                            _ir_a_registro_dir(page)
                            _seleccionar_sede(page, config)
                            paciente_actual = None
                        except Exception as restart_err:
                            logger.error("Error al reiniciar sesión: %s", str(restart_err))

            # Escribir estado en Excel en tiempo real
            ws.cell(row=fila["row_idx"], column=COL_ESTADO_ROBOT, value=estado_resultado)
            wb.save(ruta_consolidado)
            verificados += 1
            logger.info("[Fila %d/%d] ESTADO_ROBOT: %s", contador, total, estado_resultado)

            if contador % guardar_cada == 0:
                logger.info("Guardado parcial en fila %d/%d", contador, total)

        logger.info("Verificación web completada — %d/%d filas procesadas", verificados, total)
        logger.info("<< FIN subproceso: %s — OK", nombre_proceso)
        return True, {"verificados": verificados, "pendientes": total - verificados}

    except Exception as e:
        logger.error("<< FIN subproceso: %s — ERROR: %s", nombre_proceso, str(e))
        return False, None

    finally:
        if browser:
            browser.close()
        if pw:
            pw.stop()
