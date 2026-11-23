#!/usr/bin/env bash
# Publica en el servidor de AWS Academy lo que tiene commit en ambos repos.
#
#   ./deploy/aws-academy/publicar.sh
#
# Requisitos: el lab encendido y sus credenciales en ~/.aws/credentials.
# Conserva la IP, el certificado HTTPS y los .env del servidor. Si el front no
# responde después de actualizar, se regresa solo a la versión anterior.
set -euo pipefail

INSTANCIA="${SIFAT_INSTANCIA:-i-037f78480ad572271}"
BUCKET="${SIFAT_BUCKET:-sifat-despliegue-583479798355-edf684}"
REGION="${AWS_REGION:-us-east-1}"
URL="${SIFAT_URL:-https://34-235-98-187.sslip.io}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
FRONT="$(cd "$AQUI/../.." && pwd)"
BACKEND="${SIFAT_BACKEND_DIR:-$(cd "$FRONT/.." && pwd)/SIFAT-BACKEND}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

aws sts get-caller-identity >/dev/null 2>&1 || {
  echo "Las credenciales de AWS no sirven o caducaron. Inicia el lab y pega las nuevas en ~/.aws/credentials."; exit 1; }

for repo in "$FRONT" "$BACKEND"; do
  [ -z "$(git -C "$repo" status --porcelain)" ] || echo "Aviso: $repo tiene cambios sin commit; NO se publican."
done

# ---- Código: solo lo que tiene commit, nunca el .env ----
git -C "$FRONT" archive --format=zip -o "$TMP/front.zip" HEAD
git -C "$BACKEND" archive --format=zip -o "$TMP/backend.zip" HEAD
for app in front backend; do
  if unzip -l "$TMP/$app.zip" | grep -qE '(^|/)\.env$'; then echo "El zip de $app trae un .env: me detengo."; exit 1; fi
  # La versión que estaba publicada queda como respaldo en el bucket
  aws s3 cp "s3://$BUCKET/$app.zip" "s3://$BUCKET/$app.anterior.zip" --region "$REGION" --only-show-errors || true
  aws s3 cp "$TMP/$app.zip" "s3://$BUCKET/$app.zip" --region "$REGION" --only-show-errors
done
echo "Front:   $(git -C "$FRONT" log -1 --format='%h %s')"
echo "Backend: $(git -C "$BACKEND" log -1 --format='%h %s')"

# ---- Actualizar el servidor por Session Manager ----
sed "s|__BUCKET__|$BUCKET|" "$AQUI/actualizar-servidor.sh" > "$TMP/actualizar.sh"
python3 -c 'import json,sys; print(json.dumps({"commands": open(sys.argv[1]).read().splitlines()}))' \
  "$TMP/actualizar.sh" > "$TMP/parametros.json"
CMD=$(aws ssm send-command --instance-ids "$INSTANCIA" --document-name AWS-RunShellScript --region "$REGION" \
      --comment "SIFAT: publicar $(git -C "$FRONT" rev-parse --short HEAD)" \
      --parameters "file://$TMP/parametros.json" --timeout-seconds 600 --query Command.CommandId --output text)
echo "Actualizando el servidor ($CMD)…"
for _ in $(seq 1 60); do
  ESTADO=$(aws ssm get-command-invocation --command-id "$CMD" --instance-id "$INSTANCIA" --region "$REGION" \
           --query Status --output text 2>/dev/null || echo Pending)
  case "$ESTADO" in Success|Failed|Cancelled|TimedOut) break ;; esac
  sleep 5
done
aws ssm get-command-invocation --command-id "$CMD" --instance-id "$INSTANCIA" --region "$REGION" \
  --query StandardOutputContent --output text | tail -5
[ "$ESTADO" = Success ] || { echo "La actualización terminó en estado $ESTADO."; exit 1; }

# ---- Comprobación desde fuera ----
if curl -fsS -m 15 "$URL/salud" >/dev/null; then
  echo "Listo: $URL responde."
else
  echo "El servidor se actualizó pero $URL no responde; revisa con: aws ssm start-session --target $INSTANCIA"
  exit 1
fi
