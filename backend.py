"""Todo lo que sale a la red: el backend propio (MySQL) y API Gateway (catálogo).

Las funciones de lectura nunca lanzan: devuelven (datos, error) y la pantalla
muestra el error. Las escrituras pasan por proxy_backend y responden JSON.
"""
import logging

import requests
from flask import Response, jsonify

import config

log = logging.getLogger("sifat-front")


# =============================================================================
# Backend propio (SIFAT-BACKEND)
# =============================================================================
def _cabeceras_backend():
    return {"X-API-Key": config.BACKEND_API_KEY}


def _falta_backend():
    return not config.BACKEND_URL or not config.BACKEND_API_KEY


FALTA_BACKEND = "Falta configurar BACKEND_URL o BACKEND_API_KEY en el archivo .env."


def consultar_backend(ruta, llave, **filtros):
    """Devuelve (lista, error). llave=None devuelve el JSON completo."""
    if _falta_backend():
        return [], FALTA_BACKEND
    try:
        r = requests.get(f"{config.BACKEND_URL}{ruta}", params={"limite": MAXIMO_BACKEND, **filtros},
                         headers=_cabeceras_backend(), timeout=config.TIMEOUT)
    except requests.RequestException as exc:
        return [], f"No se pudo contactar al backend en {config.BACKEND_URL} ({exc.__class__.__name__}). ¿Está encendido?"
    if r.status_code == 401:
        return [], "El backend rechazó la clave: revisa que BACKEND_API_KEY sea igual en ambos .env."
    if r.status_code != 200:
        return [], f"El backend respondió {r.status_code}."
    try:
        datos = r.json()
        return (datos if llave is None else datos.get(llave, [])), None
    except ValueError:
        return [], "El backend devolvió una respuesta inválida."


POR_PAGINA = 50
MAXIMO_BACKEND = 200  # el backend no entrega más de 200 por petición
TOPE_TODO = 5000      # tope de seguridad al pedir una lista completa


def consultar_pagina(ruta, llave, pagina=1, por_pagina=POR_PAGINA, **filtros):
    """Devuelve (filas, hay_mas, error). Pide una fila de más para saber si hay otra página."""
    datos, error = consultar_backend(ruta, llave, limite=por_pagina + 1,
                                     desde=(pagina - 1) * por_pagina, **filtros)
    return datos[:por_pagina], len(datos) > por_pagina, error


def consultar_todo(ruta, llave, **filtros):
    """Devuelve (lista completa, error) recorriendo todas las páginas del backend."""
    todo, desde = [], 0
    while desde < TOPE_TODO:
        datos, error = consultar_backend(ruta, llave, limite=MAXIMO_BACKEND, desde=desde, **filtros)
        if error:
            return todo, error
        todo.extend(datos)
        if len(datos) < MAXIMO_BACKEND:
            break
        desde += MAXIMO_BACKEND
    return todo, None


CATALOGOS_VACIOS = {"regimenes": [], "usos-cfdi": [], "formas-pago": [], "metodos-pago": []}


def catalogos_sat():
    """Devuelve (catálogos, error): regímenes, usos de CFDI, formas y métodos de pago."""
    datos, error = consultar_backend("/catalogos", None)
    if error or not isinstance(datos, dict):
        return dict(CATALOGOS_VACIOS), error or "El backend devolvió catálogos inválidos."
    return {k: datos.get(k, []) for k in CATALOGOS_VACIOS}, None


def autenticar(email, password):
    """Devuelve (usuario, error)."""
    if _falta_backend():
        return None, FALTA_BACKEND
    try:
        r = requests.post(f"{config.BACKEND_URL}/auth/login", json={"email": email, "password": password},
                          headers=_cabeceras_backend(), timeout=config.TIMEOUT)
    except requests.RequestException:
        return None, "No se pudo contactar al servidor. Intenta más tarde."
    if r.status_code == 200:
        return r.json(), None
    if r.status_code in (401, 423):
        return None, r.json().get("mensaje", "Correo o contraseña incorrectos")
    if r.status_code == 400:
        return None, "Correo o contraseña incorrectos"
    return None, "No se pudo iniciar sesión. Intenta más tarde."


def estado_usuario(id_usuario):
    """Devuelve (datos, estado) con estado 'ok', 'inexistente' o 'sin_respuesta'."""
    if _falta_backend():
        return None, "sin_respuesta"
    try:
        r = requests.get(f"{config.BACKEND_URL}/usuarios/{int(id_usuario)}",
                         headers=_cabeceras_backend(), timeout=config.TIMEOUT)
    except requests.RequestException:
        return None, "sin_respuesta"
    if r.status_code == 404:
        return None, "inexistente"
    if r.status_code != 200:
        return None, "sin_respuesta"
    try:
        return r.json(), "ok"
    except ValueError:
        return None, "sin_respuesta"


# Nombres legibles para los errores de validación que devuelve el backend
ETIQUETAS = {
    "rfc": "RFC", "razon_social": "razón social", "cp_fiscal": "C.P. fiscal",
    "clave_regimen": "régimen fiscal", "clave_uso": "uso de CFDI", "email": "correo",
    "telefono": "teléfono", "activo": "estado", "id_cliente": "cliente",
    "clave_forma_pago": "forma de pago", "clave_metodo_pago": "método de pago",
    "conceptos": "conceptos", "id_servicio": "servicio", "cantidad": "cantidad",
    "motivo": "motivo", "folio": "factura", "monto": "monto", "referencia": "referencia",
    "nombre": "nombre", "apellidos": "apellidos", "password": "contraseña", "rol": "rol",
    "actual": "contraseña actual", "nueva": "contraseña nueva",
}


def _mensaje_validacion(datos):
    """Convierte la lista de errores de Pydantic del backend en una frase en español."""
    campos = []
    for e in datos.get("errores", []):
        partes = [p for p in str(e.get("campo", "")).split(".") if p and not p.isdigit()]
        etiqueta = ETIQUETAS.get(partes[-1] if partes else "", "un campo")
        if etiqueta not in campos:
            campos.append(etiqueta)
    return f"Revisa estos datos: {', '.join(campos)}" if campos else "Datos inválidos"


def proxy_backend(metodo, ruta, cuerpo=None):
    """Reenvía una petición al backend y devuelve su respuesta JSON al navegador."""
    if _falta_backend():
        return jsonify({"mensaje": FALTA_BACKEND}), 500
    try:
        # Emitir una factura consulta cada servicio en DynamoDB: se da más tiempo
        r = requests.request(metodo, f"{config.BACKEND_URL}{ruta}", json=cuerpo,
                             headers=_cabeceras_backend(), timeout=config.TIMEOUT * 2)
    except requests.RequestException as exc:
        log.warning("Backend no disponible: %s", exc.__class__.__name__)
        return jsonify({"mensaje": "No se pudo contactar al servidor. Intenta más tarde."}), 502
    if r.status_code == 401:
        # Es un problema de configuración del servidor, no de la sesión del usuario
        log.error("El backend rechazó BACKEND_API_KEY")
        return jsonify({"mensaje": "El servidor no está bien configurado. Avisa al administrador."}), 502
    try:
        datos = r.json()
    except ValueError:
        return jsonify({"mensaje": "El servidor devolvió una respuesta inválida."}), 502
    if r.status_code == 400 and isinstance(datos, dict) and "errores" in datos:
        return jsonify({"mensaje": _mensaje_validacion(datos)}), 400
    if r.status_code >= 500:
        detalle = f" (código {datos['error_id']})" if isinstance(datos, dict) and datos.get("error_id") else ""
        return jsonify({"mensaje": f"Ocurrió un error en el servidor{detalle}. Intenta de nuevo."}), 502
    return jsonify(datos), r.status_code


# =============================================================================
# Catálogo de servicios (API Gateway + Lambda + DynamoDB)
# =============================================================================
LIMITE_PAGINA = 50  # máximo que acepta la Lambda por página
MAX_PAGINAS = 20  # tope de seguridad: hasta 1000 servicios por carga

# Mensajes para los errores que genera API Gateway (no las Lambdas)
ERRORES_GATEWAY = {
    403: "API Gateway rechazó la petición: falta la clave de acceso o no es válida (revisa API_KEY).",
    429: "Se superó el límite de peticiones. Espera unos segundos e inténtalo de nuevo.",
}
FALTA_GATEWAY = "Falta configurar API_KEY o API_BASE_URL en el archivo .env."


def _cabeceras_gateway():
    return {"x-api-key": config.API_KEY}


def listar_servicios():
    """Devuelve (servicios, error).

    La Lambda responde por páginas; aquí se recorren todas (con un tope) e
    incluye los servicios dados de baja para mostrarlos como inactivos.
    """
    if not config.API_KEY or not config.API_BASE_URL:
        return [], FALTA_GATEWAY
    items, siguiente = [], None
    try:
        for _ in range(MAX_PAGINAS):
            params = {"limite": LIMITE_PAGINA, "incluir_inactivos": "true"}
            if siguiente:
                params["siguiente"] = siguiente
            r = requests.get(f"{config.API_BASE_URL}/servicios", params=params,
                             headers=_cabeceras_gateway(), timeout=config.TIMEOUT)
            if r.status_code in ERRORES_GATEWAY:
                return [], ERRORES_GATEWAY[r.status_code]
            r.raise_for_status()
            data = r.json()
            items.extend(data.get("servicios", []))
            siguiente = data.get("siguiente")
            if not siguiente:
                break
    except (requests.RequestException, ValueError) as exc:
        return [], f"No se pudo consultar API Gateway ({exc.__class__.__name__})."
    items.sort(key=lambda s: s.get("id_servicio", ""))
    return items, None


def proxy_gateway(metodo, params, cuerpo):
    """Reenvía un alta, cambio o baja de servicio a API Gateway."""
    if not config.API_KEY or not config.API_BASE_URL:
        return jsonify({"mensaje": FALTA_GATEWAY}), 500
    try:
        r = requests.request(metodo, f"{config.API_BASE_URL}/servicios", params=params, json=cuerpo,
                             headers=_cabeceras_gateway(), timeout=config.TIMEOUT)
    except requests.RequestException as exc:
        return jsonify({"mensaje": f"No se pudo contactar a API Gateway ({exc.__class__.__name__})."}), 502
    if r.status_code in ERRORES_GATEWAY:
        return jsonify({"mensaje": ERRORES_GATEWAY[r.status_code]}), r.status_code
    return Response(r.content, status=r.status_code, content_type="application/json")


def _clave_impuesto(i):
    return f"{i['nombre']}|{float(i['tasa']):.4f}|{i['tipo']}"


def listar_impuestos():
    """Devuelve (impuestos, error). Cada uno trae 'clave', 'nombre', 'tasa', 'tipo', 'etiqueta'."""
    datos, error = consultar_backend("/catalogos", "impuestos")
    impuestos = [{**i, "tasa": float(i["tasa"]), "clave": _clave_impuesto(i),
                  "etiqueta": f"{i['nombre']} {float(i['tasa']) * 100:g}% ({i['tipo']})"}
                 for i in datos]
    return impuestos, error
