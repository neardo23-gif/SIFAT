# Despliegue en AWS Academy (Learner Lab)

Learner Lab no permite CloudFront ni crear roles IAM, así que todo corre en una EC2:

```
Usuario ──HTTPS──► EC2 (IP elástica, <ip>.sslip.io)
                    ├─ nginx :443 (Let's Encrypt) y :80 (redirige a HTTPS)
                    ├─ front   gunicorn 127.0.0.1:5001
                    └─ backend uvicorn  127.0.0.1:8000 ──► RDS rds-sifat-db :3306
```

- **Dominio:** `sslip.io` convierte la IP en un nombre (`34-235-98-187.sslip.io` → `34.235.98.187`),
  y con eso Let's Encrypt emite un certificado válido. Si falla, `arranque.sh` usa uno autofirmado.
- **Permisos:** la EC2 usa `LabInstanceProfile` (LabRole) para leer el bucket y para Session Manager.
- **Sin SSH:** el grupo `sifat-servidor` solo abre 80 y 443. Para entrar al servidor:
  `aws ssm start-session --target <id-instancia>`.
- **Secretos:** los `.env` de producción viven en el bucket privado `sifat-despliegue-*`, nunca en el repo.

## Recursos creados
| Recurso | Nombre / ID |
|---|---|
| EC2 `t3.small` (Amazon Linux 2023) | etiqueta `Name=sifat-servidor` |
| IP elástica + interfaz de red | etiqueta `Name=sifat-servidor` |
| Grupo de seguridad | `sifat-servidor` (80 y 443 públicos) |
| Regla en el SG del RDS | 3306 desde `sifat-servidor` |
| Bucket S3 privado | `sifat-despliegue-<cuenta>-<sufijo>` (código y `.env`) |

## Publicar una versión nueva
El servidor instala lo que hay en el bucket cuando arranca por primera vez. Para actualizar:
1. Haz commit en ambos repos.
2. Sube el código nuevo (solo lo que tiene commit, nunca el `.env`):
   ```bash
   git -C ~/Desktop/SIFAT archive --format=zip -o /tmp/front.zip HEAD
   git -C ~/Desktop/SIFAT-BACKEND archive --format=zip -o /tmp/backend.zip HEAD
   aws s3 cp /tmp/front.zip   s3://<bucket>/front.zip
   aws s3 cp /tmp/backend.zip s3://<bucket>/backend.zip
   ```
3. Reemplaza la instancia: termínala y lanza otra con la misma interfaz de red (conserva la IP)
   y `arranque.sh` como user data, con `__BUCKET__`, `__REGION__` y `__DOMINIO__` reemplazados.

## Limitaciones del laboratorio
- Al terminar la sesión del lab la instancia se apaga, y el sitio no responde hasta que vuelves
  a iniciarlo. Los servicios arrancan solos al encender la instancia y la IP no cambia.
- Las credenciales del lab caducan cada ~4 horas.
