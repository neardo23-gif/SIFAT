"""Listas por páginas de 50 y listas completas para los formularios."""
import pytest

from conftest import RespuestaFalsa, html
from test_integracion import CLIENTE, FACTURA, PAGO, _servicio


def _facturas(n, desde=0):
    return [{**FACTURA, "folio": f"FAC-{desde + i + 1:04d}"} for i in range(n)]


def test_primera_pagina_con_mas_resultados(modo_real, red):
    red.responder(RespuestaFalsa(200, {"facturas": _facturas(51)}),
                  RespuestaFalsa(200, {"clientes": [CLIENTE]}),
                  RespuestaFalsa(200, {"servicios": [_servicio(1, "Hosting")]}))
    pagina = html(modo_real.get("/facturas"))
    assert "FAC-0050" in pagina and "FAC-0051" not in pagina  # la fila 51 solo avisa que hay más
    assert 'href="/facturas?pagina=2"' in pagina and 'rel="prev"' not in pagina


def test_segunda_pagina_pide_desde_50(modo_real, red):
    red.responder(RespuestaFalsa(200, {"facturas": _facturas(3, desde=50)}),
                  RespuestaFalsa(200, {"clientes": [CLIENTE]}),
                  RespuestaFalsa(200, {"servicios": [_servicio(1, "Hosting")]}))
    pagina = html(modo_real.get("/facturas?pagina=2"))
    assert red.llamadas[0]["params"] == {"limite": 51, "desde": 50}
    assert "FAC-0051" in pagina and 'href="/facturas?pagina=1"' in pagina and 'rel="next"' not in pagina


@pytest.mark.parametrize("valor", ["abc", "-3", "0", ""])
def test_pagina_invalida_es_la_primera(modo_real, red, valor):
    red.responder(RespuestaFalsa(200, {"clientes": []}))
    modo_real.get(f"/clientes?pagina={valor}")
    assert red.llamadas[0]["params"]["desde"] == 0


def test_sin_mas_paginas_no_hay_navegacion(modo_real, red):
    red.responder(RespuestaFalsa(200, {"pagos": [PAGO]}), RespuestaFalsa(200, {"facturas": []}))
    assert 'aria-label="Páginas"' not in html(modo_real.get("/pagos"))


def test_formulario_de_factura_recibe_todos_los_clientes(modo_real, red):
    """Con más de 200 clientes activos, se piden todas las páginas al backend."""
    primeros = [{**CLIENTE, "id_cliente": i, "razon_social": f"Cliente {i}"} for i in range(1, 201)]
    resto = [{**CLIENTE, "id_cliente": 201, "razon_social": "Cliente 201"}]
    red.responder(RespuestaFalsa(200, {"facturas": []}),
                  RespuestaFalsa(200, {"clientes": primeros}), RespuestaFalsa(200, {"clientes": resto}),
                  RespuestaFalsa(200, {"servicios": [_servicio(1, "Hosting")]}))
    pagina = html(modo_real.get("/facturas"))
    assert "Cliente 201" in pagina
    assert [c["params"]["desde"] for c in red.llamadas if c["url"].endswith("/clientes")] == [0, 200]
