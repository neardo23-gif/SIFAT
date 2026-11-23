# SIFAT · Front

Flask + Jinja + Tailwind (compilado) para el catálogo de servicios, facturas, clientes y pagos.
El navegador nunca habla con AWS ni con el backend: `app.py` hace de proxy y guarda las claves.

```
Navegador ──HTTPS──► nginx ──► gunicorn (este repo, 127.0.0.1:5001)
                                   ├──X-API-Key──► Backend SIFAT-BACKEND (127.0.0.1:8000) ──► MySQL (RDS)
                                   └──x-api-key──► API Gateway ──► Lambda ──► DynamoDB (servicios)
```

## Arranque local
Requiere **Python 3.10 o más reciente** (en Mac: `brew install python@3.13`).
```bash
/opt/homebrew/bin/python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # y llena API_KEY, BACKEND_API_KEY y SECRET_KEY
python app.py                 # http://127.0.0.1:5000  (el backend debe estar encendido)
pytest                        # pruebas sin red
```
Las pruebas no necesitan red: simulan API Gateway y el backend.

**En navegador** (Chromium con Playwright, contra un backend simulado en memoria, sin tocar la base):
```bash
pip install -r requirements-e2e.txt && python -m playwright install chromium
pytest tests/e2e
```
Sin Playwright instalado, `pytest` se salta estas pruebas.
 Para probar contra los servicios
reales (solo lectura): `SIFAT_PRUEBAS_REALES=1 pytest tests/test_integracion_real.py`.

## Qué puede hacer cada rol
| Acción | Administrador | Facturista |
|---|:-:|:-:|
| Ver todo | ✓ | ✓ |
| Alta y edición del catálogo de servicios | ✓ | |
| Alta y edición de clientes | ✓ | ✓ |
| Activar / desactivar clientes | ✓ | |
| Emitir facturas | ✓ | ✓ |
| Cancelar facturas (vigentes y sin pagos) | ✓ | |
| Registrar pagos | ✓ | ✓ |
| Registrar, desactivar y restablecer la contraseña de usuarios | ✓ | |
| Cambiar su propia contraseña (Mi cuenta) | ✓ | ✓ |

Los permisos se validan en el servidor (`PERMISOS` en `seguridad.py`); ocultar botones es solo comodidad.
Cada 5 minutos el front pregunta al backend si el usuario sigue activo: si un Administrador lo
desactiva, pierde el acceso en minutos aunque tenga la sesión abierta.
Quién emite una factura lo decide la sesión, y precios e impuestos los pone el backend desde el catálogo.

## Rutas del proxy
| Método | Ruta | Va a |
|---|---|---|
| POST, PUT, DELETE | `/api/servicios` | API Gateway `/servicios` |
| POST | `/api/clientes` | Backend `POST /clientes` |
| PATCH | `/api/clientes/<id>` | Backend `PATCH /clientes/<id>` |
| POST | `/api/facturas` | Backend `POST /facturas` |
| GET | `/api/facturas/<folio>` | Backend `GET /facturas/<folio>` |
| POST | `/api/facturas/<folio>/cancelar` | Backend `POST /facturas/<folio>/cancelar` |
| POST | `/api/pagos` | Backend `POST /pagos` |
| POST | `/api/usuarios` | Backend `POST /usuarios` (la confirmación de contraseña se revisa en el front) |
| PATCH | `/api/usuarios/<id>` | Backend `PATCH /usuarios/<id>` (activar/desactivar; nunca a uno mismo) |
| POST | `/api/usuarios/<id>/contrasena` | Backend `POST /usuarios/<id>/contrasena` |
| POST | `/api/cuenta/contrasena` | Backend `POST /auth/cambiar-contrasena` (el usuario sale de la sesión) |
| GET | `/salud` | Comprobación de vida (pública) |

Todas las rutas `/api/` piden sesión, y las que escriben piden además el token CSRF (cabecera `X-CSRF-Token`).

## Producción
Front y backend corren en el **mismo servidor**: el backend solo escucha en `127.0.0.1`.

1. **Código** en `/opt/sifat/front` y `/opt/sifat/backend`, con un usuario de sistema `sifat`.
2. **Entorno** de cada uno: `python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
3. **`.env` del front** (permisos `600`):
   `APP_ENV=production`, `SESSION_COOKIE_SECURE=true`, `TRUST_PROXY=true`,
   `FLASK_DEBUG=false`, `PORT=5001`, un `SECRET_KEY` nuevo y las claves. Si falta algo, la app
   no arranca y dice qué falta.
4. **`.env` del backend:** `ENABLE_DOCS=false`.
5. **Servicios:** copia `deploy/sifat-front.service` (y `deploy/sifat-backend.service` del otro repo)
   a `/etc/systemd/system/` y actívalos con `systemctl enable --now`.
6. **nginx + HTTPS:** usa `deploy/nginx-sifat.conf` con tu dominio y genera el certificado con certbot.
7. **Comprueba:** `curl https://tu-dominio/salud` → `{"estado":"ok"}`.

gunicorn corre con 1 proceso y varios hilos (`gunicorn.conf.py`), porque el límite de intentos
de login por IP vive en memoria.

## Tailwind
El CSS ya está compilado en `static/css/tailwind.css`. Si cambias clases en las plantillas o en `static/js/`:
```bash
npm ci
npm run build:css      # o: npm run watch:css
```

## Estructura
```
app.py              arma la app: configuración, seguridad y Blueprints
config.py           variables de entorno y validar_produccion()
seguridad.py        sesión, PERMISOS por rol, CSRF, límite de intentos, cabeceras
backend.py          llamadas al backend (MySQL) y a API Gateway (catálogo)
rutas/              un Blueprint por pantalla, con su página y sus rutas /api/
  auth.py           portada, login, logout, /salud
  catalogo.py · clientes.py · facturas.py · pagos.py · usuarios.py · cuenta.py
  comun.py          utilidades compartidas (fechas, moneda, JSON)
templates/          una plantilla por pantalla + base, app_base y _avisos
static/js/comun.js  utilidades del navegador (window.SIFAT); se carga en todas las páginas
static/js/<pantalla>.js   lo propio de cada pantalla; solo se carga en la suya
static/css/         app.css (tokens, modales) y tailwind.css (compilado)
gunicorn.conf.py · deploy/   producción (gunicorn, systemd, nginx)
```
