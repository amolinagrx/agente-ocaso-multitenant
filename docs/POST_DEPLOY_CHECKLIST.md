# Checklist post-deploy

- [ ] Backup legacy localizado y restauración ensayada.
- [ ] `PRAGMA foreign_key_check` vacío o constraints PostgreSQL validadas.
- [ ] Las 24 tablas originales tienen `tenant_id`; solo super-admins tienen `users.tenant_id = NULL`.
- [ ] DNS wildcard y certificado TLS válidos.
- [ ] Login por subdominio y por path funcionan.
- [ ] Una sesión del tenant A no abre una URL del tenant B.
- [ ] Mismo email/DNI/número de póliza se puede usar en tenants distintos.
- [ ] Tenant inactivo devuelve error genérico y no filtra su existencia.
- [ ] API keys funcionan únicamente en el host/path de su tenant.
- [ ] Upload, preview, descarga y borrado quedan bajo `/uploads/{tenant_id}`.
- [ ] Branding, locale y timezone se leen del tenant correcto.
- [ ] Logs contienen `tenant=<uuid>` durante peticiones tenant-scoped.
- [ ] `python3 -m pytest -q` termina sin fallos.
- [ ] Smoke test de carga ejecutado con `python3 -m pytest -q -m load`.
- [ ] Secretos no usan valores de `.env.example`.
- [ ] Rate limiting distribuido (Redis) configurado antes de escalar a varios workers.
- [ ] Métricas/alertas segmentadas por tenant y plan de rotación de backups aprobados.
