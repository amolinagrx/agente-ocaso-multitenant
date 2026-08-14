import pytest

from app import create_app
from models import Cliente, Tenant, User, db
from services.tenant_context import tenant_context


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/test.db')
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key')
    monkeypatch.setenv('OCASO_ENV', 'development')
    monkeypatch.setenv('TENANT_RESOLUTION_METHOD', 'path')
    monkeypatch.setenv('TENANT_BASE_DOMAIN', 'gestion.test')

    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with application.app_context():
        alpha = Tenant(name='Alpha', subdomain='alpha', active=True)
        beta = Tenant(name='Beta', subdomain='beta', active=True)
        db.session.add_all([alpha, beta])
        db.session.commit()

        with tenant_context(alpha):
            alpha_user = User(
                username='shared@example.com', email='shared@example.com',
                password='pending', nombre='Alpha Admin', is_admin=True, activo=True,
            )
            alpha_user.set_password('password-123')
            db.session.add_all([
                alpha_user,
                Cliente(nombre='Cliente Alpha', dni='DNI-COMPARTIDO'),
            ])
            db.session.commit()

        with tenant_context(beta):
            beta_user = User(
                username='shared@example.com', email='shared@example.com',
                password='pending', nombre='Beta Admin', is_admin=True, activo=True,
            )
            beta_user.set_password('password-123')
            db.session.add_all([
                beta_user,
                Cliente(nombre='Cliente Beta', dni='DNI-COMPARTIDO'),
            ])
            db.session.commit()

        super_admin = User(
            tenant_id=None, username='root@example.com', email='root@example.com',
            password='pending', nombre='Root', is_admin=True, is_super_admin=True, activo=True,
        )
        super_admin.set_password('password-123')
        db.session.add(super_admin)
        db.session.commit()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tenants(app):
    with app.app_context():
        return {
            'alpha': Tenant.query.filter_by(subdomain='alpha').one(),
            'beta': Tenant.query.filter_by(subdomain='beta').one(),
        }
