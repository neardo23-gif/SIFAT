"""Fixtures compartidas para las pruebas de integración del front SIFAT.

Las pruebas recorren la app completa (rutas Flask + plantillas Jinja + proxy)
y sustituyen solo la red: API Gateway y el backend MySQL se simulan con
respuestas falsas de `requests`, así que no hace falta conexión ni claves.
"""
import copy
import json
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as sifat  # noqa: E402
from mock_data import SERVICIOS  # noqa: E402


IMPUESTO_IVA = {"nombre": "IVA", "tasa": "0.1600", "tipo": "traslado"}
CLAVE_IVA = "IVA|0.1600|traslado"
CSRF = "token-csrf-de-prueba"


def con_csrf(cliente):
    """Simula una sesión abierta: el token vive en la cookie y se manda en el header."""
    with cliente.session_transaction() as s:
        s["csrf"] = CSRF
    cliente.environ_base["HTTP_X_CSRF_TOKEN"] = CSRF
    return cliente


class RespuestaFalsa:
    """Imita lo que el front usa de `requests.Response`."""

    def __init__(self, status_code=200, payload=None, texto=None):
        self.status_code = status_code
        self._payload = payload
        if texto is not None:
            self.content = texto.encode()
        else:
            self.content = json.dumps(payload if payload is not None else {}).encode()

    def json(self):
        if self._payload is None:
            return json.loads(self.content.decode())
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class RedFalsa:
    """Registra cada llamada saliente y responde con lo que la prueba programe."""

    def __init__(self):
        self.llamadas = []
        self._respuestas = []

    def responder(self, *respuestas):
        """Encola respuestas (o excepciones) en el orden en que se pedirán."""
        self._respuestas.extend(respuestas)

    def _siguiente(self, metodo, url, **kwargs):
        self.llamadas.append({"metodo": metodo, "url": url, **kwargs})
        if not self._respuestas:
            raise AssertionError(f"Llamada de red no esperada: {metodo} {url}")
        r = self._respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def get(self, url, **kwargs):
        # El catálogo de impuestos se pide en varias pantallas: se responde siempre igual
        if url.endswith("/catalogos"):
            return RespuestaFalsa(200, {"impuestos": [IMPUESTO_IVA]})
        return self._siguiente("GET", url, **kwargs)

    def request(self, metodo, url, **kwargs):
        return self._siguiente(metodo, url, **kwargs)


@pytest.fixture
def red(monkeypatch):
    falsa = RedFalsa()
    monkeypatch.setattr(sifat.requests, "get", falsa.get)
    monkeypatch.setattr(sifat.requests, "request", falsa.request)
    return falsa


@pytest.fixture(autouse=True)
def almacen_mock_limpio(monkeypatch):
    """Cada prueba arranca con el catálogo de ejemplo original."""
    monkeypatch.setattr(
        sifat, "_mock_store", {s["id_servicio"]: copy.deepcopy(s) for s in SERVICIOS}
    )


@pytest.fixture
def modo_mock(monkeypatch):
    monkeypatch.setattr(sifat, "USE_MOCK", True)
    sifat.app.config.update(TESTING=True)
    return con_csrf(sifat.app.test_client())


@pytest.fixture
def modo_real(monkeypatch, red):
    """App apuntando a servicios 'reales' (simulados por `red`)."""
    monkeypatch.setattr(sifat, "USE_MOCK", False)
    monkeypatch.setattr(sifat, "API_BASE_URL", "https://gateway.test/dev")
    monkeypatch.setattr(sifat, "API_KEY", "clave-gateway-prueba")
    monkeypatch.setattr(sifat, "BACKEND_URL", "http://backend.test")
    monkeypatch.setattr(sifat, "BACKEND_API_KEY", "clave-backend-prueba")
    sifat.app.config.update(TESTING=True)
    return con_csrf(sifat.app.test_client())


def html(respuesta):
    return respuesta.get_data(as_text=True)
