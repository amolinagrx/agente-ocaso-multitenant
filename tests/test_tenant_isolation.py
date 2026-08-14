import pytest

from models import Cliente, User, db
from services.tenant_context import (
    TenantContextMissing,
    TenantIsolationViolation,
    tenant_context,
)


def test_same_email_and_business_keys_are_allowed_per_tenant(app, tenants):
    with app.app_context():
        with tenant_context(tenants['alpha']):
            assert User.query.filter_by(email='shared@example.com').one().nombre == 'Alpha Admin'
            assert Cliente.query.filter_by(dni='DNI-COMPARTIDO').one().nombre == 'Cliente Alpha'
        with tenant_context(tenants['beta']):
            assert User.query.filter_by(email='shared@example.com').one().nombre == 'Beta Admin'
            assert Cliente.query.filter_by(dni='DNI-COMPARTIDO').one().nombre == 'Cliente Beta'


def test_query_without_tenant_fails_closed(app):
    with app.app_context(), pytest.raises(TenantContextMissing):
        Cliente.query.all()


def test_cross_tenant_lookup_and_bulk_update_are_isolated(app, tenants):
    with app.app_context():
        with tenant_context(tenants['beta']):
            beta_id = Cliente.query.one().id
        with tenant_context(tenants['alpha']):
            assert db.session.get(Cliente, beta_id) is None
            assert Cliente.query.update({'notas': 'solo-alpha'}) == 1
            db.session.commit()
        with tenant_context(tenants['beta']):
            assert Cliente.query.one().notas is None


def test_cross_tenant_write_is_rejected(app, tenants):
    with app.app_context(), tenant_context(tenants['alpha']):
        foreign_row = Cliente(
            tenant_id=tenants['beta'].id,
            nombre='No permitido',
        )
        db.session.add(foreign_row)
        with pytest.raises(TenantIsolationViolation):
            db.session.commit()
        db.session.rollback()


def test_login_session_cannot_cross_to_another_tenant(client):
    response = client.post('/alpha/login', data={
        'email': 'shared@example.com',
        'password': 'password-123',
    })
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/alpha/dashboard/')
    with client.session_transaction() as session:
        alpha_tenant_id = session['tenant_id']

    allowed = client.get('/alpha/clientes/')
    assert allowed.status_code == 200
    assert b'Cliente Alpha' in allowed.data

    rejected = client.get('/beta/clientes/', follow_redirects=False)
    assert rejected.status_code in {302, 404}
    assert b'Cliente Beta' not in rejected.data
    with client.session_transaction() as session:
        assert session.get('tenant_id') == alpha_tenant_id


def test_super_admin_can_login_only_on_global_entrypoint(client):
    response = client.post('/login', data={
        'email': 'root@example.com',
        'password': 'password-123',
    })
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/tenants')
    listing = client.get('/admin/tenants?format=json')
    assert listing.status_code == 200
    assert {item['subdomain'] for item in listing.json['tenants']} == {'alpha', 'beta'}


def test_global_health_does_not_require_a_tenant(client):
    response = client.get('/v1/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
