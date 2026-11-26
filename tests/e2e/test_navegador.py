"""Recorridos completos en Chromium: se hace clic y se escribe como lo haría una persona.

Cada prueba arranca con datos limpios (backend simulado nuevo) y falla si el
navegador registra cualquier error de JavaScript.
"""
import re

from playwright.sync_api import expect

from e2e.ayudas import entrar, salir

ADMIN = ("ana@sifat.test", "AdminSifat2026")
FACTURISTA = ("luis@sifat.test", "FacturaLuis2026")


def aviso(page, texto):
    """Espera el aviso (toast) que aparece después de guardar y recargar."""
    expect(page.locator("#toasts .toast").filter(has_text=texto)).to_be_visible()


def ir(page, nombre):
    page.locator("aside nav").get_by_role("link", name=nombre).click()
    page.wait_for_load_state("domcontentloaded")


# ---------------------------------------------------------------------------
def test_login_y_todas_las_pantallas(nav):
    entrar(nav, *ADMIN)
    for pantalla in ("Catálogo", "Facturas", "Clientes", "Pagos", "Usuarios"):
        ir(nav, pantalla)
        expect(nav.locator("h1")).to_have_text(re.compile(pantalla.replace("Catálogo", "Catálogo de servicios")))
    nav.locator("aside").get_by_role("link", name="Mi cuenta").click()
    expect(nav.locator("h1")).to_have_text("Mi cuenta")


def test_login_incorrecto(nav):
    nav.goto(nav.base + "/")
    nav.fill("#login-email", "ana@sifat.test")
    nav.fill("#login-pass", "equivocada")
    nav.click("form[action='/login'] button[type=submit]")
    expect(nav.get_by_text("Correo o contraseña incorrectos")).to_be_visible()


# ---------------------------------------------------------------------------
def test_alta_y_edicion_de_cliente(nav):
    entrar(nav, *ADMIN)
    ir(nav, "Clientes")
    nav.get_by_role("button", name="Nuevo cliente").click()
    dlg = nav.locator("#dlg-cliente")

    # Vacío: no se envía y se marcan los campos
    dlg.get_by_role("button", name="Guardar cliente").click()
    expect(nav.locator("#cli-error")).to_contain_text("RFC")
    expect(nav.locator("#c-rfc")).to_have_attribute("aria-invalid", "true")

    nav.fill("#c-rfc", "peml850101ab1")  # se convierte a mayúsculas
    nav.fill("#c-razon", "Maria Perez Lopez")
    nav.fill("#c-cp", "62000")
    nav.select_option("#c-regimen", "612")
    nav.select_option("#c-uso", "G03")
    nav.fill("#c-email", "Maria@Correo.Test")
    dlg.get_by_role("button", name="Guardar cliente").click()
    aviso(nav, "Cliente dado de alta")
    fila = nav.locator("#tabla-clientes tr", has_text="PEML850101AB1")
    expect(fila).to_contain_text("maria@correo.test")

    # Edición: el RFC no se puede cambiar; el C.P. sí
    fila.get_by_role("button", name=re.compile("Editar")).click()
    expect(nav.locator("#cli-titulo")).to_have_text("Editar cliente")
    expect(nav.locator("#c-rfc")).to_have_attribute("readonly", "")
    nav.fill("#c-cp", "62001")
    dlg.get_by_role("button", name="Guardar cliente").click()
    aviso(nav, "Cliente guardado")
    expect(nav.locator("#tabla-clientes tr", has_text="PEML850101AB1")).to_contain_text("62001")


def test_rfc_repetido_muestra_el_error_del_servidor(nav):
    entrar(nav, *ADMIN)
    ir(nav, "Clientes")
    nav.get_by_role("button", name="Nuevo cliente").click()
    nav.fill("#c-rfc", "CSU210315AB1")
    nav.fill("#c-razon", "Otra")
    nav.fill("#c-cp", "62000")
    nav.locator("#dlg-cliente").get_by_role("button", name="Guardar cliente").click()
    expect(nav.locator("#cli-error")).to_have_text("Ya existe un cliente con ese RFC.")


# ---------------------------------------------------------------------------
def _emitir(nav, conceptos):
    ir(nav, "Facturas")
    nav.get_by_role("button", name="Nueva factura").click()
    nav.select_option("#n-cliente", "1")  # Consultoria Sur
    for i, (servicio, cantidad) in enumerate(conceptos):
        if i:
            nav.get_by_role("button", name="Agregar concepto").click()
        fila = nav.locator("#n-conceptos > div").nth(i)
        fila.locator("select").select_option(servicio)
        fila.locator("input").fill(cantidad)


def test_factura_pago_parcial_y_cancelacion(nav):
    entrar(nav, *ADMIN)
    _emitir(nav, [("SRV-001", "2"), ("SRV-002", "1.5")])
    # Totales estimados en pantalla: 698.00 + 6750.75 = 7448.75; IVA 111.68 + 1080.12;
    # el cliente es persona moral (601): ISR retenido 69.80 + 675.08
    expect(nav.locator("#n-subtotal")).to_have_text("$7,448.75")
    expect(nav.locator("#n-iva")).to_have_text("$1,191.80")
    expect(nav.locator("#n-isr")).to_have_text("-$744.88")
    expect(nav.locator("#n-total")).to_have_text("$7,895.67")
    nav.get_by_role("button", name="Emitir factura").click()
    aviso(nav, "Factura FAC-0100 emitida por $7,895.67")

    # Detalle: conceptos, saldo y botones
    nav.get_by_role("button", name="FAC-0100").click()
    det = nav.locator("#dlg-factura")
    expect(det.locator("#fac-conceptos tr")).to_have_count(2)
    expect(det.locator("#fac-datos")).to_contain_text("$7,895.67")
    expect(det.locator("#fac-totales")).to_contain_text("ISR retenido-$744.88")
    expect(det.get_by_role("button", name="Cancelar factura")).to_be_visible()

    # Registrar pago desde el detalle: abre Pagos con la factura y el saldo puestos
    det.get_by_role("link", name="Registrar pago").click()
    nav.wait_for_url("**/pagos?folio=FAC-0100")
    expect(nav.locator("#dlg-pago")).to_be_visible()
    expect(nav.locator("#p-monto")).to_have_value("7895.67")
    expect(nav.locator("#p-saldo")).to_contain_text("Saldo pendiente: $7,895.67")

    # Más que el saldo: lo frena el navegador
    nav.fill("#p-monto", "9000")
    nav.locator("#dlg-pago").get_by_role("button", name="Registrar pago").click()
    expect(nav.locator("#p-error")).to_contain_text("no puede superar el saldo")

    nav.fill("#p-monto", "1000")
    nav.fill("#p-ref", "SPEI-123")
    nav.locator("#dlg-pago").get_by_role("button", name="Registrar pago").click()
    aviso(nav, "Saldo restante: $6,895.67")
    expect(nav.locator("main table")).to_contain_text("SPEI-123")

    # Con pagos ya no se puede cancelar
    ir(nav, "Facturas")
    nav.get_by_role("button", name="FAC-0100").click()
    expect(nav.locator("#fac-datos")).to_contain_text("$6,895.67")
    expect(nav.locator("#fac-cancelar")).to_be_hidden()
    nav.locator("#dlg-factura").get_by_role("button", name="Cerrar").last.click()

    # Otra factura sin pagos: se cancela con motivo
    _emitir(nav, [("SRV-001", "1")])
    nav.get_by_role("button", name="Emitir factura").click()
    aviso(nav, "Factura FAC-0101 emitida")
    nav.get_by_role("button", name="FAC-0101").click()
    nav.locator("#dlg-factura").get_by_role("button", name="Cancelar factura").click()
    nav.fill("#can-motivo", "abc")
    nav.locator("#dlg-cancelar").get_by_role("button", name="Cancelar factura").click()
    expect(nav.locator("#can-error")).to_contain_text("al menos 5")
    nav.fill("#can-motivo", "Error de captura")
    nav.locator("#dlg-cancelar").get_by_role("button", name="Cancelar factura").click()
    aviso(nav, "Factura FAC-0101 cancelada")
    expect(nav.locator("#tabla-facturas tr", has_text="FAC-0101")).to_contain_text("Cancelada")


def test_factura_sin_servicio_no_se_emite(nav):
    entrar(nav, *ADMIN)
    ir(nav, "Facturas")
    nav.get_by_role("button", name="Nueva factura").click()
    nav.get_by_role("button", name="Emitir factura").click()
    expect(nav.locator("#n-error")).to_contain_text("Elige el cliente")
    nav.select_option("#n-cliente", "1")  # Consultoria Sur
    nav.get_by_role("button", name="Emitir factura").click()
    expect(nav.locator("#n-error")).to_contain_text("servicio de cada concepto")


# ---------------------------------------------------------------------------
def test_alta_de_usuario_y_su_primer_ingreso(nav):
    entrar(nav, *ADMIN)
    ir(nav, "Usuarios")
    nav.get_by_role("button", name="Nuevo usuario").click()
    nav.fill("#u-nombre", "María  José")
    nav.fill("#u-apellidos", "Pérez López")
    nav.fill("#u-email", "MJ@Sifat.Test")
    nav.select_option("#u-rol", "Facturista")

    # Contraseña débil: las reglas se ven sin cumplir y no se envía
    nav.fill("#u-pass", "corta")
    expect(nav.locator("[data-regla=largo]").first).to_have_text("○ Al menos 12 caracteres")
    nav.get_by_role("button", name="Registrar usuario").click()
    expect(nav.locator("#usr-error")).to_contain_text("contraseña")

    # Contiene el nombre: tampoco
    nav.fill("#u-pass", "Perez2026clave")
    expect(nav.locator("#u-reglas [data-regla=personal]")).to_contain_text("○")

    nav.fill("#u-pass", "Facturas2026xyz")
    nav.fill("#u-pass2", "Facturas2026xy")
    expect(nav.locator("#u-reglas [data-regla=igual]")).to_contain_text("○")
    nav.fill("#u-pass2", "Facturas2026xyz")
    for regla in ("largo", "letras", "personal", "igual"):
        expect(nav.locator(f"#u-reglas [data-regla={regla}]")).to_contain_text("✓")
    nav.get_by_role("button", name="Registrar usuario").click()
    aviso(nav, "María José Pérez López ya puede iniciar sesión con mj@sifat.test")
    expect(nav.locator("main table")).to_contain_text("María José Pérez López")

    # La persona nueva entra, no ve Usuarios y cambia su contraseña
    salir(nav)
    entrar(nav, "mj@sifat.test", "Facturas2026xyz")
    expect(nav.locator("aside nav")).not_to_contain_text("Usuarios")
    nav.locator("aside").get_by_role("link", name="Mi cuenta").click()
    nav.fill("#c-actual", "equivocada")
    nav.fill("#c-nueva", "OtraClave2027ab")
    nav.fill("#c-nueva2", "OtraClave2027ab")
    nav.get_by_role("button", name="Cambiar contraseña").click()
    expect(nav.locator("#cuenta-error")).to_contain_text("La contraseña actual no es correcta")
    nav.fill("#c-actual", "Facturas2026xyz")
    nav.get_by_role("button", name="Cambiar contraseña").click()
    aviso(nav, "Contraseña cambiada")
    salir(nav)
    entrar(nav, "mj@sifat.test", "OtraClave2027ab")


def test_correo_repetido_en_usuarios(nav):
    entrar(nav, *ADMIN)
    ir(nav, "Usuarios")
    nav.get_by_role("button", name="Nuevo usuario").click()
    nav.fill("#u-nombre", "Otro")
    nav.fill("#u-apellidos", "Usuario")
    nav.fill("#u-email", "luis@sifat.test")
    nav.fill("#u-pass", "Facturas2026xyz")
    nav.fill("#u-pass2", "Facturas2026xyz")
    nav.get_by_role("button", name="Registrar usuario").click()
    expect(nav.locator("#usr-error")).to_have_text("Ya existe un usuario con ese correo.")


def test_desactivar_activar_y_restablecer(nav):
    entrar(nav, *ADMIN)
    ir(nav, "Usuarios")
    fila_ana = nav.locator("main table tr", has_text="Ana Lopez")
    expect(fila_ana.get_by_role("button", name="Desactivar")).to_have_count(0)  # a sí misma no

    nav.locator("main table tr", has_text="Luis Perez").get_by_role("button", name="Desactivar").click()
    expect(nav.locator("#est-titulo")).to_have_text("¿Desactivar a Luis Perez?")
    nav.locator("#dlg-estado").get_by_role("button", name="Desactivar").click()
    aviso(nav, "Luis Perez ya no puede entrar")
    expect(nav.locator("main table tr", has_text="Luis Perez")).to_contain_text("Inactivo")

    # Luis ya no entra
    salir(nav)
    nav.fill("#login-email", FACTURISTA[0])
    nav.fill("#login-pass", FACTURISTA[1])
    nav.click("form[action='/login'] button[type=submit]")
    expect(nav.get_by_text("Correo o contraseña incorrectos")).to_be_visible()

    # Se reactiva y se le pone contraseña nueva
    entrar(nav, *ADMIN)
    ir(nav, "Usuarios")
    nav.locator("main table tr", has_text="Luis Perez").get_by_role("button", name="Activar").click()
    nav.locator("#dlg-estado").get_by_role("button", name="Activar").click()
    aviso(nav, "Luis Perez puede volver a entrar")
    nav.locator("main table tr", has_text="Luis Perez").get_by_role("button", name=re.compile("contraseña", re.I)).click()
    expect(nav.locator("#res-nombre")).to_have_text("Luis Perez")
    nav.fill("#r-pass", "NuevaClave2027x")
    nav.fill("#r-pass2", "NuevaClave2027x")
    nav.get_by_role("button", name="Guardar contraseña").click()
    aviso(nav, "Contraseña de Luis Perez actualizada")
    salir(nav)
    entrar(nav, FACTURISTA[0], "NuevaClave2027x")


# ---------------------------------------------------------------------------
def test_facturista_no_ve_lo_del_administrador(nav):
    entrar(nav, *ADMIN)
    _emitir(nav, [("SRV-001", "1")])
    nav.get_by_role("button", name="Emitir factura").click()
    aviso(nav, "emitida")
    salir(nav)

    entrar(nav, *FACTURISTA)
    expect(nav.locator("aside nav")).not_to_contain_text("Usuarios")
    expect(nav.get_by_role("button", name="Nuevo servicio")).to_have_count(0)
    ir(nav, "Facturas")
    nav.get_by_role("button", name="FAC-0100").click()
    expect(nav.locator("#fac-conceptos tr")).to_have_count(1)
    expect(nav.locator("#fac-cancelar")).to_be_hidden()
    expect(nav.locator("#fac-pagar")).to_be_visible()  # registrar pagos sí puede
    nav.goto(nav.base + "/usuarios")
    nav.wait_for_url("**/catalogo")


def test_en_celular_no_hay_desbordes(nav):
    nav.set_viewport_size({"width": 390, "height": 844})
    entrar(nav, *ADMIN)
    for ruta in ("/facturas", "/clientes", "/pagos", "/usuarios", "/cuenta"):
        nav.goto(nav.base + ruta)
        ancho = nav.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        assert ancho[0] <= ancho[1], f"{ruta}: la página se desborda a lo ancho {ancho}"
    nav.goto(nav.base + "/facturas")
    nav.get_by_role("button", name="Nueva factura").click()
    expect(nav.locator("#dlg-nueva")).to_be_visible()
    caja = nav.locator("#dlg-nueva").bounding_box()
    assert caja["x"] >= 0 and caja["x"] + caja["width"] <= 390


# ---------------------------------------------------------------------------
def test_catalogo_alta_edicion_y_baja(nav):
    entrar(nav, *ADMIN)
    nav.get_by_role("button", name="Nuevo servicio").click()
    expect(nav.locator("#f-id")).to_have_value("SRV-003")  # siguiente identificador libre
    nav.fill("#f-clave", "soporte-1")
    nav.fill("#f-nombre", "Soporte Remoto")
    nav.fill("#f-cat", "Soporte")
    nav.fill("#f-precio", "10.555")  # más de 2 decimales: se rechaza
    nav.locator("#dlg-form").get_by_role("button", name="Guardar servicio").click()
    expect(nav.locator("#form-error")).to_be_visible()
    nav.fill("#f-precio", "850")
    nav.get_by_role("button", name="Agregar característica").click()
    fila = nav.locator("#f-caract > div").first
    fila.get_by_label("Nombre de la característica").fill("Horario")
    fila.get_by_label("Valor de la característica").fill("9 a 18 h")
    nav.locator("#dlg-form").get_by_role("button", name="Guardar servicio").click()
    aviso(nav, "Servicio agregado")

    # Buscar y abrir el detalle
    nav.fill("#q", "remoto")
    expect(nav.locator("#tabla-servicios tbody tr:visible")).to_have_count(1)
    nav.get_by_role("button", name="Soporte Remoto").click()
    expect(nav.locator("#det-clave")).to_have_text("SRV-003 · SOPORTE-1")
    expect(nav.locator("#det-caract")).to_contain_text("9 a 18 h")

    # Editar el precio
    nav.locator("#dlg-detalle").get_by_role("button", name="Editar").click()
    nav.fill("#f-precio", "900")
    nav.locator("#dlg-form").get_by_role("button", name="Guardar servicio").click()
    aviso(nav, "Servicio guardado")
    expect(nav.locator("#tabla-servicios tr", has_text="Soporte Remoto")).to_contain_text("$900.00")

    # Dar de baja: hay que escribir el identificador para confirmar
    nav.get_by_role("button", name="Soporte Remoto").click()
    nav.locator("#dlg-detalle").get_by_role("button", name="Dar de baja").click()
    boton = nav.locator("#dlg-borrar").get_by_role("button", name="Dar de baja")
    expect(boton).to_be_disabled()
    nav.fill("#borrar-confirma", "SRV-003")
    boton.click()
    aviso(nav, "Servicio dado de baja")
    expect(nav.locator("#tabla-servicios tr", has_text="Soporte Remoto")).to_contain_text("Inactivo")

    # Un servicio inactivo ya no muestra "Dar de baja" en su detalle
    nav.get_by_role("button", name="Soporte Remoto").click()
    expect(nav.locator("#det-borrar")).to_be_hidden()
