"""Global super-admin tenant management endpoints."""

from __future__ import annotations

from datetime import date, datetime
from functools import wraps
import io
import json
import os
import zipfile

from flask import Blueprint, abort, jsonify, redirect, render_template, request, send_file
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


# ---- Export / Import oficina completa ----

_EXPORT_TABLES = [
    'users',
    'configuracion',
    'plantillas_comunicacion',
    'clientes',
    'documentos_conocimiento',
    'cartera_ficheros',
    'polizas',
    'chunks_conocimiento',
    'recibos',
    'renovaciones',
    'siniestros',
    'hitos_siniestro',
    'documentos_siniestro',
    'historial_contacto',
    'documentos_cliente',
    'comunicaciones',
    'mensajes_asistente',
    'agenda',
    'leads',
    'cartera',
    'api_keys',
    'cartera_polizas',
    'cartera_bajas',
    'cartera_altas',
]

_MODEL_BY_TABLE = {m.__tablename__: m for m in (
    __import__('models', fromlist=['_TENANT_MODELS'])._TENANT_MODELS
)}


def _serialize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row_to_dict(row):
    data = {}
    for column in row.__table__.columns:
        data[column.name] = _serialize_value(getattr(row, column.name))
    return data


def _collect_tenant_data(tenant_id: str) -> dict:
    from models import _TENANT_MODELS

    tables = {}
    with tenant_context(db.session.get(Tenant, tenant_id)):
        for model in _TENANT_MODELS:
            if model.__tablename__ == 'tenants':
                continue
            rows = model.query.all()
            tables[model.__tablename__] = [_row_to_dict(r) for r in rows]
    return tables


@admin_bp.route('/tenants/<tenant_id>/export', methods=['GET'])
@super_admin_required
def export_tenant(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        abort(404)

    tables = _collect_tenant_data(tenant.id)

    # Recolectar uploads del tenant
    upload_root = None
    try:
        from flask import current_app
        from pathlib import Path
        upload_root = Path(current_app.config['UPLOAD_FOLDER']).resolve() / tenant.id
    except Exception:
        upload_root = None

    manifest = {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(),
        'tenant': _tenant_payload(tenant),
        'tables': list(tables.keys()),
        'counts': {k: len(v) for k, v in tables.items()},
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('tenant.json', json.dumps(_tenant_payload(tenant), ensure_ascii=False, indent=2))
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr('data.json', json.dumps(tables, ensure_ascii=False, indent=2, default=str))

        if upload_root and upload_root.is_dir():
            for file_path in upload_root.rglob('*'):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(upload_root.parent))
                    zf.write(str(file_path), arcname=f'uploads/{arcname}')

    buffer.seek(0)
    filename = f'oficina-{tenant.subdomain}-{datetime.utcnow().strftime("%Y%m%d")}.zip'
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/zip',
    )


@admin_bp.route('/tenants/import', methods=['POST'])
@super_admin_required
def import_tenant():
    import uuid
    from pathlib import Path

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'Selecciona un archivo .zip de oficina'}), 400
    if not file.filename.lower().endswith('.zip'):
        return jsonify({'error': 'El archivo debe ser .zip'}), 400

    new_subdomain = (request.form.get('subdomain') or '').strip().lower()
    new_name = (request.form.get('name') or '').strip()

    try:
        data = file.read()
        zf = zipfile.ZipFile(io.BytesIO(data))
        tenant_payload = json.loads(zf.read('tenant.json'))
        tables = json.loads(zf.read('data.json'))
    except Exception as exc:
        return jsonify({'error': f'Archivo no válido: {exc}'}), 400

    # Resolver subdomain y nombre
    source_subdomain = tenant_payload.get('subdomain', 'oficina-importada')
    source_name = tenant_payload.get('name', 'Oficina importada')
    subdomain = new_subdomain or source_subdomain
    name = new_name or source_name

    if not subdomain or not name:
        return jsonify({'error': 'Falta subdomain o nombre'}), 400

    # Validar subdomain
    import re
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', subdomain):
        return jsonify({'error': 'Identificador no válido (a-z, 0-9, guiones)'}), 400
    if Tenant.query.filter_by(subdomain=subdomain).first():
        return jsonify({'error': f'Ya existe una oficina con identificador \"{subdomain}\"'}), 400

    # Crear tenant nuevo
    new_tenant_id = str(uuid.uuid4())
    config_json = tenant_payload.get('config', {})
    if isinstance(config_json, dict):
        # Actualizar branding name al nuevo nombre si coincide con el original
        branding = config_json.get('branding', {})
        if isinstance(branding, dict) and branding.get('name') == source_name:
            branding['name'] = name
        config_str = json.dumps(config_json, ensure_ascii=False)
    else:
        config_str = json.dumps(tenant_payload.get('config', {}), ensure_ascii=False)
        # Fallback: si config es string ya serializado
        try:
            cfg = json.loads(tenant_payload.get('config_json') or '{}')
            config_str = json.dumps(cfg, ensure_ascii=False)
        except Exception:
            config_str = '{}'

    # Si tenant_payload trae config_json como string
    if tenant_payload.get('config_json'):
        try:
            cfg = json.loads(tenant_payload['config_json']) if isinstance(tenant_payload['config_json'], str) else tenant_payload['config_json']
            config_str = json.dumps(cfg, ensure_ascii=False)
        except Exception:
            pass

    new_tenant = Tenant(
        id=new_tenant_id,
        name=name,
        subdomain=subdomain,
        config_json=config_str,
        active=True,
    )
    db.session.add(new_tenant)
    db.session.flush()

    # Mapeo de IDs viejos -> nuevos por tabla
    id_maps: dict[str, dict] = {t: {} for t in _EXPORT_TABLES}
    # Para Tenant, mapear old tenant_id -> new
    old_tenant_id = tenant_payload.get('id')
    if old_tenant_id:
        id_maps['tenants'] = {old_tenant_id: new_tenant_id}

    # Helpers para remap
    def _map_id(table: str, old_id):
        if old_id is None:
            return None
        return id_maps.get(table, {}).get(str(old_id), old_id)

    # Orden de importación con dependencias
    import_order = [
        ('users', 'users'),
        ('configuracion', 'configuracion'),
        ('plantillas_comunicacion', 'plantillas_comunicacion'),
        ('clientes', 'clientes'),
        ('documentos_conocimiento', 'documentos_conocimiento'),
        ('cartera_ficheros', 'cartera_ficheros'),
        ('polizas', 'polizas'),
        ('chunks_conocimiento', 'chunks_conocimiento'),
        ('recibos', 'recibos'),
        ('renovaciones', 'renovaciones'),
        ('siniestros', 'siniestros'),
        ('hitos_siniestro', 'hitos_siniestro'),
        ('documentos_siniestro', 'documentos_siniestro'),
        ('historial_contacto', 'historial_contacto'),
        ('documentos_cliente', 'documentos_cliente'),
        ('comunicaciones', 'comunicaciones'),
        ('mensajes_asistente', 'mensajes_asistente'),
        ('agenda', 'agenda'),
        ('leads', 'leads'),
        ('cartera', 'cartera'),
        ('api_keys', 'api_keys'),
        ('cartera_polizas', 'cartera_polizas'),
        ('cartera_bajas', 'cartera_bajas'),
        ('cartera_altas', 'cartera_altas'),
    ]

    # Para parsear fechas
    def _parse_dt(value, col_type):
        if value is None or value == '':
            return None
        try:
            col_type_str = str(col_type).lower()
            if 'datetime' in col_type_str or 'date' in col_type_str:
                for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', ''))
                        if 'date' in col_type_str and 'datetime' not in col_type_str:
                            return dt.date()
                        return dt
                    except Exception:
                        continue
                return datetime.fromisoformat(value)
        except Exception:
            pass
        return value

    try:
        with tenant_context(new_tenant):
            for table_key, model_tablename in import_order:
                model = _MODEL_BY_TABLE.get(model_tablename)
                if model is None:
                    continue
                rows = tables.get(model_tablename, [])
                if not rows:
                    continue

                for row in rows:
                    # Preparar datos para nuevo objeto
                    new_data = {}
                    old_id = row.get('id')
                    for col in model.__table__.columns:
                        if col.name not in row:
                            continue
                        val = row[col.name]
                        # Remapear tenant_id
                        if col.name == 'tenant_id':
                            new_data[col.name] = new_tenant_id
                            continue
                        # Remapear foreign keys
                        if col.name == 'cliente_id' and val is not None:
                            new_data[col.name] = _map_id('clientes', val)
                            continue
                        if col.name == 'poliza_id' and val is not None:
                            new_data[col.name] = _map_id('polizas', val)
                            continue
                        if col.name == 'siniestro_id' and val is not None:
                            new_data[col.name] = _map_id('siniestros', val)
                            continue
                        if col.name == 'documento_id' and val is not None:
                            new_data[col.name] = _map_id('documentos_conocimiento', val)
                            continue
                        if col.name == 'user_id' and val is not None:
                            new_data[col.name] = _map_id('users', val)
                            continue
                        if col.name == 'fichero_id' and val is not None:
                            new_data[col.name] = _map_id('cartera_ficheros', val)
                            continue
                        # id lo dejamos que la BD lo genere (no lo seteamos) para evitar colisión PK
                        if col.name == 'id':
                            continue
                        # Parsear fechas
                        col_type = str(col.type)
                        if 'datetime' in col_type.lower() or 'date' in col_type.lower():
                            val = _parse_dt(val, col.type) if isinstance(val, str) else val
                        new_data[col.name] = val

                    obj = model(**new_data)
                    db.session.add(obj)
                    db.session.flush()
                    # Guardar mapeo id viejo -> nuevo
                    if old_id is not None:
                        id_maps[table_key][str(old_id)] = obj.id
                    # Actualizar rutas de archivos si existen
                    if hasattr(obj, 'ruta') and getattr(obj, 'ruta'):
                        old_ruta = row.get('ruta') or row.get('ruta_archivo') or row.get('contenido_raw')
                        # No hacemos nada aquí, lo manejamos después con uploads
                        pass

            # Restaurar uploads si existen en el ZIP
            try:
                from flask import current_app
                upload_root = Path(current_app.config['UPLOAD_FOLDER']).resolve()
                for zipinfo in zf.infolist():
                    if zipinfo.filename.startswith('uploads/'):
                        rel = zipinfo.filename[len('uploads/'):]
                        if old_tenant_id and rel.startswith(old_tenant_id):
                            rel = new_tenant_id + rel[len(old_tenant_id):]
                        target_path = upload_root / rel
                        if zipinfo.is_dir():
                            target_path.mkdir(parents=True, exist_ok=True)
                        else:
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            target_path.write_bytes(zf.read(zipinfo.filename))
                # Actualizar rutas en BD que contenían el old tenant_id
                if old_tenant_id:
                    old_frag = f'/{old_tenant_id}/'
                    new_frag = f'/{new_tenant_id}/'
                    for tbl_name in ['documentos_cliente', 'documentos_siniestro', 'cartera', 'cartera_ficheros', 'documentos_conocimiento']:
                        mdl = _MODEL_BY_TABLE.get(tbl_name)
                        if mdl is None:
                            continue
                        # Determinar columna de ruta
                        ruta_col = None
                        for cand in ('ruta', 'ruta_archivo', 'contenido_raw'):
                            if hasattr(mdl, cand):
                                ruta_col = cand
                                break
                        if not ruta_col:
                            continue
                        try:
                            # Dentro de tenant_context, query ya filtra por new_tenant_id
                            rows = mdl.query.all()
                            for r in rows:
                                val = getattr(r, ruta_col)
                                if val and old_frag in str(val):
                                    setattr(r, ruta_col, str(val).replace(old_frag, new_frag))
                            db.session.flush()
                        except Exception:
                            pass
            except Exception as up_exc:
                current_app.logger.warning(f'Error restaurando uploads: {up_exc}')

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        # Borrar tenant creado si falló
        try:
            t = db.session.get(Tenant, new_tenant_id)
            if t:
                db.session.delete(t)
                db.session.commit()
        except Exception:
            pass
        return jsonify({'error': f'Error al importar: {exc}'}), 400

    return jsonify({'tenant': _tenant_payload(new_tenant)}), 201
