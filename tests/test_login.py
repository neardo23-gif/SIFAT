"""Inicio de sesión, cierre de sesión, pantallas protegidas y permisos por rol."""
import pytest

from conftest import ADMIN, CSRF, RespuestaFalsa, con_csrf, html

FACTURISTA = {**ADMIN, "id_usuario": 2, "nombre": "Luis Perez", "rol": "Facturista"}


@pytest.mark.parametrize("ruta", ["/catalogo", "/facturas", "/clientes", "/pagos"])
def test_pantallas_piden_sesion(sin_sesion, red, ruta):
    r = sin_sesion.get(ruta)
    assert r.status_code == 302 and "#acceso" in r.headers["Location"]
    assert red.llamadas == []


def test_api_sin_sesion_responde_401(sin_sesion, red):
    r = sin_sesion.post("/api/servicios", json={"id_servicio": "SRV-001"})
    assert r.status_code == 401
    assert red.llamadas == []


def test_portada_es_publica(sin_sesion):
    assert sin_sesion.get("/").status_code == 200


def test_login_correcto_crea_sesion(sin_sesion, red):
    red.responder(RespuestaFalsa(200, ADMIN))
    r = sin_sesion.post("/login", data={"email": "Ana.Lopez@sifat.mx", "password": "ClaveSegura2026",
                                        "csrf_token": CSRF})
    assert r.status_code == 302 and r.headers["Location"].endswith("/catalogo")
    assert red.llamadas[0]["json"] == {"email": "ana.lopez@sifat.mx", "password": "ClaveSegura2026"}
    assert red.llamadas[0]["headers"] == {"X-API-Key": "clave-backend-prueba"}
    with sin_sesion.session_transaction() as s:
        assert s["usuario"]["rol"] == "Administrador"
        assert s["csrf"] != CSRF  # token nuevo al iniciar sesión


def test_login_incorrecto_muestra_error(sin_sesion, red):
    red.responder(RespuestaFalsa(401, {"mensaje": "Correo o contraseña incorrectos"}))
    r = sin_sesion.post("/login", data={"email": "ana@sifat.mx", "password": "mala", "csrf_token": CSRF})
    assert r.status_code == 401
    assert "Correo o contraseña incorrectos" in html(r)
    with sin_sesion.session_transaction() as s:
        assert "usuario" not in s


def test_login_sin_csrf_se_rechaza(sin_sesion, red):
    sin_sesion.environ_base.pop("HTTP_X_CSRF_TOKEN")
    r = sin_sesion.post("/login", data={"email": "ana@sifat.mx", "password": "x"})
    assert r.status_code == 403
    assert red.llamadas == []


def test_limite_de_intentos_por_ip(sin_sesion, red):
    for _ in range(10):
        red.responder(RespuestaFalsa(401, {"mensaje": "Correo o contraseña incorrectos"}))
        sin_sesion.post("/login", data={"email": "ana@sifat.mx", "password": "mala", "csrf_token": CSRF})
    r = sin_sesion.post("/login", data={"email": "ana@sifat.mx", "password": "mala", "csrf_token": CSRF})
    assert r.status_code == 429
    assert len(red.llamadas) == 10


def test_logout_borra_la_sesion(modo_real):
    r = modo_real.post("/logout", data={"csrf_token": CSRF})
    assert r.status_code == 302
    with modo_real.session_transaction() as s:
        assert "usuario" not in s


def test_facturista_no_puede_modificar_catalogo(sin_sesion, red):
    cliente = con_csrf(sin_sesion, usuario=FACTURISTA)
    r = cliente.post("/api/servicios", json={"id_servicio": "SRV-001", "impuesto_clave": "IVA|0.1600|traslado"})
    assert r.status_code == 403
    assert red.llamadas == []


def test_facturista_no_ve_botones_de_edicion(sin_sesion, red):
    cliente = con_csrf(sin_sesion, usuario=FACTURISTA)
    red.responder(RespuestaFalsa(200, {"servicios": [], "siguiente": None}))
    pagina = html(cliente.get("/catalogo"))
    assert 'data-action="nuevo"' not in pagina and 'data-action="editar"' not in pagina


def test_cabeceras_de_seguridad(modo_mock):
    r = modo_mock.get("/catalogo")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
