"""Pruebas de integración del front SIFAT.

Cubren el recorrido completo petición -> ruta Flask -> cliente HTTP ->
transformación de datos -> plantilla Jinja, en los dos modos de la app:

* USE_MOCK=true: datos en memoria (CRUD del catálogo de punta a punta).
* USE_MOCK=false: contra API Gateway y el backend MySQL (red simulada).
"""
import pytest
import requests

from conftest import RespuestaFalsa, html


# ---------------------------------------------------------------------------
# Modo mock: navegación y CRUD del catálogo sin red
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ruta, texto", [
    ("/", "SIFAT"),
    ("/catalogo", "Hosting Basico"),
    ("/facturas", "FAC-0001"),
    ("/clientes", "Consultoria Sur SA de CV"),
    ("/pagos", "03 Transferencia electronica"),
])
def test_mock_todas_las_pantallas_cargan(modo_mock, ruta, texto):
    r = modo_mock.get(ruta)
    assert r.status_code == 200
    assert texto in html(r)


@pytest.mark.parametrize("ruta", ["/catalogo", "/facturas", "/clientes", "/pagos"])
def test_mock_indica_origen_datos_de_ejemplo(modo_mock, ruta):
    assert "Datos de ejemplo" in html(modo_mock.get(ruta))


def test_mock_crud_completo_del_catalogo(modo_mock):
    nuevo = {"id_servicio": "SRV-900", "clave": "INT-TST", "nombre": "Servicio de Integracion",
             "categoria": "Pruebas", "precio_unitario": 123.45, "unidad_medida": "Servicio",
             "activo": True, "impuesto_clave": "IVA|0.1600|traslado"}

    # Alta: aparece en el catálogo renderizado
    r = modo_mock.post("/api/servicios", json=nuevo)
    assert r.status_code == 200
    assert r.get_json()["servicio"]["id_servicio"] == "SRV-900"
    pagina = html(modo_mock.get("/catalogo"))
    assert "Servicio de Integracion" in pagina
    assert "Pruebas" in pagina  # la categoría nueva entra al filtro

    # Duplicado rechazado
    assert modo_mock.post("/api/servicios", json=nuevo).status_code == 409

    # Modificación: se refleja en la pantalla
    r = modo_mock.put("/api/servicios", json={"id_servicio": "SRV-900",
                                               "nombre": "Servicio Integrado"})
    assert r.status_code == 200
    assert r.get_json()["servicio"]["precio_unitario"] == 123.45  # conserva lo demás
    assert "Servicio Integrado" in html(modo_mock.get("/catalogo"))

    # Baja lógica: sigue listado pero inactivo, y no se puede dar de baja dos veces
    r = modo_mock.delete("/api/servicios?id_servicio=SRV-900")
    assert r.status_code == 200
    servicio = r.get_json()["servicio"]
    assert servicio["activo"] is False and servicio["fecha_baja"]
    assert "Servicio Integrado" in html(modo_mock.get("/catalogo"))
    assert modo_mock.delete("/api/servicios?id_servicio=SRV-900").status_code == 404


@pytest.mark.parametrize("metodo, kwargs, codigo", [
    ("post", {"json": {}}, 400),
    ("post", {"json": {"nombre": "sin id"}}, 400),
    ("put", {"json": {"id_servicio": "SRV-NOEXISTE", "nombre": "x"}}, 404),
    ("delete", {}, 400),
    ("delete", {"query_string": {"id_servicio": "SRV-NOEXISTE"}}, 404),
])
def test_mock_validaciones_del_api(modo_mock, metodo, kwargs, codigo):
    r = getattr(modo_mock, metodo)("/api/servicios", **kwargs)
    assert r.status_code == codigo
    assert r.get_json()["mensaje"]


def test_mock_metodo_get_no_permitido_en_api(modo_mock):
    assert modo_mock.get("/api/servicios").status_code == 405


# ---------------------------------------------------------------------------
# Catálogo contra API Gateway (lectura paginada)
# ---------------------------------------------------------------------------

def _servicio(n, nombre, categoria="Soporte", activo=True):
    return {"id_servicio": f"SRV-{n:03d}", "clave": f"K{n}", "nombre": nombre,
            "categoria": categoria, "precio_unitario": 100, "unidad_medida": "Mes",
            "activo": activo, "caracteristicas": []}


def test_gateway_catalogo_recorre_todas_las_paginas(modo_real, red):
    red.responder(
        RespuestaFalsa(200, {"servicios": [_servicio(2, "Segundo")], "siguiente": "tok-1"}),
        RespuestaFalsa(200, {"servicios": [_servicio(1, "Primero", "Hosting")]}),
    )
    r = modo_real.get("/catalogo")

    assert r.status_code == 200
    pagina = html(r)
    assert "Primero" in pagina and "Segundo" in pagina
    assert "API Gateway" in pagina
    assert pagina.index("Primero") < pagina.index("Segundo")  # se ordena por id

    primera, segunda = red.llamadas
    assert primera["url"] == "https://gateway.test/dev/servicios"
    assert primera["headers"] == {"x-api-key": "clave-gateway-prueba"}
    assert primera["params"] == {"limite": 50, "incluir_inactivos": "true"}
    assert segunda["params"]["siguiente"] == "tok-1"


def test_gateway_catalogo_respeta_tope_de_paginas(modo_real, red, monkeypatch):
    import app as sifat
    monkeypatch.setattr(sifat, "MAX_PAGINAS", 3)
    red.responder(*[RespuestaFalsa(200, {"servicios": [_servicio(i, f"S{i}")],
                                         "siguiente": f"t{i}"}) for i in range(3)])
    assert modo_real.get("/catalogo").status_code == 200
    assert len(red.llamadas) == 3


@pytest.mark.parametrize("respuesta, mensaje", [
    (RespuestaFalsa(403, {"message": "Forbidden"}), "falta la clave de acceso"),
    (RespuestaFalsa(429, {"message": "Too Many"}), "límite de peticiones"),
    (RespuestaFalsa(500, {"message": "boom"}), "HTTPError"),
    (requests.ConnectionError("sin red"), "ConnectionError"),
    (requests.Timeout("lento"), "Timeout"),
    (RespuestaFalsa(200, texto="<html>no json</html>"), "JSONDecodeError"),
])
def test_gateway_catalogo_muestra_errores_sin_romperse(modo_real, red, respuesta, mensaje):
    red.responder(respuesta)
    r = modo_real.get("/catalogo")
    assert r.status_code == 200
    assert mensaje in html(r)


def test_gateway_catalogo_sin_api_key_no_llama_a_la_red(modo_real, red, monkeypatch):
    import app as sifat
    monkeypatch.setattr(sifat, "API_KEY", "")
    assert "Falta configurar API_KEY" in html(modo_real.get("/catalogo"))
    assert red.llamadas == []


# ---------------------------------------------------------------------------
# Proxy /api/servicios hacia API Gateway (escritura)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metodo", ["post", "put"])
def test_proxy_reenvia_cuerpo_y_clave(modo_real, red, metodo):
    cuerpo = {"id_servicio": "SRV-010", "nombre": "Nuevo", "impuesto_clave": "IVA|0.1600|traslado"}
    esperado = {"id_servicio": "SRV-010", "nombre": "Nuevo",
                "impuesto": {"nombre": "IVA", "tasa": 0.16, "tipo": "traslado"}}
    red.responder(RespuestaFalsa(200, {"mensaje": "ok", "servicio": esperado}))

    r = getattr(modo_real, metodo)("/api/servicios", json=cuerpo)

    assert r.status_code == 200
    assert r.get_json()["servicio"] == esperado
    llamada = red.llamadas[0]
    assert llamada["metodo"] == metodo.upper()
    assert llamada["url"] == "https://gateway.test/dev/servicios"
    assert llamada["json"] == esperado and llamada["params"] is None
    assert llamada["headers"] == {"x-api-key": "clave-gateway-prueba"}


def test_proxy_delete_solo_envia_id(modo_real, red):
    red.responder(RespuestaFalsa(200, {"mensaje": "Servicio dado de baja correctamente"}))
    r = modo_real.delete("/api/servicios?id_servicio=SRV-001&extra=ignorar")
    assert r.status_code == 200
    llamada = red.llamadas[0]
    assert llamada["params"] == {"id_servicio": "SRV-001"}
    assert llamada["json"] is None


def test_proxy_propaga_errores_de_la_lambda(modo_real, red):
    red.responder(RespuestaFalsa(409, {"mensaje": "Ya existe un servicio con ese id_servicio"}))
    r = modo_real.post("/api/servicios", json={"id_servicio": "SRV-001", "impuesto_clave": "IVA|0.1600|traslado"})
    assert r.status_code == 409
    assert r.get_json()["mensaje"] == "Ya existe un servicio con ese id_servicio"


@pytest.mark.parametrize("codigo", [403, 429])
def test_proxy_traduce_errores_del_gateway(modo_real, red, codigo):
    red.responder(RespuestaFalsa(codigo, {"message": "gateway"}))
    r = modo_real.put("/api/servicios", json={"id_servicio": "SRV-001"})
    assert r.status_code == codigo
    assert r.get_json()["mensaje"] == __import__("app").ERRORES_GATEWAY[codigo]


def test_proxy_sin_conexion_responde_502(modo_real, red):
    red.responder(requests.ConnectionError("sin red"))
    r = modo_real.post("/api/servicios", json={"id_servicio": "SRV-001", "impuesto_clave": "IVA|0.1600|traslado"})
    assert r.status_code == 502
    assert "ConnectionError" in r.get_json()["mensaje"]


def test_proxy_rechaza_cuerpo_no_json_sin_llamar_a_la_red(modo_real, red):
    r = modo_real.post("/api/servicios", data="texto", content_type="text/plain")
    assert r.status_code == 400
    assert red.llamadas == []


def test_proxy_sin_api_key_responde_500(modo_real, red, monkeypatch):
    import app as sifat
    monkeypatch.setattr(sifat, "API_KEY", "")
    r = modo_real.post("/api/servicios", json={"id_servicio": "SRV-001", "impuesto_clave": "IVA|0.1600|traslado"})
    assert r.status_code == 500
    assert red.llamadas == []


# ---------------------------------------------------------------------------
# Facturas, clientes y pagos contra el backend MySQL
# ---------------------------------------------------------------------------

FACTURA = {"folio": "FAC-0101", "cliente": "Cliente Backend SA", "fecha_emision": "2026-10-14T18:30:00",
           "subtotal": 1000, "iva": 160, "total": 1160, "estatus": "pagada"}
CLIENTE = {"id_cliente": 7, "razon_social": "Cliente Backend SA", "rfc": "CBA010101AA1",
           "cp_fiscal": "62000", "email": None, "activo": True}
PAGO = {"id_pago": 3, "folio": "FAC-0101", "fecha_pago": "2026-01-05", "clave_forma_pago": "03",
        "forma_pago": "Transferencia electronica", "monto": 1160, "referencia": "SPEI-123"}


def test_backend_facturas_transforma_y_renderiza(modo_real, red):
    red.responder(RespuestaFalsa(200, {"facturas": [FACTURA]}))
    pagina = html(modo_real.get("/facturas"))

    assert "FAC-0101" in pagina and "Cliente Backend SA" in pagina
    assert "14 oct 2026" in pagina  # fecha ISO -> formato corto
    assert "$1,160.00" in pagina  # filtro mxn
    assert "Backend (MySQL)" in pagina
    llamada = red.llamadas[0]
    assert llamada["url"] == "http://backend.test/facturas"
    assert llamada["headers"] == {"X-API-Key": "clave-backend-prueba"}
    assert llamada["params"] == {"limite": 200}


def test_backend_clientes_transforma_y_renderiza(modo_real, red):
    red.responder(RespuestaFalsa(200, {"clientes": [CLIENTE]}))
    pagina = html(modo_real.get("/clientes"))

    assert "CLI-007" in pagina  # id numérico -> clave con ceros
    assert "CBA010101AA1" in pagina and "62000" in pagina
    assert red.llamadas[0]["url"] == "http://backend.test/clientes"


def test_backend_pagos_transforma_y_renderiza(modo_real, red):
    red.responder(RespuestaFalsa(200, {"pagos": [PAGO, {**PAGO, "id_pago": 4, "referencia": None}]}))
    pagina = html(modo_real.get("/pagos"))

    assert "05 ene 2026" in pagina
    assert "03 Transferencia electronica" in pagina
    assert "SPEI-123" in pagina
    assert red.llamadas[0]["url"] == "http://backend.test/pagos"


@pytest.mark.parametrize("ruta", ["/facturas", "/clientes", "/pagos"])
@pytest.mark.parametrize("respuesta, mensaje", [
    (RespuestaFalsa(401, {"detail": "no"}), "rechazó la clave"),
    (RespuestaFalsa(500, {"detail": "boom"}), "El backend respondió 500"),
    (RespuestaFalsa(200, texto="no es json"), "respuesta inválida"),
    (requests.ConnectionError("apagado"), "No se pudo contactar al backend"),
])
def test_backend_errores_se_muestran_en_pantalla(modo_real, red, ruta, respuesta, mensaje):
    red.responder(respuesta)
    r = modo_real.get(ruta)
    assert r.status_code == 200
    assert mensaje in html(r)


@pytest.mark.parametrize("ruta", ["/facturas", "/clientes", "/pagos"])
def test_backend_sin_clave_no_llama_a_la_red(modo_real, red, monkeypatch, ruta):
    import app as sifat
    monkeypatch.setattr(sifat, "BACKEND_API_KEY", "")
    assert "Falta configurar BACKEND_URL o BACKEND_API_KEY" in html(modo_real.get(ruta))
    assert red.llamadas == []


@pytest.mark.parametrize("ruta, llave", [("/facturas", "facturas"), ("/clientes", "clientes"),
                                         ("/pagos", "pagos")])
def test_backend_lista_vacia(modo_real, red, ruta, llave):
    red.responder(RespuestaFalsa(200, {llave: []}))
    assert modo_real.get(ruta).status_code == 200


# ---------------------------------------------------------------------------
# Seguridad del proxy: lo que el navegador no puede alterar
# ---------------------------------------------------------------------------

def test_proxy_sin_token_csrf_responde_403(modo_real, red):
    modo_real.environ_base.pop("HTTP_X_CSRF_TOKEN")
    r = modo_real.post("/api/servicios", json={"id_servicio": "SRV-010", "impuesto_clave": "IVA|0.1600|traslado"})
    assert r.status_code == 403
    assert red.llamadas == []


def test_proxy_ignora_tasa_enviada_por_el_navegador(modo_real, red):
    """Aunque se manipule la página con DevTools, la tasa la decide el servidor."""
    red.responder(RespuestaFalsa(200, {"mensaje": "ok"}))
    modo_real.post("/api/servicios", json={
        "id_servicio": "SRV-010", "nombre": "X", "impuesto_clave": "IVA|0.1600|traslado",
        "impuesto": {"nombre": "IVA", "tasa": 0, "tipo": "traslado"}, "admin": True})
    enviado = red.llamadas[0]["json"]
    assert enviado["impuesto"]["tasa"] == 0.16
    assert "admin" not in enviado


def test_proxy_rechaza_impuesto_inexistente(modo_real, red):
    r = modo_real.post("/api/servicios", json={"id_servicio": "SRV-010", "impuesto_clave": "IVA|0.0000|traslado"})
    assert r.status_code == 400
    assert red.llamadas == []


def test_proxy_rechaza_unidad_no_permitida(modo_real, red):
    r = modo_real.put("/api/servicios", json={"id_servicio": "SRV-001", "unidad_medida": "<script>"})
    assert r.status_code == 400
    assert red.llamadas == []


def test_api_get_responde_json_y_no_html(modo_real):
    r = modo_real.get("/api/servicios")
    assert r.status_code == 405
    assert r.get_json() == {"mensaje": "Método no permitido"}
