"""Acciones comunes de las pruebas en navegador."""


def entrar(page, email, password):
    page.goto(page.base + "/")
    page.fill("#login-email", email)
    page.fill("#login-pass", password)
    page.click("form[action='/login'] button[type=submit]")
    page.wait_for_url("**/catalogo")


def salir(page):
    page.locator("aside form[action='/logout'] button").click()
    page.wait_for_url(page.base + "/")
