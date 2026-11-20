"""Configuración de gunicorn para producción.

Arranque:  gunicorn -c gunicorn.conf.py app:app
Escucha solo en 127.0.0.1: nginx recibe el tráfico HTTPS y lo reenvía aquí.
"""
import os

bind = f"127.0.0.1:{os.getenv('PORT', '5001')}"

# Un solo proceso con hilos: el límite de intentos de login por IP vive en
# memoria, y con varios procesos cada uno llevaría su propia cuenta.
workers = 1
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "8"))

# Emitir una factura consulta DynamoDB por cada concepto; se deja margen
timeout = 45
graceful_timeout = 20
keepalive = 5

# Bitácoras a la salida estándar: systemd/journald las guarda
accesslog = "-"
errorlog = "-"
loglevel = "info"
# Sin la cadena de consulta: no queremos datos de búsqueda en las bitácoras
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'

# Reinicia el proceso cada cierto número de peticiones (evita fugas de memoria)
max_requests = 2000
max_requests_jitter = 200
