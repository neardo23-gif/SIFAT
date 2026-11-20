"""Pagos (MySQL): pantalla y registro. El backend impide pagar más que el saldo."""
from flask import Blueprint, jsonify, render_template, request

import backend
import seguridad
from rutas.comun import FOLIO_RE, JSON_INVALIDO, contexto_base, fecha_corta, json_objeto

bp = Blueprint("pagos", __name__)

CAMPOS_PAGO = {"folio", "clave_forma_pago", "monto", "referencia"}


@bp.route("/pagos")
def pantalla():
    datos, error = backend.consultar_backend("/pagos", "pagos")
    filas = [{"id": p["id_pago"], "folio": p["folio"], "fecha": fecha_corta(p["fecha_pago"]),
              "forma": f"{p['clave_forma_pago']} {p['forma_pago']}", "monto": p["monto"],
              "referencia": p.get("referencia") or "-"} for p in datos]

    vigentes, aviso = [], None
    catalogos = dict(backend.CATALOGOS_VACIOS)
    if seguridad.puede("registrar_pago") and not error:
        catalogos, error_cat = backend.catalogos_sat()
        crudas, error_fac = backend.consultar_backend("/facturas", "facturas", estatus="vigente")
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


@bp.route("/api/pagos", methods=["POST"])
def api_registrar():
    error = seguridad.rechazo("registrar_pago", "Tu rol no puede registrar pagos.")
    if error:
        return error
    cuerpo = json_objeto()
    if cuerpo is None:
        return jsonify(JSON_INVALIDO), 400
    datos = {k: v for k, v in cuerpo.items() if k in CAMPOS_PAGO}
    if isinstance(datos.get("referencia"), str):
        datos["referencia"] = datos["referencia"].strip() or None
    if datos.get("referencia") is None:
        datos.pop("referencia", None)
    return backend.proxy_backend("POST", "/pagos", datos)
