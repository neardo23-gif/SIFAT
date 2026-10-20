"""SIFAT - Front (Flask).

Consume el servicio /servicios de API Gateway (Lambda + DynamoDB).
Con USE_MOCK=true trabaja con datos en memoria para desarrollar sin red.
"""
import copy
import hmac
import logging
import os
import secrets
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, session

from mock_data import CLIENTES, FACTURAS, IVA, PAGOS, SERVICIOS

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

load_dotenv()

log = logging.getLogger("sifat-front")

app = Flask(__name__)
# Firma la cookie de sesión (token CSRF). Debe venir del .env para que no cambie al reiniciar.
app.secret_key = os.getenv("SECRET_KEY", "").strip() or secrets.token_hex(32)
if not os.getenv("SECRET_KEY", "").strip():
    log.warning("SECRET_KEY no está en .env: se generó una temporal (las sesiones se reinician al reiniciar).")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")

# Sin valores por defecto: cada entorno define sus URLs en .env
API_BASE_URL = os.getenv("API_BASE_URL", "").strip().rstrip("/")
# Por defecto se usan los servicios reales; los datos de ejemplo solo si se piden
USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"
# La clave solo vive en el servidor: el navegador nunca la ve.
API_KEY = os.getenv("API_KEY", "").strip()
TIMEOUT = 8

# Backend propio (repo SIFAT-BACKEND): clientes, facturas y pagos en MySQL
BACKEND_URL = os.getenv("BACKEND_URL", "").strip().rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "").strip()
# Campos de un servicio que el navegador puede enviar. Todo lo demás se descarta,
# y el impuesto lo pone el servidor a partir del catálogo de impuestos (MySQL).
CAMPOS_SERVICIO = {"id_servicio", "clave", "nombre", "descripcion", "categoria",
                   "precio_unitario", "unidad_medida", "activo", "caracteristicas"}
UNIDADES = ["Servicio", "Mes", "Ano", "Hora", "Pieza"]

LIMITE_PAGINA = 50  # máximo que acepta la Lambda por página
MAX_PAGINAS = 20  # tope de seguridad: hasta 1000 servicios por carga

# Mensajes para los errores que genera API Gateway (no las Lambdas)
ERRORES_GATEWAY = {
    403: "API Gateway rechazó la petición: falta la clave de acceso o no es válida (revisa API_KEY).",
    429: "Se superó el límite de peticiones. Espera unos segundos e inténtalo de nuevo.",
}

_mock_store = {s["id_servicio"]: copy.deepcopy(s) for s in SERVICIOS}


@app.template_filter("mxn")
def mxn(value):
    try:
        return "${:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return "-"


def _headers_api():
    return {"x-api-key": API_KEY}


def listar_servicios():
    """Devuelve (servicios, error). Nunca lanza: el front muestra el error.

    La Lambda responde por páginas; aquí se recorren todas (con un tope) e
    incluye los servicios dados de baja para mostrarlos como inactivos.
    """
    if USE_MOCK:
        items = list(_mock_store.values())
    elif not API_KEY or not API_BASE_URL:
        return [], "Falta configurar API_KEY o API_BASE_URL en el archivo .env."
    else:
        items, siguiente = [], None
        try:
            for _ in range(MAX_PAGINAS):
                params = {"limite": LIMITE_PAGINA, "incluir_inactivos": "true"}
                if siguiente:
                    params["siguiente"] = siguiente
                r = requests.get(f"{API_BASE_URL}/servicios", params=params,
                                 headers=_headers_api(), timeout=TIMEOUT)
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


def contexto_base(active):
    origen = "API Gateway" if active == "catalogo" else "Backend (MySQL)"
    return {
        "active": active,
        "origen": "Datos de ejemplo" if USE_MOCK else origen,
        "usa_mock": USE_MOCK,
    }


def _fecha(valor):
    """'2026-10-14T18:30:00' -> '14 oct 2026'."""
    try:
        anio, mes, dia = str(valor)[:10].split("-")
        return f"{int(dia):02d} {MESES[int(mes) - 1]} {anio}"
    except (ValueError, IndexError):
        return "-"


def consultar_backend(ruta, llave):
    """Devuelve (lista, error). Nunca lanza: la pantalla muestra el error."""
    if not BACKEND_API_KEY or not BACKEND_URL:
        return [], "Falta configurar BACKEND_URL o BACKEND_API_KEY en el archivo .env."
    try:
        r = requests.get(f"{BACKEND_URL}{ruta}", params={"limite": 200},
                         headers={"X-API-Key": BACKEND_API_KEY}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return [], f"No se pudo contactar al backend en {BACKEND_URL} ({exc.__class__.__name__}). ¿Está encendido?"
    if r.status_code == 401:
        return [], "El backend rechazó la clave: revisa que BACKEND_API_KEY sea igual en ambos .env."
    if r.status_code != 200:
        return [], f"El backend respondió {r.status_code}."
    try:
        return r.json().get(llave, []), None
    except ValueError:
        return [], "El backend devolvió una respuesta inválida."


# ---------------- Protección CSRF ----------------
def token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = token_csrf


def csrf_valido():
    enviado = request.headers.get("X-CSRF-Token", "")
    guardado = session.get("csrf", "")
    return bool(enviado and guardado and hmac.compare_digest(enviado, guardado))


@app.errorhandler(404)
@app.errorhandler(405)
def error_http(err):
    # En /api/ siempre se responde JSON, nunca la página HTML de Flask
    if request.path.startswith("/api/"):
        return jsonify({"mensaje": "Método no permitido" if err.code == 405 else "Ruta no encontrada"}), err.code
    return err


# ---------------- Impuestos (catálogo del backend) ----------------
def _clave_impuesto(i):
    return f"{i['nombre']}|{float(i['tasa']):.4f}|{i['tipo']}"


def listar_impuestos():
    """Devuelve (impuestos, error). Cada uno trae 'clave', 'nombre', 'tasa', 'tipo', 'etiqueta'."""
    if USE_MOCK:
        datos, error = [IVA], None
    else:
        datos, error = consultar_backend("/catalogos", "impuestos")
    impuestos = [{**i, "tasa": float(i["tasa"]), "clave": _clave_impuesto(i),
                  "etiqueta": f"{i['nombre']} {float(i['tasa']) * 100:g}% ({i['tipo']})"}
                 for i in datos]
    return impuestos, error


def limpiar_servicio(cuerpo, es_alta):
    """Deja solo los campos permitidos y resuelve el impuesto en el servidor.

    Devuelve (servicio, error). El navegador elige un impuesto por su clave, pero
    nunca manda la tasa: así no puede alterarla desde las herramientas de desarrollo.
    """
    servicio = {k: v for k, v in cuerpo.items() if k in CAMPOS_SERVICIO}
    if "unidad_medida" in servicio and servicio["unidad_medida"] not in UNIDADES:
        return None, "Unidad de medida no permitida"
    clave = cuerpo.get("impuesto_clave")
    if clave is None:
        return (None, "Selecciona un impuesto") if es_alta else (servicio, None)
    impuestos, error = listar_impuestos()
    if error:
        return None, f"No se pudo validar el impuesto: {error}"
    elegido = next((i for i in impuestos if i["clave"] == clave), None)
    if not elegido:
        return None, "El impuesto seleccionado no existe en el catálogo"
    servicio["impuesto"] = {"nombre": elegido["nombre"], "tasa": elegido["tasa"], "tipo": elegido["tipo"]}
    return servicio, None


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/catalogo")
def catalogo():
    servicios, error = listar_servicios()
    categorias = sorted({s.get("categoria", "Sin categoria") for s in servicios})
    impuestos, error_impuestos = listar_impuestos()
    if error_impuestos and not error:
        error = f"No se cargaron los impuestos, no podrás guardar servicios: {error_impuestos}"
    return render_template(
        "catalogo.html",
        servicios=servicios,
        categorias=categorias,
        impuestos=impuestos,
        unidades=UNIDADES,
        error=error,
        **contexto_base("catalogo"),
    )


@app.route("/facturas")
def facturas():
    if USE_MOCK:
        return render_template("facturas.html", facturas=FACTURAS, **contexto_base("facturas"))
    datos, error = consultar_backend("/facturas", "facturas")
    filas = [{"folio": f["folio"], "cliente": f["cliente"], "fecha": _fecha(f["fecha_emision"]),
              "subtotal": f["subtotal"], "iva": f["iva"], "total": f["total"],
              "estatus": f["estatus"]} for f in datos]
    return render_template("facturas.html", facturas=filas, error=error, **contexto_base("facturas"))


@app.route("/clientes")
def clientes():
    if USE_MOCK:
        return render_template("clientes.html", clientes=CLIENTES, **contexto_base("clientes"))
    datos, error = consultar_backend("/clientes", "clientes")
    filas = [{"id": f"CLI-{c['id_cliente']:03d}", "razon_social": c["razon_social"], "rfc": c["rfc"],
              "cp": c["cp_fiscal"], "email": c.get("email") or "-", "activo": c["activo"]}
             for c in datos]
    return render_template("clientes.html", clientes=filas, error=error, **contexto_base("clientes"))


@app.route("/pagos")
def pagos():
    if USE_MOCK:
        return render_template("pagos.html", pagos=PAGOS, **contexto_base("pagos"))
    datos, error = consultar_backend("/pagos", "pagos")
    filas = [{"id": p["id_pago"], "folio": p["folio"], "fecha": _fecha(p["fecha_pago"]),
              "forma": f"{p['clave_forma_pago']} {p['forma_pago']}", "monto": p["monto"],
              "referencia": p.get("referencia") or "-"} for p in datos]
    return render_template("pagos.html", pagos=filas, error=error, **contexto_base("pagos"))


@app.route("/api/servicios", methods=["POST", "PUT", "DELETE"])
def api_servicios():
    """Proxy hacia API Gateway (evita CORS y mantiene la URL fuera del navegador)."""
    if not csrf_valido():
        return jsonify({"mensaje": "Sesión inválida o expirada. Recarga la página."}), 403

    # Solo se reenvía lo que cada método necesita
    if request.method == "DELETE":
        params, cuerpo = {"id_servicio": request.args.get("id_servicio", "")}, None
    else:
        crudo = request.get_json(silent=True)
        if not isinstance(crudo, dict):
            return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400
        cuerpo, error = limpiar_servicio(crudo, es_alta=request.method == "POST")
        if error:
            return jsonify({"mensaje": error}), 400
        params = None

    if USE_MOCK:
        return _mock_api(params, cuerpo)
    if not API_KEY or not API_BASE_URL:
        return jsonify({"mensaje": "Falta configurar API_KEY o API_BASE_URL en el archivo .env."}), 500

    try:
        r = requests.request(
            request.method,
            f"{API_BASE_URL}/servicios",
            params=params,
            json=cuerpo,
            headers=_headers_api(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return jsonify({"mensaje": f"No se pudo contactar a API Gateway ({exc.__class__.__name__})."}), 502
    if r.status_code in ERRORES_GATEWAY:
        return jsonify({"mensaje": ERRORES_GATEWAY[r.status_code]}), r.status_code
    return Response(r.content, status=r.status_code, content_type="application/json")


def _mock_api(params, body):
    if request.method == "DELETE":
        sid = (params or {}).get("id_servicio")
        if not sid:
            return jsonify({"mensaje": 'Falta la propiedad "id_servicio"'}), 400
        servicio = _mock_store.get(sid)
        if not servicio or not servicio.get("activo", True):
            return jsonify({"mensaje": "Servicio no encontrado o ya dado de baja"}), 404
        # Igual que la Lambda: borrado lógico
        servicio["activo"] = False
        servicio["fecha_baja"] = datetime.now(timezone.utc).isoformat()
        return jsonify({"mensaje": "Servicio dado de baja correctamente", "servicio": servicio})

    if not isinstance(body, dict) or not body:
        return jsonify({"mensaje": "El cuerpo de la petición está vacío"}), 400
    sid = body.get("id_servicio")
    if not sid:
        return jsonify({"mensaje": 'Falta la propiedad "id_servicio" dentro del JSON'}), 400

    if request.method == "POST":
        if sid in _mock_store:
            return jsonify({"mensaje": "Ya existe un servicio con ese id_servicio"}), 409
        _mock_store[sid] = body
        return jsonify({"mensaje": "Servicio agregado correctamente", "servicio": body})

    if sid not in _mock_store:
        return jsonify({"mensaje": "Servicio no encontrado"}), 404
    _mock_store[sid].update({k: v for k, v in body.items() if k != "id_servicio"})
    return jsonify({"mensaje": "Servicio modificado correctamente", "servicio": _mock_store[sid]})


if __name__ == "__main__":
    # El depurador de Flask permite ejecutar código: solo se activa a propósito
    # En macOS el puerto 5000 lo ocupa el Receptor AirPlay: usa PORT=5001
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
            port=int(os.getenv("PORT", "5000")))
