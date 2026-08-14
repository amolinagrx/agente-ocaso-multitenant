from pathlib import Path

import pytest

from services.storage import tenant_upload_path, validated_tenant_file
from services.tenant_context import TenantContextMissing, tenant_context


def test_uploads_are_separated_by_tenant(app, tenants):
    with app.app_context():
        with tenant_context(tenants['alpha']):
            alpha_path = Path(tenant_upload_path('../../documento.pdf', 'clientes'))
            alpha_path.write_bytes(b'alpha')
            assert tenants['alpha'].id in alpha_path.parts
            assert validated_tenant_file(str(alpha_path)) == str(alpha_path)
        with tenant_context(tenants['beta']):
            beta_path = Path(tenant_upload_path('documento.pdf', 'clientes'))
            assert tenants['beta'].id in beta_path.parts
            assert alpha_path != beta_path


def test_upload_without_tenant_fails(app):
    with app.app_context(), pytest.raises(TenantContextMissing):
        tenant_upload_path('documento.pdf')
