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


# ---------------------------------------------------------------------------
# Desactivar, restablecer contraseña y Mi cuenta
# ---------------------------------------------------------------------------

def test_admin_desactiva_a_otro_usuario(modo_real, red):
    red.responder(RespuestaFalsa(200, {**USUARIO, "activo": False}))
    r = modo_real.patch("/api/usuarios/9", json={"activo": False, "email": "otro@x.mx"})
    assert r.status_code == 200
    assert (red.llamadas[0]["url"], red.llamadas[0]["json"]) == ("http://backend.test/usuarios/9", {"activo": False})


def test_admin_no_se_desactiva_a_si_mismo(modo_real, red):
    r = modo_real.patch("/api/usuarios/1", json={"activo": False})
    assert r.status_code == 400 and "propio" in r.get_json()["mensaje"]
    assert red.llamadas == []


@pytest.mark.parametrize("cuerpo", [{"activo": "no"}, {"rol": "Gerente"}, {}, {"nombre": "X"}])
def test_modificar_usuario_valida_en_el_front(modo_real, red, cuerpo):
    assert modo_real.patch("/api/usuarios/9", json=cuerpo).status_code == 400
    assert red.llamadas == []


def test_ultimo_admin_llega_el_mensaje_del_backend(modo_real, red):
    red.responder(RespuestaFalsa(409, {"mensaje": "Debe quedar al menos un Administrador activo"}))
    r = modo_real.patch("/api/usuarios/3", json={"activo": False})
    assert r.status_code == 409 and "al menos un Administrador" in r.get_json()["mensaje"]


def test_admin_restablece_contrasena(modo_real, red):
    red.responder(RespuestaFalsa(200, {"mensaje": "Contraseña actualizada"}))
    r = modo_real.post("/api/usuarios/9/contrasena",
                       json={"password": "OtraClave2027xy", "confirmacion": "OtraClave2027xy", "rol": "x"})
    assert r.status_code == 200
    assert red.llamadas[0]["url"] == "http://backend.test/usuarios/9/contrasena"
    assert red.llamadas[0]["json"] == {"password": "OtraClave2027xy"}


def test_restablecer_exige_confirmacion(modo_real, red):
    r = modo_real.post("/api/usuarios/9/contrasena", json={"password": "OtraClave2027xy", "confirmacion": "x"})
    assert r.status_code == 400 and red.llamadas == []


@pytest.mark.parametrize("metodo, ruta, cuerpo", [
    ("patch", "/api/usuarios/9", {"activo": False}),
    ("post", "/api/usuarios/9/contrasena", {"password": "OtraClave2027xy", "confirmacion": "OtraClave2027xy"}),
])
def test_facturista_no_administra_usuarios(facturista, red, metodo, ruta, cuerpo):
    assert getattr(facturista, metodo)(ruta, json=cuerpo).status_code == 403
    assert red.llamadas == []


def test_cambiar_mi_contrasena_usa_mi_sesion(facturista, red):
    red.responder(RespuestaFalsa(200, {"mensaje": "Contraseña actualizada"}))
    r = facturista.post("/api/cuenta/contrasena", json={
        "actual": "sifat1234567", "nueva": "MiNuevaClave2027", "confirmacion": "MiNuevaClave2027",
        "id_usuario": 1})
    assert r.status_code == 200
    llamada = red.llamadas[0]
    assert llamada["url"] == "http://backend.test/auth/cambiar-contrasena"
    # El id sale de la sesión (Luis = 2), no del cuerpo que mandó el navegador
    assert llamada["json"] == {"id_usuario": 2, "actual": "sifat1234567", "nueva": "MiNuevaClave2027"}


@pytest.mark.parametrize("cuerpo, mensaje", [
    ({"actual": "", "nueva": "MiNuevaClave2027", "confirmacion": "MiNuevaClave2027"}, "actual"),
    ({"actual": "x", "nueva": "", "confirmacion": ""}, "nueva"),
    ({"actual": "x", "nueva": "MiNuevaClave2027", "confirmacion": "otra"}, "no coinciden"),
])
def test_cambiar_mi_contrasena_valida(facturista, red, cuerpo, mensaje):
    r = facturista.post("/api/cuenta/contrasena", json=cuerpo)
    assert r.status_code == 400 and mensaje in r.get_json()["mensaje"]
    assert red.llamadas == []


def test_contrasena_actual_incorrecta_llega_tal_cual(facturista, red):
    red.responder(RespuestaFalsa(403, {"mensaje": "La contraseña actual no es correcta"}))
    r = facturista.post("/api/cuenta/contrasena",
                        json={"actual": "mala", "nueva": "MiNuevaClave2027", "confirmacion": "MiNuevaClave2027"})
    assert r.status_code == 403 and r.get_json()["mensaje"] == "La contraseña actual no es correcta"


def test_cambiar_mi_contrasena_exige_csrf(facturista, red):
    facturista.environ_base.pop("HTTP_X_CSRF_TOKEN")
    r = facturista.post("/api/cuenta/contrasena",
                        json={"actual": "x", "nueva": "MiNuevaClave2027", "confirmacion": "MiNuevaClave2027"})
    assert r.status_code == 403 and red.llamadas == []


def test_pantalla_mi_cuenta(facturista, red):
    pagina = html(facturista.get("/cuenta"))
    assert "Cambiar mi contraseña" in pagina and "Luis Perez" in pagina and "js/cuenta.js" in pagina


def test_usuarios_muestra_acciones_menos_para_mi(modo_real, red):
    red.responder(RespuestaFalsa(200, {"usuarios": [
        USUARIO, {**USUARIO, "id_usuario": 1, "nombre": "Ana Lopez", "rol": "Administrador"}]}))
    pagina = html(modo_real.get("/usuarios"))
    assert 'data-action="restablecer" data-id="9"' in pagina
    assert 'data-action="restablecer" data-id="1"' not in pagina  # a sí misma no
    assert "Mi contraseña" in pagina


def test_acciones_escapan_el_nombre(modo_real, red):
    red.responder(RespuestaFalsa(200, {"usuarios": [{**USUARIO, "nombre": 'X" onclick="alert(1)'}]}))
    pagina = html(modo_real.get("/usuarios"))
    assert 'onclick="alert(1)' not in pagina


# ---------------------------------------------------------------------------
# Revalidación de la sesión: un usuario desactivado pierde el acceso
# ---------------------------------------------------------------------------

def _caducar(cliente):
    with cliente.session_transaction() as s:
        s["verificado"] = 0  # fuerza la revalidación en la siguiente petición


def test_usuario_desactivado_pierde_la_sesion(facturista, red):
    _caducar(facturista)
    red.responder(RespuestaFalsa(200, {**USUARIO, "id_usuario": 2, "activo": False}))
    r = facturista.get("/cuenta")
    assert r.status_code == 302 and "#acceso" in r.headers["Location"]
    assert red.llamadas[0]["url"] == "http://backend.test/usuarios/2"
    with facturista.session_transaction() as s:
        assert "usuario" not in s


def test_usuario_eliminado_pierde_la_sesion(facturista, red):
    _caducar(facturista)
    red.responder(RespuestaFalsa(404, {"mensaje": "Usuario no encontrado"}))
    assert facturista.get("/cuenta").status_code == 302


def test_cambio_de_rol_se_aplica_sin_volver_a_entrar(facturista, red):
    _caducar(facturista)
    red.responder(RespuestaFalsa(200, {**USUARIO, "id_usuario": 2, "rol": "Administrador", "activo": True}))
    assert facturista.get("/cuenta").status_code == 200
    with facturista.session_transaction() as s:
        assert s["usuario"]["rol"] == "Administrador" and s["verificado"] > 0


def test_si_el_backend_no_responde_no_se_saca_a_nadie(facturista, red):
    import requests
    _caducar(facturista)
    red.responder(requests.ConnectionError("apagado"))
    assert facturista.get("/cuenta").status_code == 200


def test_no_se_revalida_en_cada_peticion(facturista, red):
    assert facturista.get("/cuenta").status_code == 200
    assert red.llamadas == []  # recién verificado: no pregunta al backend
