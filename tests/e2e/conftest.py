"""Arranca el backend simulado y el front real en hilos, y le da a cada prueba un navegador.

Correr:  pip install -r requirements-e2e.txt && python -m playwright install chromium
         pytest tests/e2e
"""
import re
import threading

import pytest
from werkzeug.serving import make_server

pytest.importorskip("playwright", reason="Instala requirements-e2e.txt para las pruebas en navegador")

import app as sifat  # noqa: E402
import config  # noqa: E402
from e2e.backend_falso import CLAVE_BACKEND, CLAVE_GATEWAY, crear_backend_falso  # noqa: E402


class Servidor(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.srv = make_server("127.0.0.1", 0, app, threaded=True)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def run(self):
        self.srv.serve_forever()

    def detener(self):
        self.srv.shutdown()


@pytest.fixture
def servicios_de_prueba(monkeypatch):
    """Sustituye al de tests/conftest.py: aquí el front habla con el backend simulado de verdad."""
    backend = Servidor(crear_backend_falso())
    backend.start()
    for nombre, valor in {"API_BASE_URL": backend.url, "API_KEY": CLAVE_GATEWAY,
                          "BACKEND_URL": backend.url, "BACKEND_API_KEY": CLAVE_BACKEND}.items():
        monkeypatch.setattr(config, nombre, valor)
    sifat.app.config.update(TESTING=False, SESSION_COOKIE_SECURE=False)
    yield backend
    backend.detener()


@pytest.fixture
def sitio(servicios_de_prueba):
    front = Servidor(sifat.app)
    front.start()
    yield front.url
    front.detener()


@pytest.fixture
def nav(sitio, page):
    """Página de Playwright apuntando al front; falla la prueba si hay errores de JavaScript."""
    errores = []
    page.on("pageerror", lambda e: errores.append(str(e)))
    # Las respuestas 4xx de la app son esperadas (login fallido, validaciones); un 404 o 5xx no
    esperados = re.compile(r"status of (400|401|403|409|422)\b")
    page.on("console", lambda m: errores.append(m.text)
            if m.type == "error" and not esperados.search(m.text) else None)
    page.set_default_timeout(5000)
    page.base = sitio
    yield page
    assert not errores, f"Errores de JavaScript en el navegador: {errores}"
