"""Altas y cambios de clientes, facturas y pagos a través del proxy del front.

Se verifica lo que el navegador NO puede decidir (quién emite, precios, permisos)
y que los errores del backend lleguen al usuario en español.
"""
import pytest
import requests

from conftest import ADMIN, RespuestaFalsa, con_csrf, html

FACTURISTA = {**ADMIN, "id_usuario": 2, "nombre": "Luis Perez", "rol": "Facturista"}


@pytest.fixture
def facturista(modo_real):
    import app as sifat
    return con_csrf(sifat.app.test_client(), usuario=FACTURISTA)


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

def test_alta_cliente_limpia_y_reenvia(modo_real, red):
    red.responder(RespuestaFalsa(201, {"id_cliente": 9, "rfc": "CBA010101AA1"}))
    r = modo_real.post("/api/clientes", json={
        "rfc": " cba010101aa1 ", "razon_social": "  Cliente Nuevo SA ", "cp_fiscal": "62000",
        "clave_regimen": "601", "clave_uso": "G03", "email": "Ventas@Cliente.MX", "telefono": "",
        "activo": False, "id_cliente": 1})
    assert r.status_code == 201
    llamada = red.llamadas[0]
    assert (llamada["metodo"], llamada["url"]) == ("POST", "http://backend.test/clientes")
    assert llamada["headers"] == {"X-API-Key": "clave-backend-prueba"}
    # RFC en mayúsculas, correo en minúsculas, opcional vacío fuera, campos ajenos fuera
    assert llamada["json"] == {"rfc": "CBA010101AA1", "razon_social": "Cliente Nuevo SA",
                               "cp_fiscal": "62000", "clave_regimen": "601", "clave_uso": "G03",
                               "email": "ventas@cliente.mx"}


def test_editar_cliente_no_permite_cambiar_rfc(modo_real, red):
    red.responder(RespuestaFalsa(200, {"id_cliente": 7}))
    modo_real.patch("/api/clientes/7", json={"rfc": "XXX010101XX1", "razon_social": "Otro", "email": ""})
    llamada = red.llamadas[0]
    assert (llamada["metodo"], llamada["url"]) == ("PATCH", "http://backend.test/clientes/7")
    # En una edición, el correo vacío significa "quitar el correo"
    assert llamada["json"] == {"razon_social": "Otro", "email": None}


def test_facturista_no_puede_desactivar_clientes(facturista, red):
    r = facturista.patch("/api/clientes/7", json={"activo": False})
    assert r.status_code == 403
    assert red.llamadas == []


def test_facturista_si_puede_editar_datos_del_cliente(facturista, red):
    red.responder(RespuestaFalsa(200, {"id_cliente": 7}))
    assert facturista.patch("/api/clientes/7", json={"cp_fiscal": "62001"}).status_code == 200


def test_admin_puede_desactivar_clientes(modo_real, red):
    red.responder(RespuestaFalsa(200, {"id_cliente": 7, "activo": False}))
    assert modo_real.patch("/api/clientes/7", json={"activo": False}).status_code == 200
    assert red.llamadas[0]["json"] == {"activo": False}


def test_editar_cliente_sin_cambios_no_llama_a_la_red(modo_real, red):
    r = modo_real.patch("/api/clientes/7", json={"rfc": "XXX010101XX1"})
    assert r.status_code == 400
    assert red.llamadas == []


# ---------------------------------------------------------------------------
# Facturas
# ---------------------------------------------------------------------------

def test_emitir_factura_usa_el_usuario_de_la_sesion(facturista, red):
    red.responder(RespuestaFalsa(201, {"folio": "FAC-0002", "total": 1160}))
    r = facturista.post("/api/facturas", json={
        "id_cliente": 7, "id_usuario": 1, "clave_forma_pago": "03", "clave_metodo_pago": "PUE",
        "conceptos": [{"id_servicio": "SRV-001", "cantidad": "2", "precio_unitario": 0.01}]})
    assert r.status_code == 201
    enviado = red.llamadas[0]["json"]
    assert enviado["id_usuario"] == 2  # el de la sesión, no el que mandó el navegador
    # Solo servicio y cantidad: el precio lo pone el backend desde el catálogo
    assert enviado["conceptos"] == [{"id_servicio": "SRV-001", "cantidad": "2"}]


@pytest.mark.parametrize("conceptos", [None, [], "SRV-001", [1, 2]])
def test_emitir_factura_rechaza_conceptos_invalidos(modo_real, red, conceptos):
    r = modo_real.post("/api/facturas", json={"id_cliente": 7, "conceptos": conceptos})
    assert r.status_code == 400
    assert red.llamadas == []


def test_detalle_factura_valida_el_folio(modo_real, red):
    assert modo_real.get("/api/facturas/..%2Fclientes").status_code in (400, 404)
    assert modo_real.get("/api/facturas/FAC-1;DROP").status_code == 400
    assert red.llamadas == []


def test_detalle_factura_se_reenvia(modo_real, red):
    red.responder(RespuestaFalsa(200, {"folio": "FAC-0101", "saldo": 0}))
    r = modo_real.get("/api/facturas/FAC-0101")
    assert r.get_json()["folio"] == "FAC-0101"
    assert red.llamadas[0]["url"] == "http://backend.test/facturas/FAC-0101"


def test_facturista_no_puede_cancelar(facturista, red):
    r = facturista.post("/api/facturas/FAC-0101/cancelar", json={"motivo": "Error de captura"})
    assert r.status_code == 403
    assert red.llamadas == []


def test_admin_cancela_con_motivo(modo_real, red):
    red.responder(RespuestaFalsa(200, {"folio": "FAC-0101", "estatus": "cancelada"}))
    modo_real.post("/api/facturas/FAC-0101/cancelar", json={"motivo": "  Error de captura ", "x": 1})
    llamada = red.llamadas[0]
    assert llamada["url"] == "http://backend.test/facturas/FAC-0101/cancelar"
    assert llamada["json"] == {"motivo": "Error de captura"}


# ---------------------------------------------------------------------------
# Pagos
# ---------------------------------------------------------------------------

def test_registrar_pago_solo_envia_campos_permitidos(facturista, red):
    red.responder(RespuestaFalsa(201, {"folio": "FAC-0101", "factura_pagada": True}))
    facturista.post("/api/pagos", json={"folio": "FAC-0101", "clave_forma_pago": "03",
                                        "monto": "100.50", "referencia": "  ", "estatus": "pagada"})
    assert red.llamadas[0]["json"] == {"folio": "FAC-0101", "clave_forma_pago": "03", "monto": "100.50"}


# ---------------------------------------------------------------------------
# Seguridad y errores comunes a todas las escrituras
# ---------------------------------------------------------------------------

ESCRITURAS = [
    ("post", "/api/clientes", {"rfc": "CBA010101AA1"}),
    ("patch", "/api/clientes/7", {"razon_social": "X"}),
    ("post", "/api/facturas", {"conceptos": [{"id_servicio": "SRV-001", "cantidad": "1"}]}),
    ("post", "/api/facturas/FAC-0101/cancelar", {"motivo": "Error de captura"}),
    ("post", "/api/pagos", {"folio": "FAC-0101"}),
]


@pytest.mark.parametrize("metodo, ruta, cuerpo", ESCRITURAS)
def test_escrituras_exigen_csrf(modo_real, red, metodo, ruta, cuerpo):
    modo_real.environ_base.pop("HTTP_X_CSRF_TOKEN")
    assert getattr(modo_real, metodo)(ruta, json=cuerpo).status_code == 403
    assert red.llamadas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", ESCRITURAS)
def test_escrituras_exigen_sesion(sin_sesion, red, metodo, ruta, cuerpo):
    assert getattr(sin_sesion, metodo)(ruta, json=cuerpo).status_code == 401
    assert red.llamadas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", ESCRITURAS)
def test_escrituras_rechazan_cuerpo_que_no_es_objeto(modo_real, red, metodo, ruta, cuerpo):
    assert getattr(modo_real, metodo)(ruta, json=["no", "objeto"]).status_code == 400
    assert red.llamadas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", ESCRITURAS)
def test_escrituras_en_modo_ejemplo_piden_el_backend(modo_mock, metodo, ruta, cuerpo):
    r = getattr(modo_mock, metodo)(ruta, json=cuerpo)
    assert r.status_code == 503
    assert "necesita el backend" in r.get_json()["mensaje"]


def test_errores_de_validacion_se_traducen(modo_real, red):
    red.responder(RespuestaFalsa(400, {"mensaje": "Datos inválidos", "errores": [
        {"campo": "rfc", "mensaje": "String should match pattern"},
        {"campo": "conceptos.0.cantidad", "mensaje": "Input should be greater than 0"}]}))
    r = modo_real.post("/api/clientes", json={"rfc": "x"})
    assert r.status_code == 400
    assert r.get_json()["mensaje"] == "Revisa estos datos: RFC, cantidad"


def test_reglas_de_negocio_pasan_tal_cual(modo_real, red):
    red.responder(RespuestaFalsa(422, {"mensaje": "El monto excede el saldo pendiente (10.00)"}))
    r = modo_real.post("/api/pagos", json={"folio": "FAC-0101", "monto": "99"})
    assert r.status_code == 422
    assert r.get_json()["mensaje"] == "El monto excede el saldo pendiente (10.00)"


@pytest.mark.parametrize("respuesta, texto", [
    (RespuestaFalsa(500, {"mensaje": "Error interno", "error_id": "abc123"}), "abc123"),
    (RespuestaFalsa(401, {"detail": "no"}), "no está bien configurado"),
    (RespuestaFalsa(200, texto="<html>"), "respuesta inválida"),
    (requests.ConnectionError("apagado"), "No se pudo contactar"),
])
def test_fallas_del_backend_responden_502(modo_real, red, respuesta, texto):
    red.responder(respuesta)
    r = modo_real.post("/api/clientes", json={"rfc": "CBA010101AA1"})
    assert r.status_code == 502
    assert texto in r.get_json()["mensaje"]


# ---------------------------------------------------------------------------
# Pantallas: qué botones ve cada rol
# ---------------------------------------------------------------------------

def test_facturista_no_ve_cancelar_ni_activar(facturista, red):
    from test_integracion import CLIENTE, FACTURA, _servicio
    red.responder(RespuestaFalsa(200, {"facturas": [FACTURA]}),
                  RespuestaFalsa(200, {"clientes": [CLIENTE]}),
                  RespuestaFalsa(200, {"servicios": [_servicio(1, "Hosting")]}))
    pagina = html(facturista.get("/facturas"))
    assert "Nueva factura" in pagina
    assert '"puede_cancelar": false' in pagina

    red.responder(RespuestaFalsa(200, {"clientes": [CLIENTE]}))
    pagina = html(facturista.get("/clientes"))
    assert "Nuevo cliente" in pagina
    assert 'id="c-activo"' not in pagina


def test_pagos_abre_el_formulario_con_el_folio_valido(modo_real, red):
    vigente = {"folio": "FAC-0101", "cliente": "Cliente Backend SA", "total": 1160}
    red.responder(RespuestaFalsa(200, {"pagos": []}), RespuestaFalsa(200, {"facturas": [vigente]}))
    assert '"folio_inicial": "FAC-0101"' in html(modo_real.get("/pagos?folio=FAC-0101"))

    red.responder(RespuestaFalsa(200, {"pagos": []}), RespuestaFalsa(200, {"facturas": [vigente]}))
    assert '"folio_inicial": ""' in html(modo_real.get('/pagos?folio="><script>'))


def test_sin_backend_se_avisa_que_no_se_puede_escribir(modo_real, red):
    """Si la lista carga pero falla el catálogo de servicios, no se ofrece emitir."""
    from test_integracion import CLIENTE, FACTURA
    red.responder(RespuestaFalsa(200, {"facturas": [FACTURA]}),
                  RespuestaFalsa(200, {"clientes": [CLIENTE]}),
                  RespuestaFalsa(403, {"message": "Forbidden"}))
    pagina = html(modo_real.get("/facturas"))
    assert "No se podrán emitir facturas por ahora" in pagina
    assert 'data-action="nueva-factura"' not in pagina


# ---------------------------------------------------------------------------
# Producción
# ---------------------------------------------------------------------------

def test_salud_es_publica(sin_sesion):
    r = sin_sesion.get("/salud")
    assert r.status_code == 200 and r.get_json() == {"estado": "ok"}


def test_validar_produccion_detecta_configuracion_insegura(monkeypatch):
    import app as sifat
    for nombre in ("SECRET_KEY", "API_KEY", "BACKEND_URL"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setattr(sifat, "USE_MOCK", True)
    monkeypatch.setitem(sifat.app.config, "SESSION_COOKIE_SECURE", False)
    problemas = " | ".join(sifat.validar_produccion())
    for texto in ("SECRET_KEY", "USE_MOCK", "SESSION_COOKIE_SECURE", "FLASK_DEBUG",
                  "Falta API_KEY", "Falta BACKEND_URL"):
        assert texto in problemas


def test_validar_produccion_acepta_configuracion_correcta(monkeypatch):
    import app as sifat
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("FLASK_DEBUG", "false")
    for nombre in ("API_BASE_URL", "API_KEY", "BACKEND_URL", "BACKEND_API_KEY"):
        monkeypatch.setenv(nombre, "valor")
    monkeypatch.setattr(sifat, "USE_MOCK", False)
    monkeypatch.setitem(sifat.app.config, "SESSION_COOKIE_SECURE", True)
    assert sifat.validar_produccion() == []


def test_hsts_solo_con_https(modo_real, monkeypatch):
    import app as sifat
    assert "Strict-Transport-Security" not in modo_real.get("/salud").headers
    monkeypatch.setitem(sifat.app.config, "SESSION_COOKIE_SECURE", True)
    assert "max-age=31536000" in modo_real.get("/salud").headers["Strict-Transport-Security"]
