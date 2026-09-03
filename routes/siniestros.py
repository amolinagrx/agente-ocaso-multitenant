from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Siniestro, Cliente, Poliza, HitoSiniestro, DocumentoSiniestro
from datetime import date, datetime
import os

siniestros_bp = Blueprint('siniestros', __name__)

ESTADOS = [
    'abierto', 'documentacion_enviada', 'perito_asignado', 'en_taller',
    'en_valoracion', 'pendiente_resolucion', 'resuelto', 'cerrado'
]

ESTADOS_LABEL = {
    'abierto': 'Abierto',
    'documentacion_enviada': 'Documentación enviada',
    'perito_asignado': 'Perito asignado',
    'en_taller': 'En taller',
    'en_valoracion': 'En valoración',
    'pendiente_resolucion': 'Pendiente resolución',
    'resuelto': 'Resuelto',
    'cerrado': 'Cerrado'
}


@siniestros_bp.route('/')
@login_required
def index():
    query = db.session.query(Siniestro, Cliente, Poliza).join(
        Cliente, Siniestro.cliente_id == Cliente.id
    ).outerjoin(
        Poliza, Siniestro.poliza_id == Poliza.id
    )

    estado = request.args.get('estado')
    if estado:
        query = query.filter(Siniestro.estado == estado)

    buscar = request.args.get('buscar')
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Siniestro.numero_expediente.ilike(f'%{buscar}%'),
                Siniestro.tipo.ilike(f'%{buscar}%')
            )
        )

    resultados = query.order_by(Siniestro.fecha_apertura.desc()).all()

    # Marcar alerta si > 15 días sin actualización
    ahora = datetime.utcnow()
    for s, c, p in resultados:
        delta = (ahora - s.fecha_ultima_actualizacion).days if s.fecha_ultima_actualizacion else 0
        s.dias_sin_actualizar = delta

    return render_template('siniestros/index.html',
                           resultados=resultados,
                           estado=estado,
                           buscar=buscar,
                           estados=ESTADOS,
                           estados_label=ESTADOS_LABEL)


@siniestros_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', type=int)
        siniestro = Siniestro(
            cliente_id=cliente_id,
            poliza_id=request.form.get('poliza_id', type=int) or None,
            numero_expediente=request.form.get('numero_expediente'),
            tipo=request.form.get('tipo'),
            descripcion=request.form.get('descripcion'),
            fecha_ocurrencia=request.form.get('fecha_ocurrencia'),
            fecha_apertura=request.form.get('fecha_apertura', date.today()),
            estado='abierto',
            fecha_ultima_actualizacion=datetime.utcnow(),
            importe_estimado=float(request.form.get('importe_estimado', 0) or 0)
        )
        db.session.add(siniestro)
        db.session.flush()

        hito = HitoSiniestro(
            siniestro_id=siniestro.id,
            fecha=datetime.utcnow(),
            estado='abierto',
            notas=request.form.get('notas_iniciales', 'Apertura de siniestro')
        )
        db.session.add(hito)
        db.session.commit()
        flash('Siniestro registrado correctamente', 'success')
        return redirect(url_for('siniestros.ficha', id=siniestro.id))

    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return render_template('siniestros/nuevo.html', clientes=clientes)


@siniestros_bp.route('/<int:id>')
@login_required
def ficha(id):
    siniestro = Siniestro.query.get_or_404(id)
    cliente = Cliente.query.get(siniestro.cliente_id)
    poliza = Poliza.query.get(siniestro.poliza_id) if siniestro.poliza_id else None
    hitos = siniestro.hitos.all()
    documentos = siniestro.documentos.order_by(DocumentoSiniestro.uploaded_at.desc()).all()
    return render_template('siniestros/ficha.html',
                           siniestro=siniestro,
                           cliente=cliente,
                           poliza=poliza,
                           hitos=hitos,
                           documentos=documentos,
                           estados_label=ESTADOS_LABEL)


@siniestros_bp.route('/<int:id>/estado', methods=['POST'])
@login_required
def cambiar_estado(id):
    siniestro = Siniestro.query.get_or_404(id)
    nuevo_estado = request.form.get('estado')
    notas = request.form.get('notas', '')
    if nuevo_estado in ESTADOS:
        siniestro.estado = nuevo_estado
        siniestro.fecha_ultima_actualizacion = datetime.utcnow()
        hito = HitoSiniestro(
            siniestro_id=id,
            fecha=datetime.utcnow(),
            estado=nuevo_estado,
            notas=notas
        )
        db.session.add(hito)
        db.session.commit()
        flash('Estado actualizado correctamente', 'success')
    return redirect(url_for('siniestros.ficha', id=id))


@siniestros_bp.route('/<int:id>/subir-documento', methods=['POST'])
@login_required
def subir_documento(id):
    siniestro = Siniestro.query.get_or_404(id)
    file = request.files.get('documento')
    if file:
        from services.storage import tenant_upload_path
        filename = f"siniestro_{id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{file.filename}"
        ruta = tenant_upload_path(filename, 'siniestros')
        file.save(ruta)

        drive_id = None
        try:
            from utils.drive import is_drive_configured, upload_to_drive
            import os
            if os.environ.get('GOOGLE_DRIVE_ENABLED', '') != '0' and is_drive_configured():
                drive_id = upload_to_drive(ruta, file.filename)
        except Exception:
            pass

        doc = DocumentoSiniestro(
            siniestro_id=id,
            nombre=file.filename,
            tipo=request.form.get('tipo', 'otro'),
            ruta=ruta,
            drive_id=drive_id
        )
        db.session.add(doc)
        siniestro.fecha_ultima_actualizacion = datetime.utcnow()
        db.session.commit()
        flash('Documento subido', 'success')
    return redirect(url_for('siniestros.ficha', id=id))
