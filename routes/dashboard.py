from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from models import db, Recibo, Poliza, Cliente
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

dashboard_bp = Blueprint('dashboard', __name__)

MESES_ES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
MESES_CORTOS_ES = ('ene', 'feb', 'mar', 'abr', 'may', 'jun',
                   'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


@dashboard_bp.route('/')
@login_required
def index():
    hoy = date.today()

    # Mes seleccionado (por defecto, el actual)
    anio_param = request.args.get('anio', type=int)
    mes_param = request.args.get('mes', type=int)
    try:
        selected = date(anio_param, mes_param, 1) if (
            anio_param and mes_param and 1 <= mes_param <= 12
        ) else hoy.replace(day=1)
    except ValueError:
        selected = hoy.replace(day=1)

    inicio_mes = selected
    fin_mes = (inicio_mes + relativedelta(months=1)) - relativedelta(days=1)

    # KPIs del mes
    recibos_mes = Recibo.query.filter(
        Recibo.fecha_emision >= inicio_mes,
        Recibo.fecha_emision <= fin_mes
    ).all()

    primas_nuevas = sum(r.importe for r in recibos_mes if r.estado == 'cobrado')
    num_recibos_cobrados = len([r for r in recibos_mes if r.estado == 'cobrado'])
    devueltos = sum(r.importe for r in recibos_mes if r.estado == 'devuelto')
    num_devueltos = len([r for r in recibos_mes if r.estado == 'devuelto'])

    # Polizas nuevas del mes - Ocaso (suma de unidades) vs Otras
    polizas_ocaso_mes = db.session.query(db.func.coalesce(db.func.sum(Poliza.unidades), 0)).filter(
        Poliza.fecha_efecto >= inicio_mes,
        Poliza.fecha_efecto <= fin_mes,
        Poliza.compania == 'Ocaso'
    ).scalar() or 0

    polizas_otras_mes = db.session.query(db.func.count(Poliza.id)).filter(
        Poliza.fecha_efecto >= inicio_mes,
        Poliza.fecha_efecto <= fin_mes,
        Poliza.compania != 'Ocaso'
    ).scalar() or 0

    # Asegurados (clientes unicos con al menos una poliza activa)
    asegurados = db.session.query(db.func.count(db.distinct(Poliza.cliente_id))).filter(
        Poliza.activa == True
    ).scalar() or 0

    polizas_activas = Poliza.query.filter(Poliza.activa == True).count()
    total_clientes = Cliente.query.count()

    # Monthly evolution (last 12 months)
    monthly_data = []
    for i in range(11, -1, -1):
        mes_inicio = (inicio_mes - relativedelta(months=i))
        mes_fin = (mes_inicio + relativedelta(months=1)) - relativedelta(days=1)
        mes_label = f'{MESES_CORTOS_ES[mes_inicio.month - 1]} {mes_inicio.strftime("%y")}'

        nuevas_mes = Poliza.query.filter(
            Poliza.fecha_efecto >= mes_inicio,
            Poliza.fecha_efecto <= mes_fin
        ).count()

        cobradas_mes = db.session.query(db.func.sum(Recibo.importe)).filter(
            Recibo.fecha_emision >= mes_inicio,
            Recibo.fecha_emision <= mes_fin,
            Recibo.estado == 'cobrado'
        ).scalar() or 0

        monthly_data.append({
            'label': mes_label,
            'nuevas': nuevas_mes,
            'cobrados': round(cobradas_mes, 2)
        })

    # Ranking by ramo
    ramos_data = db.session.query(
        Poliza.ramo,
        db.func.count(Poliza.id).label('cantidad'),
        db.func.sum(Poliza.prima_anual).label('total')
    ).filter(Poliza.activa == True).group_by(Poliza.ramo).order_by(db.text('total DESC')).all()

    # Top 10 clients by volume
    top_clientes = db.session.query(
        Cliente.nombre,
        db.func.sum(Poliza.prima_anual).label('total')
    ).join(Poliza).filter(Poliza.activa == True).group_by(Cliente.id).order_by(
        db.text('total DESC')
    ).limit(10).all()

    anios = list(range(hoy.year - 3, hoy.year + 1))

    return render_template('dashboard/index.html',
                           primas_nuevas=round(primas_nuevas, 2),
                           num_recibos_cobrados=num_recibos_cobrados,
                           devueltos=round(devueltos, 2),
                           num_devueltos=num_devueltos,
                           polizas_ocaso_mes=polizas_ocaso_mes,
                           polizas_otras_mes=polizas_otras_mes,
                           asegurados=asegurados,
                           polizas_activas=polizas_activas,
                           total_clientes=total_clientes,
                           monthly_data=monthly_data,
                           ramos_data=ramos_data,
                           top_clientes=top_clientes,
                           mes=f'{MESES_ES[inicio_mes.month - 1]} {inicio_mes.year}',
                           meses_list=MESES_ES,
                           selected_mes=inicio_mes.month,
                           selected_anio=inicio_mes.year,
                           anios=anios)
