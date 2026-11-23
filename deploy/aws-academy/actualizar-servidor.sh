#!/bin/bash
# Corre DENTRO del servidor (lo manda publicar.sh por Session Manager).
# Cambia el código por el del bucket y conserva .env, los entornos de Python y el
# certificado de RDS. La versión anterior queda en /opt/sifat/*.anterior.
set -euo pipefail
B="__BUCKET__"; R=/opt/sifat
for app in front backend; do
  aws s3 cp "s3://$B/$app.zip" /tmp/$app.zip --region us-east-1 --only-show-errors
  rm -rf $R/$app.nuevo && mkdir $R/$app.nuevo && unzip -q /tmp/$app.zip -d $R/$app.nuevo && rm -f /tmp/$app.zip
done
for app in front backend; do
  # Se conservan .env, el entorno de Python y el certificado de RDS
  mv $R/$app/.env $R/$app.nuevo/.env
  mv $R/$app/.venv $R/$app.nuevo/.venv
  if [ -d $R/$app/certs ]; then mv $R/$app/certs $R/$app.nuevo/certs; fi
  rm -rf $R/$app.anterior && mv $R/$app $R/$app.anterior && mv $R/$app.nuevo $R/$app
  $R/$app/.venv/bin/python -m pip install -q -r $R/$app/requirements.txt
done
chown -R root:root $R/front $R/backend && chmod -R a+rX $R/front $R/backend
chown root:sifat $R/front/.env $R/backend/.env && chmod 640 $R/front/.env $R/backend/.env
cp $R/backend/deploy/sifat-backend.service $R/front/deploy/sifat-front.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart sifat-backend && sleep 2 && systemctl restart sifat-front
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:5001/salud >/dev/null; then echo "ACTUALIZADO $(date -Is)"; systemctl is-active sifat-backend sifat-front nginx; exit 0; fi
  sleep 2
done
echo "EL FRONT NO RESPONDE: regreso a la versión anterior"
journalctl -u sifat-front -u sifat-backend -n 40 --no-pager
for app in front backend; do
  mv $R/$app/.env $R/$app.anterior/.env
  mv $R/$app/.venv $R/$app.anterior/.venv
  if [ -d $R/$app/certs ]; then mv $R/$app/certs $R/$app.anterior/certs; fi
  rm -rf $R/$app.fallida && mv $R/$app $R/$app.fallida && mv $R/$app.anterior $R/$app
done
cp $R/backend/deploy/sifat-backend.service $R/front/deploy/sifat-front.service /etc/systemd/system/
systemctl daemon-reload && systemctl restart sifat-backend && sleep 2 && systemctl restart sifat-front
exit 1
