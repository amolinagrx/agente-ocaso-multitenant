import json
import pyotp
import qrcode
import base64
import io
import secrets
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from models import db, User

usuarios_bp = Blueprint('usuarios', __name__)

MODULOS = [
    ('dashboard', 'Dashboard'),
    ('recibos', 'Recibos'),
    ('clientes', 'Clientes'),
    ('polizas', 'Polizas'),
    ('renovaciones', 'Renovaciones'),
    ('listados', 'Listados'),
    ('siniestros', 'Siniestros'),
    ('comunicaciones', 'Comunicaciones'),
    ('whatsapp', 'WhatsApp'),
    ('agenda', 'Agenda'),
    ('leads', 'Leads'),
    ('utilidades', 'Utilidades'),
    ('cartera', 'Cartera'),
    ('asistente', 'Asistente IA'),
    ('ajustes', 'Ajustes'),
    ('usuarios', 'Gestion de Usuarios'),
]

NIVELES = [
    ('rw', 'Lectura y Escritura'),
    ('r', 'Solo Lectura'),
    ('none', 'Sin acceso'),
]


def requiere_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acceso denegado. Solo administradores.', 'danger')
        return redirect(url_for('dashboard.index'))


@usuarios_bp.route('/')
@login_required
def index():
    if not current_user.is_admin:
        return requiere_admin()
    usuarios = User.query.order_by(User.username).all()
    return render_template('usuarios/index.html', usuarios=usuarios, modulos=MODULOS, niveles=NIVELES)


@usuarios_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if not current_user.is_admin:
        return requiere_admin()

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        nombre = request.form.get('nombre', '')
        email = request.form.get('email', '').strip().lower()
        send_credentials = request.form.get('send_email') == 'on'

        if not email or len(password) < 8:
            flash('Email y contraseña de al menos 8 caracteres son obligatorios', 'danger')
            return redirect(url_for('usuarios.nuevo'))

        username = username or email

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('No se pudo crear el usuario', 'danger')
            return redirect(url_for('usuarios.nuevo'))

        is_admin = request.form.get('is_admin') == 'on'

        permisos = {}
        for modulo, _ in MODULOS:
            nivel = request.form.get(f'perm_{modulo}', 'none')
            if nivel != 'none' or is_admin:
                permisos[modulo] = nivel

        user = User(
            username=username, password='pending', nombre=nombre,
            is_admin=is_admin, permisos=json.dumps(permisos), activo=True,
            email=email
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        if send_credentials and email:
            from utils.email import send_new_user_email
            send_new_user_email(email, username, password)

        flash(f'Usuario {username} creado', 'success')
        return redirect(url_for('usuarios.index'))

    return render_template('usuarios/nuevo.html', modulos=MODULOS, niveles=NIVELES)


@usuarios_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    if not current_user.is_admin:
        return requiere_admin()

    user = User.query.get_or_404(id)

    try:
        permisos_actuales = json.loads(user.permisos or '{}')
    except json.JSONDecodeError:
        permisos_actuales = {}

    if request.method == 'POST':
        user.nombre = request.form.get('nombre', '')
        user.email = request.form.get('email', '').strip() or None
        user.is_admin = request.form.get('is_admin') == 'on'
        user.activo = request.form.get('activo') == 'on'

        new_password = request.form.get('password', '')
        if new_password:
            user.set_password(new_password)

        permisos = {}
        if not user.is_admin:
            for modulo, _ in MODULOS:
                nivel = request.form.get(f'perm_{modulo}', 'none')
                permisos[modulo] = nivel
        user.permisos = json.dumps(permisos)

        db.session.commit()
        flash(f'Usuario {user.username} actualizado', 'success')
        return redirect(url_for('usuarios.index'))

    return render_template('usuarios/editar.html', usuario=user, modulos=MODULOS,
                           niveles=NIVELES, permisos_actuales=permisos_actuales)


@usuarios_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    if not current_user.is_admin:
        return requiere_admin()

    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('No puedes eliminarte a ti mismo', 'danger')
        return redirect(url_for('usuarios.index'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Usuario {username} eliminado', 'success')
    return redirect(url_for('usuarios.index'))


@usuarios_bp.route('/<int:id>/2fa/setup', methods=['GET', 'POST'])
@login_required
def setup_2fa(id):
    """Enable TOTP 2FA for a user."""
    user = User.query.get_or_404(id)

    # Only admin or the user themselves can set up 2FA
    if not current_user.is_admin and current_user.id != user.id:
        flash('No tienes permisos para modificar este usuario', 'danger')
        return redirect(url_for('usuarios.index'))

    if request.method == 'POST':
        code = request.form.get('totp_code', '').strip()
        secret = request.form.get('totp_secret', '')

        if not secret or not code:
            flash('Faltan datos', 'danger')
            return redirect(url_for('usuarios.setup_2fa', id=id))

        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            user.totp_secret = secret
            user.totp_enabled = True
            db.session.commit()
            flash(f'Autenticacion en dos pasos activada para {user.username}', 'success')
            return redirect(url_for('usuarios.index'))
        else:
            flash('Codigo incorrecto. Intentalo de nuevo.', 'danger')
            return redirect(url_for('usuarios.setup_2fa', id=id))

    # Generate new secret
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.username, issuer_name='Ocaso Armilla')

    # Generate QR code as base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template('usuarios/2fa_setup.html',
                           usuario=user, secret=secret, uri=uri, qr_b64=qr_b64)


@usuarios_bp.route('/<int:id>/2fa/disable', methods=['POST'])
@login_required
def disable_2fa(id):
    """Disable 2FA for a user. Admin or self."""
    user = User.query.get_or_404(id)

    if not current_user.is_admin and current_user.id != user.id:
        flash('No tienes permisos para desactivar 2FA', 'danger')
        return redirect(url_for('usuarios.index'))

    user.totp_secret = None
    user.totp_enabled = False
    db.session.commit()
    flash(f'2FA desactivado para {user.username}', 'success')
    return redirect(url_for('usuarios.index') if current_user.is_admin else url_for('usuarios.perfil'))


@usuarios_bp.route('/<int:id>/reenviar_credenciales', methods=['POST'])
@login_required
def reenviar_credenciales(id):
    if not current_user.is_admin:
        return requiere_admin()
    user = User.query.get_or_404(id)
    password = secrets.token_urlsafe(6)[:8]
    user.set_password(password)
    user.password_temporal = True
    db.session.commit()

    if user.email:
        try:
            from utils.email import send_email
            ok = send_email(user.email, 'Credenciales Ocaso Gestion',
                f'<h3>Credenciales</h3><p>Usuario: {user.username}</p><p>Contrasena temporal: <b>{password}</b></p><p>Deberas cambiarla al iniciar sesion.</p>')
            if ok:
                flash(f'Credenciales enviadas a {user.email}', 'success')
            else:
                flash(f'Credenciales: {password} (SMTP no configurado)', 'warning')
        except Exception:
            flash(f'Credenciales: {password}', 'warning')
    else:
        flash(f'Credenciales: {password} (sin email)', 'warning')

    return redirect(url_for('usuarios.index'))


@usuarios_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    """Self-service profile page for any user."""
    user = current_user

    if request.method == 'POST':
        accion = request.form.get('accion', '')

        if accion == 'cambiar_password':
            new_pass = request.form.get('password', '')
            if len(new_pass) < 3:
                flash('Contrasena demasiado corta', 'danger')
            else:
                user.set_password(new_pass)
                db.session.commit()
                flash('Contrasena actualizada', 'success')

        elif accion == 'cambiar_email':
            new_email = request.form.get('email', '').strip()
            if not new_email:
                flash('Email requerido', 'danger')
            else:
                code = generate_code()
                user.email_verification_code = code
                user.email_verified = False
                db.session.commit()
                from utils.email import send_verification_email
                send_verification_email(new_email, user.username, code)
                session['pending_email'] = new_email
                flash('Te hemos enviado un codigo de verificacion a ' + new_email, 'info')
                return redirect(url_for('usuarios.perfil'))

        elif accion == 'verificar_email':
            code = request.form.get('code', '').strip()
            pending = session.get('pending_email', '')
            if code == user.email_verification_code:
                user.email = pending
                user.email_verified = True
                user.email_verification_code = None
                session.pop('pending_email', None)
                db.session.commit()
                flash('Email verificado correctamente', 'success')
            else:
                flash('Codigo incorrecto', 'danger')

        elif accion == 'cambiar_nombre':
            user.nombre = request.form.get('nombre', '')
            db.session.commit()
            flash('Nombre actualizado', 'success')

        return redirect(url_for('usuarios.perfil'))

    return render_template('usuarios/perfil.html', usuario=user)


@usuarios_bp.route('/cancelar-verificacion', methods=['POST'])
@login_required
def cancelar_verificacion():
    session.pop('pending_email', None)
    current_user.email_verification_code = None
    db.session.commit()
    flash('Verificacion cancelada', 'info')
    return redirect(url_for('usuarios.perfil'))


def generate_code(length=6):
    import random
    return ''.join(str(random.randint(0, 9)) for _ in range(length))
