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

        return redirect(url_for('ajustes.index'))

    # Load current config
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

    return render_template('ajustes/index.html',
                           config=config,
                           api_keys=api_keys,
                           docs_count=docs_count,
                           chunks_count=chunks_count,
                           mensajes_count=mensajes_count,
                           api_key_configured=api_key_configured,
                           key_from_env=key_from_env,
                           key_from_db=key_from_db)


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
