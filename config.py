"""Configuración del front, leída una sola vez del entorno (.env).

Los demás módulos leen los valores como `config.NOMBRE` (no con `from config import`),
así las pruebas pueden cambiarlos con monkeypatch.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _texto(nombre, defecto=""):
    return os.getenv(nombre, defecto).strip()


def _bandera(nombre, defecto="false"):
    return _texto(nombre, defecto).lower() == "true"


# development (por defecto) o production. En producción la app se niega a
# arrancar con una configuración insegura (ver validar_produccion).
APP_ENV = _texto("APP_ENV", "development").lower()
PRODUCCION = APP_ENV == "production"

# Firma la cookie de sesión. Debe venir del .env para que no cambie al reiniciar.
SECRET_KEY = _texto("SECRET_KEY")
# true cuando el sitio se sirve por HTTPS: la cookie solo viaja cifrada y se envía HSTS
SESSION_COOKIE_SECURE = _bandera("SESSION_COOKIE_SECURE")
# true solo detrás de un proxy (nginx/CloudFront) que ponga X-Forwarded-For
TRUST_PROXY = _bandera("TRUST_PROXY")
FLASK_DEBUG = _bandera("FLASK_DEBUG")
PORT = int(_texto("PORT", "5000"))

# Catálogo de servicios: API Gateway + Lambda + DynamoDB. La clave nunca llega al navegador.
API_BASE_URL = _texto("API_BASE_URL").rstrip("/")
API_KEY = _texto("API_KEY")

# Backend propio (repo SIFAT-BACKEND): clientes, facturas y pagos en MySQL
BACKEND_URL = _texto("BACKEND_URL").rstrip("/")
BACKEND_API_KEY = _texto("BACKEND_API_KEY")

# Segundos de espera para cada petición saliente
TIMEOUT = 8


def validar_produccion():
    """Lista de problemas de configuración que impiden servir en producción."""
    problemas = []
    if len(SECRET_KEY) < 32:
        problemas.append("SECRET_KEY debe existir y tener al menos 32 caracteres")
    if not SESSION_COOKIE_SECURE:
        problemas.append("SESSION_COOKIE_SECURE debe ser true (el sitio se sirve por HTTPS)")
    if FLASK_DEBUG:
        problemas.append("FLASK_DEBUG debe ser false")
    for nombre in ("API_BASE_URL", "API_KEY", "BACKEND_URL", "BACKEND_API_KEY"):
        if not globals()[nombre]:
            problemas.append(f"Falta {nombre}")
    return problemas
