# Migración desde single-tenant

## Precondiciones

Detén escrituras, conserva el volumen `/data` y genera un UUID real. No hardcodees el tenant inicial en producción.

```bash
export DEFAULT_TENANT_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
export DEFAULT_TENANT_NAME="Oficina actual"
export DEFAULT_TENANT_SUBDOMAIN="oficina-actual"
export SUPER_ADMIN_EMAIL="superadmin@empresa.es"
export SUPER_ADMIN_PASSWORD="una-clave-larga-y-aleatoria"
export INITIAL_ADMIN_EMAIL="admin@empresa.es"
export INITIAL_ADMIN_PASSWORD="otra-clave-larga-y-aleatoria"

docker compose down
python3 scripts/migrate_to_multitenant.py --database /data/ocaso.db
python3 scripts/seed_multitenant.py
python3 -m pytest -q
docker compose up -d --build
```

El migrador:

1. fuerza un checkpoint WAL;
2. crea `ocaso.db.<fecha>.bak` sin modificar el origen;
3. crea las 25 tablas con restricciones compuestas;
4. copia todas las filas y asigna el UUID inicial a los 24 modelos originales;
5. copia ficheros legacy a `/data/uploads/{tenant_id}/legacy/...` sin borrar los originales;
6. ejecuta `PRAGMA foreign_key_check`;
7. reemplaza la base solo si la validación termina correctamente.

Los usuarios existentes quedan dentro del tenant inicial. El super-admin global se crea aparte y nunca reutiliza la contraseña del administrador legacy.

## Rollback

La versión single-tenant no entiende las nuevas tablas. Para volver:

```bash
docker compose down
cp /data/ocaso.db.<fecha>.bak /data/ocaso.db
git switch main
docker compose up -d --build
```

Los uploads legacy originales no se borran, por lo que el rollback conserva sus rutas. Todo dato escrito después de la migración debe exportarse antes del rollback; no existe downgrade automático porque perdería tenants adicionales.
