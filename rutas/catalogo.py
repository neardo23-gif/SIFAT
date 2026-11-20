"""Catálogo de servicios (API Gateway + DynamoDB): pantalla y alta, cambio o baja."""
from flask import Blueprint, jsonify, render_template, request

import backend
import seguridad
from rutas.comun import JSON_INVALIDO, contexto_base, json_objeto

bp = Blueprint("catalogo", __name__)

# Campos de un servicio que el navegador puede enviar. Todo lo demás se descarta,
# y el impuesto lo pone el servidor a partir del catálogo de impuestos (MySQL).
CAMPOS_SERVICIO = {"id_servicio", "clave", "nombre", "descripcion", "categoria",
                   "precio_unitario", "unidad_medida", "activo", "caracteristicas"}
UNIDADES = ["Servicio", "Mes", "Ano", "Hora", "Pieza"]


@bp.route("/catalogo")
def pantalla():
    servicios, error = backend.listar_servicios()
    categorias = sorted({s.get("categoria", "Sin categoria") for s in servicios})
    impuestos, error_impuestos = backend.listar_impuestos()
    if error_impuestos and not error:
        error = f"No se cargaron los impuestos, no podrás guardar servicios: {error_impuestos}"
    return render_template(
        "catalogo.html",
        servicios=servicios,
        categorias=categorias,
        impuestos=impuestos,
        unidades=UNIDADES,
        puede_editar=seguridad.puede("editar_catalogo"),
        error=error,
        **contexto_base("catalogo"),
    )


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
    impuestos, error = backend.listar_impuestos()
    if error:
        return None, f"No se pudo validar el impuesto: {error}"
    elegido = next((i for i in impuestos if i["clave"] == clave), None)
    if not elegido:
        return None, "El impuesto seleccionado no existe en el catálogo"
    servicio["impuesto"] = {"nombre": elegido["nombre"], "tasa": elegido["tasa"], "tipo": elegido["tipo"]}
    return servicio, None


@bp.route("/api/servicios", methods=["POST", "PUT", "DELETE"])
def api_servicios():
    """Proxy hacia API Gateway (evita CORS y mantiene la URL y la clave fuera del navegador)."""
    error = seguridad.rechazo("editar_catalogo", "Solo un Administrador puede modificar el catálogo.")
    if error:
        return error

    # Solo se reenvía lo que cada método necesita
    if request.method == "DELETE":
        return backend.proxy_gateway("DELETE", {"id_servicio": request.args.get("id_servicio", "")}, None)
    crudo = json_objeto()
    if crudo is None:
        return jsonify(JSON_INVALIDO), 400
    cuerpo, problema = limpiar_servicio(crudo, es_alta=request.method == "POST")
    if problema:
        return jsonify({"mensaje": problema}), 400
    return backend.proxy_gateway(request.method, None, cuerpo)
