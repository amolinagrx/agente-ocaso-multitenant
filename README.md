# Agente Ocaso Multi-tenant

Versión multi-tenant de Agente Ocaso. Conserva la aplicación Flask/Jinja original y aplica aislamiento obligatorio por tenant en la resolución HTTP, ORM, autenticación, API y almacenamiento.

## Stack detectado

- Frontend: Jinja2 server-rendered, Bootstrap 5, HTMX y JavaScript.
- Backend: Python 3.11, Flask 3 y blueprints.
- Datos: Flask-SQLAlchemy 3 / SQLAlchemy 2; SQLite original, con `DATABASE_URL` para PostgreSQL.
- Auth: Flask-Login, sesión firmada de Flask, Werkzeug PBKDF2 y TOTP con `pyotp`.
- Entradas: `app.py` (aplicación), `models.py` (25 tablas), `routes/` (HTTP), `scripts/` (migración/seed).

## Arranque desde cero

```bash
git clone https://github.com/amolinagrx/agente-ocaso-multitenant.git
cd agente-ocaso-multitenant
git checkout multitenant

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env
# Edita .env y exporta sus variables antes de continuar.
set -a; source .env; set +a

python3 -c "from app import create_app; create_app()"
python3 scripts/seed_multitenant.py
python3 -m pytest -q

docker compose up -d --build
docker compose logs -f ocaso
```

Para una base existente no uses el arranque de esquema vacío: sigue [Migración](docs/MIGRATION.md). La guía de DNS/proxy y despliegue está en [Despliegue](docs/DEPLOYMENT.md).

## Crear un tenant

Como super-admin:

```bash
curl -X POST https://gestion.ocasoarmilla.es/admin/tenants \
  -H 'Content-Type: application/json' \
  -b cookies.txt \
  -d '{"name":"Oficina 1","subdomain":"oficina1","admin_email":"admin@oficina1.es","admin_password":"cambiar-esta-clave"}'
```

También puede hacerse desde `/admin/tenants`. El acceso queda disponible en:

- `https://oficina1.gestion.ocasoarmilla.es/login`
- `https://gestion.ocasoarmilla.es/oficina1/login`

## Comandos operativos

```bash
# Migrar base single-tenant existente (crea backup antes de reemplazarla)
python3 scripts/migrate_to_multitenant.py \
  --database /data/ocaso.db \
  --tenant-id "$DEFAULT_TENANT_ID" \
  --tenant-name "Oficina inicial" \
  --subdomain oficina-inicial

# Seed inicial seguro
python3 scripts/seed_multitenant.py

# Datos demo, solo dentro de un tenant ya existente
python3 seed.py --tenant oficina-inicial

# Tests normales y smoke de carga
python3 -m pytest -q -m 'not load'
python3 -m pytest -q -m load

# Deploy / rollback de contenedor
docker compose build --pull
docker compose up -d
docker compose ps
docker compose down
```

## Documentación

- [Arquitectura y garantías](docs/ARCHITECTURE.md)
- [Migración y rollback](docs/MIGRATION.md)
- [Subdominios y despliegue](docs/DEPLOYMENT.md)
- [Breaking changes](docs/BREAKING_CHANGES.md)
- [Checklist post-deploy](docs/POST_DEPLOY_CHECKLIST.md)
