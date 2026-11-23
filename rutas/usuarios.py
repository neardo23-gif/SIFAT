"""Usuarios de la app: solo un Administrador los ve y los da de alta."""
import re

from flask import Blueprint, jsonify, redirect, render_template, url_for

import backend
import seguridad
from rutas.comun import JSON_INVALIDO, contexto_base, fecha_corta, json_objeto

bp = Blueprint("usuarios", __name__)

ROLES = ["Facturista", "Administrador"]
CAMPOS = {"nombre", "apellidos", "email", "password", "confirmacion", "rol"}


@bp.route("/usuarios")
def pantalla():
    if not seguridad.puede("administrar_usuarios"):
        return redirect(url_for("catalogo.pantalla"))
    datos, error = backend.consultar_backend("/usuarios", "usuarios")
    filas = [{"id": u["id_usuario"], "nombre": u["nombre"], "email": u["email"], "rol": u["rol"],
              "activo": u["activo"], "tiene_contrasena": u.get("tiene_contrasena", False),
              "ultimo_acceso": fecha_corta(u["ultimo_acceso"]) if u.get("ultimo_acceso") else "Nunca"}
             for u in datos]
    return render_template("usuarios.html", usuarios=filas, roles=ROLES, error=error, aviso=None,
                           yo=seguridad.usuario_actual()["id_usuario"], **contexto_base("usuarios"))


def _espacios(texto):
    """'  María   José ' -> 'María José'."""
    return re.sub(r"\s+", " ", texto).strip() if isinstance(texto, str) else texto


@bp.route("/api/usuarios", methods=["POST"])
def api_crear():
    error = seguridad.rechazo("administrar_usuarios", "Solo un Administrador puede registrar usuarios.")
    if error:
        return error
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    datos = {k: v for k, v in cuerpo.items() if k in CAMPOS}

    # La confirmación se revisa aquí y no viaja al backend
    password, problema = _par_de_contrasenas(datos)
    datos.pop("password", None), datos.pop("confirmacion", None)
    if problema:
        return jsonify({"mensaje": problema}), 400
    if datos.get("rol") not in ROLES:
        return jsonify({"mensaje": "Elige un rol válido"}), 400

    datos["nombre"] = _espacios(datos.get("nombre"))
    datos["apellidos"] = _espacios(datos.get("apellidos"))
    if isinstance(datos.get("email"), str):
        datos["email"] = datos["email"].strip().lower()
    datos["password"] = password
    return backend.proxy_backend("POST", "/usuarios", datos)


def _par_de_contrasenas(cuerpo, campo="password"):
    """Revisa que la contraseña exista y coincida con su confirmación. Devuelve (password, error)."""
    password, confirmacion = cuerpo.get(campo), cuerpo.get("confirmacion")
    if not isinstance(password, str) or not password:
        return None, "Escribe una contraseña"
    if password != confirmacion:
        return None, "Las contraseñas no coinciden"
    return password, None


@bp.route("/api/usuarios/<int:id_usuario>", methods=["PATCH"])
def api_modificar(id_usuario):
    error = seguridad.rechazo("administrar_usuarios", "Solo un Administrador puede modificar usuarios.")
    if error:
        return error
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    datos = {k: v for k, v in cuerpo.items() if k in {"activo", "rol"}}
    if "activo" in datos and not isinstance(datos["activo"], bool):
        return jsonify({"mensaje": "El estado no es válido"}), 400
    if "rol" in datos and datos["rol"] not in ROLES:
        return jsonify({"mensaje": "Elige un rol válido"}), 400
    if not datos:
        return jsonify({"mensaje": "No hay cambios que guardar"}), 400
    # Uno mismo no se desactiva ni se quita el rol: evita quedarse fuera por accidente
    if id_usuario == seguridad.usuario_actual()["id_usuario"]:
        return jsonify({"mensaje": "No puedes desactivarte ni cambiar tu propio rol"}), 400
    return backend.proxy_backend("PATCH", f"/usuarios/{id_usuario}", datos)


@bp.route("/api/usuarios/<int:id_usuario>/contrasena", methods=["POST"])
def api_restablecer(id_usuario):
    error = seguridad.rechazo("administrar_usuarios", "Solo un Administrador puede restablecer contraseñas.")
    if error:
        return error
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    password, problema = _par_de_contrasenas(cuerpo)
    if problema:
        return jsonify({"mensaje": problema}), 400
    return backend.proxy_backend("POST", f"/usuarios/{id_usuario}/contrasena", {"password": password})
