"""Resolve active tenants from a trusted subdomain or a path prefix."""

from __future__ import annotations

import logging
import os

from flask import abort, request

from models import Tenant
from services.tenant_context import clear_current_tenant, set_current_tenant


RESERVED_PATHS = {
    'admin', 'login', 'logout', 'static', 'health', 'v1', 'set-remember-cookie',
    'verify-2fa', 'cambiar-password', 'recuperar',
}


class TenantPathMiddleware:
    """Strip `/tenant-slug` before Flask routes the request."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        method = os.environ.get('TENANT_RESOLUTION_METHOD', 'subdomain').lower()
        if method not in {'subdomain', 'path', 'hybrid'}:
            method = 'subdomain'
        path = environ.get('PATH_INFO', '/')
        first, separator, rest = path.lstrip('/').partition('/')
        if first and first not in RESERVED_PATHS and method in {'subdomain', 'path', 'hybrid'}:
            host = environ.get('HTTP_HOST', '').split(':', 1)[0].lower()
            base_domain = os.environ.get('TENANT_BASE_DOMAIN', 'gestion.ocasoarmilla.es').lower()
            is_main_host = host in {base_domain, f'www.{base_domain}', 'localhost', '127.0.0.1'}
            if is_main_host:
                environ['ocaso.tenant_path_slug'] = first.lower()
                environ['SCRIPT_NAME'] = environ.get('SCRIPT_NAME', '') + '/' + first
                environ['PATH_INFO'] = '/' + rest if separator else '/'
        return self.app(environ, start_response)


def _subdomain_slug() -> str | None:
    method = os.environ.get('TENANT_RESOLUTION_METHOD', 'subdomain').lower()
    if method == 'path':
        return None
    host = request.host.split(':', 1)[0].lower()
    base_domain = os.environ.get('TENANT_BASE_DOMAIN', 'gestion.ocasoarmilla.es').lower()
    suffix = '.' + base_domain
    if host.endswith(suffix):
        candidate = host[:-len(suffix)].split('.')[0]
        if candidate and candidate != 'www':
            return candidate
    return None


def _requested_slug() -> str | None:
    path_slug = request.environ.get('ocaso.tenant_path_slug')
    return _subdomain_slug() or path_slug


def resolve_tenant():
    clear_current_tenant()
    slug = _requested_slug()
    if request.endpoint in {
        'auth.login', 'auth.recuperar', 'auth.recuperar_cambiar'
    } and request.method == 'POST' and not slug:
        slug = (request.form.get('tenant') or '').strip().lower() or None
    if not slug:
        return None

    tenant = Tenant.query.filter_by(subdomain=slug, active=True).first()
    if tenant is None:
        abort(404)
    set_current_tenant(tenant)
    return None


class TenantLogFilter(logging.Filter):
    def filter(self, record):
        from services.tenant_context import get_current_tenant_id

        record.tenant_id = get_current_tenant_id() or '-'
        return True


def init_tenant_middleware(app):
    app.wsgi_app = TenantPathMiddleware(app.wsgi_app)
    app.before_request(resolve_tenant)
    app.teardown_request(lambda _error: clear_current_tenant())

    tenant_filter = TenantLogFilter()
    for handler in app.logger.handlers:
        handler.addFilter(tenant_filter)
        handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)s tenant=%(tenant_id)s %(message)s'
        ))
