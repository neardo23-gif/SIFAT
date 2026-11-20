"""SIFAT - Front (Flask).

Consume el servicio /servicios de API Gateway (Lambda + DynamoDB).
Con USE_MOCK=true trabaja con datos en memoria para desarrollar sin red.
"""
import copy
import hmac
import logging
import os
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from flask import (Flask, Response, jsonify, redirect, render_template, request, session,
                   url_for)
from werkzeug.middleware.proxy_fix import ProxyFix

from mock_data import CLIENTES, FACTURAS, IVA, PAGOS, SERVICIOS

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

load_dotenv()

log = logging.getLogger("sifat-front")


def _bandera(nombre, defecto="false"):
    return os.getenv(nombre, defecto).strip().lower() == "true"


# development (por defecto) o production. En producción la app se niega a
# arrancar con una configuración insegura (ver validar_produccion).
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
PRODUCCION = APP_ENV == "production"

app = Flask(__name__)
# Firma la cookie de sesión (token CSRF). Debe venir del .env para que no cambie al reiniciar.
app.secret_key = os.getenv("SECRET_KEY", "").strip() or secrets.token_hex(32)
if not os.getenv("SECRET_KEY", "").strip():
    log.warning("SECRET_KEY no está en .env: se generó una temporal (las sesiones se reinician al reiniciar).")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    # true cuando el sitio se sirva por HTTPS (en producción)
    SESSION_COOKIE_SECURE=_bandera("SESSION_COOKIE_SECURE"),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

# Detrás de nginx: la IP real del visitante llega en X-Forwarded-For. Solo se
# confía en esa cabecera si se indica, porque sin proxy cualquiera podría falsificarla.
if _bandera("TRUST_PROXY"):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Sin valores por defecto: cada entorno define sus URLs en .env
API_BASE_URL = os.getenv("API_BASE_URL", "").strip().rstrip("/")
# Por defecto se usan los servicios reales; los datos de ejemplo solo si se piden
USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"
# La clave solo vive en el servidor: el navegador nunca la ve.
API_KEY = os.getenv("API_KEY", "").strip()
TIMEOUT = 8

# Backend propio (repo SIFAT-BACKEND): clientes, facturas y pagos en MySQL
BACKEND_URL = os.getenv("BACKEND_URL", "").strip().rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "").strip()
# Campos de un servicio que el navegador puede enviar. Todo lo demás se descarta,
# y el impuesto lo pone el servidor a partir del catálogo de impuestos (MySQL).
CAMPOS_SERVICIO = {"id_servicio", "clave", "nombre", "descripcion", "categoria",
                   "precio_unitario", "unidad_medida", "activo", "caracteristicas"}
UNIDADES = ["Servicio", "Mes", "Ano", "Hora", "Pieza"]

LIMITE_PAGINA = 50  # máximo que acepta la Lambda por página
MAX_PAGINAS = 20  # tope de seguridad: hasta 1000 servicios por carga

# Mensajes para los errores que genera API Gateway (no las Lambdas)
ERRORES_GATEWAY = {
    403: "API Gateway rechazó la petición: falta la clave de acceso o no es válida (revisa API_KEY).",
    429: "Se superó el límite de peticiones. Espera unos segundos e inténtalo de nuevo.",
}

_mock_store = {s["id_servicio"]: copy.deepcopy(s) for s in SERVICIOS}


def validar_produccion():
    """Lista de problemas de configuración que impiden servir en producción."""
    problemas = []
    if len(os.getenv("SECRET_KEY", "").strip()) < 32:
        problemas.append("SECRET_KEY debe existir y tener al menos 32 caracteres")
    if USE_MOCK:
        problemas.append("USE_MOCK debe ser false")
    if not app.config["SESSION_COOKIE_SECURE"]:
        problemas.append("SESSION_COOKIE_SECURE debe ser true (el sitio se sirve por HTTPS)")
    if _bandera("FLASK_DEBUG"):
        problemas.append("FLASK_DEBUG debe ser false")
    for nombre in ("API_BASE_URL", "API_KEY", "BACKEND_URL", "BACKEND_API_KEY"):
        if not os.getenv(nombre, "").strip():
            problemas.append(f"Falta {nombre}")
    return problemas


if PRODUCCION:
    _problemas = validar_produccion()
    if _problemas:
        raise RuntimeError("Configuración insegura para producción: " + "; ".join(_problemas))


@app.template_filter("mxn")
def mxn(value):
    try:
        return "${:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return "-"


def _headers_api():
    return {"x-api-key": API_KEY}


def listar_servicios():
    """Devuelve (servicios, error). Nunca lanza: el front muestra el error.

    La Lambda responde por páginas; aquí se recorren todas (con un tope) e
    incluye los servicios dados de baja para mostrarlos como inactivos.
    """
    if USE_MOCK:
        items = list(_mock_store.values())
    elif not API_KEY or not API_BASE_URL:
        return [], "Falta configurar API_KEY o API_BASE_URL en el archivo .env."
    else:
        items, siguiente = [], None
        try:
            for _ in range(MAX_PAGINAS):
                params = {"limite": LIMITE_PAGINA, "incluir_inactivos": "true"}
                if siguiente:
                    params["siguiente"] = siguiente
                r = requests.get(f"{API_BASE_URL}/servicios", params=params,
                                 headers=_headers_api(), timeout=TIMEOUT)
                if r.status_code in ERRORES_GATEWAY:
                    return [], ERRORES_GATEWAY[r.status_code]
                r.raise_for_status()
                data = r.json()
                items.extend(data.get("servicios", []))
                siguiente = data.get("siguiente")
                if not siguiente:
                    break
        except (requests.RequestException, ValueError) as exc:
            return [], f"No se pudo consultar API Gateway ({exc.__class__.__name__})."
    items.sort(key=lambda s: s.get("id_servicio", ""))
    return items, None


def contexto_base(active):
    origen = "API Gateway" if active == "catalogo" else "Backend (MySQL)"
    return {
        "active": active,
        "origen": "Datos de ejemplo" if USE_MOCK else origen,
        "usa_mock": USE_MOCK,
    }


def _fecha(valor):
    """'2026-10-14T18:30:00' -> '14 oct 2026'."""
    try:
        anio, mes, dia = str(valor)[:10].split("-")
        return f"{int(dia):02d} {MESES[int(mes) - 1]} {anio}"
    except (ValueError, IndexError):
        return "-"


def consultar_backend(ruta, llave, **filtros):
    """Devuelve (lista, error). Nunca lanza: la pantalla muestra el error.

    llave=None devuelve el JSON completo (por ejemplo, todos los catálogos).
    """
    if not BACKEND_API_KEY or not BACKEND_URL:
        return [], "Falta configurar BACKEND_URL o BACKEND_API_KEY en el archivo .env."
    try:
        r = requests.get(f"{BACKEND_URL}{ruta}", params={"limite": 200, **filtros},
                         headers={"X-API-Key": BACKEND_API_KEY}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return [], f"No se pudo contactar al backend en {BACKEND_URL} ({exc.__class__.__name__}). ¿Está encendido?"
    if r.status_code == 401:
        return [], "El backend rechazó la clave: revisa que BACKEND_API_KEY sea igual en ambos .env."
    if r.status_code != 200:
        return [], f"El backend respondió {r.status_code}."
    try:
        datos = r.json()
        return (datos if llave is None else datos.get(llave, [])), None
    except ValueError:
        return [], "El backend devolvió una respuesta inválida."


def catalogos_sat():
    """Devuelve (catálogos, error): regímenes, usos de CFDI, formas y métodos de pago."""
    vacio = {"regimenes": [], "usos-cfdi": [], "formas-pago": [], "metodos-pago": []}
    if USE_MOCK:
        return vacio, None
    datos, error = consultar_backend("/catalogos", None)
    if error or not isinstance(datos, dict):
        return vacio, error or "El backend devolvió catálogos inválidos."
    return {k: datos.get(k, []) for k in vacio}, None


# ---------------- Sesión y permisos ----------------
RUTAS_PUBLICAS = {"landing", "login", "static", "salud"}
ROL_EDITA_CATALOGO = "Administrador"
ADMIN, FACTURISTA = "Administrador", "Facturista"

# Qué puede hacer cada rol. Lo que deshace o borra trabajo (cancelar facturas,
# desactivar clientes) queda solo para el Administrador.
PERMISOS = {
    "crear_cliente": {ADMIN, FACTURISTA},
    "editar_cliente": {ADMIN, FACTURISTA},
    "desactivar_cliente": {ADMIN},
    "emitir_factura": {ADMIN, FACTURISTA},
    "cancelar_factura": {ADMIN},
    "registrar_pago": {ADMIN, FACTURISTA},
}


def usuario_actual():
    return session.get("usuario")


def puede(accion):
    usuario = usuario_actual()
    return bool(usuario) and usuario.get("rol") in PERMISOS.get(accion, set())


app.jinja_env.globals["usuario_actual"] = usuario_actual
app.jinja_env.globals["puede"] = puede


@app.before_request
def exigir_sesion():
    if request.endpoint in RUTAS_PUBLICAS or request.endpoint is None:
        return None
    if usuario_actual():
        return None
    if request.path.startswith("/api/"):
        return jsonify({"mensaje": "Inicia sesión para continuar"}), 401
    return redirect(url_for("landing", _anchor="acceso"))


@app.after_request
def cabeceras_seguras(respuesta):
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    if app.config["SESSION_COOKIE_SECURE"]:
        # El navegador recordará usar solo HTTPS durante un año
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if usuario_actual():
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# Límite por IP además del bloqueo por cuenta del backend
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


def autenticar(email, password):
    """Devuelve (usuario, error)."""
    if USE_MOCK:
        return None, "El inicio de sesión necesita el backend: pon USE_MOCK=false."
    if not BACKEND_URL or not BACKEND_API_KEY:
        return None, "Falta configurar BACKEND_URL o BACKEND_API_KEY en el archivo .env."
    try:
        r = requests.post(f"{BACKEND_URL}/auth/login", json={"email": email, "password": password},
                          headers={"X-API-Key": BACKEND_API_KEY}, timeout=TIMEOUT)
    except requests.RequestException:
        return None, "No se pudo contactar al servidor. Intenta más tarde."
    if r.status_code == 200:
        return r.json(), None
    if r.status_code in (401, 423):
        return None, r.json().get("mensaje", "Correo o contraseña incorrectos")
    if r.status_code == 400:
        return None, "Correo o contraseña incorrectos"
    return None, "No se pudo iniciar sesión. Intenta más tarde."


# ---------------- Protección CSRF ----------------
def token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = token_csrf


def csrf_valido():
    enviado = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    guardado = session.get("csrf", "")
    return bool(enviado and guardado and hmac.compare_digest(enviado, guardado))


@app.errorhandler(404)
@app.errorhandler(405)
def error_http(err):
    # En /api/ siempre se responde JSON, nunca la página HTML de Flask
    if request.path.startswith("/api/"):
        return jsonify({"mensaje": "Método no permitido" if err.code == 405 else "Ruta no encontrada"}), err.code
    return err


# ---------------- Impuestos (catálogo del backend) ----------------
def _clave_impuesto(i):
    return f"{i['nombre']}|{float(i['tasa']):.4f}|{i['tipo']}"


def listar_impuestos():
    """Devuelve (impuestos, error). Cada uno trae 'clave', 'nombre', 'tasa', 'tipo', 'etiqueta'."""
    if USE_MOCK:
        datos, error = [IVA], None
    else:
        datos, error = consultar_backend("/catalogos", "impuestos")
    impuestos = [{**i, "tasa": float(i["tasa"]), "clave": _clave_impuesto(i),
                  "etiqueta": f"{i['nombre']} {float(i['tasa']) * 100:g}% ({i['tipo']})"}
                 for i in datos]
    return impuestos, error


def limpiar_servicio(cuerpo, es_alta):
    """Deja solo los campos permitidos y resuelve el impuesto en el servidor.

    Devuelve (servicio, error). El navegador elige un impuesto por su clave, pero
    nunca manda la tasa: así no puede alterarla desde las herramientas de desarrollo.
    """
    servicio = {k: v for k, v in cuerpo.items() if k in CAMPOS_SERVICIO}
    if "unidad_medida" in servicio and servicio["unidad_medida"] not in UNIDADES:
        return None, "Unidad de medida no permitida"
    clave = cuerpo.get("impuesto_clave")
    if clave is None:
        return (None, "Selecciona un impuesto") if es_alta else (servicio, None)
    impuestos, error = listar_impuestos()
    if error:
        return None, f"No se pudo validar el impuesto: {error}"
    elegido = next((i for i in impuestos if i["clave"] == clave), None)
    if not elegido:
        return None, "El impuesto seleccionado no existe en el catálogo"
    servicio["impuesto"] = {"nombre": elegido["nombre"], "tasa": elegido["tasa"], "tipo": elegido["tipo"]}
    return servicio, None


@app.route("/login", methods=["POST"])
def login():
    if not csrf_valido():
        return render_template("landing.html", error_login="Tu sesión expiró. Vuelve a intentarlo."), 403
    if demasiados_intentos(request.remote_addr or "?"):
        return render_template("landing.html", error_login="Demasiados intentos. Espera 15 minutos."), 429
    email = request.form.get("email", "").strip().lower()[:120]
    password = request.form.get("password", "")[:128]
    if not email or not password:
        return render_template("landing.html", error_login="Escribe tu correo y contraseña.", email=email), 400
    usuario, error = autenticar(email, password)
    if error:
        return render_template("landing.html", error_login=error, email=email), 401
    # Sesión nueva tras iniciar sesión: evita reutilizar una cookie anterior
    session.clear()
    session.permanent = True
    session["usuario"] = {k: usuario[k] for k in ("id_usuario", "nombre", "email", "rol")}
    session["csrf"] = secrets.token_urlsafe(32)
    return redirect(url_for("catalogo"))


@app.route("/logout", methods=["POST"])
def logout():
    if csrf_valido():
        session.clear()
    return redirect(url_for("landing"))


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/catalogo")
def catalogo():
    servicios, error = listar_servicios()
    categorias = sorted({s.get("categoria", "Sin categoria") for s in servicios})
    impuestos, error_impuestos = listar_impuestos()
    if error_impuestos and not error:
        error = f"No se cargaron los impuestos, no podrás guardar servicios: {error_impuestos}"
    return render_template(
        "catalogo.html",
        servicios=servicios,
        categorias=categorias,
        impuestos=impuestos,
        unidades=UNIDADES,
        puede_editar=usuario_actual()["rol"] == ROL_EDITA_CATALOGO,
        error=error,
        **contexto_base("catalogo"),
    )


def _sin_formulario():
    """Contexto de las pantallas cuando no se puede escribir (modo de ejemplo)."""
    return {"catalogos": {"regimenes": [], "usos-cfdi": [], "formas-pago": [], "metodos-pago": []},
            "aviso": None}


@app.route("/facturas")
def facturas():
    if USE_MOCK:
        return render_template("facturas.html", facturas=FACTURAS, clientes_activos=[],
                               servicios_activos=[], **_sin_formulario(), **contexto_base("facturas"))
    datos, error = consultar_backend("/facturas", "facturas")
    filas = [{"folio": f["folio"], "cliente": f["cliente"], "fecha": _fecha(f["fecha_emision"]),
              "subtotal": f["subtotal"], "iva": f["iva"], "total": f["total"],
              "estatus": f["estatus"]} for f in datos]

    # Lo que necesita el formulario de "Nueva factura": clientes activos,
    # servicios activos del catálogo y las claves del SAT.
    clientes_activos, servicios_activos, aviso = [], [], None
    catalogos, error_cat = _sin_formulario()["catalogos"], None
    # Si ni la lista cargó, el backend no responde: no tiene caso pedir más datos
    if puede("emitir_factura") and not error:
        catalogos, error_cat = catalogos_sat()
        crudos, error_cli = consultar_backend("/clientes", "clientes")
        clientes_activos = [{"id_cliente": c["id_cliente"], "razon_social": c["razon_social"],
                             "rfc": c["rfc"]} for c in crudos]
        servicios, error_srv = listar_servicios()
        servicios_activos = [{"id_servicio": s["id_servicio"], "clave": s.get("clave", ""),
                              "nombre": s.get("nombre", ""),
                              "precio_unitario": s.get("precio_unitario", 0),
                              "unidad_medida": s.get("unidad_medida", ""),
                              "tasa": (s.get("impuesto") or {}).get("tasa", 0)}
                             for s in servicios if s.get("activo")]
        problema = error_cat or error_cli or error_srv
        if problema:
            aviso = f"No se podrán emitir facturas por ahora: {problema}"
    return render_template("facturas.html", facturas=filas, error=error, aviso=aviso,
                           catalogos=catalogos, clientes_activos=clientes_activos,
                           servicios_activos=servicios_activos, **contexto_base("facturas"))


@app.route("/clientes")
def clientes():
    if USE_MOCK:
        return render_template("clientes.html", clientes=CLIENTES, **_sin_formulario(),
                               **contexto_base("clientes"))
    datos, error = consultar_backend("/clientes", "clientes", incluir_inactivos="true")
    filas = [{"id": f"CLI-{c['id_cliente']:03d}", "id_cliente": c["id_cliente"],
              "razon_social": c["razon_social"], "rfc": c["rfc"], "cp": c["cp_fiscal"],
              "email": c.get("email") or "-", "email_crudo": c.get("email") or "",
              "telefono": c.get("telefono") or "", "clave_regimen": c.get("clave_regimen", ""),
              "regimen": c.get("regimen", ""), "clave_uso": c.get("clave_uso", ""),
              "uso_cfdi": c.get("uso_cfdi", ""), "activo": c["activo"]}
             for c in datos]
    catalogos, aviso = _sin_formulario()["catalogos"], None
    if (puede("crear_cliente") or puede("editar_cliente")) and not error:
        catalogos, error_cat = catalogos_sat()
        if error_cat:
            aviso = f"No se podrán guardar clientes por ahora: {error_cat}"
    return render_template("clientes.html", clientes=filas, error=error, aviso=aviso,
                           catalogos=catalogos, **contexto_base("clientes"))


@app.route("/pagos")
def pagos():
    if USE_MOCK:
        return render_template("pagos.html", pagos=PAGOS, facturas_vigentes=[], folio_inicial="",
                               **_sin_formulario(), **contexto_base("pagos"))
    datos, error = consultar_backend("/pagos", "pagos")
    filas = [{"id": p["id_pago"], "folio": p["folio"], "fecha": _fecha(p["fecha_pago"]),
              "forma": f"{p['clave_forma_pago']} {p['forma_pago']}", "monto": p["monto"],
              "referencia": p.get("referencia") or "-"} for p in datos]

    vigentes, aviso = [], None
    catalogos, error_cat = _sin_formulario()["catalogos"], None
    if puede("registrar_pago") and not error:
        catalogos, error_cat = catalogos_sat()
        crudas, error_fac = consultar_backend("/facturas", "facturas", estatus="vigente")
        vigentes = [{"folio": f["folio"], "cliente": f["cliente"], "total": f["total"]} for f in crudas]
        problema = error_cat or error_fac
        if problema:
            aviso = f"No se podrán registrar pagos por ahora: {problema}"
    # /pagos?folio=FAC-0001 abre el formulario con esa factura elegida
    folio = request.args.get("folio", "")
    folio_inicial = folio if FOLIO_RE.match(folio) else ""
    return render_template("pagos.html", pagos=filas, error=error, aviso=aviso,
                           catalogos=catalogos, facturas_vigentes=vigentes,
                           folio_inicial=folio_inicial, **contexto_base("pagos"))


@app.route("/salud")
def salud():
    """Comprobación de vida para el balanceador o el monitoreo (no consulta nada)."""
    return jsonify({"estado": "ok"})


# ---------------- Escrituras hacia el backend (clientes, facturas, pagos) ----------------
FOLIO_RE = re.compile(r"^FAC-\d{4,10}$")
CAMPOS_CLIENTE = {"rfc", "razon_social", "cp_fiscal", "clave_regimen", "clave_uso", "email", "telefono"}
CAMPOS_CLIENTE_CAMBIO = (CAMPOS_CLIENTE - {"rfc"}) | {"activo"}
OPCIONALES_CLIENTE = {"email", "telefono"}
CAMPOS_PAGO = {"folio", "clave_forma_pago", "monto", "referencia"}

# Nombres legibles para los errores de validación que devuelve el backend
ETIQUETAS = {
    "rfc": "RFC", "razon_social": "razón social", "cp_fiscal": "C.P. fiscal",
    "clave_regimen": "régimen fiscal", "clave_uso": "uso de CFDI", "email": "correo",
    "telefono": "teléfono", "activo": "estado", "id_cliente": "cliente",
    "clave_forma_pago": "forma de pago", "clave_metodo_pago": "método de pago",
    "conceptos": "conceptos", "id_servicio": "servicio", "cantidad": "cantidad",
    "motivo": "motivo", "folio": "factura", "monto": "monto", "referencia": "referencia",
}


def _json_objeto():
    crudo = request.get_json(silent=True)
    return crudo if isinstance(crudo, dict) else None


def _mensaje_validacion(datos):
    """Convierte la lista de errores de Pydantic del backend en una frase en español."""
    campos = []
    for e in datos.get("errores", []):
        partes = [p for p in str(e.get("campo", "")).split(".") if p and not p.isdigit()]
        etiqueta = ETIQUETAS.get(partes[-1] if partes else "", "un campo")
        if etiqueta not in campos:
            campos.append(etiqueta)
    return f"Revisa estos datos: {', '.join(campos)}" if campos else "Datos inválidos"


def proxy_backend(metodo, ruta, cuerpo=None):
    """Reenvía una petición al backend y devuelve su respuesta JSON al navegador."""
    if USE_MOCK:
        return jsonify({"mensaje": "Esta acción necesita el backend: pon USE_MOCK=false."}), 503
    if not BACKEND_URL or not BACKEND_API_KEY:
        return jsonify({"mensaje": "Falta configurar BACKEND_URL o BACKEND_API_KEY en el archivo .env."}), 500
    try:
        # Emitir una factura consulta cada servicio en DynamoDB: se da más tiempo
        r = requests.request(metodo, f"{BACKEND_URL}{ruta}", json=cuerpo,
                             headers={"X-API-Key": BACKEND_API_KEY}, timeout=TIMEOUT * 2)
    except requests.RequestException as exc:
        log.warning("Backend no disponible: %s", exc.__class__.__name__)
        return jsonify({"mensaje": "No se pudo contactar al servidor. Intenta más tarde."}), 502
    if r.status_code == 401:
        # Es un problema de configuración del servidor, no de la sesión del usuario
        log.error("El backend rechazó BACKEND_API_KEY")
        return jsonify({"mensaje": "El servidor no está bien configurado. Avisa al administrador."}), 502
    try:
        datos = r.json()
    except ValueError:
        return jsonify({"mensaje": "El servidor devolvió una respuesta inválida."}), 502
    if r.status_code == 400 and isinstance(datos, dict) and "errores" in datos:
        return jsonify({"mensaje": _mensaje_validacion(datos)}), 400
    if r.status_code >= 500:
        detalle = f" (código {datos['error_id']})" if isinstance(datos, dict) and datos.get("error_id") else ""
        return jsonify({"mensaje": f"Ocurrió un error en el servidor{detalle}. Intenta de nuevo."}), 502
    return jsonify(datos), r.status_code


def _rechazo(accion, texto):
    """Valida CSRF y permiso. Devuelve una respuesta de error o None si todo bien."""
    if not csrf_valido():
        return jsonify({"mensaje": "Sesión inválida o expirada. Recarga la página."}), 403
    if not puede(accion):
        return jsonify({"mensaje": texto}), 403
    return None


def _limpiar_cliente(cuerpo, permitidos):
    datos = {k: v for k, v in cuerpo.items() if k in permitidos}
    for k, v in list(datos.items()):
        if isinstance(v, str):
            datos[k] = v.strip()
        if k in OPCIONALES_CLIENTE and datos[k] == "":
            datos[k] = None  # vacío = sin dato
    if "rfc" in datos and isinstance(datos["rfc"], str):
        datos["rfc"] = datos["rfc"].upper()
    if "email" in datos and isinstance(datos["email"], str):
        datos["email"] = datos["email"].lower()
    return datos


@app.route("/api/clientes", methods=["POST"])
def api_crear_cliente():
    rechazo = _rechazo("crear_cliente", "Tu rol no puede dar de alta clientes.")
    if rechazo:
        return rechazo
    cuerpo = _json_objeto()
    if cuerpo is None:
        return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400
    datos = _limpiar_cliente(cuerpo, CAMPOS_CLIENTE)
    # En un alta, un opcional vacío simplemente no se manda
    datos = {k: v for k, v in datos.items() if v is not None}
    return proxy_backend("POST", "/clientes", datos)


@app.route("/api/clientes/<int:id_cliente>", methods=["PATCH"])
def api_modificar_cliente(id_cliente):
    rechazo = _rechazo("editar_cliente", "Tu rol no puede modificar clientes.")
    if rechazo:
        return rechazo
    cuerpo = _json_objeto()
    if cuerpo is None:
        return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400
    datos = _limpiar_cliente(cuerpo, CAMPOS_CLIENTE_CAMBIO)
    if "activo" in datos:
        if not isinstance(datos["activo"], bool):
            return jsonify({"mensaje": "El estado del cliente no es válido"}), 400
        if not puede("desactivar_cliente"):
            return jsonify({"mensaje": "Solo un Administrador puede activar o desactivar clientes."}), 403
    if not datos:
        return jsonify({"mensaje": "No hay cambios que guardar"}), 400
    return proxy_backend("PATCH", f"/clientes/{id_cliente}", datos)


@app.route("/api/facturas", methods=["POST"])
def api_emitir_factura():
    rechazo = _rechazo("emitir_factura", "Tu rol no puede emitir facturas.")
    if rechazo:
        return rechazo
    cuerpo = _json_objeto()
    if cuerpo is None:
        return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400
    conceptos = cuerpo.get("conceptos")
    if not isinstance(conceptos, list) or not conceptos:
        return jsonify({"mensaje": "Agrega al menos un concepto"}), 400
    if any(not isinstance(c, dict) for c in conceptos):
        return jsonify({"mensaje": "Los conceptos no son válidos"}), 400
    datos = {
        "id_cliente": cuerpo.get("id_cliente"),
        # Quién emite lo decide la sesión, nunca el navegador
        "id_usuario": usuario_actual()["id_usuario"],
        "clave_forma_pago": cuerpo.get("clave_forma_pago"),
        "clave_metodo_pago": cuerpo.get("clave_metodo_pago"),
        # Solo servicio y cantidad: precio e impuesto los pone el backend desde el catálogo
        "conceptos": [{"id_servicio": c.get("id_servicio"), "cantidad": c.get("cantidad")}
                      for c in conceptos],
    }
    return proxy_backend("POST", "/facturas", datos)


@app.route("/api/facturas/<folio>", methods=["GET"])
def api_detalle_factura(folio):
    if not FOLIO_RE.match(folio):
        return jsonify({"mensaje": "Folio inválido"}), 400
    return proxy_backend("GET", f"/facturas/{folio}")


@app.route("/api/facturas/<folio>/cancelar", methods=["POST"])
def api_cancelar_factura(folio):
    rechazo = _rechazo("cancelar_factura", "Solo un Administrador puede cancelar facturas.")
    if rechazo:
        return rechazo
    if not FOLIO_RE.match(folio):
        return jsonify({"mensaje": "Folio inválido"}), 400
    cuerpo = _json_objeto()
    if cuerpo is None:
        return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400
    motivo = cuerpo.get("motivo")
    return proxy_backend("POST", f"/facturas/{folio}/cancelar",
                         {"motivo": motivo.strip() if isinstance(motivo, str) else motivo})


@app.route("/api/pagos", methods=["POST"])
def api_registrar_pago():
    rechazo = _rechazo("registrar_pago", "Tu rol no puede registrar pagos.")
    if rechazo:
        return rechazo
    cuerpo = _json_objeto()
    if cuerpo is None:
        return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400
    datos = {k: v for k, v in cuerpo.items() if k in CAMPOS_PAGO}
    if isinstance(datos.get("referencia"), str):
        datos["referencia"] = datos["referencia"].strip() or None
    if datos.get("referencia") is None:
        datos.pop("referencia", None)
    return proxy_backend("POST", "/pagos", datos)


@app.route("/api/servicios", methods=["POST", "PUT", "DELETE"])
def api_servicios():
    """Proxy hacia API Gateway (evita CORS y mantiene la URL fuera del navegador)."""
    if not csrf_valido():
        return jsonify({"mensaje": "Sesión inválida o expirada. Recarga la página."}), 403
    if usuario_actual()["rol"] != ROL_EDITA_CATALOGO:
        return jsonify({"mensaje": "Solo un Administrador puede modificar el catálogo."}), 403

    # Solo se reenvía lo que cada método necesita
    if request.method == "DELETE":
        params, cuerpo = {"id_servicio": request.args.get("id_servicio", "")}, None
    else:
        crudo = request.get_json(silent=True)
        if not isinstance(crudo, dict):
            return jsonify({"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}), 400
        cuerpo, error = limpiar_servicio(crudo, es_alta=request.method == "POST")
        if error:
            return jsonify({"mensaje": error}), 400
        params = None

    if USE_MOCK:
        return _mock_api(params, cuerpo)
    if not API_KEY or not API_BASE_URL:
        return jsonify({"mensaje": "Falta configurar API_KEY o API_BASE_URL en el archivo .env."}), 500

    try:
        r = requests.request(
            request.method,
            f"{API_BASE_URL}/servicios",
            params=params,
            json=cuerpo,
            headers=_headers_api(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return jsonify({"mensaje": f"No se pudo contactar a API Gateway ({exc.__class__.__name__})."}), 502
    if r.status_code in ERRORES_GATEWAY:
        return jsonify({"mensaje": ERRORES_GATEWAY[r.status_code]}), r.status_code
    return Response(r.content, status=r.status_code, content_type="application/json")


def _mock_api(params, body):
    if request.method == "DELETE":
        sid = (params or {}).get("id_servicio")
        if not sid:
            return jsonify({"mensaje": 'Falta la propiedad "id_servicio"'}), 400
        servicio = _mock_store.get(sid)
        if not servicio or not servicio.get("activo", True):
            return jsonify({"mensaje": "Servicio no encontrado o ya dado de baja"}), 404
        # Igual que la Lambda: borrado lógico
        servicio["activo"] = False
        servicio["fecha_baja"] = datetime.now(timezone.utc).isoformat()
        return jsonify({"mensaje": "Servicio dado de baja correctamente", "servicio": servicio})

    if not isinstance(body, dict) or not body:
        return jsonify({"mensaje": "El cuerpo de la petición está vacío"}), 400
    sid = body.get("id_servicio")
    if not sid:
        return jsonify({"mensaje": 'Falta la propiedad "id_servicio" dentro del JSON'}), 400

    if request.method == "POST":
        if sid in _mock_store:
            return jsonify({"mensaje": "Ya existe un servicio con ese id_servicio"}), 409
        _mock_store[sid] = body
        return jsonify({"mensaje": "Servicio agregado correctamente", "servicio": body})

    if sid not in _mock_store:
        return jsonify({"mensaje": "Servicio no encontrado"}), 404
    _mock_store[sid].update({k: v for k, v in body.items() if k != "id_servicio"})
    return jsonify({"mensaje": "Servicio modificado correctamente", "servicio": _mock_store[sid]})


if __name__ == "__main__":
    # El depurador de Flask permite ejecutar código: solo se activa a propósito
    # En macOS el puerto 5000 lo ocupa el Receptor AirPlay: usa PORT=5001
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
            port=int(os.getenv("PORT", "5000")))
