"""Request-local tenant context. Tenant identity is never sourced from session."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from flask import g, has_request_context


class TenantContextMissing(RuntimeError):
    pass


class TenantIsolationViolation(RuntimeError):
    pass


_tenant_id_var: ContextVar[str | None] = ContextVar('tenant_id', default=None)
_tenant_var: ContextVar[object | None] = ContextVar('tenant', default=None)


def set_current_tenant(tenant) -> None:
    _tenant_var.set(tenant)
    _tenant_id_var.set(str(tenant.id) if tenant is not None else None)
    if has_request_context():
        g.current_tenant = tenant
        g.tenant_id = str(tenant.id) if tenant is not None else None


def clear_current_tenant() -> None:
    set_current_tenant(None)


def get_current_tenant():
    if has_request_context():
        return getattr(g, 'current_tenant', None)
    return _tenant_var.get()


def get_current_tenant_id() -> str | None:
    if has_request_context():
        value = getattr(g, 'tenant_id', None)
        return str(value) if value else None
    return _tenant_id_var.get()


@contextmanager
def tenant_context(tenant):
    """Explicit tenant context for CLI tasks, tests and admin operations."""
    previous_tenant = _tenant_var.get()
    previous_id = _tenant_id_var.get()
    set_current_tenant(tenant)
    try:
        yield tenant
    finally:
        _tenant_var.set(previous_tenant)
        _tenant_id_var.set(previous_id)
        if has_request_context():
            g.current_tenant = previous_tenant
            g.tenant_id = previous_id
