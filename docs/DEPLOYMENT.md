# Despliegue y subdominios

## DNS y TLS

Crea un registro wildcard `*.gestion.ocasoarmilla.es` hacia el balanceador y otro para `gestion.ocasoarmilla.es`. El certificado debe cubrir ambos nombres. El proxy debe conservar el `Host` original.

Ejemplo Nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name gestion.ocasoarmilla.es *.gestion.ocasoarmilla.es;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://127.0.0.1:5050;
    }
}
```

Configura `TENANT_BASE_DOMAIN=gestion.ocasoarmilla.es`. `TENANT_RESOLUTION_METHOD=subdomain` activa subdominio con fallback de path; `path` desactiva la lectura por subdominio; `hybrid` es un alias explícito del modo combinado.

## Docker

```bash
cp .env.example .env
# Define secretos y UUIDs reales.
docker compose config
docker compose build --pull
docker compose up -d
docker compose exec ocaso python3 scripts/seed_multitenant.py
docker compose ps
curl -fsS https://gestion.ocasoarmilla.es/v1/health
```

El contenedor ejecuta Gunicorn. SQLite debe usar un único worker; para escalar horizontalmente configura PostgreSQL mediante `DATABASE_URL=postgresql+psycopg://usuario:clave@host/db` y un almacenamiento compartido/objeto para uploads.

## Crear oficinas posteriores

Inicia sesión como super-admin en el dominio principal, abre `/admin/tenants`, crea la oficina y su administrador, y verifica tanto URL de subdominio como URL de path. Desactivar un tenant produce una respuesta genérica 404 y no elimina datos.
