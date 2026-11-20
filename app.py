"""SIFAT - Front (Flask).

Arma la aplicación: configuración, seguridad y las rutas de cada pantalla.
  config.py     variables de entorno y validación para producción
  seguridad.py  sesión, permisos por rol, CSRF, límite de intentos, cabeceras
  backend.py    llamadas al backend (MySQL) y a API Gateway (catálogo)
  rutas/        un Blueprint por pantalla

Desarrollo:  python app.py        Producción:  gunicorn -c gunicorn.conf.py app:app
"""
import logging
import secrets
from datetime import timedelta

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

import config
import seguridad
from rutas import BLUEPRINTS
from rutas.comun import mxn

log = logging.getLogger("sifat-front")

if config.PRODUCCION:
    _problemas = config.validar_produccion()
    if _problemas:
        raise RuntimeError("Configuración insegura para producción: " + "; ".join(_problemas))

app = Flask(__name__)
app.secret_key = config.SECRET_KEY or secrets.token_hex(32)
if not config.SECRET_KEY:
    log.warning("SECRET_KEY no está en .env: se generó una temporal (las sesiones se reinician al reiniciar).")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

# Detrás de nginx/CloudFront la IP real llega en X-Forwarded-For. Solo se confía
# en esa cabecera si se indica, porque sin proxy cualquiera podría falsificarla.
if config.TRUST_PROXY:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

seguridad.instalar(app)
app.add_template_filter(mxn, "mxn")
for bp in BLUEPRINTS:
    app.register_blueprint(bp)


@app.errorhandler(404)
@app.errorhandler(405)
def error_http(err):
    # En /api/ siempre se responde JSON, nunca la página HTML de Flask
    if request.path.startswith("/api/"):
        return jsonify({"mensaje": "Método no permitido" if err.code == 405 else "Ruta no encontrada"}), err.code
    return err


if __name__ == "__main__":
    # El depurador de Flask permite ejecutar código: solo se activa a propósito
    # En macOS el puerto 5000 lo ocupa el Receptor AirPlay: usa PORT=5001
    app.run(debug=config.FLASK_DEBUG, port=config.PORT)
