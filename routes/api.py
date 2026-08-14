from flask import Blueprint, jsonify, request, url_for
from flask_login import login_required
from models import db, Cliente, Poliza, Recibo

api_bp = Blueprint('api', __name__)


@api_bp.route('/buscar')
@login_required
def buscar():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    clientes = Cliente.query.filter(
        db.or_(
            Cliente.nombre.ilike(f'%{q}%'),
            Cliente.dni.ilike(f'%{q}%'),
            Cliente.telefono.ilike(f'%{q}%'),
            Cliente.email.ilike(f'%{q}%'),
            Cliente.poblacion.ilike(f'%{q}%'),
        )
    ).limit(15).all()

    polizas = Poliza.query.filter(
        db.or_(
            Poliza.numero_poliza.ilike(f'%{q}%'),
            Poliza.matricula.ilike(f'%{q}%')
        )
    ).limit(10).all()

    results = []

    for c in clientes:
        polizas_activas = c.polizas.filter(Poliza.activa == True).count()
        results.append({
            'type': 'cliente',
            'id': c.id,
            'nombre': c.nombre,
            'dni': c.dni or '',
            'telefono': c.telefono or '',
            'polizas_activas': polizas_activas,
            'alerta': c.alerta_devoluciones,
            'url': url_for('clientes.ficha', id=c.id)
        })

    for p in polizas:
        cliente = Cliente.query.get(p.cliente_id)
        results.append({
            'type': 'poliza',
            'id': p.id,
            'numero': p.numero_poliza,
            'ramo': p.ramo,
            'cliente_nombre': cliente.nombre if cliente else '',
            'cliente_id': p.cliente_id,
            'matricula': p.matricula or '',
            'url': url_for('clientes.ficha', id=p.cliente_id)
        })

    return jsonify(results)


@api_bp.route('/polizas-cliente/<int:cliente_id>')
@login_required
def polizas_cliente(cliente_id):
    polizas = Poliza.query.filter_by(cliente_id=cliente_id, activa=True).all()
    return jsonify([{'id': p.id, 'numero_poliza': p.numero_poliza, 'ramo': p.ramo} for p in polizas])


@api_bp.route('/cumpleaneros')
@login_required
def cumpleaneros():
    """Get clients with birthdays this month for auto-messaging"""
    from datetime import date
    hoy = date.today()
    clientes = Cliente.query.filter(
        db.extract('month', Cliente.fecha_nacimiento) == hoy.month
    ).all()
    return jsonify([{'id': c.id, 'nombre': c.nombre, 'fecha_nacimiento': str(c.fecha_nacimiento),
                     'telefono': c.telefono} for c in clientes if c.fecha_nacimiento])


@api_bp.route('/configuracion', methods=['POST'])
@login_required
def guardar_configuracion():
    from models import Configuracion
    clave = request.form.get('clave')
    valor = request.form.get('valor')
    conf = Configuracion.query.filter_by(clave=clave).first()
    if conf:
        conf.valor = valor
    else:
        conf = Configuracion(clave=clave, valor=valor)
        db.session.add(conf)
    db.session.commit()
    return jsonify({'ok': True})
