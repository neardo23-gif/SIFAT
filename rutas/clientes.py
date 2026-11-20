"""Clientes (MySQL): pantalla, alta y cambios. No se borran: se desactivan."""
from flask import Blueprint, jsonify, render_template

import backend
import seguridad
from rutas.comun import JSON_INVALIDO, contexto_base, json_objeto

bp = Blueprint("clientes", __name__)

CAMPOS_ALTA = {"rfc", "razon_social", "cp_fiscal", "clave_regimen", "clave_uso", "email", "telefono"}
CAMPOS_CAMBIO = (CAMPOS_ALTA - {"rfc"}) | {"activo"}
OPCIONALES = {"email", "telefono"}


@bp.route("/clientes")
def pantalla():
    datos, error = backend.consultar_backend("/clientes", "clientes", incluir_inactivos="true")
    filas = [{"id": f"CLI-{c['id_cliente']:03d}", "id_cliente": c["id_cliente"],
              "razon_social": c["razon_social"], "rfc": c["rfc"], "cp": c["cp_fiscal"],
              "email": c.get("email") or "-", "email_crudo": c.get("email") or "",
              "telefono": c.get("telefono") or "", "clave_regimen": c.get("clave_regimen", ""),
              "regimen": c.get("regimen", ""), "clave_uso": c.get("clave_uso", ""),
              "uso_cfdi": c.get("uso_cfdi", ""), "activo": c["activo"]}
             for c in datos]

    catalogos, aviso = dict(backend.CATALOGOS_VACIOS), None
    # Si ni la lista cargó, el backend no responde: no tiene caso pedir más datos
    if (seguridad.puede("crear_cliente") or seguridad.puede("editar_cliente")) and not error:
        catalogos, error_cat = backend.catalogos_sat()
        if error_cat:
            aviso = f"No se podrán guardar clientes por ahora: {error_cat}"
    return render_template("clientes.html", clientes=filas, error=error, aviso=aviso,
                           catalogos=catalogos, **contexto_base("clientes"))


def _limpiar(cuerpo, permitidos):
    datos = {k: v for k, v in cuerpo.items() if k in permitidos}
    for k, v in list(datos.items()):
        if isinstance(v, str):
            datos[k] = v.strip()
        if k in OPCIONALES and datos[k] == "":
            datos[k] = None  # vacío = sin dato
    if isinstance(datos.get("rfc"), str):
        datos["rfc"] = datos["rfc"].upper()
    if isinstance(datos.get("email"), str):
        datos["email"] = datos["email"].lower()
    return datos


@bp.route("/api/clientes", methods=["POST"])
def api_crear():
    error = seguridad.rechazo("crear_cliente", "Tu rol no puede dar de alta clientes.")
    if error:
        return error
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    # En un alta, un opcional vacío simplemente no se manda
    datos = {k: v for k, v in _limpiar(cuerpo, CAMPOS_ALTA).items() if v is not None}
    return backend.proxy_backend("POST", "/clientes", datos)


@bp.route("/api/clientes/<int:id_cliente>", methods=["PATCH"])
def api_modificar(id_cliente):
    error = seguridad.rechazo("editar_cliente", "Tu rol no puede modificar clientes.")
    if error:
        return error
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    datos = _limpiar(cuerpo, CAMPOS_CAMBIO)
    if "activo" in datos:
        if not isinstance(datos["activo"], bool):
            return jsonify({"mensaje": "El estado del cliente no es válido"}), 400
        if not seguridad.puede("desactivar_cliente"):
            return jsonify({"mensaje": "Solo un Administrador puede activar o desactivar clientes."}), 403
    if not datos:
        return jsonify({"mensaje": "No hay cambios que guardar"}), 400
    return backend.proxy_backend("PATCH", f"/clientes/{id_cliente}", datos)
