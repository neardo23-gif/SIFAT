"""Pruebas de integración contra los servicios reales (solo lectura).

Se omiten por defecto. Para correrlas, con las claves en .env y el backend
SIFAT-BACKEND encendido:

    SIFAT_PRUEBAS_REALES=1 python -m pytest tests/test_integracion_real.py -v

Solo hacen GET: no crean, modifican ni dan de baja nada en AWS ni en MySQL.
"""
import os

import pytest

import app as sifat
from conftest import html

pytestmark = pytest.mark.skipif(
    os.getenv("SIFAT_PRUEBAS_REALES") != "1",
    reason="Define SIFAT_PRUEBAS_REALES=1 para probar contra API Gateway y el backend reales.",
)


@pytest.fixture
def cliente_real(monkeypatch):
    monkeypatch.setattr(sifat, "USE_MOCK", False)
    sifat.app.config.update(TESTING=True)
    return sifat.app.test_client()


def test_api_gateway_lista_servicios():
    if not sifat.API_KEY:
        pytest.skip("Falta API_KEY en .env")
    servicios, error = _sin_mock(sifat.listar_servicios)
    assert error is None, error
    assert isinstance(servicios, list)
    for s in servicios:
        assert s.get("id_servicio") and "nombre" in s


def test_catalogo_real_sin_error(cliente_real):
    if not sifat.API_KEY:
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
    if not sifat.BACKEND_API_KEY:
        pytest.skip("Falta BACKEND_API_KEY en .env")
    datos, error = sifat.consultar_backend(ruta, llave)
    assert error is None, error
    for fila in datos:
        faltan = campos - fila.keys()
        assert not faltan, f"{ruta}: faltan campos {faltan}"


@pytest.mark.parametrize("ruta", ["/facturas", "/clientes", "/pagos"])
def test_pantallas_backend_reales_sin_error(cliente_real, ruta):
    if not sifat.BACKEND_API_KEY:
        pytest.skip("Falta BACKEND_API_KEY en .env")
    r = cliente_real.get(ruta)
    assert r.status_code == 200
    assert "No se pudo contactar al backend" not in html(r)
    assert "Backend (MySQL)" in html(r)


def _sin_mock(funcion):
    anterior, sifat.USE_MOCK = sifat.USE_MOCK, False
    try:
        return funcion()
    finally:
        sifat.USE_MOCK = anterior
