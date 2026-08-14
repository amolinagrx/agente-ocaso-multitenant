import os
import os
import secrets
import functools
from datetime import date, datetime, timedelta
from flask import Blueprint, jsonify, request
from models import db, ApiKey, Cliente, Poliza, Recibo, Siniestro, Lead, User, DocumentoCliente

api_externa_bp = Blueprint('api_externa', __name__)


def require_api_key(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-API-Key')
        if not token:
            return jsonify({'error': 'API key requerida'}), 401

        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        api_key = ApiKey.query.filter_by(token=token_hash, activo=True).first()
        if not api_key:
            return jsonify({'error': 'API key invalida o inactiva'}), 403

        api_key.last_used = datetime.utcnow()
        db.session.commit()

        request.api_user = User.query.get(api_key.user_id)
        if not request.api_user or not request.api_user.activo:
            return jsonify({'error': 'Usuario desactivado'}), 403

        return f(*args, **kwargs)
    return decorated


@api_externa_bp.route('/v1/health')
def health():
    return jsonify({
        'status': 'ok',
        'version': '1.0',
        'timestamp': datetime.utcnow().isoformat()
    })


# ========== CLIENTES ==========

@api_externa_bp.route('/v1/clientes')
@require_api_key
def clientes_list():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    buscar = request.args.get('buscar', '')

    query = Cliente.query
    if buscar:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{buscar}%'),
                Cliente.dni.ilike(f'%{buscar}%'),
                Cliente.telefono.ilike(f'%{buscar}%')
            )
        )

    pag = query.order_by(Cliente.nombre).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pag.total,
        'page': page,
        'per_page': per_page,
        'data': [_cliente_to_dict(c) for c in pag.items]
    })


@api_externa_bp.route('/v1/clientes/<int:id>')
@require_api_key
def clientes_get(id):
    c = Cliente.query.get_or_404(id)
    return jsonify(_cliente_to_dict(c, include_polizas=True))


@api_externa_bp.route('/v1/clientes', methods=['POST'])
@require_api_key
def clientes_create():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('nombre'):
        return jsonify({'error': 'nombre requerido'}), 400

    c = Cliente(
        nombre=data['nombre'],
        dni=data.get('dni', ''),
        direccion=data.get('direccion', ''),
        codigo_postal=data.get('codigo_postal', ''),
        poblacion=data.get('poblacion', ''),
        provincia=data.get('provincia', ''),
        telefono=data.get('telefono', ''),
        email=data.get('email', ''),
        notas=data.get('notas', '')
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(_cliente_to_dict(c)), 201


@api_externa_bp.route('/v1/clientes/<int:id>', methods=['PUT'])
@require_api_key
def clientes_update(id):
    c = Cliente.query.get_or_404(id)
    data = request.get_json(force=True, silent=True) or {}
    for field in ['nombre', 'dni', 'direccion', 'codigo_postal', 'poblacion',
                  'provincia', 'telefono', 'email', 'notas']:
        if field in data:
            setattr(c, field, data[field])
    db.session.commit()
    return jsonify(_cliente_to_dict(c))


@api_externa_bp.route('/v1/clientes/<int:id>', methods=['DELETE'])
@require_api_key
def clientes_delete(id):
    c = Cliente.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'deleted': True})


@api_externa_bp.route('/v1/clientes/<int:id>/documentos', methods=['POST'])
@require_api_key
def clientes_upload_documento(id):
    Cliente.query.get_or_404(id)
    file = request.files.get('documento')
    if not file or not file.filename:
        return jsonify({'error': 'Archivo requerido'}), 400

    from services.storage import tenant_upload_path
    filename = f"api_{id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{file.filename}"
    ruta = tenant_upload_path(filename, 'clientes')
    file.save(ruta)

    doc = DocumentoCliente(
        cliente_id=id, nombre=file.filename,
        tipo=request.form.get('tipo', 'otro'), ruta=ruta
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({'id': doc.id, 'nombre': doc.nombre, 'tipo': doc.tipo}), 201


@api_externa_bp.route('/v1/clientes/<int:id>/documentos')
@require_api_key
def clientes_documentos(id):
    Cliente.query.get_or_404(id)
    docs = DocumentoCliente.query.filter_by(cliente_id=id).order_by(
        DocumentoCliente.uploaded_at.desc()).all()
    return jsonify([{'id': d.id, 'nombre': d.nombre, 'tipo': d.tipo} for d in docs])


# ========== POLIZAS ==========

@api_externa_bp.route('/v1/polizas')
@require_api_key
def polizas_list():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    ramo = request.args.get('ramo', '')
    activa = request.args.get('activa', '')

    query = Poliza.query
    if ramo:
        query = query.filter(Poliza.ramo == ramo)
    if activa == 'true':
        query = query.filter(Poliza.activa == True)
    elif activa == 'false':
        query = query.filter(Poliza.activa == False)

    pag = query.order_by(Poliza.fecha_efecto.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pag.total, 'page': page, 'per_page': per_page,
        'data': [_poliza_to_dict(p) for p in pag.items]
    })


    db.session.commit()
    return jsonify({'deleted': True})


@api_externa_bp.route('/v1/polizas/<int:id>', methods=['PUT'])
@require_api_key
def polizas_update(id):
    p = Poliza.query.get_or_404(id)
    data = request.get_json(force=True, silent=True) or {}
    for field in ['ramo', 'compania', 'descripcion', 'numero_poliza',
                  'prima_anual', 'capital_asegurado', 'numero_cuenta',
                  'unidades', 'detalles', 'activa']:
        if field in data:
            if field in ('prima_anual', 'capital_asegurado'):
                setattr(p, field, float(data[field]))
            elif field == 'unidades':
                setattr(p, field, int(data[field]))
            elif field == 'activa':
                setattr(p, field, bool(data[field]))
            else:
                setattr(p, field, data[field])
    db.session.commit()
    return jsonify(_poliza_to_dict(p))


@api_externa_bp.route('/v1/polizas/<int:id>', methods=['DELETE'])
@require_api_key
def polizas_delete(id):
    p = Poliza.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'deleted': True})


@api_externa_bp.route('/v1/recibos', methods=['POST'])
@require_api_key
def recibos_create():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('cliente_id') or not data.get('importe'):
        return jsonify({'error': 'cliente_id e importe requeridos'}), 400
    cliente = Cliente.query.get_or_404(data['cliente_id'])
    if data.get('poliza_id'):
        poliza = Poliza.query.get_or_404(data['poliza_id'])
        if poliza.cliente_id != cliente.id:
            return jsonify({'error': 'No se pudo completar la operación'}), 400

    r = Recibo(
        cliente_id=data['cliente_id'],
        poliza_id=data.get('poliza_id'),
        numero_poliza=data.get('numero_poliza', ''),
        concepto=data.get('concepto', ''),
        importe=float(data['importe']),
        fecha_emision=_parse_date(data.get('fecha_emision')) or date.today(),
        fecha_cargo=_parse_date(data.get('fecha_cargo')),
        estado=data.get('estado', 'pendiente'),
        compania=data.get('compania', 'Ocaso'),
        notas=data.get('notas', '')
    )
    db.session.add(r)
    db.session.commit()
    return jsonify(_recibo_to_dict(r)), 201


@api_externa_bp.route('/v1/search')
@require_api_key
def search():
    """Busqueda unificada para agentes IA."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': [], 'total': 0})

    results = []
    clientes = Cliente.query.filter(
        db.or_(Cliente.nombre.ilike(f'%{q}%'), Cliente.dni.ilike(f'%{q}%'))
    ).limit(20).all()

    for c in clientes:
        results.append({
            'type': 'cliente', 'id': c.id, 'nombre': c.nombre,
            'dni': c.dni, 'telefono': c.telefono,
            'polizas_activas': c.polizas.filter(Poliza.activa == True).count(),
            'url': f'/clientes/{c.id}'
        })

    polizas = Poliza.query.filter(
        Poliza.numero_poliza.ilike(f'%{q}%')
    ).limit(10).all()
    for p in polizas:
        c = Cliente.query.get(p.cliente_id)
        results.append({
            'type': 'poliza', 'id': p.id,
            'numero_poliza': p.numero_poliza, 'ramo': p.ramo,
            'cliente_nombre': c.nombre if c else '', 'cliente_id': p.cliente_id,
            'url': f'/polizas/'
        })

    siniestros = Siniestro.query.filter(
        Siniestro.numero_expediente.ilike(f'%{q}%')
    ).limit(10).all()
    for s in siniestros:
        results.append({
            'type': 'siniestro', 'id': s.id,
            'numero_expediente': s.numero_expediente, 'estado': s.estado,
            'url': f'/siniestros/{s.id}'
        })

    return jsonify({'results': results, 'total': len(results)})


# ========== EXISTING ENDPOINTS CONTINUE ==========



@api_externa_bp.route('/v1/polizas/<int:id>')
@require_api_key
def polizas_get(id):
    p = Poliza.query.get_or_404(id)
    return jsonify(_poliza_to_dict(p))


@api_externa_bp.route('/v1/polizas', methods=['POST'])
@require_api_key
def polizas_create():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('numero_poliza') or not data.get('cliente_id'):
        return jsonify({'error': 'numero_poliza y cliente_id requeridos'}), 400
    Cliente.query.get_or_404(data['cliente_id'])

    p = Poliza(
        cliente_id=data['cliente_id'],
        numero_poliza=data['numero_poliza'],
        ramo=data.get('ramo', ''),
        compania=data.get('compania', 'Ocaso'),
        descripcion=data.get('descripcion', ''),
        capital_asegurado=float(data.get('capital_asegurado', 0)),
        prima_anual=float(data.get('prima_anual', 0)),
        fecha_efecto=_parse_date(data.get('fecha_efecto')) or date.today(),
        fecha_vencimiento=_parse_date(data.get('fecha_vencimiento')) or date.today(),
        activa=data.get('activa', True),
        numero_cuenta=data.get('numero_cuenta', ''),
        unidades=float(data.get('unidades', 1)),
        detalles=data.get('detalles', '')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(_poliza_to_dict(p)), 201


# ========== RECIBOS ==========

@api_externa_bp.route('/v1/recibos')
@require_api_key
def recibos_list():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    estado = request.args.get('estado', '')

    query = Recibo.query
    if estado:
        query = query.filter(Recibo.estado == estado)

    pag = query.order_by(Recibo.fecha_emision.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pag.total, 'page': page, 'per_page': per_page,
        'data': [_recibo_to_dict(r) for r in pag.items]
    })


# ========== SINIESTROS ==========

@api_externa_bp.route('/v1/siniestros')
@require_api_key
def siniestros_list():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)

    query = Siniestro.query.order_by(Siniestro.fecha_apertura.desc())
    pag = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pag.total, 'page': page, 'per_page': per_page,
        'data': [_siniestro_to_dict(s) for s in pag.items]
    })


@api_externa_bp.route('/v1/siniestros', methods=['POST'])
@require_api_key
def siniestros_create():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('cliente_id') or not data.get('tipo') or not data.get('numero_expediente'):
        return jsonify({'error': 'cliente_id, tipo y numero_expediente requeridos'}), 400
    cliente = Cliente.query.get_or_404(data['cliente_id'])
    if data.get('poliza_id'):
        poliza = Poliza.query.get_or_404(data['poliza_id'])
        if poliza.cliente_id != cliente.id:
            return jsonify({'error': 'No se pudo completar la operación'}), 400

    s = Siniestro(
        cliente_id=data['cliente_id'],
        poliza_id=data.get('poliza_id'),
        numero_expediente=data['numero_expediente'],
        tipo=data['tipo'],
        descripcion=data.get('descripcion', ''),
        fecha_ocurrencia=_parse_date(data.get('fecha_ocurrencia')) or date.today(),
        fecha_apertura=_parse_date(data.get('fecha_apertura')) or date.today(),
        estado=data.get('estado', 'abierto'),
        importe_estimado=float(data.get('importe_estimado', 0)),
        fecha_ultima_actualizacion=datetime.utcnow()
    )
    db.session.add(s)
    db.session.commit()

    from models import HitoSiniestro
    db.session.add(HitoSiniestro(
        siniestro_id=s.id, fecha=datetime.utcnow(),
        estado='abierto', notas='Creado via API'
    ))
    db.session.commit()

    return jsonify(_siniestro_to_dict(s)), 201


@api_externa_bp.route('/v1/siniestros/<int:id>')
@require_api_key
def siniestros_get(id):
    s = Siniestro.query.get_or_404(id)
    return jsonify(_siniestro_to_dict(s))


# ========== LEADS ==========

@api_externa_bp.route('/v1/leads')
@require_api_key
def leads_list():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    estado = request.args.get('estado', '')

    query = Lead.query
    if estado:
        query = query.filter(Lead.estado == estado)

    pag = query.order_by(Lead.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pag.total, 'page': page, 'per_page': per_page,
        'data': [_lead_to_dict(l) for l in pag.items]
    })


@api_externa_bp.route('/v1/leads', methods=['POST'])
@require_api_key
def leads_create():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('nombre'):
        return jsonify({'error': 'nombre requerido'}), 400

    l = Lead(
        nombre=data['nombre'],
        telefono=data.get('telefono', ''),
        email=data.get('email', ''),
        dni=data.get('dni', ''),
        ramo_interes=data.get('ramo_interes', ''),
        origen=data.get('origen', 'web'),
        estado=data.get('estado', 'nuevo'),
        notas=data.get('notas', ''),
        user_id=request.api_user.id
    )
    db.session.add(l)
    db.session.commit()
    return jsonify(_lead_to_dict(l)), 201


@api_externa_bp.route('/v1/leads/<int:id>', methods=['DELETE'])
@require_api_key
def leads_delete(id):
    l = Lead.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    return jsonify({'deleted': True})


@api_externa_bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'No encontrado'}), 404


@api_externa_bp.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Error interno del servidor'}), 500


# ========== STATS ==========

@api_externa_bp.route('/v1/stats')
@require_api_key
def stats():
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)

    return jsonify({
        'clientes_total': Cliente.query.count(),
        'polizas_activas': Poliza.query.filter(Poliza.activa == True).count(),
        'polizas_mes': Poliza.query.filter(Poliza.fecha_efecto >= inicio_mes).count(),
        'recibos_pendientes': Recibo.query.filter(Recibo.estado == 'pendiente').count(),
        'siniestros_abiertos': Siniestro.query.filter(
            ~Siniestro.estado.in_(['cerrado', 'resuelto'])
        ).count(),
        'leads_activos': Lead.query.filter(~Lead.estado.in_(['ganado', 'perdido'])).count(),
        'timestamp': datetime.utcnow().isoformat()
    })


# ========== API KEY MANAGEMENT ==========

@api_externa_bp.route('/v1/me')
@require_api_key
def me():
    """Returns info about the current API key/user."""
    user = request.api_user
    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'is_admin': user.is_admin
    })


# ========== SERIALIZERS ==========

def _cliente_to_dict(c, include_polizas=False):
    d = {
        'id': c.id, 'nombre': c.nombre, 'dni': c.dni,
        'telefono': c.telefono, 'email': c.email,
        'direccion': c.direccion, 'codigo_postal': c.codigo_postal,
        'poblacion': c.poblacion, 'provincia': c.provincia,
        'fecha_alta': c.fecha_alta.isoformat() if c.fecha_alta else None,
        'alerta_devoluciones': c.alerta_devoluciones
    }
    if include_polizas:
        d['polizas'] = [_poliza_to_dict(p) for p in c.polizas_activas]
    return d


def _poliza_to_dict(p):
    return {
        'id': p.id, 'cliente_id': p.cliente_id,
        'numero_poliza': p.numero_poliza, 'ramo': p.ramo,
        'compania': p.compania, 'descripcion': p.descripcion,
        'capital_asegurado': p.capital_asegurado,
        'prima_anual': p.prima_anual,
        'fecha_efecto': p.fecha_efecto.isoformat() if p.fecha_efecto else None,
        'fecha_vencimiento': p.fecha_vencimiento.isoformat() if p.fecha_vencimiento else None,
        'activa': p.activa, 'numero_cuenta': p.numero_cuenta,
        'unidades': p.unidades, 'detalles': p.detalles,
        'marca': p.marca, 'modelo': p.modelo, 'matricula': p.matricula,
    }


def _recibo_to_dict(r):
    return {
        'id': r.id, 'cliente_id': r.cliente_id,
        'numero_poliza': r.numero_poliza, 'concepto': r.concepto,
        'importe': r.importe, 'fecha_emision': r.fecha_emision.isoformat() if r.fecha_emision else None,
        'fecha_cargo': r.fecha_cargo.isoformat() if r.fecha_cargo else None,
        'estado': r.estado, 'estado_gestion': r.estado_gestion,
        'compania': r.compania, 'notas': r.notas
    }


def _siniestro_to_dict(s):
    return {
        'id': s.id, 'cliente_id': s.cliente_id, 'poliza_id': s.poliza_id,
        'numero_expediente': s.numero_expediente, 'tipo': s.tipo,
        'descripcion': s.descripcion,
        'fecha_ocurrencia': s.fecha_ocurrencia.isoformat() if s.fecha_ocurrencia else None,
        'fecha_apertura': s.fecha_apertura.isoformat() if s.fecha_apertura else None,
        'estado': s.estado, 'importe_estimado': s.importe_estimado,
        'fecha_ultima_actualizacion': s.fecha_ultima_actualizacion.isoformat() if s.fecha_ultima_actualizacion else None
    }


def _lead_to_dict(l):
    return {
        'id': l.id, 'nombre': l.nombre, 'telefono': l.telefono,
        'email': l.email, 'dni': l.dni, 'ramo_interes': l.ramo_interes,
        'origen': l.origen, 'estado': l.estado, 'notas': l.notas,
        'cliente_id': l.cliente_id,
        'created_at': l.created_at.isoformat() if l.created_at else None
    }


def _parse_date(val):
    if not val: return None
    try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except: return None
