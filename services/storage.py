"""Tenant-separated upload paths and path validation."""

from __future__ import annotations

from pathlib import Path

from flask import abort, current_app
from werkzeug.utils import secure_filename

from services.tenant_context import TenantContextMissing, get_current_tenant_id


def tenant_upload_directory(category: str | None = None) -> Path:
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise TenantContextMissing('El almacenamiento requiere contexto de tenant')
    root = Path(current_app.config['UPLOAD_FOLDER']).resolve()
    folder = root / tenant_id
    if category:
        folder = folder / secure_filename(category)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def tenant_upload_path(filename: str, category: str | None = None) -> str:
    safe_name = secure_filename(filename)
    if not safe_name:
        raise ValueError('Nombre de archivo no válido')
    return str(tenant_upload_directory(category) / safe_name)


def validated_tenant_file(path: str) -> str:
    candidate = Path(path).resolve()
    root = tenant_upload_directory().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        abort(404)
    if not candidate.is_file():
        abort(404)
    return str(candidate)
