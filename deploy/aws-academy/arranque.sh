#!/bin/bash
# Arranque del servidor SIFAT en Amazon Linux 2023 (user data de EC2).
# Bitácora: /var/log/sifat-init.log y la consola de la instancia.
set -euo pipefail
exec > >(tee -a /var/log/sifat-init.log /dev/console) 2>&1
echo "== SIFAT: inicio $(date -Is)"

BUCKET="__BUCKET__"
REGION="__REGION__"
DOMINIO="__DOMINIO__"
RAIZ=/opt/sifat

# ---------- Paquetes ----------
dnf install -y -q nginx unzip
if dnf install -y -q python3.12 python3.12-pip; then PY=python3.12; else dnf install -y -q python3.11 python3.11-pip; PY=python3.11; fi
echo "== Python: $($PY --version)"

id sifat >/dev/null 2>&1 || useradd --system --home-dir $RAIZ --shell /sbin/nologin sifat

# ---------- Código y configuración desde S3 (bucket privado) ----------
rm -rf $RAIZ && mkdir -p $RAIZ/front $RAIZ/backend
for app in front backend; do
  aws s3 cp "s3://$BUCKET/$app.zip" /tmp/$app.zip --region "$REGION" --only-show-errors
  unzip -q /tmp/$app.zip -d $RAIZ/$app && rm -f /tmp/$app.zip
  aws s3 cp "s3://$BUCKET/$app.env" $RAIZ/$app/.env --region "$REGION" --only-show-errors
done

mkdir -p $RAIZ/backend/certs
curl -fsSL -o $RAIZ/backend/certs/global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem

for app in front backend; do
  $PY -m venv $RAIZ/$app/.venv
  $RAIZ/$app/.venv/bin/pip install -q --upgrade pip
  $RAIZ/$app/.venv/bin/pip install -q -r $RAIZ/$app/requirements.txt
done

# El código es de root y solo se lee; los .env solo los lee el usuario del servicio
chown -R root:root $RAIZ && chmod -R a+rX $RAIZ
chown root:sifat $RAIZ/front/.env $RAIZ/backend/.env && chmod 640 $RAIZ/front/.env $RAIZ/backend/.env

cp $RAIZ/backend/deploy/sifat-backend.service $RAIZ/front/deploy/sifat-front.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sifat-backend
systemctl enable --now sifat-front

# ---------- nginx, fase 1: solo HTTP, para que Let's Encrypt valide el dominio ----------
mkdir -p /var/www/certbot
escribir_nginx() {  # $1 = ruta del certificado, $2 = ruta de la llave
cat > /etc/nginx/nginx.conf <<NGINX
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    server_tokens off;
    log_format sifat '\$remote_addr "\$request_method \$uri" \$status \$body_bytes_sent \$request_time';
    access_log /var/log/nginx/access.log sifat;

    server {
        listen 80 default_server;
        server_name _;
        location /.well-known/acme-challenge/ { root /var/www/certbot; }
        location / { return 301 https://$DOMINIO\$request_uri; }
    }
NGINX
if [ -n "$1" ]; then
cat >> /etc/nginx/nginx.conf <<NGINX
    server {
        listen 443 ssl default_server;
        http2 on;
        server_name $DOMINIO;
        ssl_certificate     $1;
        ssl_certificate_key $2;
        ssl_protocols TLSv1.2 TLSv1.3;
        client_max_body_size 64k;

        location /static/ {
            alias /opt/sifat/front/static/;
            expires 7d;
            add_header Cache-Control "public";
            add_header X-Content-Type-Options "nosniff";
        }
        location / {
            proxy_pass http://127.0.0.1:5001;
            proxy_set_header Host \$host;
            # Con TRUST_PROXY=true el front toma de aquí la IP real (límite de intentos)
            proxy_set_header X-Forwarded-For \$remote_addr;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_read_timeout 60s;
        }
    }
NGINX
fi
echo "}" >> /etc/nginx/nginx.conf
nginx -t
}
escribir_nginx "" ""
systemctl enable --now nginx

# ---------- Certificado: Let's Encrypt; si falla, autofirmado para no quedar sin HTTPS ----------
$PY -m venv /opt/certbot
/opt/certbot/bin/pip install -q --upgrade pip
/opt/certbot/bin/pip install -q certbot
if /opt/certbot/bin/certbot certonly --webroot -w /var/www/certbot -d "$DOMINIO" \
     --non-interactive --agree-tos --register-unsafely-without-email; then
  CERT=/etc/letsencrypt/live/$DOMINIO/fullchain.pem; LLAVE=/etc/letsencrypt/live/$DOMINIO/privkey.pem
  echo "== Certificado de Let's Encrypt emitido"
  # Renovación automática dos veces al día (Let's Encrypt dura 90 días)
  cat > /etc/systemd/system/certbot-renovar.service <<'UNIT'
[Unit]
Description=Renovar certificado de Let's Encrypt
[Service]
Type=oneshot
ExecStart=/opt/certbot/bin/certbot renew --quiet --deploy-hook "systemctl reload nginx"
UNIT
  cat > /etc/systemd/system/certbot-renovar.timer <<'UNIT'
[Unit]
Description=Renovar certificado dos veces al día
[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=1h
Persistent=true
[Install]
WantedBy=timers.target
UNIT
  systemctl daemon-reload && systemctl enable --now certbot-renovar.timer
else
  echo "== Let's Encrypt falló: uso un certificado autofirmado (el navegador mostrará advertencia)"
  mkdir -p /etc/nginx/ssl
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 -subj "/CN=$DOMINIO" \
    -keyout /etc/nginx/ssl/sifat.key -out /etc/nginx/ssl/sifat.crt
  chmod 600 /etc/nginx/ssl/sifat.key
  CERT=/etc/nginx/ssl/sifat.crt; LLAVE=/etc/nginx/ssl/sifat.key
fi

# ---------- nginx, fase 2: HTTPS ----------
escribir_nginx "$CERT" "$LLAVE"
systemctl reload nginx

for i in $(seq 1 30); do
  if curl -fsSk "https://127.0.0.1/salud" -H "Host: $DOMINIO" >/dev/null; then
    echo "== SIFAT: listo en https://$DOMINIO $(date -Is)"; exit 0
  fi
  sleep 2
done
echo "== SIFAT: el front no respondió; revisa journalctl -u sifat-front -u sifat-backend"
exit 1
