"""Facturas (MySQL): pantalla, emisión, detalle y cancelación. No se borran: se cancelan."""
from flask import Blueprint, jsonify, render_template

import backend
import seguridad
from rutas.comun import FOLIO_RE, JSON_INVALIDO, contexto_base, fecha_corta, json_objeto

bp = Blueprint("facturas", __name__)


@bp.route("/facturas")
def pantalla():
    datos, error = backend.consultar_backend("/facturas", "facturas")
    filas = [{"folio": f["folio"], "cliente": f["cliente"], "fecha": fecha_corta(f["fecha_emision"]),
              "subtotal": f["subtotal"], "iva": f["iva"], "total": f["total"],
              "estatus": f["estatus"]} for f in datos]

    # Lo que necesita el formulario de "Nueva factura": clientes activos,
    # servicios activos del catálogo y las claves del SAT.
    clientes_activos, servicios_activos, aviso = [], [], None
    catalogos = dict(backend.CATALOGOS_VACIOS)
    # Si ni la lista cargó, el backend no responde: no tiene caso pedir más datos
    if seguridad.puede("emitir_factura") and not error:
        catalogos, error_cat = backend.catalogos_sat()
        crudos, error_cli = backend.consultar_backend("/clientes", "clientes")
        clientes_activos = [{"id_cliente": c["id_cliente"], "razon_social": c["razon_social"],
                             "rfc": c["rfc"]} for c in crudos]
        servicios, error_srv = backend.listar_servicios()
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


@bp.route("/api/facturas", methods=["POST"])
def api_emitir():
    error = seguridad.rechazo("emitir_factura", "Tu rol no puede emitir facturas.")
    if error:
        return error
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    conceptos = cuerpo.get("conceptos")
    if not isinstance(conceptos, list) or not conceptos:
        return jsonify({"mensaje": "Agrega al menos un concepto"}), 400
    if any(not isinstance(c, dict) for c in conceptos):
        return jsonify({"mensaje": "Los conceptos no son válidos"}), 400
    datos = {
        "id_cliente": cuerpo.get("id_cliente"),
        # Quién emite lo decide la sesión, nunca el navegador
        "id_usuario": seguridad.usuario_actual()["id_usuario"],
        "clave_forma_pago": cuerpo.get("clave_forma_pago"),
        "clave_metodo_pago": cuerpo.get("clave_metodo_pago"),
        # Solo servicio y cantidad: precio e impuesto los pone el backend desde el catálogo
        "conceptos": [{"id_servicio": c.get("id_servicio"), "cantidad": c.get("cantidad")}
                      for c in conceptos],
    }
    return backend.proxy_backend("POST", "/facturas", datos)


@bp.route("/api/facturas/<folio>", methods=["GET"])
def api_detalle(folio):
    if not FOLIO_RE.match(folio):
        return jsonify({"mensaje": "Folio inválido"}), 400
    return backend.proxy_backend("GET", f"/facturas/{folio}")


@bp.route("/api/facturas/<folio>/cancelar", methods=["POST"])
def api_cancelar(folio):
    error = seguridad.rechazo("cancelar_factura", "Solo un Administrador puede cancelar facturas.")
    if error:
        return error
    if not FOLIO_RE.match(folio):
        return jsonify({"mensaje": "Folio inválido"}), 400
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    motivo = cuerpo.get("motivo")
    return backend.proxy_backend("POST", f"/facturas/{folio}/cancelar",
                                 {"motivo": motivo.strip() if isinstance(motivo, str) else motivo})
