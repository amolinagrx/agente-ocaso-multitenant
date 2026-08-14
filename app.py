import os
import secrets
from flask import Flask, abort, session
from flask_login import LoginManager, current_user, logout_user
from models import db, User


def create_app(run_startup_tasks=True):
    app = Flask(__name__)

    @app.context_processor
    def inject_globals():
        from models import COMPANIAS_ESPANA, RAMOS_ESPANA
        import json
        from services.tenant_context import get_current_tenant
        version = '1.0.0'
        try:
            with open(os.path.join(os.path.dirname(__file__), 'VERSION')) as f:
                version = f.read().strip()
        except Exception:
            pass
        tenant = get_current_tenant()
        try:
            tenant_config = json.loads(tenant.config_json or '{}') if tenant else {}
        except (TypeError, json.JSONDecodeError):
            tenant_config = {}
        return {
            'companias': COMPANIAS_ESPANA,
            'ramos_list': RAMOS_ESPANA,
            'today': __import__('datetime').date.today(),
            'app_version': version,
            'current_tenant': tenant,
            'tenant_config': tenant_config,
        }

    @app.route('/')
    def root():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.is_super_admin:
                return redirect(url_for('admin.list_tenants'))
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('OCASO_ENV') != 'development'
    data_dir = os.environ.get('DATA_DIR', '/data')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', f'sqlite:///{data_dir}/ocaso.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = f'{data_dir}/uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    db.init_app(app)

    # Importing registers SQLAlchemy's mandatory tenant guards.
    from services import tenant_isolation  # noqa: F401
    from middleware import init_tenant_middleware
    from services.tenant_context import (
        TenantContextMissing,
        TenantIsolationViolation,
        get_current_tenant_id,
    )
    init_tenant_middleware(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from sqlalchemy import select

        request_tenant_id = get_current_tenant_id()
        session_tenant_id = session.get('tenant_id')
        if session_tenant_id:
            if str(session_tenant_id) != str(request_tenant_id):
                return None
            return db.session.get(User, int(user_id))

        statement = (
            select(User)
            .where(User.id == int(user_id), User.tenant_id.is_(None), User.is_super_admin.is_(True))
            .execution_options(tenant_bypass=True)
        )
        return db.session.execute(statement).scalar_one_or_none()

    @app.before_request
    def validate_authenticated_tenant():
        if not current_user.is_authenticated:
            return None
        tenant_id = get_current_tenant_id()
        if current_user.is_super_admin:
            return None
        if not tenant_id or str(current_user.tenant_id) != tenant_id:
            logout_user()
            session.clear()
            abort(404)
        if str(session.get('tenant_id')) != tenant_id:
            logout_user()
            session.clear()
            abort(404)
        return None

    @app.errorhandler(TenantContextMissing)
    @app.errorhandler(TenantIsolationViolation)
    def handle_tenant_security_error(error):
        app.logger.warning('Operación rechazada por aislamiento: %s', type(error).__name__)
        return ('Solicitud no disponible', 404)

    from routes.auth import auth_bp
    from routes.recibos import recibos_bp
    from routes.clientes import clientes_bp
    from routes.polizas import polizas_bp
    from routes.renovaciones import renovaciones_bp
    from routes.siniestros import siniestros_bp
    from routes.dashboard import dashboard_bp
    from routes.comunicaciones import comunicaciones_bp
    from routes.whatsapp import whatsapp_bp
    from routes.listados import listados_bp
    from routes.asistente import asistente_bp
    from routes.ajustes import ajustes_bp
    from routes.usuarios import usuarios_bp
    from routes.agenda import agenda_bp
    from routes.leads import leads_bp
    from routes.portal import portal_bp
    from routes.utilidades import utilidades_bp
    from routes.cartera import cartera_bp
    from routes.api_externa import api_externa_bp
    from routes.api import api_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(recibos_bp, url_prefix='/recibos')
    app.register_blueprint(clientes_bp, url_prefix='/clientes')
    app.register_blueprint(polizas_bp, url_prefix='/polizas')
    app.register_blueprint(renovaciones_bp, url_prefix='/renovaciones')
    app.register_blueprint(siniestros_bp, url_prefix='/siniestros')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(comunicaciones_bp, url_prefix='/comunicaciones')
    app.register_blueprint(whatsapp_bp, url_prefix='/whatsapp')
    app.register_blueprint(listados_bp, url_prefix='/listados')
    app.register_blueprint(asistente_bp, url_prefix='/asistente')
    app.register_blueprint(ajustes_bp, url_prefix='/ajustes')
    app.register_blueprint(usuarios_bp, url_prefix='/usuarios')
    app.register_blueprint(agenda_bp, url_prefix='/agenda')
    app.register_blueprint(leads_bp, url_prefix='/leads')
    app.register_blueprint(portal_bp)
    app.register_blueprint(utilidades_bp, url_prefix='/utilidades')
    app.register_blueprint(cartera_bp, url_prefix='/cartera')
    app.register_blueprint(api_externa_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    if run_startup_tasks:
        with app.app_context():
            _prepare_database()

    return app


def _prepare_database():
    """Create a fresh schema or reject a legacy database before serving traffic."""
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if not tables:
        db.create_all()
        return
    if 'users' in tables:
        user_columns = {column['name'] for column in inspector.get_columns('users')}
        if 'tenant_id' not in user_columns:
            raise RuntimeError(
                'Esquema single-tenant detectado. Ejecuta '
                '`python scripts/migrate_to_multitenant.py` antes de arrancar.'
            )
    db.create_all()


if __name__ == '__main__':
    app = create_app()
    debug = os.environ.get('OCASO_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=5050, debug=debug)
