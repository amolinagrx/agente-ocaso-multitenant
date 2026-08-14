# Arquitectura multi-tenant

## Modelo de datos

La base es compartida y el esquema es compartido. `tenants` es global; `users.tenant_id` es nullable únicamente para super-admins; las otras 23 tablas originales tienen `tenant_id NOT NULL`. Las claves de negocio antes globales son compuestas por tenant (email/username, DNI, número de póliza, expediente, configuración y mes/año de cartera).

Cada tabla tenant-scoped tiene índice `(tenant_id, id)` y los accesos frecuentes añaden índices como `(tenant_id, nombre)`, `(tenant_id, cliente_id)` o `(tenant_id, estado)`.

## Flujo de una petición

1. `TenantPathMiddleware` extrae y retira el prefijo `/oficina1` antes del routing.
2. `TenantResolver` prioriza un subdominio válido y usa el path como fallback; consulta un tenant activo y lo guarda en `flask.g`/`ContextVar`, nunca lo obtiene de la sesión.
3. Flask-Login carga el usuario solo si el `tenant_id` firmado en su sesión coincide con el tenant resuelto. El super-admin global es la única excepción explícita.
4. Los eventos de SQLAlchemy aplican `with_loader_criteria` a todo SELECT tenant-scoped, añaden condición a UPDATE/DELETE y bloquean operaciones sin tenant.
5. `before_flush` asigna el tenant a objetos nuevos y rechaza objetos de otro tenant.
6. Los uploads se guardan bajo `/uploads/{tenant_id}/{categoria}` y se valida el path antes de servirlo.

Las consultas globales de `tenants` no se filtran. Las lecturas globales de super-admin usan una opción interna explícita `tenant_bypass=True`; no se acepta `tenant_id` del frontend como fuente de autoridad.

## Configuración por tenant

`tenants.config_json` contiene `branding`, `locale`, `timezone`, `plan` y `features`. Los ajustes de la oficina actualizan branding/locale/timezone. El super-admin puede editar plan/features por el endpoint global.

## Límites conocidos

- SQLite es compatible y mantiene rollback sencillo, pero PostgreSQL es recomendable para múltiples procesos y carga de escritura sostenida.
- El rate limit actual se separa por tenant+IP y se guarda en sesión. Para despliegue horizontal debe sustituirse por Redis/Flask-Limiter.
- Billing se representa mediante `plan`/`features`; no hay aún proveedor de pagos ni medición facturable.
