"""Portada, inicio y cierre de sesión, y comprobación de vida."""
import secrets

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

import backend
import seguridad

bp = Blueprint("auth", __name__)


@bp.route("/")
def portada():
    return render_template("landing.html")


@bp.route("/login", methods=["POST"])
def login():
    if not seguridad.csrf_valido():
        return render_template("landing.html", error_login="Tu sesión expiró. Vuelve a intentarlo."), 403
    if seguridad.demasiados_intentos(request.remote_addr or "?"):
        return render_template("landing.html", error_login="Demasiados intentos. Espera 15 minutos."), 429
    email = request.form.get("email", "").strip().lower()[:120]
    password = request.form.get("password", "")[:128]
    if not email or not password:
        return render_template("landing.html", error_login="Escribe tu correo y contraseña.", email=email), 400
    usuario, error = backend.autenticar(email, password)
    if error:
        return render_template("landing.html", error_login=error, email=email), 401
    # Sesión nueva tras iniciar sesión: evita reutilizar una cookie anterior
    session.clear()
    session.permanent = True
    session["usuario"] = {k: usuario[k] for k in ("id_usuario", "nombre", "email", "rol")}
    session["csrf"] = secrets.token_urlsafe(32)
    return redirect(url_for("catalogo.pantalla"))


@bp.route("/logout", methods=["POST"])
def logout():
    if seguridad.csrf_valido():
        session.clear()
    return redirect(url_for("auth.portada"))


@bp.route("/salud")
def salud():
    """Comprobación de vida para CloudFront o el monitoreo (no consulta nada)."""
    return jsonify({"estado": "ok"})
