import secrets
import functools
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Cliente, Poliza, Siniestro, DocumentoCliente, Recibo
from services.tenant_context import get_current_tenant_id

portal_bp = Blueprint('portal', __name__, url_prefix='/portal')

SESSION_TIMEOUT = timedelta(minutes=30)


def cliente_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        cliente_id = session.get('cliente_id')
        if not cliente_id or str(session.get('portal_tenant_id')) != str(get_current_tenant_id()):
            session.clear()
            return redirect(url_for('portal.login'))

        last_activity = session.get('last_activity')
        if last_activity:
            elapsed = datetime.utcnow() - datetime.fromisoformat(last_activity)
            if elapsed > SESSION_TIMEOUT:
                session.clear()
                return redirect(url_for('portal.login'))

        session['last_activity'] = datetime.utcnow().isoformat()
        return f(*args, **kwargs)
    return decorated


def get_cliente():
    cliente_id = session.get('cliente_id')
    if cliente_id:
        return Cliente.query.get(cliente_id)
    return None


@portal_bp.route('/')
def index():
    return redirect(url_for('portal.login'))


@portal_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rate_key = f'_rl_portal_{get_current_tenant_id()}_{request.remote_addr}'
        now = datetime.utcnow()
        data = session.get(rate_key, {'c': 0, 't': now.isoformat()})
        last = datetime.fromisoformat(data['t']) if data.get('t') else now
        if (now - last).seconds < 60 and data.get('c', 0) >= 10:
            flash('Demasiados intentos. Espera un minuto.', 'danger')
            return render_template('portal/login.html')
        session[rate_key] = {'c': data.get('c', 0) + 1 if (now - last).seconds < 60 else 1, 't': now.isoformat()}

        dni = request.form.get('dni', '').strip().upper()
        password = request.form.get('password', '')

        cliente = Cliente.query.filter_by(dni=dni, portal_activo=True).first()
        if cliente and cliente.portal_password and check_password_hash(cliente.portal_password, password):
            session.clear()
            session['cliente_id'] = cliente.id
            session['portal_tenant_id'] = get_current_tenant_id()
            session['last_activity'] = datetime.utcnow().isoformat()
            session.permanent = True

            if cliente.portal_password_temporal:
                session['must_change_password'] = True
                return redirect(url_for('portal.cambiar_password'))

            return redirect(url_for('portal.dashboard'))

        flash('DNI o contraseña incorrectos', 'danger')

    return render_template('portal/login.html')


@portal_bp.route('/cambiar-password', methods=['GET', 'POST'])
def cambiar_password():
    cliente_id = session.get('cliente_id')
    if not cliente_id:
        return redirect(url_for('portal.login'))
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        session.clear()
        return redirect(url_for('portal.login'))

    if request.method == 'POST':
        new_pass = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if len(new_pass) < 8:
            flash('La contrasena debe tener al menos 8 caracteres', 'danger')
        elif new_pass != confirm:
            flash('Las contrasenas no coinciden', 'danger')
        else:
            cliente.portal_password = generate_password_hash(new_pass, method='pbkdf2:sha256')
            cliente.portal_password_temporal = False
            db.session.commit()
            session.pop('must_change_password', None)
            flash('Contrasena cambiada correctamente', 'success')
            return redirect(url_for('portal.dashboard'))

    return render_template('portal/cambiar_password.html', cliente=cliente)


@portal_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('portal.login'))


@portal_bp.route('/dashboard')
@cliente_required
def dashboard():
    cliente = get_cliente()
    try:
        polizas_activas = Poliza.query.filter_by(cliente_id=cliente.id, activa=True).count()
        siniestros_abiertos = Siniestro.query.filter(
            Siniestro.cliente_id == cliente.id,
            Siniestro.estado.notin_(['cerrado', 'resuelto'])
        ).count()
        documentos_count = DocumentoCliente.query.filter_by(cliente_id=cliente.id).count()
        recibos_count = Recibo.query.filter_by(cliente_id=cliente.id, deleted_at=None).count()
    except Exception:
        polizas_activas = 0
        siniestros_abiertos = 0
        documentos_count = 0
        recibos_count = 0

    return render_template('portal/dashboard.html',
                           cliente=cliente,
                           polizas_activas=polizas_activas,
                           siniestros_abiertos=siniestros_abiertos,
                           documentos_count=documentos_count,
                           recibos_count=recibos_count)


@portal_bp.route('/polizas')
@cliente_required
def polizas():
    cliente = get_cliente()
    try:
        polizas = Poliza.query.filter_by(cliente_id=cliente.id).order_by(
            Poliza.activa.desc(), Poliza.fecha_efecto.desc()).all()
    except Exception:
        polizas = []
    return render_template('portal/polizas.html', cliente=cliente, polizas=polizas)


@portal_bp.route('/siniestros')
@cliente_required
def siniestros():
    cliente = get_cliente()
    try:
        siniestros = Siniestro.query.filter_by(cliente_id=cliente.id).order_by(
            Siniestro.fecha_apertura.desc()).all()
    except Exception:
        siniestros = []
    return render_template('portal/siniestros.html', cliente=cliente, siniestros=siniestros)


@portal_bp.route('/recibos')
@cliente_required
def recibos():
    cliente = get_cliente()
    try:
        recibos = Recibo.query.filter_by(cliente_id=cliente.id, deleted_at=None).order_by(
            Recibo.fecha_emision.desc()).limit(100).all()
    except Exception:
        recibos = []
    return render_template('portal/recibos.html', cliente=cliente, recibos=recibos)


@portal_bp.route('/documentos')
@cliente_required
def documentos():
    cliente = get_cliente()
    try:
        docs = DocumentoCliente.query.filter_by(cliente_id=cliente.id).order_by(
            DocumentoCliente.uploaded_at.desc()).all()
    except Exception:
        docs = []
    return render_template('portal/documentos.html', cliente=cliente, documentos=docs)
