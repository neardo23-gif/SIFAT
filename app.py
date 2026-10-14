"""SIFAT - Front (Flask).

Consume el servicio /servicios de API Gateway (Lambda + DynamoDB).
Con USE_MOCK=true trabaja con datos en memoria para desarrollar sin red.
"""
import copy
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

from mock_data import CLIENTES, FACTURAS, PAGOS, SERVICIOS

load_dotenv()

app = Flask(__name__)

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://4er7ekb4h6.execute-api.us-east-1.amazonaws.com/dev",
).rstrip("/")
USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"
# La clave solo vive en el servidor: el navegador nunca la ve.
API_KEY = os.getenv("API_KEY", "").strip()
TIMEOUT = 8
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
    elif not API_KEY:
        return [], "Falta configurar API_KEY en el archivo .env."
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
    return {
        "active": active,
        "origen": "Datos de ejemplo" if USE_MOCK else "API Gateway",
        "usa_mock": USE_MOCK,
    }


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/catalogo")
def catalogo():
    servicios, error = listar_servicios()
    categorias = sorted({s.get("categoria", "Sin categoria") for s in servicios})
    return render_template(
        "catalogo.html",
        servicios=servicios,
        categorias=categorias,
        error=error,
        **contexto_base("catalogo"),
    )


@app.route("/facturas")
def facturas():
    return render_template("facturas.html", facturas=FACTURAS, **contexto_base("facturas"))


@app.route("/clientes")
def clientes():
    return render_template("clientes.html", clientes=CLIENTES, **contexto_base("clientes"))


@app.route("/pagos")
def pagos():
    return render_template("pagos.html", pagos=PAGOS, **contexto_base("pagos"))


@app.route("/api/servicios", methods=["POST", "PUT", "DELETE"])
def api_servicios():
    """Proxy hacia API Gateway (evita CORS y mantiene la URL fuera del navegador)."""
    if USE_MOCK:
        return _mock_api()
    if not API_KEY:
        return jsonify({"mensaje": "Falta configurar API_KEY en el archivo .env."}), 500

    # Solo se reenvía lo que cada método necesita
    if request.method == "DELETE":
        params, cuerpo = {"id_servicio": request.args.get("id_servicio", "")}, None
    else:
        params, cuerpo = None, request.get_json(silent=True)
        if not isinstance(cuerpo, dict):
            return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400

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


def _mock_api():
    if request.method == "DELETE":
        sid = request.args.get("id_servicio")
        if not sid:
            return jsonify({"mensaje": 'Falta la propiedad "id_servicio"'}), 400
        servicio = _mock_store.get(sid)
        if not servicio or not servicio.get("activo", True):
            return jsonify({"mensaje": "Servicio no encontrado o ya dado de baja"}), 404
        # Igual que la Lambda: borrado lógico
        servicio["activo"] = False
        servicio["fecha_baja"] = datetime.now(timezone.utc).isoformat()
        return jsonify({"mensaje": "Servicio dado de baja correctamente", "servicio": servicio})

    body = request.get_json(silent=True)
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
