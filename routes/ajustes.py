import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, abort
from flask_login import login_required, current_user
from models import db, Configuracion, DocumentoConocimiento, ChunkConocimiento, MensajeAsistente, ApiKey
from datetime import datetime
import secrets

ajustes_bp = Blueprint('ajustes', __name__)


@ajustes_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if not current_user.tiene_permiso('ajustes', 'r'):
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        if not current_user.tiene_permiso('ajustes', 'rw'):
            return redirect(url_for('dashboard.index'))
        seccion = request.form.get('seccion', '')

        if seccion == 'general':
            _guardar_config('oficina_nombre', request.form.get('oficina_nombre', ''))
            _guardar_config('oficina_direccion', request.form.get('oficina_direccion', ''))
            _guardar_config('oficina_telefono', request.form.get('oficina_telefono', ''))
            _guardar_config('oficina_email', request.form.get('oficina_email', ''))
            _guardar_config('whatsapp_empresa', request.form.get('whatsapp_empresa', ''))
            _guardar_config('dias_alerta_siniestro', request.form.get('dias_alerta_siniestro', '15'))
            from services.tenant_context import get_current_tenant
            import json
            import re
            tenant = get_current_tenant()
            tenant_settings = json.loads(tenant.config_json or '{}')
            tenant_settings.setdefault('branding', {})
            requested_color = request.form.get('branding_color', '#003396').strip()
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', requested_color):
                requested_color = '#003396'
            tenant_settings['branding'].update({
                'name': request.form.get('oficina_nombre', '').strip() or tenant.name,
                'logo': request.form.get('branding_logo', '').strip() or None,
                'primary_color': requested_color,
            })
            tenant_settings['timezone'] = request.form.get('timezone', 'Europe/Madrid').strip()
            tenant_settings['locale'] = request.form.get('locale', 'es-ES').strip()
            tenant.config_json = json.dumps(tenant_settings, ensure_ascii=False)
            tenant.name = tenant_settings['branding']['name']
            db.session.commit()
            flash('Configuracion general guardada', 'success')

        elif seccion == 'api':
            api_key = request.form.get('deepseek_api_key', '').strip()
            if api_key:
                _guardar_config('deepseek_api_key', api_key)
                db.session.commit()
                flash('API Key de Deepseek guardada', 'success')
            else:
                flash('La API Key no puede estar vacia', 'warning')

        elif seccion == 'drive':
            _guardar_config('drive_folder_id', request.form.get('drive_folder_id', ''))
            creds_file = request.files.get('drive_credentials')
            if creds_file and creds_file.filename:
                import json
                creds_text = creds_file.read().decode('utf-8')
                try:
                    json.loads(creds_text)
                    _guardar_config('drive_credentials', creds_text)
                except json.JSONDecodeError:
                    flash('El archivo JSON no es valido', 'danger')
            db.session.commit()
            flash('Configuracion Google Drive guardada', 'success')

            # Migración automática: si Drive ya está configurado, migrar documentos existentes
            try:
                from utils.drive import is_drive_configured, migrar_documentos_existentes_a_drive
                from services.tenant_context import get_current_tenant
                if is_drive_configured():
                    tenant = get_current_tenant()
                    # Si estamos en un tenant, migrar solo ese tenant; si es global (superadmin), migrar todos
                    tid = tenant.id if tenant else None
                    result = migrar_documentos_existentes_a_drive(tid)
                    if result.get('ok') and result.get('migrados', 0) > 0:
                        flash(f"Se han migrado {result['migrados']} documento(s) existente(s) a Google Drive ({result.get('errores', 0)} errores, {result.get('omitidos', 0)} omitidos).", 'success')
                    elif result.get('ok') and result.get('migrados', 0) == 0 and (result.get('errores', 0) > 0 or result.get('omitidos', 0) > 0):
                        flash(f"No se migró ningún documento nuevo ({result.get('errores', 0)} errores, {result.get('omitidos', 0)} omitidos).", 'info')
            except Exception as e:
                # No bloquear el guardado por fallo de migración
                import logging
                logging.getLogger(__name__).warning(f"Error en migración automática a Drive: {e}")

        elif seccion == 'smtp':
            _guardar_config('smtp_host', request.form.get('smtp_host', ''))
            _guardar_config('smtp_port', request.form.get('smtp_port', '587'))
            _guardar_config('smtp_user', request.form.get('smtp_user', ''))
            _guardar_config('smtp_pass', request.form.get('smtp_pass', ''))
            _guardar_config('smtp_from', request.form.get('smtp_from', ''))
            db.session.commit()
            flash('Configuracion SMTP guardada', 'success')

        elif seccion == 'smtp_test':
            from utils.email import test_smtp_connection
            test_to = request.form.get('smtp_test_email', '').strip()
            if not test_to:
                flash('Introduce un email de prueba', 'warning')
            else:
                ok, msg = test_smtp_connection()
                if ok:
                    from utils.email import send_email
                    send_email(test_to, 'Ocaso Gestion - Test SMTP',
                               '<h3>Test SMTP</h3><p>Si ves esto, el servidor SMTP funciona.</p>')
                    flash(f'Conexion OK. Email enviado a {test_to}', 'success')
                else:
                    flash(f'Error: {msg}', 'danger')

        elif seccion == 'drive_migrar':
            from utils.drive import is_drive_configured, migrar_documentos_existentes_a_drive
            from services.tenant_context import get_current_tenant
            if not is_drive_configured():
                flash('Google Drive no está configurado. Conecta tu cuenta personal (OAuth) o sube el JSON de la cuenta de servicio.', 'warning')
            else:
                tenant = get_current_tenant()
                tid = tenant.id if tenant else None
                result = migrar_documentos_existentes_a_drive(tid)
                if result.get('ok'):
                    flash(f"Migración completada: {result.get('migrados', 0)} migrados, {result.get('errores', 0)} errores, {result.get('omitidos', 0)} omitidos.", 'success' if result.get('migrados', 0) > 0 else 'info')
                else:
                    flash(f"No se pudo migrar: {result.get('error', 'desconocido')}", 'danger')

        elif seccion == 'drive_oauth':
            # Guardar client_id/secret si se proporcionan
            client_id = request.form.get('oauth_client_id', '').strip()
            client_secret = request.form.get('oauth_client_secret', '').strip()
            if client_id:
                _guardar_config('drive_oauth_client_id', client_id)
            if client_secret:
                _guardar_config('drive_oauth_client_secret', client_secret)
            db.session.commit()
            flash('Credenciales OAuth guardadas. Ahora pulsa "Conectar con Google".', 'success')

        return redirect(url_for('ajustes.index'))

    # GET
    ctx = _load_ajustes_context()
    return render_template('ajustes/index.html', **ctx)


@ajustes_bp.route('/drive/oauth')
@login_required
def drive_oauth_start():
    from flask import current_app, request
    from services.tenant_context import get_current_tenant
    tenant = get_current_tenant()
    # Guardar tenant para el callback
    session['drive_oauth_tenant_id'] = tenant.id if tenant else None
    # Usar credenciales OAuth guardadas o env
    from models import Configuracion
    client_id = None
    client_secret = None
    # Intentar desde Configuracion
    for clave in ('drive_oauth_client_id', 'drive_oauth_client_secret'):
        c = Configuracion.query.filter_by(clave=clave).first()
        # Necesitamos tenant_context para leer bien, pero ya estamos en tenant_context? Ajustes es por tenant, así que sí
        pass
    # Leer de Configuracion dentro de tenant
    cfg = {c.clave: c.valor for c in Configuracion.query.all()}
    client_id = cfg.get('drive_oauth_client_id') or os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = cfg.get('drive_oauth_client_secret') or os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    if not client_id or not client_secret:
        flash('Falta Client ID/Secret de OAuth. Configúralos en Ajustes → Drive (sección OAuth) o define GOOGLE_OAUTH_CLIENT_ID/SECRET en el servidor.', 'danger')
        return redirect(url_for('ajustes.index'))
    # Construir Flow
    from google_auth_oauthlib.flow import Flow
    redirect_uri = request.url_root.rstrip('/') + url_for('ajustes.drive_oauth_callback')
    # Google requiere https para redirect_uri en producción
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=['https://www.googleapis.com/auth/drive'],
        redirect_uri=redirect_uri,
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )
    session['drive_oauth_state'] = state
    return redirect(authorization_url)


@ajustes_bp.route('/drive/oauth/callback')
@login_required
def drive_oauth_callback():
    from flask import request
    from services.tenant_context import get_current_tenant, tenant_context
    from models import Tenant
    state = session.get('drive_oauth_state')
    tenant_id = session.get('drive_oauth_tenant_id')
    # Validar state
    if not state or state != request.args.get('state'):
        flash('Estado OAuth inválido. Intenta de nuevo.', 'danger')
        return redirect(url_for('ajustes.index'))
    # Recuperar tenant
    tenant = db.session.get(Tenant, tenant_id) if tenant_id else get_current_tenant()
    if not tenant:
        # Si no hay tenant (superadmin global), usar el tenant actual o el primero
        tenant = get_current_tenant()
        if not tenant:
            flash('No se pudo determinar la oficina para guardar el token.', 'danger')
            return redirect(url_for('ajustes.index'))
    # Intercambiar code por token
    from models import Configuracion
    cfg = {c.clave: c.valor for c in Configuracion.query.filter_by(tenant_id=tenant.id).all()} if tenant else {}
    # Leer client_id/secret del tenant o env
    # Necesitamos leer dentro de tenant_context
    with tenant_context(tenant):
        cfg2 = {c.clave: c.valor for c in Configuracion.query.all()}
        client_id = cfg2.get('drive_oauth_client_id') or os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
        client_secret = cfg2.get('drive_oauth_client_secret') or os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
        if not client_id or not client_secret:
            flash('Falta Client ID/Secret.', 'danger')
            return redirect(url_for('ajustes.index'))
        from google_auth_oauthlib.flow import Flow
        redirect_uri = request.url_root.rstrip('/') + url_for('ajustes.drive_oauth_callback')
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=['https://www.googleapis.com/auth/drive'],
            redirect_uri=redirect_uri,
            state=state,
        )
        try:
            flow.fetch_token(authorization_response=request.url)
            creds = flow.credentials
            # Guardar token
            token_json = creds.to_json()
            # Dentro de tenant_context
            existing = Configuracion.query.filter_by(clave='drive_oauth_token').first()
            if existing:
                existing.valor = token_json
            else:
                db.session.add(Configuracion(clave='drive_oauth_token', valor=token_json))
            db.session.commit()
            flash('¡Conectado con Google Drive! Ahora puedes migrar tus documentos.', 'success')
        except Exception as e:
            flash(f'Error al conectar con Google: {e}', 'danger')
        return redirect(url_for('ajustes.index'))


def _load_ajustes_context():
    config = {}
    for c in Configuracion.query.all():
        config[c.clave] = c.valor

    # AI stats
    docs_count = DocumentoConocimiento.query.count()
    chunks_count = ChunkConocimiento.query.count()
    mensajes_count = MensajeAsistente.query.count()
    key_from_env = bool(os.environ.get('DEEPSEEK_API_KEY', ''))
    key_from_db = bool(config.get('deepseek_api_key', ''))
    api_key_configured = key_from_env or key_from_db
    api_keys = ApiKey.query.filter_by(activo=True).order_by(ApiKey.created_at.desc()).all()

    return {
        'config': config,
        'api_keys': api_keys,
        'docs_count': docs_count,
        'chunks_count': chunks_count,
        'mensajes_count': mensajes_count,
        'api_key_configured': api_key_configured,
        'key_from_env': key_from_env,
        'key_from_db': key_from_db,
    }


def _guardar_config(clave, valor):
    conf = Configuracion.query.filter_by(clave=clave).first()
    if conf:
        conf.valor = valor.strip() if valor else ''
    else:
        if valor:
            db.session.add(Configuracion(clave=clave, valor=valor.strip()))


@ajustes_bp.route('/exportar-backup')
@login_required
def exportar_backup():
    from services.tenant_context import get_current_tenant_id
    if not current_user.is_super_admin or get_current_tenant_id() is not None:
        abort(404)
    """Download the SQLite database as backup."""
    import shutil
    import tempfile
    from flask import send_file, current_app

    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if not os.path.exists(db_path):
        flash('No se encuentra la base de datos', 'danger')
        return redirect(url_for('ajustes.index'))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    shutil.copy2(db_path, tmp.name)
    tmp.close()

    from datetime import date
    filename = f'ocaso_backup_{date.today().strftime("%Y%m%d")}.db'

    return send_file(tmp.name, as_attachment=True, download_name=filename,
                     mimetype='application/octet-stream')


@ajustes_bp.route('/importar-backup', methods=['POST'])
@login_required
def importar_backup():
    from services.tenant_context import get_current_tenant_id
    if not current_user.is_super_admin or get_current_tenant_id() is not None:
        abort(404)
    """Restore database from uploaded backup file."""
    from flask import current_app
    import shutil

    file = request.files.get('backup_file')
    if not file or not file.filename.endswith('.db'):
        flash('Selecciona un archivo .db valido', 'danger')
        return redirect(url_for('ajustes.index'))

    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    backup_path = db_path + '.backup_previo'

    # Backup current DB just in case
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)

    try:
        file.save(db_path)
        flash('Backup restaurado correctamente. La aplicacion se reiniciara al recargar.', 'success')
    except Exception as e:
        # Restore previous DB if import fails
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)
        flash(f'Error al restaurar: {e}', 'danger')

    return redirect(url_for('ajustes.index'))


@ajustes_bp.route('/reset-all', methods=['POST'])
@login_required
def reset_all():
    """Delete all data after confirming security code."""
    codigo = request.form.get('codigo_seguridad', '')
    confirmacion = request.form.get('confirmacion', '')

    reset_code = os.environ.get('RESET_CODE')
    if not current_user.is_admin or not reset_code or codigo != reset_code:
        flash('Codigo de seguridad incorrecto', 'danger')
        return redirect(url_for('ajustes.index'))

    if confirmacion != 'BORRAR TODO':
        flash('Debes escribir "BORRAR TODO" para confirmar', 'danger')
        return redirect(url_for('ajustes.index'))

    try:
        # Delete business data but keep users table
        from models import (Comunicacion, MensajeAsistente, DocumentoConocimiento,
                            ChunkConocimiento, Siniestro, HitoSiniestro, DocumentoSiniestro,
                            Renovacion, Recibo, Poliza, HistorialContacto, DocumentoCliente,
                            Cliente, Configuracion)
        Comunicacion.query.delete()
        MensajeAsistente.query.delete()
        ChunkConocimiento.query.delete()
        DocumentoConocimiento.query.delete()
        DocumentoSiniestro.query.delete()
        HitoSiniestro.query.delete()
        Siniestro.query.delete()
        Renovacion.query.delete()
        Recibo.query.delete()
        Poliza.query.delete()
        HistorialContacto.query.delete()
        DocumentoCliente.query.delete()
        Cliente.query.delete()
        Configuracion.query.delete()
        db.session.commit()

        flash('Todos los datos han sido eliminados. Los usuarios se conservan.', 'success')
    except Exception as e:
        flash(f'Error al resetear: {e}', 'danger')

    return redirect(url_for('ajustes.index'))


@ajustes_bp.route('/api-key/nueva', methods=['POST'])
@login_required
def nueva_api_key():
    nombre = request.form.get('nombre', 'API Key').strip()
    token = secrets.token_hex(32)
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    key = ApiKey(user_id=current_user.id, nombre=nombre, token=token_hash)
    db.session.add(key)
    db.session.commit()
    session['new_api_token'] = token
    flash('API Key generada', 'warning')
    return redirect(url_for('ajustes.index', _anchor='api-keys'))


@ajustes_bp.route('/api-key/<int:id>/revocar', methods=['POST'])
@login_required
def revocar_api_key(id):
    key = ApiKey.query.get_or_404(id)
    key.activo = False
    db.session.commit()
    flash('API Key revocada', 'success')
    return redirect(url_for('ajustes.index'))

    return redirect(url_for('ajustes.index'))
