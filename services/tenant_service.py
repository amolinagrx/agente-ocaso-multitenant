"""Tenant lifecycle and configuration operations."""

from __future__ import annotations

import json
import re

from flask import g, has_request_context, request, url_for

from models import Tenant, db
from services.tenant_context import get_current_tenant, set_current_tenant


SUBDOMAIN_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


class TenantService:
    @staticmethod
    def get_current_tenant():
        return get_current_tenant()

    @staticmethod
    def create_tenant(data: dict) -> Tenant:
        name = str(data.get('name', '')).strip()
        subdomain = str(data.get('subdomain', '')).strip().lower()
        if not name or not SUBDOMAIN_RE.fullmatch(subdomain):
            raise ValueError('Datos de tenant no válidos')
        if Tenant.query.filter_by(subdomain=subdomain).first():
            raise ValueError('Datos de tenant no válidos')

        config = data.get('config') or {
            'branding': {'name': name, 'logo': None, 'primary_color': '#b7192e'},
            'locale': data.get('locale', 'es-ES'),
            'timezone': data.get('timezone', 'Europe/Madrid'),
            'plan': data.get('plan', 'standard'),
            'features': data.get('features', {}),
        }
        tenant = Tenant(
            name=name,
            subdomain=subdomain,
            config_json=json.dumps(config, ensure_ascii=False),
            active=bool(data.get('active', True)),
        )
        db.session.add(tenant)
        db.session.flush()
        return tenant

    @staticmethod
    def switch_tenant(tenant_id: str) -> Tenant:
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None or not tenant.active:
            raise ValueError('Tenant no disponible')
        db.session.expire_all()
        set_current_tenant(tenant)
        if has_request_context():
            g.tenant_switched_by_admin = True
        return tenant

    @staticmethod
    def get_tenant_config(tenant_id: str | None = None) -> dict:
        tenant = get_current_tenant() if tenant_id is None else db.session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError('Tenant no disponible')
        try:
            return json.loads(tenant.config_json or '{}')
        except (TypeError, json.JSONDecodeError):
            return {}

    # Compatibility with the service names in the architecture specification.
    getCurrentTenant = get_current_tenant
    createTenant = create_tenant
    switchTenant = switch_tenant
    getTenantConfig = get_tenant_config


def tenant_url_for(endpoint: str, **values) -> str:
    """Build a tenant-preserving URL for subdomain and path-based requests."""
    target = url_for(endpoint, **values)
    tenant = get_current_tenant()
    if tenant is None or request.environ.get('ocaso.tenant_path_slug'):
        return target
    host = request.host.split(':', 1)[0].lower()
    base_domain = __import__('os').environ.get(
        'TENANT_BASE_DOMAIN', 'gestion.ocasoarmilla.es'
    ).lower()
    if host in {base_domain, f'www.{base_domain}', 'localhost', '127.0.0.1'}:
        return f'/{tenant.subdomain}{target}'
    return target
