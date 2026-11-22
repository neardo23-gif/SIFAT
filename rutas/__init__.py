"""Un Blueprint por pantalla. Cada uno trae su página y sus rutas /api/."""
from rutas import auth, catalogo, clientes, facturas, pagos, usuarios

BLUEPRINTS = [auth.bp, catalogo.bp, clientes.bp, facturas.bp, pagos.bp, usuarios.bp]
