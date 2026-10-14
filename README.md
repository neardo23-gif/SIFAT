# SIFAT · Front

Flask + Jinja + Tailwind (compilado) para el catálogo de servicios, facturas, clientes y pagos.

## Arranque
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # USE_MOCK=true por defecto
python app.py                 # http://127.0.0.1:5000
```

## Conectar con API Gateway
En `.env`: `USE_MOCK=false` y `API_BASE_URL=https://<id>.execute-api.us-east-1.amazonaws.com/dev`.
El navegador nunca llama a AWS: `app.py` hace de proxy en `/api/servicios` (POST, PUT, DELETE) y renderiza el GET.

## Tailwind
El CSS ya está compilado en `static/css/tailwind.css`. Si cambias clases en las plantillas:
```bash
npm install
npm run build:css      # o: npm run watch:css
```

## Estructura
- `app.py` rutas y proxy · `mock_data.py` datos de ejemplo
- `templates/` landing, catálogo, facturas, clientes, pagos
- `static/css/app.css` tokens, movimiento, modales · `static/js/app.js` filtros, modales, CRUD
