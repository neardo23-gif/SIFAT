"""Sesión, permisos por rol, protección CSRF, límite de intentos y cabeceras seguras."""
import hmac
import secrets
import time
from collections import defaultdict, deque

from flask import current_app, jsonify, redirect, request, session, url_for

# Lo que se puede abrir sin iniciar sesión (nombres de endpoint de Flask)
RUTAS_PUBLICAS = {"auth.portada", "auth.login", "auth.salud", "static"}

ADMIN, FACTURISTA = "Administrador", "Facturista"

# Qué puede hacer cada rol. Lo que deshace o borra trabajo (cancelar facturas,
# desactivar clientes) y el catálogo quedan solo para el Administrador.
PERMISOS = {
    "editar_catalogo": {ADMIN},
    "crear_cliente": {ADMIN, FACTURISTA},
    "editar_cliente": {ADMIN, FACTURISTA},
    "desactivar_cliente": {ADMIN},
    "emitir_factura": {ADMIN, FACTURISTA},
    "cancelar_factura": {ADMIN},
    "registrar_pago": {ADMIN, FACTURISTA},
    "administrar_usuarios": {ADMIN},
}


# ---------------- Sesión y permisos ----------------
def usuario_actual():
    return session.get("usuario")


def puede(accion):
    usuario = usuario_actual()
    return bool(usuario) and usuario.get("rol") in PERMISOS.get(accion, set())


# ---------------- CSRF ----------------
def token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_valido():
    enviado = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    guardado = session.get("csrf", "")
    return bool(enviado and guardado and hmac.compare_digest(enviado, guardado))


def rechazo(accion, texto):
    """Para rutas que escriben: valida CSRF y permiso. Devuelve la respuesta de error o None."""
    if not csrf_valido():
        return jsonify({"mensaje": "Sesión inválida o expirada. Recarga la página."}), 403
    if not puede(accion):
        return jsonify({"mensaje": texto}), 403
    return None


# ---------------- Límite de intentos de login por IP ----------------
# Además del bloqueo por cuenta que hace el backend. Vive en memoria: por eso
# gunicorn corre con un solo proceso (ver gunicorn.conf.py).
INTENTOS_POR_IP = 10
VENTANA_SEGUNDOS = 15 * 60
_intentos_ip = defaultdict(deque)


def demasiados_intentos(ip):
    ahora = time.monotonic()
    cola = _intentos_ip[ip]
    while cola and ahora - cola[0] > VENTANA_SEGUNDOS:
        cola.popleft()
    if len(cola) >= INTENTOS_POR_IP:
        return True
    cola.append(ahora)
    return False


# ---------------- Ganchos de la app ----------------
def exigir_sesion():
    if request.endpoint in RUTAS_PUBLICAS or request.endpoint is None:
        return None
    if usuario_actual():
        return None
    if request.path.startswith("/api/"):
        return jsonify({"mensaje": "Inicia sesión para continuar"}), 401
    return redirect(url_for("auth.portada", _anchor="acceso"))


def cabeceras_seguras(respuesta):
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    if current_app.config["SESSION_COOKIE_SECURE"]:
        # El navegador recordará usar solo HTTPS durante un año
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if usuario_actual():
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def instalar(app):
    app.before_request(exigir_sesion)
    app.after_request(cabeceras_seguras)
    app.jinja_env.globals.update(usuario_actual=usuario_actual, puede=puede, csrf_token=token_csrf)
