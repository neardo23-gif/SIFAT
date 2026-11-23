"""Mi cuenta: cualquier usuario cambia su propia contraseña (debe escribir la actual)."""
from flask import Blueprint, jsonify, render_template

import backend
import seguridad
from rutas.comun import JSON_INVALIDO, contexto_base, json_objeto

bp = Blueprint("cuenta", __name__)


@bp.route("/cuenta")
def pantalla():
    return render_template("cuenta.html", error=None, aviso=None, **contexto_base("cuenta"))


@bp.route("/api/cuenta/contrasena", methods=["POST"])
def api_cambiar_contrasena():
    if not seguridad.csrf_valido():
        return jsonify({"mensaje": "Sesión inválida o expirada. Recarga la página."}), 403
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    actual, nueva, confirmacion = cuerpo.get("actual"), cuerpo.get("nueva"), cuerpo.get("confirmacion")
    if not isinstance(actual, str) or not actual:
        return jsonify({"mensaje": "Escribe tu contraseña actual"}), 400
    if not isinstance(nueva, str) or not nueva:
        return jsonify({"mensaje": "Escribe la contraseña nueva"}), 400
    if nueva != confirmacion:
        return jsonify({"mensaje": "Las contraseñas nuevas no coinciden"}), 400
    # Qué usuario cambia lo decide la sesión, nunca el navegador
    return backend.proxy_backend("POST", "/auth/cambiar-contrasena", {
        "id_usuario": seguridad.usuario_actual()["id_usuario"], "actual": actual, "nueva": nueva})
