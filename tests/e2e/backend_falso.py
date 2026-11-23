"""Backend y API Gateway simulados para las pruebas en navegador.

Responde las mismas rutas y con la misma forma que SIFAT-BACKEND y la Lambda de
servicios, con los datos en memoria. Así el navegador recorre la app completa sin
tocar la base de datos real. Las reglas de validación de fondo se prueban en el
repo del backend; aquí solo se replican las que la interfaz necesita mostrar.
"""
import itertools
import threading
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from flask import Flask, jsonify, request

CLAVE_BACKEND = "clave-backend-e2e"
CLAVE_GATEWAY = "clave-gateway-e2e"
CENT = Decimal("0.01")


def _r(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def crear_backend_falso():
    app = Flask("backend_falso")
    candado = threading.Lock()
    ids = itertools.count(100)
    folios = itertools.count(100)  # como el backend real: el folio sale de su propia secuencia
    ahora = lambda: datetime.now().isoformat(timespec="seconds")  # noqa: E731

    usuarios = {
        1: {"id_usuario": 1, "nombre": "Ana Lopez", "email": "ana@sifat.test", "rol": "Administrador",
            "activo": True, "password": "AdminSifat2026", "ultimo_acceso": None},
        2: {"id_usuario": 2, "nombre": "Luis Perez", "email": "luis@sifat.test", "rol": "Facturista",
            "activo": True, "password": "FacturaLuis2026", "ultimo_acceso": None},
    }
    clientes = {
        1: {"id_cliente": 1, "rfc": "CSU210315AB1", "razon_social": "Consultoria Sur SA de CV", "cp_fiscal": "62000",
            "email": "contacto@sur.test", "telefono": None, "activo": True, "clave_regimen": "601",
            "regimen": "General de Ley Personas Morales", "clave_uso": "G03", "uso_cfdi": "Gastos en general"},
    }
    facturas, pagos = {}, []
    servicios = [
        {"id_servicio": "SRV-001", "clave": "HOST-BAS", "nombre": "Hosting Basico", "descripcion": "Hosting",
         "categoria": "Hosting", "precio_unitario": 349, "unidad_medida": "Mes", "activo": True,
         "impuesto": {"nombre": "IVA", "tasa": 0.16, "tipo": "traslado"}, "caracteristicas": []},
        {"id_servicio": "SRV-002", "clave": "WEB-LAND", "nombre": "Landing Page", "descripcion": "Sitio",
         "categoria": "Web", "precio_unitario": 4500.5, "unidad_medida": "Servicio", "activo": True,
         "impuesto": {"nombre": "IVA", "tasa": 0.16, "tipo": "traslado"}, "caracteristicas": []},
    ]
    formas = {"01": "Efectivo", "03": "Transferencia electronica de fondos", "99": "Por definir"}
    metodos = {"PUE": "Pago en una sola exhibicion", "PPD": "Pago en parcialidades o diferido"}

    def error(mensaje, status=422):
        return jsonify({"mensaje": mensaje}), status

    @app.before_request
    def clave():
        if request.path == "/servicios":
            if request.headers.get("x-api-key") != CLAVE_GATEWAY:
                return jsonify({"message": "Forbidden"}), 403
        elif request.headers.get("X-API-Key") != CLAVE_BACKEND:
            return error("Clave inválida", 401)

    def pagina(lista):
        desde, limite = int(request.args.get("desde", 0)), int(request.args.get("limite", 50))
        return lista[desde:desde + limite]

    def publico(u):
        return {k: u[k] for k in ("id_usuario", "nombre", "email", "rol", "activo", "ultimo_acceso")} | {
            "tiene_contrasena": bool(u["password"])}

    # ---------------- catálogo (API Gateway) ----------------
    @app.get("/servicios")
    def listar_servicios():
        return jsonify({"servicios": servicios, "siguiente": None})

    @app.post("/servicios")
    def crear_servicio():
        d = request.get_json()
        if any(x["id_servicio"] == d["id_servicio"] for x in servicios):
            return jsonify({"mensaje": "Ya existe un servicio con ese id_servicio"}), 409
        servicios.append({"caracteristicas": [], **d})
        return jsonify({"mensaje": "Servicio agregado correctamente", "servicio": d})

    @app.put("/servicios")
    def modificar_servicio():
        d = request.get_json()
        s = next(x for x in servicios if x["id_servicio"] == d["id_servicio"])
        s.update(d)
        return jsonify({"mensaje": "Servicio modificado correctamente", "servicio": s})

    @app.delete("/servicios")
    def baja_servicio():
        s = next(x for x in servicios if x["id_servicio"] == request.args["id_servicio"])
        s["activo"] = False
        return jsonify({"mensaje": "Servicio dado de baja correctamente", "servicio": s})

    # ---------------- auth y usuarios ----------------
    @app.post("/auth/login")
    def login():
        d = request.get_json()
        u = next((u for u in usuarios.values() if u["email"] == d["email"]), None)
        if not u or not u["activo"] or u["password"] != d["password"]:
            return error("Correo o contraseña incorrectos", 401)
        u["ultimo_acceso"] = ahora()
        return jsonify({k: u[k] for k in ("id_usuario", "nombre", "email", "rol")})

    @app.post("/auth/cambiar-contrasena")
    def cambiar():
        d = request.get_json()
        u = usuarios[d["id_usuario"]]
        if u["password"] != d["actual"]:
            return error("La contraseña actual no es correcta", 403)
        if len(d["nueva"]) < 12:
            return error("La contraseña debe tener al menos 12 caracteres, con letras y números")
        u["password"] = d["nueva"]
        return jsonify({"mensaje": "Contraseña actualizada"})

    @app.get("/usuarios")
    def listar_usuarios():
        return jsonify({"usuarios": [publico(u) for u in usuarios.values()]})

    @app.get("/usuarios/<int:i>")
    def un_usuario(i):
        return jsonify(publico(usuarios[i])) if i in usuarios else error("Usuario no encontrado", 404)

    @app.post("/usuarios")
    def crear_usuario():
        d = request.get_json()
        if any(u["email"] == d["email"] for u in usuarios.values()):
            return error("Ya existe un usuario con ese correo", 409)
        if len(d["password"]) < 12:
            return error("La contraseña debe tener al menos 12 caracteres, con letras y números")
        with candado:
            i = next(ids)
        usuarios[i] = {"id_usuario": i, "nombre": f"{d['nombre']} {d['apellidos']}", "email": d["email"],
                       "rol": d["rol"], "activo": True, "password": d["password"], "ultimo_acceso": None}
        return jsonify(publico(usuarios[i])), 201

    @app.patch("/usuarios/<int:i>")
    def modificar_usuario(i):
        d = request.get_json()
        u = usuarios[i]
        otros_admins = [x for x in usuarios.values() if x["rol"] == "Administrador" and x["activo"] and x is not u]
        if u["rol"] == "Administrador" and d.get("activo") is False and not otros_admins:
            return error("Debe quedar al menos un Administrador activo", 409)
        u.update(d)
        return jsonify(publico(u))

    @app.post("/usuarios/<int:i>/contrasena")
    def restablecer(i):
        usuarios[i]["password"] = request.get_json()["password"]
        return jsonify({"mensaje": "Contraseña actualizada"})

    # ---------------- catálogos SAT ----------------
    @app.get("/catalogos")
    def catalogos():
        return jsonify({
            "regimenes": [{"clave": "601", "descripcion": "General de Ley Personas Morales", "tipo_persona": "M"},
                          {"clave": "612", "descripcion": "Personas Fisicas con Actividades Empresariales",
                           "tipo_persona": "F"}],
            "usos-cfdi": [{"clave": "G03", "descripcion": "Gastos en general"},
                          {"clave": "S01", "descripcion": "Sin efectos fiscales"}],
            "formas-pago": [{"clave": k, "descripcion": v} for k, v in formas.items()],
            "metodos-pago": [{"clave": k, "descripcion": v} for k, v in metodos.items()],
            "impuestos": [{"nombre": "IVA", "tasa": "0.1600", "tipo": "traslado"}],
            "usuarios": [],
        })

    # ---------------- clientes ----------------
    @app.get("/clientes")
    def listar_clientes():
        todos = sorted(clientes.values(), key=lambda c: c["razon_social"])
        if request.args.get("incluir_inactivos") != "true":
            todos = [c for c in todos if c["activo"]]
        return jsonify({"clientes": pagina(todos)})

    @app.post("/clientes")
    def crear_cliente():
        d = request.get_json()
        if any(c["rfc"] == d["rfc"] for c in clientes.values()):
            return error("Ya existe un cliente con ese RFC", 409)
        with candado:
            i = next(ids)
        clientes[i] = {"id_cliente": i, "email": None, "telefono": None, "activo": True,
                       "regimen": "", "uso_cfdi": "", **d}
        return jsonify(clientes[i]), 201

    @app.patch("/clientes/<int:i>")
    def modificar_cliente(i):
        clientes[i].update(request.get_json())
        return jsonify(clientes[i])

    # ---------------- facturas ----------------
    def detalle(f):
        pagado = sum((p["monto"] for p in pagos if p["folio"] == f["folio"]), Decimal("0"))
        saldo = Decimal("0") if f["estatus"] == "cancelada" else f["total"] - pagado
        return {**f, "subtotal": float(f["subtotal"]), "iva": float(f["iva"]), "total": float(f["total"]),
                "saldo": float(saldo),
                "pagos": [{**p, "monto": float(p["monto"])} for p in pagos if p["folio"] == f["folio"]]}

    @app.get("/facturas")
    def listar_facturas():
        todas = sorted(facturas.values(), key=lambda f: f["folio"], reverse=True)
        if request.args.get("estatus"):
            todas = [f for f in todas if f["estatus"] == request.args["estatus"]]
        return jsonify({"facturas": [detalle(f) for f in pagina(todas)]})

    @app.get("/facturas/<folio>")
    def una_factura(folio):
        return jsonify(detalle(facturas[folio])) if folio in facturas else error("Factura no encontrada", 404)

    @app.post("/facturas")
    def emitir():
        d = request.get_json()
        cliente = clientes.get(d["id_cliente"])
        if not cliente or not cliente["activo"]:
            return error("El cliente no existe")
        conceptos = []
        for c in d["conceptos"]:
            s = next(x for x in servicios if x["id_servicio"] == c["id_servicio"])
            importe = _r(Decimal(c["cantidad"]) * Decimal(str(s["precio_unitario"])))
            iva = _r(importe * Decimal(str(s["impuesto"]["tasa"])))
            conceptos.append({"id_servicio": s["id_servicio"], "clave_servicio": s["clave"],
                              "nombre_servicio": s["nombre"], "cantidad": float(c["cantidad"]),
                              "precio_unitario": s["precio_unitario"], "importe": float(importe),
                              "tasa_aplicada": s["impuesto"]["tasa"], "iva_importe": float(iva),
                              "_importe": importe, "_iva": iva})
        subtotal = sum((c.pop("_importe") for c in conceptos), Decimal("0"))
        iva = sum((c.pop("_iva") for c in conceptos), Decimal("0"))
        with candado:
            folio = f"FAC-{next(folios):04d}"
        usuario = usuarios[d["id_usuario"]]
        facturas[folio] = {
            "folio": folio, "id_cliente": cliente["id_cliente"], "cliente": cliente["razon_social"],
            "rfc": cliente["rfc"], "fecha_emision": ahora(), "subtotal": _r(subtotal), "iva": _r(iva),
            "total": _r(subtotal + iva), "estatus": "vigente", "usuario": usuario["nombre"],
            "clave_forma_pago": d["clave_forma_pago"], "forma_pago": formas[d["clave_forma_pago"]],
            "clave_metodo_pago": d["clave_metodo_pago"], "metodo_pago": metodos[d["clave_metodo_pago"]],
            "motivo_cancelacion": None, "fecha_cancelacion": None, "conceptos": conceptos,
        }
        return jsonify(detalle(facturas[folio])), 201

    @app.post("/facturas/<folio>/cancelar")
    def cancelar(folio):
        f = facturas[folio]
        if f["estatus"] != "vigente":
            return error(f"Solo se cancelan facturas vigentes (esta está {f['estatus']})", 409)
        if any(p["folio"] == folio for p in pagos):
            return error("La factura tiene pagos registrados y no se puede cancelar", 409)
        f.update(estatus="cancelada", motivo_cancelacion=request.get_json()["motivo"], fecha_cancelacion=ahora())
        return jsonify(detalle(f))

    # ---------------- pagos ----------------
    @app.get("/pagos")
    def listar_pagos():
        todos = [{**p, "monto": float(p["monto"])} for p in reversed(pagos)]
        return jsonify({"pagos": pagina(todos)})

    @app.post("/pagos")
    def registrar_pago():
        d = request.get_json()
        f = facturas.get(d["folio"])
        if not f:
            return error("Factura no encontrada", 404)
        if f["estatus"] != "vigente":
            return error(f"La factura está {f['estatus']}: no admite pagos", 409)
        saldo = Decimal(str(detalle(f)["saldo"]))
        monto = Decimal(d["monto"])
        if monto > saldo:
            return error(f"El monto excede el saldo pendiente ({saldo})")
        with candado:
            i = next(ids)
        pagos.append({"id_pago": i, "folio": f["folio"], "cliente": f["cliente"], "fecha_pago": ahora(),
                      "monto": monto, "referencia": d.get("referencia"), "clave_forma_pago": d["clave_forma_pago"],
                      "forma_pago": formas[d["clave_forma_pago"]]})
        restante = saldo - monto
        if restante == 0:
            f["estatus"] = "pagada"
        return jsonify({"id_pago": i, "folio": f["folio"], "monto": float(monto),
                        "saldo_restante": float(restante), "factura_pagada": restante == 0}), 201

    return app
