"""Global super-admin tenant management endpoints."""

from __future__ import annotations

from functools import wraps
import json

from flask import Blueprint, abort, jsonify, redirect, render_template, request
from flask_login import current_user, login_required

from models import Tenant, User, db
from services.tenant_context import tenant_context
from services.tenant_service import TenantService


admin_bp = Blueprint('admin', __name__)


def super_admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_super_admin or current_user.tenant_id is not None:
            abort(404)
        return view(*args, **kwargs)
    return wrapped


def _tenant_payload(tenant: Tenant) -> dict:
    try:
        config = json.loads(tenant.config_json or '{}')
    except json.JSONDecodeError:
        config = {}
    return {
        'id': tenant.id,
        'name': tenant.name,
        'subdomain': tenant.subdomain,
        'config': config,
        'active': tenant.active,
        'created_at': tenant.created_at.isoformat() if tenant.created_at else None,
    }


@admin_bp.route('/tenants', methods=['GET'])
@super_admin_required
def list_tenants():
    tenants = Tenant.query.order_by(Tenant.name).all()
    if request.args.get('format') == 'json' or request.accept_mimetypes.best == 'application/json':
        return jsonify({'tenants': [_tenant_payload(tenant) for tenant in tenants]})
    return render_template('admin/tenants.html', tenants=tenants)


@admin_bp.route('/tenants', methods=['POST'])
@super_admin_required
def create_tenant():
    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        tenant = TenantService.create_tenant(data)
        admin_email = str(data.get('admin_email', '')).strip().lower()
        admin_password = str(data.get('admin_password', ''))
        if admin_email:
            if len(admin_password) < 8:
                raise ValueError('Datos de tenant no válidos')
            with tenant_context(tenant):
                admin = User(
                    tenant_id=tenant.id,
                    username=admin_email,
                    email=admin_email,
                    nombre=data.get('admin_name') or 'Administrador',
                    is_admin=True,
                    activo=True,
                    permisos='{}',
                )
                admin.set_password(admin_password)
                db.session.add(admin)
                db.session.flush()
        db.session.commit()
    except (ValueError, TypeError):
        db.session.rollback()
        return jsonify({'error': 'No se pudo completar la operación'}), 400
    return jsonify({'tenant': _tenant_payload(tenant)}), 201


@admin_bp.route('/tenants/<tenant_id>', methods=['PATCH'])
@super_admin_required
def update_tenant(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        abort(404)
    data = request.get_json(silent=True) or request.form.to_dict()
    if 'active' in data:
        tenant.active = data['active'] in {True, 1, '1', 'true', 'on', 'yes'}
    if 'name' in data and str(data['name']).strip():
        tenant.name = str(data['name']).strip()
    if 'config' in data:
        config = data['config']
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError:
                return jsonify({'error': 'No se pudo completar la operación'}), 400
        tenant.config_json = json.dumps(config, ensure_ascii=False)
    db.session.commit()
    return jsonify({'tenant': _tenant_payload(tenant)})


@admin_bp.route('/tenants/<tenant_id>/switch', methods=['POST'])
@super_admin_required
def switch_tenant(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None or not tenant.active:
        abort(404)
    return redirect(f'/{tenant.subdomain}/dashboard/')
