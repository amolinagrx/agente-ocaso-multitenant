# Migraciones

- Instalación nueva SQLite: `sqlite3 /data/ocaso.db < migrations/001_multitenant_schema.sql`.
- Base single-tenant existente: usa `python3 scripts/migrate_to_multitenant.py`. Este es el camino recomendado porque reconstruye las restricciones globales como restricciones por tenant, valida claves foráneas, copia uploads y conserva un backup fechado.
- PostgreSQL: define `DATABASE_URL` y crea el esquema desde los modelos antes del primer despliegue. La migración de datos incluida es deliberadamente específica de SQLite, que es el motor de la aplicación original.

No arranques la aplicación contra una base legacy. El arranque la detecta y falla con un mensaje que indica el comando de migración, evitando servir tráfico con aislamiento incompleto.
