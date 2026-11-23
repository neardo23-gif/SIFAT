"""Utilidades compartidas por las rutas."""
import re

from flask import request

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
FOLIO_RE = re.compile(r"^FAC-\d{4,10}$")
JSON_INVALIDO = {"mensaje": "El cuerpo de la petición debe ser un objeto JSON"}


def contexto_base(active):
    """Lo que necesita app_base.html: pantalla activa y de dónde salen los datos."""
    return {"active": active, "origen": "API Gateway" if active == "catalogo" else "Backend (MySQL)"}


def json_objeto():
    """El cuerpo JSON de la petición si es un objeto; None si falta o es otra cosa."""
    crudo = request.get_json(silent=True)
    return crudo if isinstance(crudo, dict) else None


def fecha_corta(valor):
    """'2026-10-14T18:30:00' -> '14 oct 2026'."""
    try:
        anio, mes, dia = str(valor)[:10].split("-")
        return f"{int(dia):02d} {MESES[int(mes) - 1]} {anio}"
    except (ValueError, IndexError):
        return "-"


def mxn(valor):
    """Filtro de plantilla: 1160 -> '$1,160.00'."""
    try:
        return "${:,.2f}".format(float(valor))
    except (TypeError, ValueError):
        return "-"


def pagina_pedida():
    """El número de página de ?pagina=N (1 si falta o no es válido)."""
    try:
        return max(1, min(int(request.args.get("pagina", 1)), 10000))
    except ValueError:
        return 1


def paginacion(pagina, hay_mas, **extra):
    """Lo que necesita _paginacion.html. `extra` son otros parámetros a conservar en los enlaces."""
    return {"pagina": pagina, "hay_mas": hay_mas, "anterior": pagina - 1 if pagina > 1 else None,
            "siguiente": pagina + 1 if hay_mas else None, "extra": {k: v for k, v in extra.items() if v}}
