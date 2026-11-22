"""Alta de usuarios desde el panel: solo Administrador, validación y lo que llega al backend."""
import pytest

from conftest import RespuestaFalsa, html

NUEVO = {"nombre": "  María   José ", "apellidos": "Pérez  López", "email": " MJ.Perez@Sifat.MX ",
         "rol": "Facturista", "password": "Facturas2026xyz", "confirmacion": "Facturas2026xyz"}
USUARIO = {"id_usuario": 9, "nombre": "María José Pérez López", "email": "mj.perez@sifat.mx",
           "rol": "Facturista", "activo": True, "ultimo_acceso": None, "tiene_contrasena": True}


def test_admin_registra_usuario(modo_real, red):
    red.responder(RespuestaFalsa(201, USUARIO))
    r = modo_real.post("/api/usuarios", json={**NUEVO, "activo": False, "id_usuario": 1})
    assert r.status_code == 201 and r.get_json()["email"] == "mj.perez@sifat.mx"
    llamada = red.llamadas[0]
    assert (llamada["metodo"], llamada["url"]) == ("POST", "http://backend.test/usuarios")
    # Espacios normalizados, correo en minúsculas, sin confirmación ni campos ajenos
    assert llamada["json"] == {"nombre": "María José", "apellidos": "Pérez López",
                               "email": "mj.perez@sifat.mx", "rol": "Facturista",
                               "password": "Facturas2026xyz"}


@pytest.mark.parametrize("cambio, mensaje", [
    ({"confirmacion": "Otra2026clave"}, "no coinciden"),
    ({"password": "", "confirmacion": ""}, "Escribe una contraseña"),
    ({"password": None}, "Escribe una contraseña"),
    ({"rol": "Gerente"}, "rol válido"),
    ({"rol": None}, "rol válido"),
])
def test_validaciones_antes_de_llamar_al_backend(modo_real, red, cambio, mensaje):
    r = modo_real.post("/api/usuarios", json={**NUEVO, **cambio})
    assert r.status_code == 400 and mensaje in r.get_json()["mensaje"]
    assert red.llamadas == []


def test_facturista_no_registra_usuarios(facturista, red):
    assert facturista.post("/api/usuarios", json=NUEVO).status_code == 403
    assert red.llamadas == []


def test_registrar_usuario_exige_csrf(modo_real, red):
    modo_real.environ_base.pop("HTTP_X_CSRF_TOKEN")
    assert modo_real.post("/api/usuarios", json=NUEVO).status_code == 403
    assert red.llamadas == []


def test_registrar_usuario_exige_sesion(sin_sesion, red):
    assert sin_sesion.post("/api/usuarios", json=NUEVO).status_code == 401


def test_errores_del_backend_llegan_en_espanol(modo_real, red):
    red.responder(RespuestaFalsa(409, {"mensaje": "Ya existe un usuario con ese correo"}))
    r = modo_real.post("/api/usuarios", json=NUEVO)
    assert r.status_code == 409 and r.get_json()["mensaje"] == "Ya existe un usuario con ese correo"

    red.responder(RespuestaFalsa(400, {"mensaje": "Datos inválidos", "errores": [
        {"campo": "nombre", "mensaje": "String should match pattern"},
        {"campo": "email", "mensaje": "String should match pattern"}]}))
    r = modo_real.post("/api/usuarios", json=NUEVO)
    assert r.get_json()["mensaje"] == "Revisa estos datos: nombre, correo"


def test_pantalla_de_usuarios_para_admin(modo_real, red):
    red.responder(RespuestaFalsa(200, {"usuarios": [
        USUARIO, {**USUARIO, "id_usuario": 1, "nombre": "Ana Lopez", "rol": "Administrador",
                  "ultimo_acceso": "2026-11-20T10:00:00"}]}))
    pagina = html(modo_real.get("/usuarios"))
    assert "María José Pérez López" in pagina and "20 nov 2026" in pagina and "Nunca" in pagina
    assert 'data-action="nuevo-usuario"' in pagina
    assert "(tú)" in pagina  # Ana es la sesión actual
    assert "js/usuarios.js" in pagina
    assert "password_hash" not in pagina


def test_facturista_no_ve_usuarios(facturista, red):
    r = facturista.get("/usuarios")
    assert r.status_code == 302 and r.headers["Location"].endswith("/catalogo")
    assert red.llamadas == []


def test_menu_muestra_usuarios_solo_al_admin(modo_real, facturista, red):
    red.responder(RespuestaFalsa(200, {"pagos": []}), RespuestaFalsa(200, {"facturas": []}))
    assert 'href="/usuarios"' in html(modo_real.get("/pagos"))
    red.responder(RespuestaFalsa(200, {"pagos": []}), RespuestaFalsa(200, {"facturas": []}))
    assert 'href="/usuarios"' not in html(facturista.get("/pagos"))
