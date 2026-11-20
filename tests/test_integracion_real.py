"""Pruebas de integración contra los servicios reales (solo lectura).

Se omiten por defecto. Para correrlas, con las claves en .env y el backend
SIFAT-BACKEND encendido:

    SIFAT_PRUEBAS_REALES=1 python -m pytest tests/test_integracion_real.py -v

Solo hacen GET: no crean, modifican ni dan de baja nada en AWS ni en MySQL.
"""
import os

import pytest
from dotenv import dotenv_values

import app as sifat
import backend
import config
from conftest import con_csrf, html

pytestmark = pytest.mark.skipif(
    os.getenv("SIFAT_PRUEBAS_REALES") != "1",
    reason="Define SIFAT_PRUEBAS_REALES=1 para probar contra API Gateway y el backend reales.",
)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def servicios_reales(monkeypatch):
    """Deshace las URLs de prueba de conftest: aquí se usa el .env de verdad."""
    env = dotenv_values(os.path.join(RAIZ, ".env"))
    for nombre in ("API_BASE_URL", "API_KEY", "BACKEND_URL", "BACKEND_API_KEY"):
        monkeypatch.setattr(config, nombre, (env.get(nombre) or "").strip().rstrip("/"))


@pytest.fixture
def cliente_real():
    return con_csrf(sifat.app.test_client())


def test_api_gateway_lista_servicios():
    if not config.API_KEY:
        pytest.skip("Falta API_KEY en .env")
    servicios, error = backend.listar_servicios()
    assert error is None, error
    assert isinstance(servicios, list)
    for s in servicios:
        assert s.get("id_servicio") and "nombre" in s


def test_catalogo_real_sin_error(cliente_real):
    if not config.API_KEY:
        pytest.skip("Falta API_KEY en .env")
    r = cliente_real.get("/catalogo")
    assert r.status_code == 200
    assert "No se pudo consultar API Gateway" not in html(r)
    assert "API Gateway rechazó" not in html(r)


@pytest.mark.parametrize("ruta, llave, campos", [
    ("/facturas", "facturas", {"folio", "cliente", "fecha_emision", "subtotal", "iva", "total", "estatus"}),
    ("/clientes", "clientes", {"id_cliente", "razon_social", "rfc", "cp_fiscal", "activo"}),
    ("/pagos", "pagos", {"id_pago", "folio", "fecha_pago", "clave_forma_pago", "forma_pago", "monto"}),
])
def test_backend_cumple_el_contrato(ruta, llave, campos):
    """El front depende de estos campos: si el backend los renombra, falla aquí."""
    if not config.BACKEND_API_KEY:
        pytest.skip("Falta BACKEND_API_KEY en .env")
    datos, error = backend.consultar_backend(ruta, llave)
    assert error is None, error
    for fila in datos:
        faltan = campos - fila.keys()
        assert not faltan, f"{ruta}: faltan campos {faltan}"


@pytest.mark.parametrize("ruta", ["/facturas", "/clientes", "/pagos"])
def test_pantallas_backend_reales_sin_error(cliente_real, ruta):
    if not config.BACKEND_API_KEY:
        pytest.skip("Falta BACKEND_API_KEY en .env")
    r = cliente_real.get(ruta)
    assert r.status_code == 200
    assert "No se pudo contactar al backend" not in html(r)
    assert "Backend (MySQL)" in html(r)
