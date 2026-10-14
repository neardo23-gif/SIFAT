"""SIFAT - Front (Flask).

Consume el servicio /servicios de API Gateway (Lambda + DynamoDB).
Con USE_MOCK=true trabaja con datos en memoria para desarrollar sin red.
"""
import copy
import os

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
TIMEOUT = 8

_mock_store = {s["id_servicio"]: copy.deepcopy(s) for s in SERVICIOS}


@app.template_filter("mxn")
def mxn(value):
    try:
        return "${:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return "-"


def listar_servicios():
    """Devuelve (servicios, error). Nunca lanza: el front muestra el error."""
    if USE_MOCK:
        items = list(_mock_store.values())
    else:
        try:
            r = requests.get(f"{API_BASE_URL}/servicios", timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            items = data.get("servicios", []) if isinstance(data, dict) else data
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
    try:
        r = requests.request(
            request.method,
            f"{API_BASE_URL}/servicios",
            params=request.args,
            json=request.get_json(silent=True),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return jsonify({"mensaje": f"No se pudo contactar a API Gateway ({exc.__class__.__name__})."}), 502
    return Response(r.content, status=r.status_code, content_type="application/json")


def _mock_api():
    if request.method == "DELETE":
        sid = request.args.get("id_servicio")
        if not sid:
            return jsonify({"mensaje": 'Falta la propiedad "id_servicio"'}), 400
        if sid not in _mock_store:
            return jsonify({"mensaje": "Servicio no encontrado"}), 404
        borrado = _mock_store.pop(sid)
        return jsonify({"mensaje": "Servicio eliminado correctamente", "servicio": borrado})

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
    app.run(debug=True, port=5000)
