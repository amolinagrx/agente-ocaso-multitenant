# Breaking changes

- Ya no se crean credenciales `admin/ocaso2025`; el seed exige `SUPER_ADMIN_EMAIL` y genera o recibe una contraseña segura.
- El login usa email y tenant; `username` se mantiene como compatibilidad interna.
- Todas las rutas de negocio requieren subdominio o prefijo de tenant. Las URLs absolutas `/api/...` o `/portal/...` deben conservar el prefijo mediante `url_for`.
- Toda operación ORM sobre modelos tenant-scoped sin contexto lanza `TenantContextMissing`.
- Las tablas incorporan `tenant_id`; unicidades globales pasan a ser compuestas.
- Los uploads se trasladan a `/uploads/{tenant_id}/...`.
- El backup/restauración global desde Ajustes deja de estar disponible para administradores de oficina. El reset borra únicamente el tenant actual.
- `db.create_all()` ya no intenta alterar silenciosamente una base legacy; el proceso se niega a arrancar hasta ejecutar el migrador.
- La configuración principal de branding/locale/timezone reside en `tenants.config_json`; `configuracion` permanece tenant-scoped para compatibilidad funcional.
