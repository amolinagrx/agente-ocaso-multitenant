"""Mandatory SQLAlchemy tenant filters and write guards."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from models import TenantScopedMixin, User
from services.tenant_context import (
    TenantContextMissing,
    TenantIsolationViolation,
    get_current_tenant_id,
)


def _is_scoped_entity(entity) -> bool:
    try:
        return isinstance(entity, type) and issubclass(entity, TenantScopedMixin)
    except TypeError:
        return False


def _select_has_scoped_entity(statement) -> bool:
    for description in getattr(statement, 'column_descriptions', ()):  # ORM Select
        if _is_scoped_entity(description.get('entity')):
            return True
    return False


def _mapper_entity(execute_state):
    mapper = getattr(execute_state, 'bind_mapper', None)
    return mapper.class_ if mapper is not None else None


@event.listens_for(Session, 'do_orm_execute')
def enforce_tenant_on_execute(execute_state):
    if execute_state.execution_options.get('tenant_bypass'):
        return

    tenant_id = get_current_tenant_id()
    if execute_state.is_select:
        scoped = _select_has_scoped_entity(execute_state.statement)
        if tenant_id is None:
            if scoped:
                raise TenantContextMissing('La operación requiere contexto de tenant')
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantScopedMixin,
                lambda model: model.tenant_id == tenant_id,
                include_aliases=True,
            )
        )
        return

    entity = _mapper_entity(execute_state)
    if not _is_scoped_entity(entity):
        return
    if tenant_id is None:
        raise TenantContextMissing('La operación requiere contexto de tenant')
    if execute_state.is_update or execute_state.is_delete:
        execute_state.statement = execute_state.statement.where(entity.tenant_id == tenant_id)
    elif execute_state.is_insert:
        raise TenantIsolationViolation('Usa objetos ORM para escrituras tenant-scoped')


@event.listens_for(Session, 'before_flush')
def enforce_tenant_on_flush(session, _flush_context, _instances):
    tenant_id = get_current_tenant_id()
    for item in session.new:
        if not isinstance(item, TenantScopedMixin):
            continue
        if isinstance(item, User) and item.is_super_admin and item.tenant_id is None:
            continue
        if tenant_id is None:
            raise TenantContextMissing('La escritura requiere contexto de tenant')
        if item.tenant_id is None:
            item.tenant_id = tenant_id
        elif str(item.tenant_id) != tenant_id:
            raise TenantIsolationViolation('Escritura fuera del tenant activo')

    for item in session.dirty.union(session.deleted):
        if not isinstance(item, TenantScopedMixin):
            continue
        if isinstance(item, User) and item.is_super_admin and item.tenant_id is None:
            continue
        if tenant_id is None:
            raise TenantContextMissing('La escritura requiere contexto de tenant')
        if str(item.tenant_id) != tenant_id:
            raise TenantIsolationViolation('Escritura fuera del tenant activo')
